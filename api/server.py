"""FastAPI server — serves Mini App + REST API for bot."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes.webapp_api import router as webapp_router
from api.routes.health import router as health_router

app = FastAPI(title="PayPal Credit Agent API")

# API routes
app.include_router(health_router, prefix="/api")
app.include_router(webapp_router, prefix="/api")

# Serve Mini App static files
app.mount("/static", StaticFiles(directory="webapp"), name="static")


@app.get("/")
async def root():
    return FileResponse("webapp/index.html")


@app.get("/webapp")
async def webapp():
    return FileResponse("webapp/index.html")
