#!/bin/bash
# Convenience launcher
cd "$(dirname "$0")"
export OLLAMA_HOST="${OLLAMA_HOST:-http://165.22.112.6:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-jarvis:latest}"
echo "Launching Kali MSN Agent -> $OLLAMA_HOST / $OLLAMA_MODEL"
python3 main.py
