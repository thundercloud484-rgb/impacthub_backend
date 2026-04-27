# FIX: Silences the passlib/bcrypt 72-byte padding bug
import logging
import os

logging.getLogger("passlib").handlers = [logging.NullHandler()]

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.api.routes.auth           import router as auth_router
from app.api.routes.users          import router as users_router
from app.api.routes.posts          import router as posts_router
from app.api.routes.social         import router as social_router
from app.api.routes.events         import router as events_router
from app.api.routes.notifications import router as notif_router
from app.api.routes.admin          import router as admin_router
from app.api.routes                import chat

limiter = Limiter(key_func=get_remote_address, default_limits=["200/15minutes"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()

app = FastAPI(
    title="CivicImpact API",
    description="Social platform for public good",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [
    str(settings.FRONTEND_URL), 
    "https://impacthub-dnjr.vercel.app",
    "https://impacthub-dnjr-git-main-tanishs-projects-de6a879e.vercel.app",
    "https://impacthub-l5umgo7qy-vishal-2821s-projects.vercel.app",
    "https://impacthub-mu.vercel.app",
    "https://impacthub-dnjr-a8uiow79p-tanishs-projects-de6a879e.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route registration
app.include_router(auth_router,   prefix="/api")
app.include_router(users_router,  prefix="/api")
app.include_router(posts_router,  prefix="/api")
app.include_router(social_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(notif_router,  prefix="/api")
app.include_router(admin_router,  prefix="/api")

# FIX: Added prefix="/api" to match your frontend requests
@app.get("/api/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "CivicImpact API", "version": "3.0.0"}
