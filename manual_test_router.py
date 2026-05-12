import json
import sys
from typing import Tuple

import requests


BASE = "http://127.0.0.1:7866"
USER = "testuser"
PASSWORD = "testpass123"


def ensure_logged_in(session: requests.Session) -> None:
    # Attempt registration; if it fails (user exists), login instead.
    session.get(f"{BASE}/register", timeout=10)
    response = session.post(
        f"{BASE}/register",
        data={"username": USER, "password": PASSWORD, "confirm_password": PASSWORD},
        allow_redirects=True,
        timeout=10,
    )
    if response.status_code >= 400:
        session.post(
            f"{BASE}/login",
            data={"username": USER, "password": PASSWORD},
            allow_redirects=True,
            timeout=10,
        )


def create_chat(session: requests.Session) -> str:
    response = session.post(f"{BASE}/api/chats", json={}, timeout=10)
    response.raise_for_status()
    return str(response.json()["id"])


def stream_message(session: requests.Session, chat_id: str, message: str) -> Tuple[str, str, str]:
    response = session.post(
        f"{BASE}/api/chat/stream",
        json={"chat_id": chat_id, "mode": "auto", "message": message},
        stream=True,
        timeout=180,
    )
    response.raise_for_status()
    mode = ""
    label = ""
    parts: list[str] = []
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        event = json.loads(line)
        if event.get("type") == "mode":
            mode = str(event.get("mode") or "")
            label = str(event.get("label") or "")
        if event.get("type") == "token":
            token = str(event.get("token") or "")
            if token:
                parts.append(token)
        if event.get("type") == "done":
            break
    return mode, label, "".join(parts).strip()


def main() -> int:
    session = requests.Session()
    ensure_logged_in(session)
    chat_id = create_chat(session)

    cases = [
        ("hola", "rapido"),
        ("Dime 30 dígitos de pi", "rapido"),
        ("Escribe un script Python que lea un CSV y calcule promedio por columna.", "codigo"),
        ("Hazme un esquema de presentación en 8 diapositivas sobre redes neuronales y qué poner en cada una.", "combinado"),
    ]

    ok = True
    for message, expected in cases:
        mode, label, answer = stream_message(session, chat_id, message)
        preview = answer[:160].replace("\n", " ")
        # Consolas Windows pueden fallar con algunos caracteres (ej. π).
        try:
            preview = preview.encode(sys.stdout.encoding or "utf-8", "replace").decode(sys.stdout.encoding or "utf-8")
        except Exception:
            preview = preview.encode("utf-8", "replace").decode("utf-8")
        print("---")
        print("msg:", message)
        print("mode:", mode, "label:", label, "expected:", expected)
        print("preview:", preview)
        if mode != expected:
            ok = False

    print("OK" if ok else "MISMATCH")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

