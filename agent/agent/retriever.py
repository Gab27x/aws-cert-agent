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

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
import os

CONNECTION_STRING = os.getenv("DATABASE_URL", "")
COLLECTION_NAME = "aws_certifications"

def get_retriever():
    """
    TODO: Implementar cuando los documentos estén ingestados.

    Retorna un retriever de LangChain conectado a pgvector.
    Busca entre los documentos de las 3 certificaciones AWS:
    - Cloud Practitioner (CLF-C02)
    - Security Specialty (SCS-C02)
    - Machine Learning Specialty (MLS-C01)
    """
    # PENDIENTE: descomentar cuando ingest.py esté listo
    # embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    # vectorstore = PGVector(
    #     connection_string=CONNECTION_STRING,
    #     embedding_function=embeddings,
    #     collection_name=COLLECTION_NAME,
    # )
    # return vectorstore.as_retriever(search_kwargs={"k": 5})
    raise NotImplementedError("RAG pendiente de implementación. Ver ingest/ingest.py")
