#!/usr/bin/env python3
"""Test your OpenRouter API key with a free model.

Usage:
    python scripts/test_openrouter_key.py YOUR_API_KEY [model_id]

Default model: google/gemma-4-26b-a4b-it:free
"""

import sys
import os

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")  # <-- Paste your OpenRouter API key here, or pass as argument
MODEL = "google/gemma-4-26b-a4b-it:free"

if not API_KEY:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        API_KEY = args[0]
    if len(args) > 1:
        MODEL = args[1]

if not API_KEY:
    print("Usage: python scripts/test_openrouter_key.py YOUR_API_KEY [model_id]")
    print("   Or edit API_KEY in the script and run it directly.")
    sys.exit(1)

from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

try:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
        timeout=30,
    )
    print("Model:", MODEL)
    print("Response:", resp.choices[0].message.content)
    print("\nYour OpenRouter key works!")
except Exception as e:
    print("Error:", e)
