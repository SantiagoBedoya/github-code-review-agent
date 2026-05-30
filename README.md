# n8n-local + GitHub Code Review Agent

Entorno local de **n8n** (workflow automation) integrado con un **bot multi-agente de code review** para Pull Requests de GitHub, optimizado mediante **aprendizaje por refuerzo** (Contextual Multi-Armed Bandit).

---

## Arquitectura

El proyecto tiene dos componentes independientes pero complementarios:

| Componente | Descripción | Puerto |
|-----------|-------------|--------|
| **n8n** | Motor de automatización de workflows v2.20.0 | `5678` |
| **github-code-review** | Bot Python/FastAPI que revisa PRs usando 5 agentes especializados de IA | `8000` |

```
GitHub Webhook (PR opened/synchronize)
       │
       ▼
┌──────────────────────┐     ┌──────────────────────┐
│  n8n Workflow        │     │  Python FastAPI Bot  │
│  (workflows/*.json)  │     │ (github-code-review) │
│                      │     │                      │
│  5 Agentes IA        │     │  5 Agentes IA        │
│  + RL Bandit         │     │  + RL Bandit         │
│  Postea comentario   │     │  Postea comentario   │
└──────────────────────┘     └──────────────────────┘
       │                             │
       ▼                             ▼
    OpenAI GPT-4o-mini          OpenAI GPT-4o-mini
    Neon PostgreSQL             PostgreSQL local/remoto
```

Ambos resuelven el mismo problema con implementaciones distintas: el primero como workflow visual de n8n, el segundo como servicio Python nativo.

---

## Estructura del Repositorio

```
.
├── docker-compose.yaml              # Despliegue de n8n con Docker Compose
├── .env.example                     # Variables de entorno requeridas (n8n)
├── local-files/                     # Montura para archivos locales en n8n
│
├── github-code-review/              # Bot de code review en Python
│   ├── .env.example                 # Variables de entorno del bot
│   ├── pyproject.toml               # Dependencias y configuración del paquete
│   ├── uv.lock                      # Lock file de dependencias
│   └── src/github_code_review/
│       ├── __main__.py              # Entrypoint (uvicorn)
│       ├── main.py                  # FastAPI app + webhook endpoint
│       ├── config.py                # Configuración con Pydantic Settings
│       ├── database.py              # Modelos ORM + conexión PostgreSQL
│       ├── filters.py               # Filtrado de archivos válidos
│       ├── models.py                # Modelos Pydantic
│       ├── agents/
│       │   ├── bandit.py            # Algoritmo Multi-Armed Bandit (RL)
│       │   ├── reviewer.py          # Orquestador de revisión por archivo
│       │   ├── synthesizer.py       # Consolidación de resultados en Markdown
│       │   └── prompts.py           # Prompts de los 5 agentes especializados
│       └── github/
│           └── client.py            # Cliente REST para GitHub API
│
└── workflows/                       # Exportaciones JSON de workflows de n8n
    ├── github-code-review-agents.json       # Workflow principal
    ├── github-code-review-agents-RL.json    # Variante con Reinforcement Learning
    └── RL_CODE_REVIEW_EXPLANATION.md        # Explicación del algoritmo RL
```

---

## Requisitos Previos

- **Docker** y **Docker Compose** (para n8n)
- **Python 3.14+** y **uv** (para github-code-review)
- Una cuenta de **OpenAI** con API key
- Una base de datos **PostgreSQL** (Neon recomendado para n8n; local o remota para el bot)
- Un **repositorio en GitHub** para recibir los webhooks

---

## Configuración de Variables de Entorno

### n8n (raíz del proyecto)

Copia `.env.example` a `.env` y completa los valores:

```env
# General
GENERIC_TIMEZONE=America/Bogota
NODE_ENV=production

# n8n
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
WEBHOOK_URL=http://localhost:5678/

# PostgreSQL (Neon)
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=tu-host-neon
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_DATABASE=tu-database
DB_POSTGRESDB_USER=tu-usuario
DB_POSTGRESDB_PASSWORD=tu-contraseña
DB_POSTGRESDB_SSL_ENABLED=true

# OpenAI
OPENAI_API_KEY=sk-tu-api-key

# GitHub
GITHUB_API_KEY=ghp_tu-token
GITHUB_PAT=ghp_tu-token
GITHUB_TOKEN=ghp_tu-token
```

### github-code-review (`github-code-review/.env`)

```env
GITHUB_TOKEN=ghp_tu_github_token
OPENAI_API_KEY=sk-tu_openai_api_key
OPENAI_MODEL=gpt-4o-mini
WEBHOOK_SECRET=

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/github_code_review

# Parámetros del Bandit (opcionales, valores por defecto)
BANDIT_EPSILON=0.3
BANDIT_ALPHA=0.2
BANDIT_BETA=0.1
BANDIT_EPSILON_DECAY=0.95
BANDIT_EPSILON_MIN=0.05
BANDIT_DECAY_INTERVAL=10

# Filtrado de archivos
MAX_CHANGED_LINES=300
```

