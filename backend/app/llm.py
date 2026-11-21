"""OpenRouter chat model (OpenAI-compatible)."""
from functools import lru_cache
from langchain_openai import ChatOpenAI
from . import config


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.1, max_tokens: int = 1500) -> ChatOpenAI:
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
    return ChatOpenAI(
        model=config.OPENROUTER_MODEL, api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE, temperature=temperature,
        max_tokens=max_tokens, timeout=90, max_retries=2,
    )


def complete(system: str, user: str, **kw) -> str:
    from langchain_core.messages import SystemMessage, HumanMessage
    r = get_llm(**kw).invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return r.content if isinstance(r.content, str) else "".join(
        p.get("text", "") for p in r.content if isinstance(p, dict))
