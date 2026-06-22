import pytest

from sparkweave.services import sparkbot as sparkbot_module
from sparkweave.services.sparkbot_support.cron import (
    SparkBotCronSchedule,
    SparkBotCronService,
)


def test_sparkbot_reexports_cron_support_for_compatibility():
    assert sparkbot_module.SparkBotCronSchedule is SparkBotCronSchedule
    assert sparkbot_module.SparkBotCronService is SparkBotCronService


def test_cron_service_persists_jobs_and_sorts_active_jobs(tmp_path):
    store_path = tmp_path / "cron" / "jobs.json"
    cron = SparkBotCronService(store_path=store_path)

    later = cron.add_job(
        name="later",
        schedule=SparkBotCronSchedule(kind="every", every_ms=60_000),
        message="later message",
    )
    earlier = cron.add_job(
        name="earlier",
        schedule=SparkBotCronSchedule(kind="every", every_ms=1_000),
        message="earlier message",
    )

    reloaded = SparkBotCronService(store_path=store_path)
    jobs = reloaded.list_jobs(include_disabled=True)

    assert [job.id for job in jobs] == [earlier.id, later.id]
    assert jobs[0].payload.message == "earlier message"


def test_cron_schedule_rejects_timezone_on_non_cron_schedule(tmp_path):
    cron = SparkBotCronService(store_path=tmp_path / "cron" / "jobs.json")

    with pytest.raises(ValueError, match="tz can only be used"):
        cron.add_job(
            name="bad",
            schedule=SparkBotCronSchedule(kind="every", every_ms=1_000, tz="UTC"),
            message="bad message",
        )
