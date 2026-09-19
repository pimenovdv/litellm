# Текущие задачи (Очистка от неактуальных артефактов)
- [ ] Удалить файлы из .circleci: `.circleci/scripts/classify_changes.sh`, `.circleci/scripts/path_filter.sh`, `.circleci/config.yml`.
- [ ] Удалить файлы из .devcontainer и packaging: `.devcontainer/post-create.sh`, `.devcontainer/devcontainer.json`, `packaging/homebrew/lite.rb`, `packaging/homebrew/README.md`.
- [ ] Удалить файлы из .semgrep: `.semgrep/rules/security/no-claude-directory.yml`, `.semgrep/rules/python/reliability/unbounded-memory.yml`, `.semgrep/rules/python/unbounded-memory.yml`, `.semgrep/rules/README.md`.
- [ ] Удалить директорию `litellm-proxy-extras` (часть 1, 5 файлов): `litellm-proxy-extras/README.md`, `litellm-proxy-extras/__init__.py`, `litellm-proxy-extras/main.py`, `litellm-proxy-extras/requirements.txt`, `litellm-proxy-extras/setup.py`. (Будет уточняться по мере выполнения)
- [ ] Проверить и удалить связанные файлы конфигурации (например, скрипты `QA` и `ruff/pyright` бюджеты, если они больше не нужны, но начать с четко указанных артефактов).
- [ ] Убедиться, что сборка Backend не требует `litellm-proxy-extras` в `pyproject.toml` (если оно там было).
