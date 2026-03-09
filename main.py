from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.lifespan import lifespan
from api.v1.router import v1_router
from api.v1.admin.admin import setup_admin
from api.v1.auth.utils.dependencies import get_current_user_admin_core
from api.legal.legal import router as legal_router

from database.main.core.session import AsyncSessionLocal
from utilities.common.common_utility import debug_print

# ---------------- APP ----------------

app = FastAPI(
    lifespan=lifespan,
    title="Forkit - Core Systems Interface",
    version="1.0.0",
)

# ---------------- CORS ----------------
# Exact origins = faster preflight handling

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://forkit.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------- STATIC FILES ----------------

BASE_DIR = Path(__file__).resolve().parents[1]

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "app" / "static"),
    name="static",
)

# ---------------- ROUTERS ----------------

app.include_router(v1_router, prefix="/api")
app.include_router(legal_router, prefix="/api")

setup_admin(app)

# ---------------- ROOT ----------------

@app.get("/")
async def root():
    return {"message": "Hello World"}
