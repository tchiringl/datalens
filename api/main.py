from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import sources, pipelines, dq, cdm, health, mock

app = FastAPI(
    title="Data Lens API",
    description="Retail AI Data Lens - Backend API Gateway",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(sources.router, prefix="/api/sources", tags=["Sources"])
app.include_router(pipelines.router, prefix="/api/pipelines", tags=["Pipelines"])
app.include_router(dq.router, prefix="/api/dq", tags=["Data Quality"])
app.include_router(cdm.router, prefix="/api/cdm", tags=["CDM"])
app.include_router(mock.router, prefix="/mock", tags=["Mock Data"])
