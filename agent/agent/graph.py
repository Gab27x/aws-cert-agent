# graph.py — LangGraph Agent
import os
from typing import TypedDict
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
    answer: str


# ── Nodo principal: llamada al LLM ───────────────────────────
def call_llm(state: AgentState, config: RunnableConfig) -> AgentState:
    llm = _build_llm()

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    for turn in state.get("history", []):
        messages.append(HumanMessage(content=turn["human"]))
        messages.append(AIMessage(content=turn["ai"]))

    messages.append(HumanMessage(content=state["question"]))

    # ── RAG: PENDIENTE ────────────────────────────────────────
    # Cuando el RAG esté listo, antes del LLM se hará:
    #
    # from .retriever import get_retriever
    # retriever = get_retriever()
    # docs = retriever.invoke(state["question"])
    # context = "\n\n".join([d.page_content for d in docs])
    # Y se inyectará `context` en el SystemMessage o como mensaje adicional
    # ─────────────────────────────────────────────────────────

    response = llm.invoke(messages, config)

    return {**state, "answer": response.content}


# ── Construcción del grafo ────────────────────────────────────
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.set_entry_point("llm")
    graph.add_edge("llm", END)
    return graph.compile()
