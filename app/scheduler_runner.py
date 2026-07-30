import asyncio
import logging
import os
import signal
import socket
from datetime import datetime

from app.config import settings
from app.database import SessionLocal, engine
from app.models.scheduler_state import SchedulerHeartbeat
from app.scheduler import scheduler, start_scheduler
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _update_heartbeat(owner_id: str) -> None:
    db = SessionLocal()
    try:
        heartbeat = db.query(SchedulerHeartbeat).filter(
            SchedulerHeartbeat.id == 1
        ).first()
        if heartbeat is None:
            heartbeat = SchedulerHeartbeat(id=1, owner_id=owner_id)
            db.add(heartbeat)
        heartbeat.owner_id = owner_id
        heartbeat.heartbeat_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


async def _heartbeat_loop(owner_id: str, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await asyncio.to_thread(_update_heartbeat, owner_id)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass


async def run() -> None:
    settings.validate_runtime_security()
    owner_id = f"{socket.gethostname()}:{os.getpid()}"
    lock_connection = engine.connect()
    if engine.dialect.name == "postgresql":
        acquired = lock_connection.execute(
            text("SELECT pg_try_advisory_lock(hashtext('safar_scheduler_owner'))")
        ).scalar()
        if not acquired:
            lock_connection.close()
            raise RuntimeError("Another scheduler owns the database advisory lock.")
    elif engine.dialect.name == "mysql":
        acquired = lock_connection.execute(
            text("SELECT GET_LOCK('safar_scheduler_owner', 0)")
        ).scalar()
        if acquired != 1:
            lock_connection.close()
            raise RuntimeError("Another scheduler owns the database advisory lock.")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    heartbeat_task = asyncio.create_task(_heartbeat_loop(owner_id, stop_event))
    try:
        start_scheduler()
        await stop_event.wait()
        scheduler.shutdown(wait=True)
    finally:
        stop_event.set()
        await heartbeat_task
        if engine.dialect.name == "postgresql":
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(hashtext('safar_scheduler_owner'))")
            )
        elif engine.dialect.name == "mysql":
            lock_connection.execute(
                text("SELECT RELEASE_LOCK('safar_scheduler_owner')")
            )
        lock_connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
