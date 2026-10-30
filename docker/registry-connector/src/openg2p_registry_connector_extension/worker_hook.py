"""Register the re-drive task and its beat entry on the connector's Celery app."""

from . import requeue

_MARK = "_openg2p_registry_connector_extension_redrive"


def install(worker) -> None:
    app = worker.celery_app
    if getattr(app, _MARK, False):
        return
    setattr(app, _MARK, True)

    @app.task(name=requeue.TASK_NAME)
    def redrive_unsigned() -> dict:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(worker.get_engine(), expire_on_commit=False)
        return worker._run_async(requeue.redrive(factory, worker.IngestionService()))

    schedule = dict(app.conf.beat_schedule or {})
    schedule["oan-redrive-unsigned"] = {"task": requeue.TASK_NAME, "schedule": requeue.INTERVAL_SECONDS}
    app.conf.beat_schedule = schedule
