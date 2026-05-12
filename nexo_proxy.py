from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ⚙️ Ajusta estas variables si cambiaste el puerto o usas URL pública
NEXO_API_URL = "http://127.0.0.1:7860/api/v1/chat"
NEXO_API_KEY = "nexo_dev_fqQclBRsoY2Qo4Z7QPOi4I8kFwZagbR1JakN9Hw9ek"
PROXY_PORT = 8001  # el puerto al que se conectará Continue

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.get_json()
    
    # Extraemos el último mensaje del usuario (simplificado)
    messages = data.get("messages", [])
    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break
    
    # Modo por defecto "auto", o lo podrías leer de un campo custom
    mode = "auto"
    
    # Llamamos a Nexo
    try:
        resp = requests.post(
            NEXO_API_URL,
            json={"message": user_msg, "mode": mode},
            headers={"Authorization": f"Bearer {NEXO_API_KEY}"},
            timeout=60
        )
        resp.raise_for_status()
        nexo_data = resp.json()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Construimos la respuesta en formato OpenAI
    return jsonify({
        "id": "chatcmpl-nexo-local",
        "object": "chat.completion",
        "created": 0,
        "model": "nexo",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": nexo_data.get("text", "")
            },
            "finish_reason": "stop"
        }]
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PROXY_PORT)