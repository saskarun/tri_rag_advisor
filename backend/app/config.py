"""Environment settings and runtime-editable hyperparameters."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
load_dotenv(ROOT / ".env")
load_dotenv(BACKEND / ".env")

STORAGE = BACKEND / "storage"
SAMPLES = BACKEND / "data" / "samples"
STORAGE.mkdir(exist_ok=True, parents=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-5.5")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-large-en-v1.5")
GRAPH_BACKEND = os.getenv("GRAPH_BACKEND", "networkx")

# Hyperparameters (spec section 4). Mutable at runtime through /api/config.
HYPERPARAMS = {
    "chunk_size": 600,   # tokens
    "chunk_overlap": 60,  # tokens
    "hyde_n": 3,         # synthetic passages
    "hop_radius": 2,     # graph traversal k
    "rrf_alpha": 60,     # RRF constant
    "top_k": 3,          # final chunks sent to the LLM
}
