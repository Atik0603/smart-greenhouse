from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from src.infrastructure.settings import settings
from src.interfaces.api.health import router as health_router

app = FastAPI(title="Smart Greenhouse API", docs_url=None)  # disable built-in Swagger /docs

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.get("/scalar", include_in_schema=False)
def scalar_docs():
    return get_scalar_api_reference(openapi_url="/openapi.json", title=app.title)