"""
Punkt wejścia dla Vercel: instancja FastAPI musi nazywać się `app` w pliku `main.py` w katalogu głównym.
Lokalnie: `uvicorn main:app` lub `uvicorn app.main:app`.
"""
from app.main import app

__all__ = ["app"]
