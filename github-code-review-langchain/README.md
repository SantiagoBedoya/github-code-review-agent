# GitHub Code Review LangChain

Bot multi-agente de revisión de código para Pull Requests de GitHub. Utiliza **LangChain** + **OpenAI** con **5 agentes especializados** y un algoritmo **Multi-Armed Bandit** contextual que aprende qué agentes son más efectivos según el tipo de archivo.

---

## Arquitectura

```
Webhook GitHub (opened/synchronize)
        │
        ▼
  FastAPI ──► Filtro de archivos ──► 5 Agentes (LLM) ──► Sintetizador ──► Comentario en PR
                          │                    ▲
                          ▼                    │
                   Multi-Armed Bandit ◄── PostgreSQL (pesos e historial)
```

---

## Agentes de revisión

| Agente | Enfoque |
|---|---|
| `seguridad` | OWASP Top 10, credenciales, datos sensibles, auth |
| `estructuras` | Algoritmos, complejidad O(n²), estructuras de datos |
| `calidad` | SOLID, código duplicado, magic numbers |
| `performance` | Queries N+1, sync/async, caching, memory leaks |
| `documentacion` | Docstrings faltantes, TODOs, comentarios obsoletos |

Los agentes `seguridad` y `estructuras` usan **Chain-of-Thought** (razonan en `<razonamiento>` antes del JSON).

---

## Multi-Armed Bandit

- **Contexto**: vector de 9 features (extensión + proporción de líneas)
- **Epsilon-greedy** con decaimiento: explora vs explota según score aprendido
- **Recompensa**: +1.0 si encuentra issues, -0.5 si no
- **Persistencia**: pesos y epsilon guardados en PostgreSQL entre reinicios

---

## Requisitos

- **Python >= 3.14**
- **PostgreSQL** (o base compatible con asyncpg)
- **Cuenta de GitHub** con token de acceso
- **API key de OpenAI**

---

## Configuración

Copiar `.env.example` a `.env` y completar:

| Variable | Descripción |
|---|---|
| `GITHUB_TOKEN` | Token de GitHub con permisos `repo` |
| `OPENAI_API_KEY` | API key de OpenAI |
| `OPENAI_MODEL` | Modelo OpenAI (default: `gpt-4o-mini`) |
| `WEBHOOK_SECRET` | Secreto para validar webhooks (opcional) |
| `DATABASE_URL` | Conexión PostgreSQL |
| `MAX_CHANGED_LINES` | Máx. líneas modificadas por archivo (default: 300) |

Parámetros del bandit: `BANDIT_EPSILON`, `BANDIT_ALPHA`, `BANDIT_BETA`, `BANDIT_EPSILON_DECAY`, `BANDIT_EPSILON_MIN`, `BANDIT_DECAY_INTERVAL`.

---

## Instalación y ejecución

```bash
uv sync
uv run github-code-review
```

Inicia un servidor FastAPI en `http://0.0.0.0:8000`.

### Webhook en GitHub

1. En el repositorio destino: Settings → Webhooks → Add webhook
2. **Payload URL**: `http://<tu-servidor>:8000/webhook/github-review`
3. **Content type**: `application/json`
4. **Events**: Pull requests

El bot responde a eventos `opened` y `synchronize`.

---

## Stack

- **FastAPI** + **uvicorn** — servidor web
- **LangChain** + **langchain-openai** — orquestación de LLMs
- **SQLAlchemy** + **asyncpg** — persistencia asincrónica en PostgreSQL
- **httpx** — cliente HTTP asincrónico para API de GitHub
- **Pydantic** — validación de datos
- **ruff** + **pyright** — linting y type checking

---

## Licencia

MIT
