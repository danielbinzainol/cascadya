import uvicorn

from src.backoffice.api.main import app

__all__ = ["app"]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
