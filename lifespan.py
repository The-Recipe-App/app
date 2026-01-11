from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from utilities.common.common_utility import debug_print
from utilities.helpers.task_manager.manager import task_manager, TaskType

from database.security.init_db import init_db as init_security_db
from database.security.session import engine as security_engine

from database.main.core.session import engine as main_engine
import time
from app.startup_timer import PROCESS_BOOT_TS, STARTUP_TIME_MS

background_task: asyncio.Task | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        debug_print("Starting Task Manager...", color="cyan")
        await task_manager.start()

        debug_print("Initializing security system...", color="cyan")
        await init_security_db()   # BLOCKING, guaranteed complete

        debug_print("Lifespan startup complete. Security online.", color="green")
        globals()["STARTUP_TIME_MS"] = (time.perf_counter() - PROCESS_BOOT_TS) * 1000
        debug_print(f"Startup Time: {STARTUP_TIME_MS:.2f} ms", color="green")
        yield

    finally:
        debug_print("Closing Task Manager...", color="cyan")
        await task_manager.shutdown()

        debug_print("Disposing DB engines...", color="cyan")
        await security_engine.dispose()
        await main_engine.dispose()

        debug_print("Done! Goodbye!", color="cyan")

