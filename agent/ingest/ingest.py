# ingest.py — Carga de documentos de certificaciones AWS a pgvector
# ══════════════════════════════════════════════════════════════
# ESTADO: PENDIENTE DE IMPLEMENTACIÓN
#
# Este script se encargará de:
# 1. Leer los PDFs/documentos de las 3 certificaciones desde /app/docs/
#    - /app/docs/cloud-practitioner/   (CLF-C02)
#    - /app/docs/security-specialty/   (SCS-C02)
#    - /app/docs/ml-specialty/         (MLS-C01)
# 2. Dividir los documentos en chunks
# 3. Generar embeddings con OpenAI text-embedding-3-small
# 4. Insertar los vectores en PostgreSQL (postgres-rag)
#
# Uso: docker compose exec agent python ingest/ingest.py
# ══════════════════════════════════════════════════════════════

print("RAG pendiente de implementación.")
print("Pasos a completar:")
print("  1. Agregar documentos en agent/docs/ por certificación")
print("  2. Implementar lógica de chunking y embeddings")
print("  3. Insertar vectores en postgres-rag con pgvector")
print("  4. Activar get_retriever() en retriever.py")
print("  5. Conectar retriever en graph.py")
