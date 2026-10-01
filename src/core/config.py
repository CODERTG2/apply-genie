"""
Centralized configuration for the apply-genie pipeline.
All paths, model names, and settings in one place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Directory Paths ──────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
TMP_DIR = PROJECT_ROOT / ".tmp"
TMP_DIR.mkdir(exist_ok=True)

# ── Data Files ───────────────────────────────────────────────────
SCHEMA_PATH = DATA_DIR / "attribute_schema.json"
ENTITY_DB_PATH = DATA_DIR / "entity_db.json"

# ── Runtime Files (in .tmp/) ────────────────────────────────────
SCHOLARSHIPS_PATH = TMP_DIR / "current_scholarships.json"
CLASSIFICATIONS_PATH = TMP_DIR / "dry_run_classifications.json"
PIPELINE_STATE_PATH = TMP_DIR / "pipeline_state.json"

# ── API Keys ─────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI", "")

# ── LM Studio (local LLM) ───────────────────────────────────────
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio") # it doesn't matter what this is.

# ── LM Studio / Local LLMs used ───────────────────────────────────
FILTER_MODEL = "google/gemma-4-12b"
DATE_MODEL = "meta-llama-3.1-8b-instruct"
REPHRASER_MODEL = "meta-llama-3.1-8b-instruct"

# ── Gemini (cloud LLM) ──────────────────────────────────────────
GEMINI_CLASSIFY_MODEL = "gemini-3.5-flash-lite"

# ── Turso Database ───────────────────────────────────────────────
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# ── Pipeline Settings ────────────────────────────────────────────
CLASSIFY_CONCURRENCY = 5
CURRENT_YEAR = datetime.now().year
