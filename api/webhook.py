"""Webhook de Telegram para Vercel: Telegram hace un POST aquí con cada mensaje.

En Vercel no hay un proceso encendido todo el tiempo (run_polling), cada mensaje es una petición HTTP.
"""

import asyncio
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Para poder importar bot.py / agent.py / tools.py desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update  # noqa: E402

from bot import crear_app  # noqa: E402


async def procesar(datos: dict) -> None:
    app = crear_app(os.environ["TELEGRAM_BOT_TOKEN"])
    async with app:
        update = Update.de_json(datos, app.bot)
        if update:
            await app.process_update(update)


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        # Telegram manda este header con el secret_token que le dimos en setWebhook; así nadie más puede llamarnos
        secreto = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        recibido = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not secreto or not hmac.compare_digest(secreto, recibido):
            self.send_response(403)
            self.end_headers()
            return

        largo = int(self.headers.get("Content-Length", 0))
        asyncio.run(procesar(json.loads(self.rfile.read(largo))))

        self.send_response(200)
        self.end_headers()
