# План реструктуризации тестов (Шаг 1 из N)

- [ ] Удалить `tests/e2e`. (Удалены: models.py, proxy_client.py, transport.py, conftest.py, pytest.ini, e2e_config.py, e2e_db.py, e2e_http.py, junit_properties.py, lifecycle.py, test_azure_openai.py, test_azure.py, test_bedrock_converse.py, test_anthropic.py, test_bedrock_invoke.py, test_block_code_execution_guardrail_e2e.py, test_team_disable_global_guardrail_e2e.py, test_apply_guardrail_e2e.py, guardrails/conftest.py, test_presidio_guardrail_e2e.py, guardrails/test_bedrock_guardrail_e2e.py, guardrails/guardrails_client.py, guardrails/test_openai_moderation_guardrail_e2e.py, management/test_model_tag_accessgroup_e2e.py, management/test_key_management_e2e.py, management/test_management_e2e.py, management/test_team_management_e2e.py, CLAUDE.md, CONTRIBUTING.md, a2a/a2a_client.py, a2a/test_a2a_agent_e2e.py, a2a/conftest.py)
- [ ] Удалить `tests/integration`.
- [ ] Удалить `tests/multi_instance_e2e_tests`.
- [ ] Удалить `tests/proxy_e2e_anthropic_messages_tests`.
