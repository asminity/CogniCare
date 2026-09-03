from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="Cognicare API", version="0.1.0")
app.include_router(router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"name": "Cognicare API", "status": "ready"}