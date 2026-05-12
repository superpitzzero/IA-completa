"""
Web rÃ¡pida para NEXO
Arranca con link pÃºblico instantÃ¡neo via Gradio share

Uso:
    python web_rapida.py
    python web_rapida.py --no-share    (solo local)
    python web_rapida.py --password miClave  (con contraseÃ±a)

Instalar dependencias:
    pip install gradio requests
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterator

import requests

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
OLLAMA_HOST = "http://localhost:11434"

MODELS = {
    "ðŸ§  Arquitecto (14B) â€” anÃ¡lisis y diseÃ±o":  "qwen2.5-coder:14b",
    "ðŸ”¨ Programador (7B) â€” cÃ³digo rÃ¡pido":      "qwen2.5-coder:7b",
    "âš¡ RÃ¡pido (7B) â€” respuestas cortas":        "qwen2.5-coder:7b",
}

SYSTEM_PROMPTS = {
    "ðŸ§  Arquitecto (14B) â€” anÃ¡lisis y diseÃ±o": (
        "Eres un arquitecto de software experto. Analiza cÃ³digo, detecta errores, "
        "optimiza y proporciona soluciones completas. Responde con cÃ³digo funcional "
        "y completo. Explica tus decisiones tÃ©cnicas."
    ),
    "ðŸ”¨ Programador (7B) â€” cÃ³digo rÃ¡pido": (
        "Eres un programador experto. Escribe cÃ³digo limpio, completo y funcional. "
        "Incluye comentarios Ãºtiles y manejo de errores."
    ),
    "âš¡ RÃ¡pido (7B) â€” respuestas cortas": (
        "Responde de forma directa y concisa."
    ),
}

# â”€â”€ Ollama helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def check_ollama() -> tuple[bool, str]:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, f"Ollama activo. Modelos: {', '.join(models) or 'ninguno'}"
    except Exception as e:
        return False, f"Ollama no disponible: {e}"
    return False, "Ollama no responde"


def chat_stream(model_label: str, history: list, user_msg: str) -> Iterator[list]:
    """Genera respuesta en streaming y actualiza el historial de Gradio."""
    model = MODELS.get(model_label, "qwen2.5-coder:7b")
    system = SYSTEM_PROMPTS.get(model_label, "")

    # Construir mensajes
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    for h in history:
        messages.append({"role": "user",      "content": h[0]})
        messages.append({"role": "assistant", "content": h[1]})
    messages.append({"role": "user", "content": user_msg})

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": "10m",
    }

    new_history = history + [[user_msg, ""]]

    try:
        with requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            if resp.status_code != 200:
                new_history[-1][1] = f"âŒ Error {resp.status_code}: {resp.text[:200]}"
                yield new_history
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    new_history[-1][1] += token
                    yield new_history
                except json.JSONDecodeError:
                    continue

    except requests.exceptions.ConnectionError:
        new_history[-1][1] = "âŒ No se puede conectar a Ollama. Â¿EstÃ¡ corriendo?"
        yield new_history
    except requests.exceptions.Timeout:
        new_history[-1][1] += "\n\nâš ï¸ Timeout â€” respuesta parcial"
        yield new_history
    except Exception as e:
        new_history[-1][1] = f"âŒ Error: {e}"
        yield new_history


# â”€â”€ Gradio UI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_app():
    try:
        import gradio as gr
    except ImportError:
        print("âŒ Gradio no instalado. Ejecuta:")
        print("   pip install gradio")
        sys.exit(1)

    ok, status_msg = check_ollama()
    status_icon = "ðŸŸ¢" if ok else "ðŸ”´"

    css = """
    .gradio-container { max-width: 900px !important; margin: auto; }
    .message-wrap { font-size: 15px; }
    footer { display: none !important; }
    """

    with gr.Blocks(
        title="NEXO",
        theme=gr.themes.Soft(primary_hue="indigo"),
        css=css,
    ) as app:

        gr.Markdown(
            "# ðŸ¤– NEXO\n"
            "Chat con tus modelos Ollama locales Â· "
            f"{status_icon} `{status_msg}`"
        )

        with gr.Row():
            model_selector = gr.Dropdown(
                choices=list(MODELS.keys()),
                value="ðŸ”¨ Programador (7B) â€” cÃ³digo rÃ¡pido",
                label="Modelo",
                scale=3,
            )
            clear_btn = gr.Button("ðŸ—‘ï¸ Limpiar chat", scale=1, variant="secondary")

        chatbot = gr.Chatbot(
            label="ConversaciÃ³n",
            height=520,
            show_copy_button=True,
            bubble_full_width=False,
            render_markdown=True,
        )

        with gr.Row():
            msg_box = gr.Textbox(
                placeholder="Escribe tu mensajeâ€¦ (Enter para enviar, Shift+Enter nueva lÃ­nea)",
                label="",
                lines=3,
                scale=5,
                autofocus=True,
            )
            send_btn = gr.Button("Enviar â–¶", scale=1, variant="primary")

        gr.Markdown(
            "<small>ðŸ’¡ Tip: para cÃ³digo mÃ¡s complejo usa el Arquitecto 14B Â· "
            "Los modelos se mantienen en memoria 10 min tras cada uso</small>"
        )

        # â”€â”€ Eventos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def submit(model, history, message):
            if not message.strip():
                yield history
                return
            yield from chat_stream(model, history, message)

        send_btn.click(
            fn=submit,
            inputs=[model_selector, chatbot, msg_box],
            outputs=chatbot,
        ).then(lambda: "", outputs=msg_box)

        msg_box.submit(
            fn=submit,
            inputs=[model_selector, chatbot, msg_box],
            outputs=chatbot,
        ).then(lambda: "", outputs=msg_box)

        clear_btn.click(lambda: [], outputs=chatbot)

    return app


# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    parser = argparse.ArgumentParser(description="NEXO â€” Web rÃ¡pida con Gradio")
    parser.add_argument("--no-share", action="store_true", help="Solo red local, sin link pÃºblico")
    parser.add_argument("--port", type=int, default=7861, help="Puerto local (default: 7861)")
    parser.add_argument("--password", type=str, default=None, help="ContraseÃ±a de acceso")
    args = parser.parse_args()

    share = not args.no_share

    print("\n" + "="*60)
    print("  NEXO â€” Web rÃ¡pida (Gradio)")
    print("="*60)

    ok, status = check_ollama()
    print(f"  Ollama: {'âœ…' if ok else 'âŒ'} {status}")

    if args.password:
        print(f"  ContraseÃ±a activa: {'*' * len(args.password)}")
    if share:
        print("  ðŸŒ Generando link pÃºblico de Gradio...")
    print()

    app = build_app()

    auth = None
    if args.password:
        auth = ("admin", args.password)

    app.launch(
        server_port=args.port,
        share=share,
        auth=auth,
        show_error=True,
        quiet=False,
    )


if __name__ == "__main__":
    main()
