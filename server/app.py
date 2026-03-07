"""FastAPI application and entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db
from .routers import books, bookshelves, scans
from .worker import recover_pending_scans, start_worker, stop_worker

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    init_db()
    start_worker()
    recover_pending_scans()
    yield
    stop_worker()


app = FastAPI(
    title="Home Library",
    description="Track books on your shelves using photo OCR",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(books.router)
app.include_router(bookshelves.router)
app.include_router(scans.router)


@app.get("/health")
def health():
    return {"status": "ok"}


def main():
    """CLI entry point."""
    import uvicorn

    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
