#!/usr/bin/env python3
"""
Creates .env in repo root with all required / optional API keys.
Keys may be left blank by pressing Enter.
Adds .env to .gitignore automatically.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
GITIGNORE_PATH = ROOT / ".gitignore"

FIELDS = [
    ("OPENAI_API_KEY",      "Enter your OpenAI API key (sk-...)"),
    ("LANGSMITH_API_KEY",   "Enter your LangSmith API key"),
    ("COHERE_API_KEY",      "Enter your Cohere API key"),
    ("CLAUDE_API_KEY",      "Enter your Anthropic/Claude API key"),
    ("TAVILY_API_KEY",      "Enter your Tavily API key"),
    ("NCBI_API_KEY",        "Enter your NCBI API key"),
    ("NCBI_EMAIL",          "Enter the NCBI-registered email address")
]

def main():
    print("🔐 DemoDay secrets setup (press Enter to leave blank)")
    env_lines = []
    for key, prompt in FIELDS:
        val = input(f"{prompt}: ").strip()
        env_lines.append(f"{key}={val}")

    ENV_PATH.write_text("\n".join(env_lines) + "\n")
    print(f"✅ Wrote {ENV_PATH}")

    if GITIGNORE_PATH.exists():
        gi = GITIGNORE_PATH.read_text()
    else:
        gi = ""
    if ".env" not in gi:
        with GITIGNORE_PATH.open("a", encoding="utf-8") as f:
            if gi and not gi.endswith("\n"):
                f.write("\n")
            f.write(".env\n")
        print("✅ Added .env to .gitignore")

if __name__ == "__main__":
    main()
