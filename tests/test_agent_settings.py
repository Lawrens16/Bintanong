import importlib

import pytest


def agent():
    return importlib.import_module('backend.bintanong_agent.settings')


def test_from_env_defaults_to_deepseek_flash():
    settings = agent().AgentSettings.from_env({'DEEPSEEK_API_KEY': 'k'})
    assert (settings.provider, settings.model, settings.api_key) == ('deepseek', 'deepseek-flash', 'k')


@pytest.mark.parametrize('provider, key_name, default_model', [
    ('openai', 'OPENAI_API_KEY', 'gpt-test'),
    ('gemini', 'GEMINI_API_KEY', 'gemini-3.8-flash'),
    ('anthropic', 'ANTHROPIC_API_KEY', 'claude-haiku-5-5'),
])
def test_from_env_selects_provider_key_and_model(provider, key_name, default_model):
    env = {'BINTANONG_LLM_PROVIDER': provider, key_name: 'k', 'DEEPSEEK_API_KEY': 'other'}
    if provider == 'openai':
        env['BINTANONG_LLM_MODEL'] = default_model
    settings = agent().AgentSettings.from_env(env)
    assert (settings.provider, settings.model, settings.api_key) == (provider, default_model, 'k')


def test_from_env_model_override():
    env = {'DEEPSEEK_API_KEY': 'k', 'BINTANONG_LLM_MODEL': 'custom'}
    assert agent().AgentSettings.from_env(env).model == 'custom'


def test_from_env_requires_key_for_selected_provider():
    with pytest.raises(ValueError, match='llm_api_key_required'):
        agent().AgentSettings.from_env({'BINTANONG_LLM_PROVIDER': 'anthropic', 'DEEPSEEK_API_KEY': 'k'})
    with pytest.raises(ValueError, match='llm_api_key_required'):
        agent().AgentSettings.from_env({'DEEPSEEK_API_KEY': '  '})


def test_from_env_openai_requires_model():
    with pytest.raises(ValueError, match='llm_model_required'):
        agent().AgentSettings.from_env({'BINTANONG_LLM_PROVIDER': 'openai', 'OPENAI_API_KEY': 'k'})


def test_from_env_rejects_unknown_provider():
    with pytest.raises(ValueError, match='llm_provider_invalid'):
        agent().AgentSettings.from_env({'BINTANONG_LLM_PROVIDER': 'other'})
