from fastapi import FastAPI

from nexusquant_risk.config import settings

app = FastAPI(title=settings.service_name)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ok"}
