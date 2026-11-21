"""Step 3 - HuggingFace sub-word tokenization matching the embedding model."""
from functools import lru_cache
from transformers import AutoTokenizer
from .. import config

MAX_TOKENS = 512  # bge-large-en-v1.5 / MiniLM-class context limits


@lru_cache(maxsize=1)
def get_tokenizer():
    return AutoTokenizer.from_pretrained(config.EMBED_MODEL)


def count_tokens(text: str) -> int:
    return len(get_tokenizer().encode(text, add_special_tokens=False))
