# app.py — Entry point Chainlit
import chainlit as cl
from agent.graph import build_graph
from langfuse.callback import CallbackHandler
import os

graph = build_graph()


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("history", [])
    provider = os.getenv("LLM_PROVIDER", "openai").upper()
    await cl.Message(
        content=(
            f"👋 ¡Hola! Soy tu asistente experto en certificaciones AWS. *(usando {provider})*\n\n"
            "Puedo ayudarte con:\n"
            "- ☁️ **Cloud Practitioner** (CLF-C02)\n"
            "- 🔒 **Security Specialty** (SCS-C02)\n"
            "- 🤖 **Machine Learning Specialty** (MLS-C01)\n\n"
            "¿Qué quieres aprender hoy?"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    history = cl.user_session.get("history", [])

    # Soporta tanto LANGFUSE_HOST como LANGFUSE_BASE_URL
    langfuse_host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")

    langfuse_handler = CallbackHandler(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=langfuse_host,
    )

    response_message = cl.Message(content="")
    await response_message.send()

    full_response = ""

    async for chunk in graph.astream(
        {"question": message.content, "history": history},
        config={"callbacks": [langfuse_handler]},
    ):
        if "llm" in chunk and chunk["llm"].get("answer"):
            token = chunk["llm"]["answer"]
            await response_message.stream_token(token)
            full_response = chunk["llm"]["answer"]

    await response_message.update()

    history.append({"human": message.content, "ai": full_response})
    cl.user_session.set("history", history)
