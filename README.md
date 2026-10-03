# LiteLLM Offline OpenAI Gateway

This project is a customized, offline-first branch of [LiteLLM](https://github.com/BerriAI/litellm). It has been stripped of external SaaS integrations, telemetry, and non-essential features (like RAG and Semantic Caching) to serve as a secure, isolated OpenAI-compatible Gateway for internal enterprise deployments.

## Architecture

The project has been refactored into two strictly separated main components for independent scaling and development:

1.  **Backend (`Backend/`)**: A lightweight API gateway built on FastAPI (Python) that handles routing, rate limiting (Redis), budget management (PostgreSQL), and exact-match caching. It connects exclusively to your internal or custom endpoints (`api_base`).
    - The `Backend/` directory contains all Python code (`litellm`, `gateway`, `enterprise`).
    - All telemetry, third-party integrations, and non-OpenAI LLM support have been removed.
2.  **Frontend (`frontend/`)**: A dashboard (`frontend/litellm-dashboard`) for managing users, keys, and budgets. It is completely decoupled from the backend codebase and communicates strictly via the REST API.

## Core Features Kept
- **OpenAI Provider Support**: Fully supports custom `api_base` targets.
- **Routing & Fallbacks**: Supports advanced load balancing and fallback mechanisms across internal nodes.
- **Auth & Budgets**: RBAC, API key generation, and budget limits relying purely on local PostgreSQL and Redis.
- **Caching**: Exact-match caching using a local Redis instance.

## Deployment & Running Locally

You can launch the entire stack using `docker-compose`:

```bash
docker-compose up -d
```

This will spin up:
-   `litellm`: The Python API Gateway (Port: 4000)
-   `frontend`: The Next.js Admin Dashboard (Port: 3000)
-   `db`: PostgreSQL database for accounts and keys
-   `redis`: Redis cache for rate limiting and exact matching

### Local Development

**Backend:**
1. Navigate to the `Backend/` directory.
2. Ensure you have `uv` installed (`pip install uv`).
3. Install dependencies: `uv pip install --system -r requirements.txt` (or via `pyproject.toml`).
4. Run tests: `pytest tests/`

**Frontend:**
1. Navigate to the `frontend/litellm-dashboard/` directory.
2. Install dependencies: `npm install`
3. Start the dev server: `npm run dev`

## Adding New Code

- All new backend logic must be placed inside the `Backend/` directory. Ensure any new modules or functions include proper Python docstrings.
- All new frontend components and hooks must be placed inside `frontend/` and documented using JSDoc.
- Maintain the strict separation: the frontend must only interact with the backend via the exposed REST API. Do not introduce shared code or cross-imports between the two domains.
