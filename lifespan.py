from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from utilities.common.common_utility import debug_print
from utilities.helpers.task_manager.manager import task_manager, TaskType

from database.security.bootstrap.init_db import bootstrap_security_db
from database.security.core.session import engine as security_engine

from database.main.core.session import engine as main_engine, AsyncSessionLocal, prewarm_pool as prewarm_main_pool
from sqlalchemy import select

from database.main.core.models import User
from database.main.counter_aggregator import aggregate_once
from app.username_index import username_index
import time
from database.main.core.bootstrap.init_db import bootstrap_main_db
from database.security.core.session import prewarm_pool as prewarm_security_pool
from app.tools.seed_policies import ensure_legal_policies
from app.startup_timer import PROCESS_BOOT_TS, STARTUP_TIME_MS

background_task: asyncio.Task | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.main_db_prewarm_done = asyncio.Event()
    app.state.security_db_prewarm_done = asyncio.Event()

    try:
        debug_print("Starting Task Manager...", color="cyan")
        await task_manager.start()

        # -------------------------------
        # STAGE 1 — STRICTLY AWAIT DB BOOTSTRAP
        # -------------------------------
        debug_print("Bootstrapping databases...", color="cyan")

        main_bootstrap_task = asyncio.create_task(bootstrap_main_db())
        security_bootstrap_task = asyncio.create_task(bootstrap_security_db())

        await asyncio.gather(
            main_bootstrap_task,
            security_bootstrap_task,
        )
        debug_print("Database bootstrapping complete.", color="green")
        
        # -------------------------------
        # STAGE 2 — PREWARM IN PARALLEL
        # -------------------------------
        debug_print("Starting DB prewarm tasks...", color="cyan")

        prewarm_main_task = asyncio.create_task(
            prewarm_main_pool(app.state.main_db_prewarm_done)
        )

        prewarm_security_task = asyncio.create_task(
            prewarm_security_pool(app.state.security_db_prewarm_done)
        )

        # -------------------------------
        # STAGE 3 — MAIN DB DEPENDENT WORK
        # (can run while pools warming)
        # -------------------------------
        debug_print("Initializing baseline policies & username index...", color="cyan")

        async def init_username_index():
            async with AsyncSessionLocal() as session:
                result = await session.scalars(select(User.username))
                username_index.load(result.all())
            debug_print("Username index initialized.", color="green")

        policies_task = asyncio.create_task(ensure_legal_policies())
        index_task = asyncio.create_task(init_username_index())

        # Wait for BOTH main-db dependent tasks to finish
        await asyncio.gather(policies_task, index_task)

        # -------------------------------
        # STAGE 4 — WAIT FOR FULL PREWARM
        # (Cloud DB slow-connect safe)
        # -------------------------------
        debug_print("Waiting for full DB prewarm completion...", color="cyan")

        await asyncio.gather(
            app.state.main_db_prewarm_done.wait(),
            app.state.security_db_prewarm_done.wait(),
        )

        # Ensure background tasks didn’t silently fail
        await asyncio.gather(prewarm_main_task, prewarm_security_task)
        
        debug_print("Starting counter aggregator...", color="cyan")
        await task_manager.add_recurring(
            aggregate_once,
            interval_seconds=60,
            name="counter_aggregator",
            start_immediately=True,
            debug=False,
        )

        # -------------------------------
        # STARTUP COMPLETE
        # -------------------------------
        globals()["STARTUP_TIME_MS"] = (time.perf_counter() - PROCESS_BOOT_TS) * 1000

        debug_print("Lifespan startup complete. Security online.", color="green")
        debug_print(f"Startup Time: {STARTUP_TIME_MS:.2f} ms", color="green")

        yield

    except Exception as e:
        debug_print(f"Error during lifespan startup: {e}", color="red")
        raise e

    finally:
        debug_print("Closing Task Manager...", color="cyan")
        await task_manager.shutdown()

        debug_print("Disposing DB engines...", color="cyan")
        await security_engine.dispose()
        await main_engine.dispose()

        debug_print("Done! Goodbye!", color="cyan")
