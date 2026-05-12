# graph.py — LangGraph Agent
import os
from typing import TypedDict, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from .prompts import SYSTEM_PROMPT


def _build_llm():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            temperature=0.2,
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
        streaming=True,
    )


# ── Estado del grafo ──────────────────────────────────────────
class AgentState(TypedDict):
    question: str
    history: list
    context: str
    answer: str


def retrieve(state: AgentState, config: Optional[RunnableConfig] = None) -> AgentState:
    """Recupera contexto desde pgvector (si está disponible).

    Nunca debe tumbar el chat: si hay un error (sin docs, sin DB, sin OPENAI_API_KEY),
    devuelve `context` vacío y el agente responde sin RAG.
    """

    rag_enabled = os.getenv("RAG_ENABLED", "true").lower() in {"1", "true", "yes", "y"}
    if not rag_enabled:
        return {**state, "context": ""}

    try:
        from .retriever import get_retriever

        retriever = get_retriever()
        docs = retriever.invoke(state["question"], config=config)
        context = "\n\n".join(
            [
                f"[cert={d.metadata.get('certification','unknown')}]\n{d.page_content}"
                for d in docs
                if getattr(d, "page_content", None)
            ]
        )
        return {**state, "context": context}
    except Exception:
        return {**state, "context": ""}


# ── Nodo principal: llamada al LLM ───────────────────────────
def call_llm(state: AgentState, config: RunnableConfig) -> AgentState:
    llm = _build_llm()

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if state.get("context"):
        messages.append(
            SystemMessage(
                content=(
                    "Contexto (RAG) de materiales de estudio. "
                    "Úsalo solo si es relevante para responder.\n\n"
                    f"{state['context']}"
                )
            )
        )

    for turn in state.get("history", []):
        messages.append(HumanMessage(content=turn["human"]))
        messages.append(AIMessage(content=turn["ai"]))

    messages.append(HumanMessage(content=state["question"]))

    response = llm.invoke(messages, config=config)

    return {**state, "answer": response.content}


# ── Construcción del grafo ────────────────────────────────────
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("llm", call_llm)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "llm")
    graph.add_edge("llm", END)
    return graph.compile()
