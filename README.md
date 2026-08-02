# LiteLLM Offline OpenAI Gateway

This project is a customized, offline-first branch of [LiteLLM](https://github.com/BerriAI/litellm). It has been stripped of external SaaS integrations, telemetry, and non-essential features (like RAG and Semantic Caching) to serve as a secure, isolated OpenAI-compatible Gateway for internal enterprise deployments.

## Architecture

The project consists of two main components separated for independent scaling:

1.  **Backend (Python)**: A lightweight API gateway built on FastAPI that handles routing, rate limiting (Redis), budget management (PostgreSQL), and exact-match caching. It connects exclusively to your internal or custom endpoints (`api_base`).
2.  **Frontend (Next.js)**: A dashboard (`ui/litellm-dashboard`) for managing users, keys, and budgets, completely decoupled from the backend codebase and communicating strictly via REST API.

## Features Kept
- **OpenAI Provider Support**: Fully supports custom `api_base` targets.
- **Routing & Fallbacks**: Supports advanced load balancing and fallback mechanisms across internal nodes.
- **Auth & Budgets**: RBAC, API key generation, and budget limits relying purely on local PostgreSQL and Redis.
- **Caching**: Exact-match caching using a local Redis instance.
- **Monitoring**: Local `/metrics` endpoint for Prometheus.

## Running Locally

You can launch the entire stack using `docker-compose`:

```bash
docker-compose up -d
```

This will spin up:
-   `litellm`: The Python API Gateway (Port: 4000)
-   `frontend`: The Next.js Admin Dashboard (Port: 3000)
-   `db`: PostgreSQL database for accounts and keys
-   `redis`: Redis cache for rate limiting and exact matching

