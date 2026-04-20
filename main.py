"""
Punkt wejścia dla Vercel: instancja FastAPI musi nazywać się `app` w pliku `main.py` w katalogu głównym.
Lokalnie: `uvicorn main:app` lub `uvicorn backend.main:app`.
"""
from backend.main import app

__all__ = ["app"]
