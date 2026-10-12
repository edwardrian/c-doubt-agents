import os
from functools import lru_cache
from typing import Any, cast

from dotenv import load_dotenv
from langchain_core.tools import tool
from supabase import Client, create_client

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_KEY en el .env")
    return create_client(url, key)


@tool
def consultar_compras() -> list[dict[str, Any]]:
    """Devuelve todas las compras registradas en la tabla purchases."""
    return cast(list[dict[str, Any]], get_supabase().table("purchases").select("*").execute().data)


@tool
def consultar_deuda() -> dict:
    """Devuelve las deudas del cliente."""
    return {"response": "contienes una deuda"}


TOOLS_AGENT_DOUBT = [consultar_deuda]
TOOLS_AGENT_BUY = [consultar_compras]
