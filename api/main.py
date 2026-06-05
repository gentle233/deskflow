"""DeskFlow - FastAPI application entry point"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

from main import init_deskflow

app = FastAPI(title="DeskFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:7788"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# Import all route modules
from api.routes import chat, autolearn, config_routes, email_routes, logs, monitor, tasks, shortcuts

app.include_router(chat.router)
app.include_router(autolearn.router)
app.include_router(config_routes.router)
app.include_router(email_routes.router)
app.include_router(logs.router)
app.include_router(monitor.router)
app.include_router(tasks.router)
app.include_router(shortcuts.router)

@app.on_event("startup")
async def startup():
    init_deskflow()

static_dir = os.path.join(PROJECT_DIR, "ui", "static")
vue_dist = os.path.join(PROJECT_DIR, "frontend", "dist")
vue_index = os.path.join(vue_dist, "index.html")

# If Vue build exists, serve it; otherwise fall back to old HTML templates
USE_VUE = os.path.exists(vue_index)

if USE_VUE:
    app.mount("/", StaticFiles(directory=vue_dist, html=True), name="frontend")
else:
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/settings")
    async def settings_page():
        with open(os.path.join(PROJECT_DIR, "ui", "templates", "settings.html")) as f:
            return HTMLResponse(f.read())

    @app.get("/")
    async def index():
        from core.config import load_config
        config = load_config()
        template = "setup.html" if config.get("first_run") else "chat.html"
        with open(os.path.join(PROJECT_DIR, "ui", "templates", template)) as f:
            return HTMLResponse(f.read())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7788)
