"""Bot de Telegram para el agente de soporte bancario.

Uso: python bot.py  (requiere TELEGRAM_BOT_TOKEN en el .env)
"""

import logging
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from agent import MENSAJE_ERROR, DoubtState, texto, workflow

load_dotenv()

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Fuera de langgraph dev la persistencia la ponemos nosotros (en memoria: se pierde al reiniciar el bot).
graph = workflow.compile(checkpointer=InMemorySaver(), store=InMemoryStore())

LIMITE_TELEGRAM = 4096


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "¡Hola! Soy el asistente virtual del banco. Puedo ayudarte a consultar tus compras y deudas. ¿Qué necesitas?"
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message, chat, user = update.message, update.effective_chat, update.effective_user
    if not message or not message.text or not chat or not user:
        return
    pregunta = message.text
    chat_id = str(chat.id)
    user_id = str(user.id)

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Cada chat de Telegram es un thread (memoria de la conversación) y cada usuario tiene su memoria en el store
    config: RunnableConfig = {"configurable": {"thread_id": chat_id, "user_id": user_id}}
    entrada: DoubtState = {"messages": [HumanMessage(pregunta)]}
    try:
        result = await graph.ainvoke(entrada, config)
        respuesta = texto(result["messages"][-1].content)
    except Exception:
        logger.exception("Error al ejecutar el grafo")
        respuesta = MENSAJE_ERROR

    for i in range(0, len(respuesta), LIMITE_TELEGRAM):
        await message.reply_text(respuesta[i : i + LIMITE_TELEGRAM])


def crear_app(token: str) -> Application:
    # La usan el modo polling (main) y el webhook de Vercel (api/webhook.py)
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    return app


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Falta TELEGRAM_BOT_TOKEN en el .env")

    app = crear_app(token)

    logger.info("Bot de Telegram iniciado. Ctrl+C para detenerlo.")
    app.run_polling()


if __name__ == "__main__":
    main()
