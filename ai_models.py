"""Request-local model selection; never shared between users or workers."""
from contextvars import ContextVar

DEFAULT_MODEL = 'openai/gpt-4.1'
MODELS = {
    DEFAULT_MODEL: 'OpenAI GPT-4.1',
    'openai/gpt-6-astra': 'OpenAI GPT-6 Astra',
    'openai/gpt-6.1-sol': 'OpenAI GPT-6.1 Sol',
    'openai/gpt-6-luna': 'OpenAI GPT-6 Luna',
    'google/gemini-4-argon': 'Google Gemini 4 Argon',
}
_model = ContextVar('finance_ai_model', default=DEFAULT_MODEL)

def selected_model():
    return _model.get()

def select_model(model):
    if not isinstance(model, str) or model not in MODELS:
        raise ValueError('Choose a supported AI model from the application selector.')
    return _model.set(model)

def reset_model(token):
    _model.reset(token)

def model_payload(payload):
    """Reasoning GPT models do not accept temperature on OpenRouter."""
    result = {**payload, 'model': selected_model()}
    if selected_model().startswith('openai/gpt-6'):
        result.pop('temperature', None)
    return result
