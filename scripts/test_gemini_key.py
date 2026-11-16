#!/usr/bin/env python3
"""Test your Google Gemini API key.

Usage:
    python scripts/test_gemini_key.py YOUR_API_KEY

Or edit the API_KEY below and run:
    python scripts/test_gemini_key.py
"""

import sys
import os

API_KEY = ""  # <-- Paste your API key here, or pass as argument

if not API_KEY:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        API_KEY = args[0]

if not API_KEY:
    print("Usage: python scripts/test_gemini_key.py YOUR_API_KEY")
    print("   Or edit API_KEY in the script and run it directly.")
    sys.exit(1)

os.environ["GOOGLE_API_KEY"] = API_KEY

import google.generativeai as genai

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")
resp = model.generate_content("Say hello in one short sentence.")
print("Response:", resp.text)
print("\nYour Gemini API key works!")
