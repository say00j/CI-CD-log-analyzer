"""
llm.py

Handles communication with a remote Ollama LLM server
running on another machine (accessed via Tailscale or LAN).
"""

import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv("backend\.env")

# Load LLM endpoint from environment (DO NOT hardcode IPs)
LLM_URL = os.getenv("LLM_URL")  # e.g. http://100.x.x.x:11434/api/generate
LLM_MODEL = os.getenv("LLM_MODEL")


if not LLM_URL:
    raise RuntimeError("LLM_URL is not set. Add it to your environment or .env file.")
    

def run_llm(prompt: str, timeout: int = 120) -> str:
    """
    Sends a prompt to the remote LLM server and returns the response text.
    """
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(
            LLM_URL,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.RequestException as e:
        return f"[LLM ERROR] Failed to contact LLM server: {e}"
