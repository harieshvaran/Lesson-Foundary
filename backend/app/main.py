"""FastAPI Application Entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

from backend.app.core.config import settings
from backend.app.core.exceptions import LessonFoundryException
from backend.app.db.base import Base
from backend.app.db.session import engine
# Import models so Base.metadata knows about them
import backend.app.db.models  # noqa: F401
from backend.app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database tables are created
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# Mount API v1 router under /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(LessonFoundryException)
async def lesson_foundry_exception_handler(request: Request, exc: LessonFoundryException):
    return JSONResponse(
        status_code=400,
        content={
            "error_code": exc.__class__.__name__,
            "message": exc.message,
            "recoverable": True,
            "details": exc.details,
        },
    )


if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
