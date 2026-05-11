# CLAUDE.md — Agente Experto en Certificaciones AWS

> **Misión:** Implementar un agente de IA experto en las certificaciones AWS Cloud Practitioner, Security Specialty y Machine Learning Specialty. El agente expone una interfaz de chat via Chainlit, usa LangGraph como motor, y tiene observabilidad completa con Langfuse v3. Todo corre en Docker Compose.
>
> **Al finalizar la implementación, el agente DEBE dejar una guía `IMPLEMENTADO.md` en la raíz del proyecto documentando lo que hizo.**

---

## REGLAS ESTRICTAS PARA EL AGENTE

1. **PROHIBIDO** usar `openssl` para generar ningún valor en ningún momento.
2. **PROHIBIDO** crear cuentas de servicios externos ni configurar nada fuera del proyecto.
3. Todos los passwords y secrets de test son literalmente `test` o `test1234` (MinIO requiere mínimo 8 caracteres).
4. El apartado de RAG debe crearse con la estructura lista pero **sin implementar la lógica de retrieval** — se indica claramente dónde va.
5. Seguir el orden de pasos exactamente como está documentado.

---

## ESTRUCTURA DEL PROYECTO

```
aws-cert-agent/
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
├── README.md
└── agent/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py                  # Entry point Chainlit
    ├── agent/
    │   ├── __init__.py
    │   ├── graph.py            # LangGraph agent
    │   ├── retriever.py        # RAG — PENDIENTE (estructura lista)
    │   └── prompts.py          # System prompts del agente AWS
    └── ingest/
        ├── __init__.py
        └── ingest.py           # Script ingestión documentos — PENDIENTE
```

---

## PASO 1 — Crear la estructura de carpetas

```bash
mkdir -p aws-cert-agent/agent/agent
mkdir -p aws-cert-agent/agent/ingest
cd aws-cert-agent
```

---

## PASO 2 — Crear `docker-compose.yml`

Crear el archivo `docker-compose.yml` en la raíz del proyecto con el siguiente contenido **exacto**:

```yaml
services:

  # ══════════════════════════════════════════════
  # RAG — PostgreSQL con pgvector
  # Base de datos para embeddings y vectores
  # ══════════════════════════════════════════════
  postgres-rag:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: rag
    volumes:
      - pgdata-rag:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 5s
      timeout: 5s
      retries: 10

  # ══════════════════════════════════════════════
  # LANGFUSE v3 — Infraestructura de observabilidad
  # ══════════════════════════════════════════════

  postgres-langfuse:
    image: postgres:16
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: langfuse
    volumes:
      - pgdata-langfuse:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

  clickhouse:
    image: clickhouse/clickhouse-server:24.3
    restart: always
    environment:
      CLICKHOUSE_DB: default
      CLICKHOUSE_USER: test
      CLICKHOUSE_PASSWORD: test
    volumes:
      - clickhouse-data:/var/lib/clickhouse
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8123/ping"]
      interval: 5s
      timeout: 5s
      retries: 10

  minio:
    image: minio/minio
    restart: always
    entrypoint: sh
    command: -c 'mkdir -p /data/langfuse && minio server /data --console-address ":9090"'
    environment:
      MINIO_ROOT_USER: test
      MINIO_ROOT_PASSWORD: test1234
    volumes:
      - minio-data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 10

  langfuse-web:
    image: langfuse/langfuse:3
    restart: always
    depends_on:
      postgres-langfuse:
        condition: service_healthy
      redis:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      minio:
        condition: service_healthy
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://test:test@postgres-langfuse:5432/langfuse
      SALT: "test"
      ENCRYPTION_KEY: "0000000000000000000000000000000000000000000000000000000000000000"
      NEXTAUTH_SECRET: "test"
      NEXTAUTH_URL: http://localhost:3000
      TELEMETRY_ENABLED: "false"
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_USER: test
      CLICKHOUSE_PASSWORD: test
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: test
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: test1234
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
      LANGFUSE_S3_EVENT_UPLOAD_REGION: auto

  langfuse-worker:
    image: langfuse/langfuse-worker:3
    restart: always
    depends_on:
      postgres-langfuse:
        condition: service_healthy
      redis:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      minio:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://test:test@postgres-langfuse:5432/langfuse
      SALT: "test"
      ENCRYPTION_KEY: "0000000000000000000000000000000000000000000000000000000000000000"
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_USER: test
      CLICKHOUSE_PASSWORD: test
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: test
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: test1234
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
      LANGFUSE_S3_EVENT_UPLOAD_REGION: auto

  # ══════════════════════════════════════════════
  # AGENTE — Chainlit + LangGraph
  # ══════════════════════════════════════════════
  agent:
    build: ./agent
    ports:
      - "8000:8000"
    depends_on:
      postgres-rag:
        condition: service_healthy
    env_file:
      - .env
    volumes:
      - ./agent:/app

volumes:
  pgdata-rag:
  pgdata-langfuse:
  clickhouse-data:
  minio-data:
```

---

## PASO 3 — Crear `.env` y `.env.example`

**`.env`** (este archivo NO va a git):

