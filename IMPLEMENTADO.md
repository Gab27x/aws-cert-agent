# IMPLEMENTADO.md — Registro de implementación

## Fecha de implementación
2026-05-11 (actualizado 2026-05-11)

## Estado de los servicios
- [x] postgres-rag — corriendo en puerto 5432
- [x] postgres-langfuse — corriendo (interno)
- [x] redis — corriendo (interno)
- [x] clickhouse — corriendo (interno, con ClickHouse Keeper integrado)
- [x] minio — corriendo en puerto 9090
- [x] langfuse-web — corriendo en puerto 3000
- [x] langfuse-worker — corriendo (interno)
- [x] agent (Chainlit) — corriendo en puerto 8000

## URLs disponibles
- Chat del agente: http://localhost:8000
- Langfuse observabilidad: http://localhost:3000

## Configuración actual del LLM
- Proveedor activo: `LLM_PROVIDER=openai` (configurable en `.env`)
- Modelo OpenAI: `gpt-4o-mini` (configurable con `OPENAI_MODEL`)
- Proveedor alternativo disponible: Groq (`LLM_PROVIDER=groq`, modelo `llama-3.3-70b-versatile`)
- `OPENAI_API_KEY`: configurada en `.env`

## Configuración Langfuse
- `LANGFUSE_PUBLIC_KEY`: configurada en `.env` (`pk-lf-...`)
- `LANGFUSE_SECRET_KEY`: configurada en `.env` (`sk-lf-...`)
- `LANGFUSE_BASE_URL`: `http://localhost:3000`
- Variable aceptada también como `LANGFUSE_HOST` (app.py soporta ambas)

## Prueba de funcionamiento
- Pregunta de prueba realizada: PENDIENTE (verificar en http://localhost:8000)
- Traza visible en Langfuse: PENDIENTE (keys configuradas, verificar en http://localhost:3000)

## RAG (pgvector)

Estado del código:
- [x] Implementada ingesta en `agent/ingest/ingest.py`
- [x] Implementado retriever en `agent/agent/retriever.py`
- [x] Activado nodo `retrieve` en `agent/agent/graph.py`

Pendiente para quedar operativo con tus documentos:
- [ ] Agregar documentos en `agent/docs/` organizados por certificación
- [ ] Ejecutar `docker compose exec agent python ingest/ingest.py --reset`

## Notas del agente implementador

### Correcciones aplicadas durante el despliegue

1. **sqlalchemy==2.0.36 → 2.0.35**: `langchain-community==0.3.7` requiere `SQLAlchemy<2.0.36`.

2. **pydantic<2.10 añadido**: `chainlit==1.3.2` es incompatible con `pydantic>=2.10` (error `PydanticUserError: CodeSettings is not fully defined`). Se añadió `pydantic>=2.6.0,<2.10.0` al requirements.txt.

3. **CLICKHOUSE_MIGRATION_URL**: Langfuse v3 requiere esta variable de entorno adicional. Formato correcto: `clickhouse://user:pass@host:9000/default` (protocolo nativo, no HTTP). Añadida en `langfuse-web` y `langfuse-worker`.

4. **ClickHouse Keeper**: Langfuse v3 usa `ReplicatedMergeTree ON CLUSTER default` en las migraciones, lo que requiere ZooKeeper o ClickHouse Keeper. Se creó `clickhouse/config.xml` con la configuración de Keeper integrado y se montó en el contenedor vía `./clickhouse/config.xml:/etc/clickhouse-server/config.d/keeper.xml`.

5. **venv local**: Python local es 3.14 — incompatible con las versiones pinadas para 3.11. El venv se crea con `python3 -m venv .venv` pero la instalación de paquetes solo funciona dentro del Docker (Python 3.11-slim).

6. **Multi-proveedor LLM (nuevo)**: Se añadió soporte para Groq como proveedor alternativo sin costo. `graph.py` tiene `_build_llm()` que selecciona el proveedor según `LLM_PROVIDER` en `.env`. `app.py` muestra el proveedor activo en el mensaje de bienvenida. Se añadió `langchain-groq==0.2.1` a `requirements.txt`.

7. **LANGFUSE_BASE_URL vs LANGFUSE_HOST**: Langfuse SDK usa `LANGFUSE_BASE_URL` pero el CLAUDE.md original usaba `LANGFUSE_HOST`. `app.py` acepta ambas variables para compatibilidad (`os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")`).

### Pasos para configurar Langfuse tras el despliegue
1. Abrir http://localhost:3000
2. Registrarse (email/contraseña locales, no importan)
3. Crear organización y proyecto
4. Settings → API Keys → Create new API key
5. Copiar claves al `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-xxxxx
   LANGFUSE_SECRET_KEY=sk-lf-xxxxx
   ```
6. Añadir la OpenAI API key real al `.env`:
   ```
   OPENAI_API_KEY=sk-xxxxx
   ```
7. `docker compose restart agent`

### Cambiar a Groq (LLM gratuito)
Editar `.env`:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxx   # obtener en console.groq.com
GROQ_MODEL=llama-3.3-70b-versatile
```
Luego: `docker compose restart agent`
