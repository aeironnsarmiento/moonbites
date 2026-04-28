from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api.routes import router as extract_router
from .core.config import get_settings
from .core.rate_limit import limiter


MAX_REQUEST_BYTES = 64 * 1024


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="LD Parser API")

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def cap_body_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BYTES:
                    return JSONResponse(
                        {"detail": "Payload too large"},
                        status_code=413,
                    )
            except ValueError:
                pass
        return await call_next(request)

    app.include_router(extract_router)
    return app


app = create_app()