```env
# ── LLM ──────────────────────────────────────
OPENAI_API_KEY=sk-REEMPLAZAR_CON_TU_KEY

# ── RAG Database ─────────────────────────────
DATABASE_URL=postgresql://test:test@postgres-rag:5432/rag

# ── Langfuse ─────────────────────────────────
# Completar DESPUÉS de registrarse en http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-PENDIENTE
LANGFUSE_SECRET_KEY=sk-lf-PENDIENTE
LANGFUSE_HOST=http://langfuse-web:3000
```

**`.env.example`** (este SÍ va a git):

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://test:test@postgres-rag:5432/rag
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://langfuse-web:3000
```

---

## PASO 4 — Crear `.gitignore`

```gitignore
.env
__pycache__/
*.pyc
.DS_Store
```

---

## PASO 5 — Crear `agent/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
```

---

## PASO 6 — Crear `agent/requirements.txt`

```txt
chainlit==1.3.2
langchain==0.3.7
langchain-openai==0.2.9
langchain-community==0.3.7
langgraph==0.2.39
pgvector==0.3.5
psycopg2-binary==2.9.9
langfuse==2.60.0
python-dotenv==1.0.1
sqlalchemy==2.0.36
```

---

## PASO 7 — Crear `agent/agent/prompts.py`

```python
SYSTEM_PROMPT = """Eres un experto en certificaciones de AWS con conocimiento profundo en:

1. **AWS Cloud Practitioner (CLF-C02)**
   - Conceptos fundamentales de la nube
   - Servicios principales de AWS (EC2, S3, RDS, Lambda, etc.)
   - Modelos de facturación y precios
   - Seguridad y cumplimiento básico
   - Arquitectura de la nube AWS

2. **AWS Security Specialty (SCS-C02)**
   - Identity and Access Management (IAM) avanzado
   - Protección de infraestructura (VPC, Security Groups, NACLs)
   - Detección de amenazas (GuardDuty, Inspector, Macie)
   - Respuesta a incidentes en AWS
   - Cifrado y gestión de claves (KMS, CloudHSM)
   - Cumplimiento y gobernanza (Config, CloudTrail, Audit Manager)

3. **AWS Machine Learning Specialty (MLS-C01)**
   - Ingeniería de datos para ML (S3, Glue, Kinesis)
   - Análisis exploratorio y feature engineering
   - Modelado con SageMaker
   - Algoritmos integrados de AWS
   - Evaluación, optimización y despliegue de modelos
   - MLOps en AWS

## Tu comportamiento:
- Responde siempre en el idioma en que te pregunten
- Da respuestas precisas orientadas a la certificación
- Cuando expliques conceptos, menciona el servicio AWS específico
- Si la pregunta es sobre un examen, indica qué certificación cubre ese tema
- Usa ejemplos prácticos cuando sea útil
- Si no sabes algo con certeza, dilo claramente en lugar de inventar

## Formato de respuesta:
- Usa markdown para estructurar las respuestas
- Para preguntas de examen, indica la respuesta correcta y explica por qué las otras opciones son incorrectas
- Sé conciso pero completo
"""
```

---

## PASO 8 — Crear `agent/agent/retriever.py`

> ⚠️ **PENDIENTE — RAG no implementado aún**
> Este archivo tiene la estructura lista. La lógica de retrieval se implementará en la siguiente fase cuando se ingesten los documentos de las certificaciones.

```python
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
```

---

## PASO 9 — Crear `agent/agent/graph.py`

```python
# graph.py — LangGraph Agent
import os
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from .prompts import SYSTEM_PROMPT


# ── Estado del grafo ──────────────────────────────────────────
class AgentState(TypedDict):
    question: str
    history: list
    answer: str


# ── Nodo principal: llamada al LLM ───────────────────────────
def call_llm(state: AgentState) -> AgentState:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        streaming=True,
    )

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    # Agregar historial de conversación
    for turn in state.get("history", []):
        messages.append(HumanMessage(content=turn["human"]))
        messages.append(AIMessage(content=turn["ai"]))

    # Agregar la pregunta actual
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

    response = llm.invoke(messages)

    return {**state, "answer": response.content}


# ── Construcción del grafo ────────────────────────────────────
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.set_entry_point("llm")
    graph.add_edge("llm", END)
    return graph.compile()
```

---

## PASO 10 — Crear `agent/agent/__init__.py`

```python
```

*(archivo vacío)*

---

## PASO 11 — Crear `agent/ingest/__init__.py`

```python
```

*(archivo vacío)*

---

## PASO 12 — Crear `agent/ingest/ingest.py`

> ⚠️ **PENDIENTE — Script de ingestión de documentos**

```python
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
```

---

## PASO 13 — Crear `agent/app.py`

```python
# app.py — Entry point Chainlit
import chainlit as cl
from agent.graph import build_graph
from langfuse.callback import CallbackHandler
import os

# Compilar el grafo una sola vez al arrancar
graph = build_graph()


