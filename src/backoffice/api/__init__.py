"""API package exposing the deployable FastAPI application."""

from typing import Any

__all__ = ["app", "create_app"]


# lazy import, avoids circular import between src.backoffice and src.connection_aeolus_api
def __getattr__(name: str) -> Any:
    if name in {"app", "create_app"}:
        from .main import app, create_app

        return {"app": app, "create_app": create_app}[name]
    raise AttributeError(name)
