from sparkweave.services import sparkbot as sparkbot_module
from sparkweave.services.sparkbot_support.heartbeat import SparkBotHeartbeatService


def test_sparkbot_reexports_heartbeat_service_for_compatibility():
    assert sparkbot_module.SparkBotHeartbeatService is SparkBotHeartbeatService


def test_heartbeat_parsers_accept_dicts_and_embedded_json():
    assert SparkBotHeartbeatService._parse_decision(
        'Decision: {"action": "run", "tasks": "review notes"}'
    ) == {"action": "run", "tasks": "review notes"}
    assert SparkBotHeartbeatService._parse_should_notify({"should_notify": "no"}) is False
    assert (
        SparkBotHeartbeatService._parse_should_notify(
            'Gate: {"should_notify": true, "reason": "done"}'
        )
        is True
    )