@cl.on_chat_start
async def on_chat_start():
    """Inicializa la sesión de chat."""
    cl.user_session.set("history", [])
    await cl.Message(
        content=(
            "👋 ¡Hola! Soy tu asistente experto en certificaciones AWS.\n\n"
            "Puedo ayudarte con:\n"
            "- ☁️ **Cloud Practitioner** (CLF-C02)\n"
            "- 🔒 **Security Specialty** (SCS-C02)\n"
            "- 🤖 **Machine Learning Specialty** (MLS-C01)\n\n"
            "¿Qué quieres aprender hoy?"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Procesa cada mensaje del usuario."""
    history = cl.user_session.get("history", [])

    # Langfuse: tracing automático via callback
    langfuse_handler = CallbackHandler(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST"),
    )

    # Streaming: mostrar respuesta token a token
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

    # Guardar en historial de la sesión
    history.append({"human": message.content, "ai": full_response})
    cl.user_session.set("history", history)
```

---

## PASO 14 — Levantar la infraestructura

Ejecutar en la raíz del proyecto:

```bash
docker compose up -d
```

Verificar que todos los contenedores estén corriendo:

```bash
docker compose ps
```

Todos deben aparecer con estado `running` o `healthy`. Esperar ~3 minutos a que ClickHouse termine de inicializar. Verificar con:

```bash
docker compose logs -f langfuse-web
```

Cuando aparezca el mensaje `Ready`, continuar al siguiente paso.

---

## PASO 15 — Configurar Langfuse

1. Abrir `http://localhost:3000` en el navegador
2. Registrarse con cualquier email y contraseña (es local, no importa)
3. Crear una **organización** (ej: `aws-agent-org`)
4. Crear un **proyecto** (ej: `aws-cert-agent`)
5. Ir a **Settings → API Keys → Create new API key**
6. Copiar el `Public Key` y `Secret Key`
7. Editar el archivo `.env` y reemplazar los valores:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-xxxxx
   LANGFUSE_SECRET_KEY=sk-lf-xxxxx
   ```
8. Reiniciar el contenedor del agente:
   ```bash
   docker compose restart agent
   ```

---

## PASO 16 — Verificar el agente

```bash
# Ver logs del agente
docker compose logs -f agent
```

Abrir `http://localhost:8000` en el navegador. Debe aparecer la interfaz de chat de Chainlit con el mensaje de bienvenida del agente AWS.

Hacer una pregunta de prueba, por ejemplo:
> "¿Cuál es la diferencia entre Security Groups y NACLs en AWS?"

Verificar que:
- ✅ El agente responde correctamente en el chat
- ✅ En Langfuse (`localhost:3000`) aparece la traza de la llamada

---

## PASO 17 — Crear `IMPLEMENTADO.md`

Una vez completados todos los pasos anteriores y verificado el funcionamiento, el agente DEBE crear el archivo `IMPLEMENTADO.md` en la raíz del proyecto con el siguiente contenido mínimo:

```markdown
# IMPLEMENTADO.md — Registro de implementación

## Fecha de implementación
[FECHA Y HORA]

## Estado de los servicios
- [ ] postgres-rag — corriendo en puerto 5432
- [ ] postgres-langfuse — corriendo (interno)
- [ ] redis — corriendo (interno)
- [ ] clickhouse — corriendo (interno)
- [ ] minio — corriendo en puerto 9090
- [ ] langfuse-web — corriendo en puerto 3000
- [ ] langfuse-worker — corriendo (interno)
- [ ] agent (Chainlit) — corriendo en puerto 8000

## URLs disponibles
- Chat del agente: http://localhost:8000
- Langfuse observabilidad: http://localhost:3000

## Prueba de funcionamiento
- Pregunta de prueba realizada: [SÍ/NO]
- Traza visible en Langfuse: [SÍ/NO]

## Pendiente — RAG
- [ ] Agregar documentos en `agent/docs/` organizados por certificación
- [ ] Implementar `agent/ingest/ingest.py`
- [ ] Implementar `agent/agent/retriever.py`
- [ ] Activar el nodo RAG en `agent/agent/graph.py`
- [ ] Ejecutar `docker compose exec agent python ingest/ingest.py`

## Notas del agente implementador
[ESPACIO PARA NOTAS ADICIONALES]
```

---

## RESUMEN VISUAL DE LA ARQUITECTURA

```
Usuario (Browser :8000)
        │
        ▼
   Chainlit UI
   (app.py)
        │
        ▼
  LangGraph Agent          Langfuse (localhost:3000)
  (graph.py)      ─────── CallbackHandler ──────────►  langfuse-web
        │                                               langfuse-worker
        │                                               clickhouse
        ▼                                               minio
  ChatOpenAI GPT-4o-mini                                redis
        │                                               postgres-langfuse
        │
        ▼
  [RAG PENDIENTE]
  retriever.py
        │
        ▼
  postgres-rag
  (pgvector :5432)
```

---

## SERVICIOS Y PUERTOS

| Servicio | Puerto expuesto | Uso |
|---|---|---|
| agent (Chainlit) | 8000 | Chat UI del agente |
| langfuse-web | 3000 | Dashboard de observabilidad |
| postgres-rag | 5432 | Base de datos vectores (RAG) |
| minio | 9090 | Console MinIO (opcional) |

---

*Fin del CLAUDE.md*
