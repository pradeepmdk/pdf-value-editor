"""Request-local model selection; never shared between users or workers."""
from contextvars import ContextVar

DEFAULT_MODEL = 'openai/gpt-4.1'
MODELS = {
    DEFAULT_MODEL: 'OpenAI GPT-4.1',
    'openai/gpt-6-astra': 'OpenAI GPT-6 Astra',
    'openai/gpt-6.1-sol': 'OpenAI GPT-6.1 Sol',
    'openai/gpt-6-luna': 'OpenAI GPT-6 Luna',
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

REASONING_HEADROOM = 16000

def model_payload(payload):
    """Reasoning GPT models do not accept temperature on OpenRouter. All
    reasoning models (everything except GPT-4.1) think before answering: low
    effort keeps them fast, and extra tokens stop the thinking from using up
    the space meant for the answer."""
    result = {**payload, 'model': selected_model()}
    if selected_model().startswith('openai/gpt-6'):
        result.pop('temperature', None)
    if selected_model() != DEFAULT_MODEL:
        result.setdefault('reasoning', {'effort': 'low'})
        if 'max_tokens' in result:
            result['max_tokens'] += REASONING_HEADROOM
    return result
