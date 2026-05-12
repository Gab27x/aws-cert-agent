"""ingest.py — Ingesta de documentos (RAG) a pgvector.

Lee documentos desde /app/docs/ (montado desde agent/docs/ en el host),
los divide en chunks y los inserta en PostgreSQL (pgvector).

Uso recomendado (dentro de Docker):
  docker compose exec agent python ingest/ingest.py --reset
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector


DEFAULT_DOCS_DIR = Path(os.getenv("DOCS_DIR", "/app/docs"))
DEFAULT_COLLECTION_NAME = os.getenv("RAG_COLLECTION", "aws_certifications")


def _env(name: str) -> str:
	value = os.getenv(name, "").strip()
	if not value:
		raise RuntimeError(f"Falta la variable de entorno obligatoria: {name}")
	return value


def _iter_files(root: Path) -> list[Path]:
	if not root.exists():
		return []
	supported = {".pdf", ".txt", ".md"}
	files: list[Path] = []
	for path in root.rglob("*"):
		if not path.is_file():
			continue
		if path.name.startswith("."):
			continue
		if path.suffix.lower() in supported:
			files.append(path)
	return sorted(files)


def _certification_from_path(docs_root: Path, file_path: Path) -> str:
	try:
		rel = file_path.relative_to(docs_root)
		if rel.parts:
			return rel.parts[0]
	except Exception:
		pass
	return "unknown"


def _load_one(docs_root: Path, file_path: Path) -> list[Document]:
	suffix = file_path.suffix.lower()
	if suffix == ".pdf":
		loader = PyPDFLoader(str(file_path))
		docs = loader.load()
	else:
		loader = TextLoader(str(file_path), encoding="utf-8")
		docs = loader.load()

	certification = _certification_from_path(docs_root, file_path)
	for doc in docs:
		doc.metadata = {
			**(doc.metadata or {}),
			"certification": certification,
			"source": str(file_path),
			"file_name": file_path.name,
		}
	return docs


def _load_all(docs_root: Path, files: Iterable[Path]) -> list[Document]:
	all_docs: list[Document] = []
	for file_path in files:
		all_docs.extend(_load_one(docs_root, file_path))
	return all_docs


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Ingesta de documentos AWS a pgvector")
	parser.add_argument("--docs", default=str(DEFAULT_DOCS_DIR), help="Directorio raíz de docs")
	parser.add_argument(
		"--collection",
		default=DEFAULT_COLLECTION_NAME,
		help="Nombre de la colección en pgvector",
	)
	parser.add_argument(
		"--reset",
		action="store_true",
		help="Borra y recrea la colección antes de insertar",
	)
	parser.add_argument("--chunk-size", type=int, default=1000)
	parser.add_argument("--chunk-overlap", type=int, default=150)
	parser.add_argument(
		"--embedding-model",
		default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
	)
	args = parser.parse_args(argv)

	docs_root = Path(args.docs)
	if not docs_root.exists():
		print(f"No existe el directorio de docs: {docs_root}")
		print("Crea carpetas y agrega tus documentos, por ejemplo:")
		print("  agent/docs/cloud-practitioner/")
		print("  agent/docs/security-specialty/")
		print("  agent/docs/ml-specialty/")
		return 1

	files = _iter_files(docs_root)
	if not files:
		print(f"No se encontraron documentos en: {docs_root}")
		return 0

	database_url = _env("DATABASE_URL")

	# Embeddings: actualmente se usa OpenAI para embeddings.
	# Aunque el LLM sea Groq, para RAG necesitas OPENAI_API_KEY.
	_env("OPENAI_API_KEY")

	print(f"Docs root: {docs_root}")
	print(f"Archivos detectados: {len(files)}")
	print(f"Colección: {args.collection}")
	print(f"Reset colección: {args.reset}")

	raw_docs = _load_all(docs_root, files)

	splitter = RecursiveCharacterTextSplitter(
		chunk_size=args.chunk_size,
		chunk_overlap=args.chunk_overlap,
		add_start_index=True,
	)
	chunks = splitter.split_documents(raw_docs)

	embeddings = OpenAIEmbeddings(model=args.embedding_model)
	try:
		vectorstore = PGVector(
			connection_string=database_url,
			embedding_function=embeddings,
			collection_name=args.collection,
			pre_delete_collection=args.reset,
		)
	except TypeError:
		# Compatibilidad con versiones antiguas del wrapper.
		vectorstore = PGVector(
			connection_string=database_url,
			embedding_function=embeddings,
			collection_name=args.collection,
		)
		if args.reset:
			try:
				vectorstore.delete_collection()
			except Exception:
				pass
	vectorstore.add_documents(chunks)

	print(f"Documentos cargados: {len(raw_docs)}")
	print(f"Chunks insertados: {len(chunks)}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))
