# Текущие задачи (Очистка от неактуальных артефактов)
- [x] Удалить файлы правил: `.semgrep/rules/python/reliability/unbounded-memory.yml`, `.semgrep/rules/python/unbounded-memory.yml`, `.semgrep/rules/security/no-claude-directory.yml`
- [ ] Удалить оставшиеся файлы и директорию: `.semgrep`
- [ ] Удалить директории: `.circleci`, `.devcontainer`, `litellm-proxy-extras`, `packaging`.
- [ ] Проверить и удалить связанные файлы конфигурации (например, скрипты `QA` и `ruff/pyright` бюджеты, если они больше не нужны, но начать с четко указанных артефактов).
- [ ] Убедиться, что сборка Backend не требует `litellm-proxy-extras` в `pyproject.toml` (если оно там было).
