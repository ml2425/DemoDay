#!/usr/bin/env python3
"""
Creates or updates configs/config.yaml with safe defaults.
Prompts for overrides; [Enter] accepts default.
>3 rps to NCBI requires an API key.
"""
import os
import shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

DEFAULTS = {
    "ncbi": {
        "email": "${NCBI_EMAIL}",
        "api_key": "${NCBI_API_KEY}",
        "rate_limit_rps": 6,
        "max_retries": 3,
        "backoff_seconds": [0.5, 1, 2, 4]
    },
    "llm": {
        "provider": "openai",
        "canonicalizer_model": "gpt-4o-mini",
        "verifier_model": "gpt-4o-mini",
        "mcq_generator_model": "gpt-4o",
        "temperature": 0
    },
    "limits": {
        "llm_verify_max_calls_per_doc": 50,
        "max_triples_per_doc": 30,
        "min_triples_per_doc": 3
    },
    "validation": {
        "min_confidence": 0.6,
        "max_evidence_sentences": 3
    },
    "features": {
        "extract_microbe": False,
        "dry_run": False
    },
    "providers": {
        "openai_api_key": "${OPENAI_API_KEY}",
        "langsmith_api_key": "${LANGSMITH_API_KEY}",
        "cohere_api_key": "${COHERE_API_KEY}",
        "claude_api_key": "${CLAUDE_API_KEY}",
        "tavily_api_key": "${TAVILY_API_KEY}"
    },
    "pricing": {
        "openai": {
            "gpt-4o-mini": {
                "input_per_1k": 0.00015,
                "output_per_1k": 0.0006
            },
            "gpt-4o": {
                "input_per_1k": 0.0025,
                "output_per_1k": 0.01
            }
        }
    }
}

def prompt(section, key, default):
    val = input(f"{section}.{key} [{default}]: ").strip()
    if val == "":
        return default
    try:
        if isinstance(default, bool):
            return val.lower() in ("1","true","yes","y","on")
        if isinstance(default, int):
            return int(val)
        if isinstance(default, float):
            return float(val)
        if isinstance(default, list):
            return [x.strip() for x in val.split(",")]
        return val
    except Exception:
        print(f"⚠️ Invalid input for {section}.{key}; keeping default {default}")
        return default

def main():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {}

    print("⚙️ DemoDay config setup (press Enter for defaults)\n")
    for section, params in DEFAULTS.items():
        config[section] = {}
        for key, default in params.items():
            config[section][key] = prompt(section, key, default)

    if CONFIG_PATH.exists():
        backup = CONFIG_PATH.with_suffix(".yaml.bak")
        shutil.copyfile(CONFIG_PATH, backup)
        print(f"🗂️  Backed up existing config to {backup}")

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    print(f"✅ Saved configuration to {CONFIG_PATH}")

if __name__ == "__main__":
    main()
