<h1 align="center">
  <br>
  <a href="https://litellm.ai"><img src="https://raw.githubusercontent.com/BerriAI/litellm/main/docs/my-website/static/img/litellm_logo.png" alt="LiteLLM" width="30%"></a>
  <br>
  LiteLLM
  <br>
</h1>

<h4 align="center">Call 100+ LLM APIs using the OpenAI format - Bedrock, Azure, OpenAI, Cohere, Anthropic, Ollama, Sagemaker, HuggingFace, Replicate</h4>

<p align="center">
  <a href="https://github.com/BerriAI/litellm/actions/workflows/main.yml">
    <img src="https://github.com/BerriAI/litellm/actions/workflows/main.yml/badge.svg" alt="CI">
  </a>
  <a href="https://pypi.org/project/litellm/">
    <img src="https://img.shields.io/pypi/v/litellm" alt="PyPI Version">
  </a>
</p>

## Architecture
LiteLLM is split into two parts:
- `Backend`: Python backend, providing the core LiteLLM routing, proxy logic, and integrations.
- `frontend`: NextJS dashboard to manage the backend.

## Quick Start
To start the backend and frontend locally:
1. Navigate to the backend:
`cd Backend`
2. Install dependencies:
`uv sync`
3. Run the backend proxy:
`uv run litellm --config config.yaml`

4. For the frontend:
`cd frontend/litellm-dashboard`
`npm install`
`npm run dev`

## Contribution
Check out `todo.md` for our ongoing migration checklist and development tasks.
