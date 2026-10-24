"""Loaded by native run_celery.py CELERY_IMPORTS in worker and beat processes."""
import asyncio
from celery import current_app, shared_task
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from .runtime import install
from .workflow import dispatch_pending

install()


@shared_task(name="coss.farmer_reference.deliver_workflows")
def deliver_workflows():
    async def run():
        from openg2p_registry_celery_worker.engine import Engine
        # The native worker owns a different engine from fastapi-common. Keep
        # this extension task's short-lived loop from reusing either loop's pool.
        engine = create_async_engine(Engine.construct_async_db_datasource(), poolclass=NullPool)
        try:
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions.begin() as session:
                return await dispatch_pending(session)
        finally:
            await engine.dispose()
    return asyncio.run(run())


current_app.conf.beat_schedule = {
    **(current_app.conf.beat_schedule or {}),
    "coss-farmer-reference-workflows": {"task": "coss.farmer_reference.deliver_workflows", "schedule": 30.0},
}
