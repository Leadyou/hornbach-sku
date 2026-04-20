#!/usr/bin/env bash
# Wystawia lokalną aplikację (port 8000) pod publicznym adresem HTTPS.
# Wymaga: wcześniej uruchomiony uvicorn na porcie 8000.
set -euo pipefail
PORT="${1:-8000}"
echo "Tunel na port $PORT — uruchomiona musi być aplikacja (uvicorn)."
echo "Adres wyświetli się poniżej; wyślij go znajomemu."
exec npx --yes localtunnel --port "$PORT"
