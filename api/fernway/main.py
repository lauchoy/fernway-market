from fastapi import FastAPI

from fernway.routes import health

app = FastAPI(title="Fernway Market payouts console")
app.include_router(health.router)
