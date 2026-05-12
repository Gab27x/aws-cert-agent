# retriever.py — RAG con pgvector
# ══════════════════════════════════════════════════════════════
# ESTADO: PENDIENTE DE IMPLEMENTACIÓN
#
# Este módulo se encargará de:
# 1. Conectarse a PostgreSQL con pgvector (postgres-rag)
# 2. Recibir una query del usuario
# 3. Generar el embedding de la query con OpenAI
# 4. Buscar los chunks más similares en la base de datos
# 5. Retornar el contexto relevante al agente
#
# Se integrará con graph.py reemplazando el nodo "retrieve"
# que actualmente está comentado.
# ══════════════════════════════════════════════════════════════

from __future__ import annotations

import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable de entorno obligatoria: {name}")
    return value


def get_vectorstore() -> PGVector:
    """Crea un vectorstore PGVector apuntando a postgres-rag."""

    connection_string = _env("DATABASE_URL")
    collection_name = os.getenv("RAG_COLLECTION", "aws_certifications")
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Embeddings: actualmente se usa OpenAI para embeddings.
    # Aunque el LLM sea Groq, para RAG necesitas OPENAI_API_KEY.
    _env("OPENAI_API_KEY")

    embeddings = OpenAIEmbeddings(model=embedding_model)
    return PGVector(
        connection_string=connection_string,
        embedding_function=embeddings,
        collection_name=collection_name,
    )


def get_retriever(k: int | None = None):
    """Retorna un retriever conectado a pgvector.

    Requiere que antes se haya corrido la ingesta en `agent/ingest/ingest.py`.
    """

    k_final = k or int(os.getenv("RAG_K", "5"))
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": k_final})
