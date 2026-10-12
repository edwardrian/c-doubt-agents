import logging
from functools import wraps
from typing import NotRequired

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import RunnableConfig
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.base import BaseStore
from langsmith import Client

from tools import TOOLS_AGENT_BUY, TOOLS_AGENT_DOUBT

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = Client()
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")


class DoubtState(MessagesState):
    intent: NotRequired[str]
    debug: NotRequired[dict]  # info de depuración del último nodo, visible en Studio,


def texto(content) -> str:
    # Gemini puede devolver una lista de bloques o un string
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return content


MENSAJE_ERROR = "Lo siento, tuvimos un problema técnico. Por favor, inténtalo de nuevo en unos minutos."
MENSAJE_ERROR_TOOL = "No se pudo consultar la información en este momento. Avisa al cliente que lo intente más tarde."


def manejar_errores(nodo):
    # Si el nodo falla, registra el error completo y responde al cliente con un mensaje amable
    @wraps(nodo)
    def wrapper(state, *args, **kwargs):
        try:
            return nodo(state, *args, **kwargs)
        except Exception:
            logger.exception(f"Error en el nodo {nodo.__name__}")
            return {"messages": [AIMessage(MENSAJE_ERROR)], "intent": "ERROR"}

    return wrapper


def error_tool(e: Exception) -> str:
    # El ToolNode devuelve este texto a Gemini como resultado de la herramienta
    logger.exception(f"Error en una herramienta: {e}")
    return MENSAJE_ERROR_TOOL


@manejar_errores
def agentRouter(state: DoubtState) -> dict:
    prompt = client.pull_prompt("agent-router")
    question = texto(state["messages"][-1].content)
    response = (prompt | llm).invoke({"question": question})
    intent = texto(response.content).strip().upper()
    return {"intent": intent, "debug": {"nodo": "agent_router", "pregunta": question, "intent": intent}}


@manejar_errores
def agentBuy(state: DoubtState) -> dict:
    prompt = client.pull_prompt("agente-compras")
    system = prompt.format_messages(intent=state.get("intent", ""))
    response = llm.bind_tools(TOOLS_AGENT_BUY).invoke([*system, *state["messages"]])
    tool_calls = [t["name"] for t in getattr(response, "tool_calls", [])]
    return {
        "messages": [response],
        "debug": {"nodo": "agent_buy", "intent": state.get("intent"), "tool_calls": tool_calls},
    }


def agentDoubt(state: DoubtState) -> dict:
    return {}


@manejar_errores
def agentResponse(state: DoubtState, config: RunnableConfig, store: BaseStore) -> dict:

    user_id = config.get("configurable", {}).get("user_id") or "anonimo"
    perfil = store.get(("memoria", user_id), "perfil")
    datos = perfil.value if perfil else {}

    prompt = client.pull_prompt("agent-response")
    system = prompt.format_messages()
    memoria = SystemMessage(f"datos conocidos :{datos}")
    response = llm.invoke([*system, memoria, *state["messages"]])
    store.put(("memoria", user_id), "perfil", {"userid": user_id, "response": response})
    return {"messages": [response]}


workflow = StateGraph(DoubtState)
workflow.add_node("agent_router", agentRouter)
workflow.add_node("agent_buy", agentBuy)
workflow.add_node("agent_doubt", agentDoubt)
workflow.add_node("agent_response", agentResponse)
workflow.add_node("tools_buy", ToolNode(TOOLS_AGENT_BUY, handle_tool_errors=error_tool))
workflow.add_node("tools_doubt", ToolNode(TOOLS_AGENT_DOUBT, handle_tool_errors=error_tool))


# edge
def route_intent(state: DoubtState) -> str:
    intent = state.get("intent", "")
    if intent == "ERROR":
        return END
    if "DEUDAS" in intent:
        return "agent_doubt"
    if "MOVIMIENTOS" in intent or "PAGOS" in intent:
        return "agent_buy"
    return "agent_response"


workflow.add_edge(START, "agent_router")
workflow.add_conditional_edges("agent_router", route_intent, ["agent_buy", "agent_doubt", "agent_response", END])

workflow.add_edge("tools_buy", "agent_buy")
workflow.add_conditional_edges("agent_buy", tools_condition, {"tools": "tools_buy", END: END})

workflow.add_edge("tools_doubt", "agent_doubt")
workflow.add_conditional_edges("agent_doubt", tools_condition, {"tools": "tools_doubt", END: END})

workflow.add_edge("agent_response", END)


# langgraph dev añade su propio checkpointer y store (persistentes en .langgraph_api/).
graph = workflow.compile()
