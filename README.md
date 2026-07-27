# LiteLLM Offline Gateway

A modified version of LiteLLM optimized to work as a fully offline gateway, preserving proxy capabilities such as RBAC, user management, and proxy fallbacks/load balancing solely for local OpenAI compatible server endpoints.

## Architecture

This project has been split into two independent components:
1. **Backend**: Python-based API server with Redis and PostgreSQL integration for rate limiting and data persistence.
2. **Frontend**: Next.js React Dashboard (`ui/litellm-dashboard`) for visual configuration.

## Getting Started

To run the offline gateway locally, use the provided `docker-compose.yml`:

```bash
docker-compose up --build
```

Access the frontend dashboard at `http://localhost:3000`.

## Notes
- All external API provider support (Anthropic, Gemini, Vertex, Azure, etc.) has been removed.
- SaaS integrations and Telemetry logic have been completely disabled.
- Only the standard `openai` and `custom_openai` endpoints are active.
