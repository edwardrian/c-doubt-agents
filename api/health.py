"""Health check: GET /api/health responde 200 si el bot puede arrancar en Vercel.

Revisa que existan las variables de entorno (sin mostrar sus valores) y que se pueda importar el bot.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Para poder importar bot.py / agent.py / tools.py desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VARIABLES = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "GOOGLE_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "LANGSMITH_API_KEY",
]


def revisar() -> dict:
    faltan = [v for v in VARIABLES if not os.environ.get(v)]
    try:
        import bot  # noqa: F401

        error_import = None
    except Exception as e:
        error_import = f"{type(e).__name__}: {e}"

    return {
        "status": "ok" if not faltan and not error_import else "error",
        "variables_faltantes": faltan,
        "error_import": error_import,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        resultado = revisar()
        cuerpo = json.dumps(resultado).encode()

        self.send_response(200 if resultado["status"] == "ok" else 500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(cuerpo)
