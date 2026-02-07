"""Cross-platform uvicorn launcher.

On Windows, psycopg (used by LangGraph AsyncPostgresSaver) cannot run under
the default ProactorEventLoop.  This script switches to SelectorEventLoop
*before* uvicorn has a chance to create its own loop, then starts uvicorn
programmatically.

Usage:
    python run.py              # development (reload enabled)
    python run.py --no-reload  # production-like
"""

import asyncio
import sys

# Must be set BEFORE any event loop is created
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402

if __name__ == "__main__":
    reload = "--no-reload" not in sys.argv
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload,
    )
