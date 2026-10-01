"""Loads settings from .env and the YAML files in config/.

Why a separate file: every other module asks this one for settings,
so there is exactly one place that knows where things live.
"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Project root = the folder that contains this "core" folder.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

# Read .env (if it exists) into environment variables. Missing .env is fine.
load_dotenv(ROOT / ".env")


def db_path() -> Path:
    """Where the SQLite database file lives. Relative paths are from the project root."""
    path = Path(os.getenv("DB_PATH") or "data/jobs.db")
    return path if path.is_absolute() else ROOT / path


def load_yaml(name: str) -> dict:
    """Read config/<name>. For answers.yaml, fall back to the example file."""
    path = CONFIG_DIR / name
    if not path.exists() and name == "answers.yaml":
        path = CONFIG_DIR / "answers.example.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
