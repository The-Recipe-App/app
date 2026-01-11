from app.lifespan import lifespan
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.router import v1_router
from security.firewall.session import FirewallSession

app = FastAPI(
    lifespan=lifespan,
    title="My API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://forkit.up.railway.app"],  # exact frontend origin
    allow_credentials=True,                   # 🔴 REQUIRED
    allow_methods=["*"],
    allow_headers=["*"],
)

FirewallSession(app).initialize()

# ---- ROUTERS ----
app.include_router(v1_router, prefix="/api")

# ---- HEALTH / ROOT ----
@app.get("/")
async def root():
    return {"message": "Hello World"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)