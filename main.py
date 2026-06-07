#!/usr/bin/env python3
"""
Kali MSN Agent - Retro MSN Messenger UI for full-control Kali Linux AI agent.
Connects to remote Ollama (jarvis:latest) on 165.22.112.6:11434
"""

import os
import sys
import threading
import queue
import json
from pathlib import Path

# Add current dir to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from agent_core import KaliAgent, OLLAMA_HOST, MODEL_NAME
from msn_ui import MSNMainWindow

def main():
    print("=" * 60)
    print("Kali MSN Agent - Starting")
    print(f"  Ollama: {OLLAMA_HOST}")
    print(f"  Model : {MODEL_NAME}")
    print("=" * 60)

    # Quick connectivity check (non-blocking for UX)
    try:
        import requests
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=4)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            print(f"[OK] Connected to Ollama. Available models: {models}")
            if "jarvis:latest" not in models and not any("jarvis" in m for m in models):
                print("[WARN] 'jarvis:latest' not listed. Will try anyway.")
        else:
            print(f"[WARN] Ollama responded {r.status_code}")
    except Exception as e:
        print(f"[WARN] Could not reach Ollama at {OLLAMA_HOST}: {e}")
        print("       The app will still launch. Check connection from the UI.")

    # Launch the retro MSN UI
    app = MSNMainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()
