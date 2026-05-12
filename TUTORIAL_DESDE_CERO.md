# Tutorial desde cero — AWS Cert Agent (Docker Compose)

Este proyecto levanta un agente de chat (Chainlit + LangGraph) con **RAG en pgvector** y **observabilidad en Langfuse v3**, todo en Docker Compose.

## 0) Requisitos

- Windows 10/11
- **Docker Desktop** instalado y corriendo (con Docker Compose)
- Una API key válida:
  - **OpenAI** (recomendado si quieres RAG), o
  - **Groq** (solo para el chat; el RAG/embeddings igualmente usan OpenAI en este repo)

> Nota: el RAG (embeddings) usa OpenAI (`text-embedding-3-small`). Aunque el chat use Groq, para ingestar y recuperar contexto necesitas `OPENAI_API_KEY`.

---

## 1) Clonar el repositorio

En PowerShell:

```powershell
cd $HOME\Desktop
git clone https://github.com/Gab27x/aws-cert-agent.git
cd aws-cert-agent
```

---

## 2) Crear el archivo `.env`

Copia la plantilla:

```powershell
Copy-Item .env.example .env
```

Abre `.env` y configura como mínimo:

- LLM (elige uno)
  - OpenAI:
    - `LLM_PROVIDER=openai`
    - `OPENAI_API_KEY=sk-...`
  - Groq:
    - `LLM_PROVIDER=groq`
    - `GROQ_API_KEY=gsk_...`

- Base de datos RAG (déjalo como está por defecto):
  - `DATABASE_URL=postgresql://test:test@postgres-rag:5432/rag`

- Langfuse (lo completas después del paso 4):
  - `LANGFUSE_PUBLIC_KEY=pk-lf-...`
  - `LANGFUSE_SECRET_KEY=sk-lf-...`
  - `LANGFUSE_BASE_URL=http://langfuse-web:3000`

---

## 3) Levantar todos los servicios

Desde la raíz del proyecto:

```powershell
docker compose up -d
```

Verifica estado:

```powershell
docker compose ps
```

Langfuse (ClickHouse) tarda ~2–3 min en estar listo. Puedes seguir logs:

```powershell
docker compose logs -f langfuse-web
```

Cuando veas `Ready`, continúa.

---

## 4) Configurar Langfuse (observabilidad)

1. Abre: `http://localhost:3000`
2. Crea una cuenta local (Sign up) con cualquier email/contraseña
3. Crea una **Organization** y luego un **Project**
4. En el proyecto: **Settings → API Keys → Create new API key**
5. Copia:
   - `Public Key` (`pk-lf-...`)
   - `Secret Key` (`sk-lf-...`)
6. Pega esas claves en tu `.env`

### Importante (Docker networking)

- Desde tu navegador, Langfuse es `http://localhost:3000`
- Pero **desde el contenedor del agente**, Langfuse debe ser:

```env
LANGFUSE_BASE_URL=http://langfuse-web:3000
```

### Aplicar cambios de `.env`

Docker Compose **no recarga** variables del `.env` con un simple `restart`. Para que el contenedor lea los cambios, recréalo:

```powershell
docker compose up -d --force-recreate --no-deps agent
```

---

## 5) Colocar documentos para el RAG

Pon tus PDFs/TXT/MD en estas carpetas (según la certificación):

- `agent/docs/cloud-practitioner/`
- `agent/docs/security-specialty/`
- `agent/docs/ml-specialty/`

---

## 6) Ejecutar la ingesta (cargar documentos a pgvector)

Recomendado (borra y recrea la colección para evitar duplicados):

```powershell
docker compose exec agent python ingest/ingest.py --reset
```

Si falla por autenticación o cuota:
- `401 invalid_api_key`: revisa `OPENAI_API_KEY`
- `429 insufficient_quota`: necesitas créditos/billing en OpenAI para embeddings

---

## 7) Probar el chat y confirmar que el RAG está activo

1. Abre el chat:
   - `http://localhost:8000`

2. Haz una pregunta (ej.):
   - “¿Cuál es la diferencia entre Security Groups y NACLs en AWS?”

3. Abre Langfuse:
   - `http://localhost:3000` → **Tracing**

Para confirmar RAG, en la traza debes ver:
- Un nodo **`retrieve`** antes del nodo **`llm`**
- Dentro de `retrieve`, el **VectorStoreRetriever**
- Un campo **`context`** con texto (no vacío)

---

## 8) Evaluar tu RAG con Ragas (RAG Assessment)

Este repo incluye un script para evaluar tu pipeline actual con métricas de Ragas.

### 8.1) Instalar dependencias en el contenedor

Como `ragas` vive en `agent/requirements.txt`, solo necesitas reconstruir la imagen del servicio `agent`:

```powershell
docker compose build agent
docker compose up -d --force-recreate --no-deps agent
```

### 8.2) Ejecutar evaluación

Ejemplo con dataset de muestra:

```powershell
docker compose exec agent python eval/ragas_eval.py --input eval/sample_questions.jsonl
```

Esto genera un resumen en `agent/eval/ragas_results.json` (dentro del contenedor / volumen).

### 8.3) Evaluar con tus propias preguntas

Crea un JSONL similar con una línea por ejemplo:

```json
{"question":"...","ground_truth":"..."}
```

`ground_truth` es opcional:
- Si lo incluyes, se calculan métricas adicionales (precision/recall de contexto).
- Si no lo incluyes, se calculan métricas que no lo requieren (p.ej. relevancia y faithfulness).

### 8.4) Generar gráficas (para presentación)

El script `eval/plot_ragas.py` genera 2 imágenes (PNG) para que sea más fácil explicar resultados:

- `agent/eval/ragas_metrics_avg.png` → barras con el promedio por métrica
- `agent/eval/ragas_metrics_boxplot.png` → boxplot con la distribución por pregunta

Primero asegúrate de haber corrido la evaluación (paso 8.2) para que exista `eval/ragas_results.json`.

Luego reconstruye el contenedor del `agent` (incluye `matplotlib`):

```powershell
docker compose build agent
docker compose up -d --force-recreate --no-deps agent
```

Finalmente genera las gráficas:

```powershell
docker compose exec agent python eval/plot_ragas.py
```

Abre los PNG desde tu VS Code/Explorador en:

- `agent/eval/ragas_metrics_avg.png`
- `agent/eval/ragas_metrics_boxplot.png`

---

## Comandos útiles

```powershell
# Ver contenedores
docker compose ps

# Logs del agente
docker compose logs -f agent

# Parar todo
docker compose down

# Reset total (borra datos de DBs/volúmenes)
docker compose down -v
```

---

## Troubleshooting rápido

- No aparecen trazas en Langfuse:
  - Confirma `LANGFUSE_BASE_URL=http://langfuse-web:3000` en `.env`
  - Re-crea el agente: `docker compose up -d --force-recreate --no-deps agent`

- El chat responde pero no usa RAG:
  - Revisa `RAG_ENABLED=true`
  - Revisa que hayas corrido ingesta y que no haya errores en `docker compose logs -f agent`

- Langfuse tarda mucho en levantar:
  - Espera 2–3 min (ClickHouse/migraciones)
  - Revisa `docker compose logs -f langfuse-web`
