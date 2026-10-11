# LiteLLM Offline OpenAI Gateway

This project is a customized, offline-first branch of [LiteLLM](https://github.com/BerriAI/litellm). It has been stripped of external SaaS integrations, telemetry, and non-essential features (like RAG and Semantic Caching) to serve as a secure, isolated OpenAI-compatible Gateway for internal enterprise deployments.

## Architecture

The project consists of two main components separated for independent scaling:

1.  **Backend (Python)**: Located in the `Backend/` directory. A lightweight API gateway built on FastAPI that handles routing, rate limiting (Redis), budget management (PostgreSQL), and exact-match caching. It connects exclusively to your internal or custom endpoints (`api_base`).
2.  **Frontend (Next.js)**: Located in the `frontend/` directory. A dashboard for managing users, keys, and budgets, completely decoupled from the backend codebase and communicating strictly via REST API.

## Features Kept
- **OpenAI Provider Support**: Fully supports custom `api_base` targets.
- **Routing & Fallbacks**: Supports advanced load balancing and fallback mechanisms across internal nodes.
- **Auth & Budgets**: RBAC, API key generation, and budget limits relying purely on local PostgreSQL and Redis.
- **Caching**: Exact-match caching using a local Redis instance.
- **Monitoring**: Local `/metrics` endpoint for Prometheus.

## Running Locally

### Prerequisites
Ensure you have Docker and Docker Compose installed. You should also create a `.env` file from the provided `.env.example` file.

### Deployment
You can launch the entire stack using `docker-compose`:

```bash
docker-compose up -d --build
```

This will build the images and spin up the following services (as defined in `docker-compose.yml`):
-   `backend`: The Python API Gateway (Port: 4000)
-   `frontend`: The Next.js Admin Dashboard (Port: 3000)
-   `db`: PostgreSQL database for accounts and keys
-   `redis`: Redis cache for rate limiting and exact matching

To view the logs:
```bash
docker-compose logs -f
```

To stop the stack:
```bash
docker-compose down
```

## Adding New Code

To contribute new features or fixes, please follow these guidelines:
1. **Backend**: Add new Python code to the `Backend/` directory. Ensure it aligns with the strict offline architecture (no external SaaS telemetry or dependencies). Follow the existing type hints and PEP-8 conventions. Run targeted unit tests when modifying backend logic.
2. **Frontend**: Add new React/Next.js code to the `frontend/` directory. Ensure the UI only communicates with the backend via REST API. Follow existing component structures and JSDoc conventions.

All changes must include relevant unit tests, pass linters, and respect the project's offline-first constraints.