---

## Uso

### Iniciar n8n

```bash
docker-compose up -d
```

Acceder a `http://localhost:5678`. Importar los workflows desde la carpeta `workflows/` y configurar los webhooks.

### Iniciar el bot de code review

```bash
cd github-code-review
uv run github-code-review
```

El servidor FastAPI inicia en `http://localhost:8000`. El webhook escucha en `POST /webhook/github-review`.

---

## Agentes Especializados

Ambos componentes (n8n y Python) utilizan 5 agentes de IA, cada uno con un enfoque específico:

| Agente | Enfoque | Severidades |
|--------|---------|-------------|
| **Seguridad** | OWASP Top 10, hardcoded secrets, autenticación débil | crítica / alta / media / baja |
| **Estructuras de Datos** | Complejidad algorítmica, estructuras ineficientes | alta / media / baja |
| **Calidad de Código** | Principios SOLID, duplicación, naming, magic numbers | alta / media / baja |
| **Performance** | N+1 queries, caché ausente, memory leaks, blocking calls | alta / media / baja |
| **Documentación** | Falta de docstrings, TODOs, comentarios obsoletos | media / baja |

---

## Algoritmo de Reinforcement Learning (Multi-Armed Bandit)

El sistema usa un **Contextual Multi-Armed Bandit con política ε-greedy** para decidir qué agentes ejecutar en cada archivo, optimizando el costo de API de OpenAI.

**Feature vector** (9 dimensiones por archivo):
- 8 one-hot encoding por extensión (.py, .js, .ts, .java, .go, .rb, .php, .cs)
- 1 valor normalizado de líneas cambiadas (÷300)

**Decisión**:
- Probabilidad ε: exploración aleatoria
- Probabilidad 1−ε: ejecutar agente si `score = w · features > 0`

**Recompensa**: `+1.0` si encontró issues, `−0.5` si no encontró nada.

Los pesos se actualizan con SGD y epsilon decae de 0.3 hasta 0.05 cada 10 iteraciones.

> El detalle completo del algoritmo está en `workflows/RL_CODE_REVIEW_EXPLANATION.md`.

---

## Configuración Necesaria en GitHub

Para que el sistema funcione, debes configurar lo siguiente en tu repositorio de GitHub:

### 1. Personal Access Token (PAT)

Crea un token clásico en **Settings → Developer settings → Personal access tokens → Tokens (classic)**.

Requisitos del token:
- Permiso `repo` (acceso completo a repositorios privados)
- Permiso `write:discussion` (si se usan discusiones)

Este token se usa en las variables `GITHUB_TOKEN`, `GITHUB_PAT` y `GITHUB_API_KEY` del `.env`.

### 2. Webhook del Repositorio

En **Settings → Webhooks → Add webhook**:

| Campo | Valor |
|-------|-------|
| **Payload URL** | `http://<tu-dominio-o-ip>:8000/webhook/github-review` (para el bot Python) o `http://<tu-dominio-o-ip>:5678/webhook/github-review` (para n8n) |
| **Content type** | `application/json` |
| **Secret** | (opcional) Debe coincidir con `WEBHOOK_SECRET` en tu `.env` |
| **Events** | Seleccionar **Let me select individual events** y marcar solo **Pull requests** |
| **Active** | ✔ |

> **Nota:** Si ejecutas localmente, necesitas exponer tu servidor con [ngrok](https://ngrok.com) o similar para que GitHub pueda alcanzar el webhook:
> ```bash
> ngrok http 8000   # Para el bot Python
> # o
> ngrok http 5678   # Para n8n
> ```
> Luego usa la URL de ngrok (`https://xxxx.ngrok.io`) como Payload URL.

### 3. Configurar el Webhook en n8n (si usas los workflows)

Si usas los workflows de n8n:
1. Importa el workflow desde `workflows/github-code-review-agents.json`
2. Activa el workflow
3. Configura el webhook de GitHub apuntando a `http://<tu-host>:5678/webhook/github-review`
4. Verifica que los nodos de OpenAI tengan acceso a `OPENAI_API_KEY` (configurado vía `N8N_CODE_ENV_ALLOW_LIST`)

---

## Tecnologías

| Tecnología | Uso |
|-----------|-----|
| **n8n 2.20.0** | Motor de workflows |
| **Python 3.14** | Runtime del bot de code review |
| **FastAPI** | Servidor webhook |
| **LangChain** | Orquestación de LLMs |
| **OpenAI GPT-4o-mini** | Modelo de IA para los agentes |
| **PostgreSQL (Neon)** | Base de datos para n8n |
| **PostgreSQL + asyncpg** | Persistencia del estado del bandit |
| **SQLAlchemy (async)** | ORM del bot |
| **Docker Compose** | Despliegue de n8n |
| **httpx** | Cliente HTTP para GitHub API |
| **Pydantic** | Validación de datos y configuración |
| **uv** | Gestor de paquetes y build de Python |
| **ruff / pyright** | Linter y type checker (dev) |
