# AWS Cert Agent

Agente de IA experto en certificaciones AWS con interfaz de chat, observabilidad completa y soporte multi-proveedor LLM. Todo corre en Docker Compose.

## Certificaciones cubiertas

- **Cloud Practitioner (CLF-C02)** — Fundamentos de la nube, servicios principales, facturación
- **Security Specialty (SCS-C02)** — IAM avanzado, detección de amenazas, KMS, cumplimiento
- **Machine Learning Specialty (MLS-C01)** — SageMaker, feature engineering, MLOps en AWS

## Stack

| Componente | Tecnología |
|---|---|
| Chat UI | Chainlit 1.3.2 |
| Motor del agente | LangGraph 0.2.39 |
| LLM (OpenAI) | gpt-4o-mini via langchain-openai |
| LLM (Groq) | llama-3.3-70b-versatile via langchain-groq |
| Observabilidad | Langfuse v3 |
| RAG (pendiente) | pgvector + PostgreSQL 16 |
| Almacenamiento eventos | ClickHouse 24.3 + MinIO |

## Requisitos

- Docker y Docker Compose
- Una API key de OpenAI **o** Groq (gratuito)

## Inicio rápido

**1. Copiar y editar el archivo de entorno:**

```bash
cp .env.example .env
```

Editar `.env` con el proveedor LLM elegido:

```env
# Opción A — OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Opción B — Groq (gratuito, obtener key en console.groq.com)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

**2. Levantar los servicios:**

```bash
docker compose up -d
```

**3. Esperar a que ClickHouse inicialice (~2-3 min):**

```bash
docker compose logs -f langfuse-web
# Esperar el mensaje "Ready"
```

**4. Configurar Langfuse (observabilidad):**

Abrir http://localhost:3000 y seguir estos pasos en orden:

1. Hacer clic en **Sign up** e ingresar cualquier email y contraseña (es local, no se valida)
2. En la pantalla **Create organization**, escribir un nombre (ej. `aws-agent-org`) y confirmar
3. En la pantalla **Create project**, escribir un nombre (ej. `aws-cert-agent`) y confirmar
4. En el panel del proyecto, ir a **Settings** (menú lateral izquierdo, abajo)
5. Ir a la sección **API Keys** y hacer clic en **Create new API key**
6. Copiar el **Public Key** (`pk-lf-...`) y el **Secret Key** (`sk-lf-...`)
7. Pegar las claves en `.env`:
   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
8. Reiniciar el agente para que tome las nuevas variables:
   ```bash
   docker compose restart agent
   ```

**5. Abrir el chat:**

```
http://localhost:8000
```

## URLs

| Servicio | URL |
|---|---|
| Chat del agente | http://localhost:8000 |
| Langfuse (observabilidad) | http://localhost:3000 |
| MinIO console (opcional) | http://localhost:9090 |
| PostgreSQL RAG | localhost:5432 |

## Estructura del proyecto

```
aws-cert-agent/
├── docker-compose.yml
├── .env                        # Variables de entorno (no en git)
├── .env.example                # Plantilla
├── clickhouse/
│   └── config.xml              # ClickHouse Keeper integrado (requerido por Langfuse v3)
└── agent/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py                  # Entry point Chainlit
    ├── agent/
    │   ├── graph.py            # LangGraph — nodo LLM + soporte multi-proveedor
    │   ├── retriever.py        # RAG con pgvector (pendiente)
    │   └── prompts.py          # System prompt del agente AWS
    └── ingest/
        └── ingest.py           # Ingestión de documentos (pendiente)
```

## Cambiar proveedor LLM

Editar `.env` y reiniciar:

```bash
# Cambiar a Groq
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile   # opcional, es el valor por defecto

docker compose restart agent
```

El mensaje de bienvenida del chat indica el proveedor activo.

## RAG — Implementación pendiente

El módulo de Retrieval-Augmented Generation está estructurado pero no implementado. Para activarlo:

1. Agregar documentos PDF en `agent/docs/` por certificación:
   ```
   agent/docs/cloud-practitioner/
   agent/docs/security-specialty/
   agent/docs/ml-specialty/
   ```
2. Implementar la lógica en `agent/ingest/ingest.py` (chunking + embeddings + inserción en pgvector)
3. Implementar `get_retriever()` en `agent/agent/retriever.py`
4. Descomentar el bloque RAG en `agent/agent/graph.py`
5. Ejecutar la ingestión:
   ```bash
   docker compose exec agent python ingest/ingest.py
   ```

## Comandos útiles

```bash
# Ver estado de todos los contenedores
docker compose ps

# Logs del agente
docker compose logs -f agent

# Reiniciar solo el agente (tras cambios en .env)
docker compose restart agent

# Detener todo
docker compose down

# Detener y eliminar volúmenes (reset completo)
docker compose down -v
```

## Notas técnicas

- `sqlalchemy==2.0.35` — langchain-community 0.3.7 es incompatible con 2.0.36
- `pydantic>=2.6.0,<2.10.0` — chainlit 1.3.2 es incompatible con pydantic 2.10+
- `clickhouse/config.xml` monta ClickHouse Keeper integrado, requerido por las migraciones de Langfuse v3 (`ReplicatedMergeTree ON CLUSTER default`)
- `CLICKHOUSE_MIGRATION_URL` usa el protocolo nativo (`clickhouse://`) no HTTP
