"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eufy_security_agents.core.config import get_settings

from .dependencies import repository
from .routes import router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Evidence-grounded multi-agent backend that forecasts future eufy Security "
            "opportunities, generates multiple products, supports human selection, and creates "
            "a standard ProductSpec for the later validation phase."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)
    app.state.recovered_interrupted_runs = repository.recover_interrupted_runs()
    app.state.recovered_interrupted_validation_projects = (
        repository.recover_interrupted_validation_projects()
    )
    return app
