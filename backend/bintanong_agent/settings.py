"""Hosted-model selection from environment variables; the API key never appears in repr."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

Provider = Literal['deepseek', 'openai', 'gemini', 'anthropic']

# Official defaults as read on 15 Nov 2026; OpenAI has none, so its model must be chosen.
DEFAULT_MODELS = {'deepseek': 'deepseek-flash', 'openai': None,
                  'gemini': 'gemini-3.8-flash', 'anthropic': 'claude-haiku-5-5'}
API_KEY_VARIABLES = {'deepseek': 'DEEPSEEK_API_KEY', 'openai': 'OPENAI_API_KEY',
                     'gemini': 'GEMINI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY'}


@dataclass(frozen=True)
class AgentSettings:
    provider: Provider
    model: str
    api_key: str = field(repr=False)
    thinking: bool = False  # provider-side reasoning; off unless chosen, since its tokens bill as output

    @classmethod
    def from_env(cls, env=os.environ) -> 'AgentSettings':
        provider = env.get('BINTANONG_LLM_PROVIDER', '').strip().lower() or 'deepseek'
        if provider not in DEFAULT_MODELS:
            raise ValueError('llm_provider_invalid')
        api_key = env.get(API_KEY_VARIABLES[provider], '').strip()
        if not api_key:
            raise ValueError('llm_api_key_required')
        model = env.get('BINTANONG_LLM_MODEL', '').strip() or DEFAULT_MODELS[provider]
        if not model:
            raise ValueError('llm_model_required')
        return cls(provider, model, api_key, env.get('BINTANONG_LLM_THINKING', '').strip() == '1')
