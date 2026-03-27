from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401 — registers models with Base
from app.routers import auth, races, predictions, leaderboard, admin, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    if settings.scheduler_enabled:
        from app.scheduler.jobs import init_scheduler
        init_scheduler()
    yield
    # Shutdown
    if settings.scheduler_enabled:
        from app.scheduler.jobs import shutdown_scheduler
        shutdown_scheduler()


app = FastAPI(title="F1 Predict API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(races.router)
app.include_router(predictions.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)
app.include_router(users.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
