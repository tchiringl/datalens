import logging
import logging.config
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from routers import sources, pipelines, dq, cdm, health, mock

_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

logging.config.dictConfig(_LOG_CONFIG)
_log = logging.getLogger("datalens.api")

app = FastAPI(
    title="Data Lens API",
    description="Retail AI Data Lens - Backend API Gateway",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    _log.info("%s %s request_id=%s", request.method, request.url.path, request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health.router, tags=["Health"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["Pipelines"])
app.include_router(dq.router, prefix="/api/v1/dq", tags=["Data Quality"])
app.include_router(cdm.router, prefix="/api/v1/cdm", tags=["CDM"])
app.include_router(mock.router, prefix="/mock", tags=["Mock Data"])
