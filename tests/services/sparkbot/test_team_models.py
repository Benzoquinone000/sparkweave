from pathlib import Path

from sparkweave.services import sparkbot as sparkbot_module
from sparkweave.services.sparkbot_support.team_models import (
    SparkBotTeamMail,
    SparkBotTeamMember,
    SparkBotTeamRuntime,
    SparkBotTeamState,
    SparkBotTeamTask,
)


def test_sparkbot_reexports_team_models_for_compatibility():
    assert sparkbot_module.SparkBotTeamTask is SparkBotTeamTask
    assert sparkbot_module.SparkBotTeamState is SparkBotTeamState
    assert sparkbot_module.SparkBotTeamRuntime is SparkBotTeamRuntime


def test_team_task_from_json_normalizes_legacy_tool_fields():
    task = SparkBotTeamTask.from_json(
        {
            "id": "t1",
            "title": "Research",
            "owner": "researcher",
            "depends_on": ["t0", 2],
            "tool": "web_search",
            "tool_args": {"query": "SparkWeave"},
            "tool_results": "not-a-list",
            "artifacts": [{"path": "report.md"}, "skip"],
            "lastError": "previous failure",
        }
    )

    assert task.depends_on == ["t0", "2"]
    assert task.tool_calls == [{"name": "web_search", "arguments": {"query": "SparkWeave"}}]
    assert task.tool_results == []
    assert task.artifacts == [{"path": "report.md"}]
    assert task.last_error == "previous failure"


def test_team_state_mail_and_runtime_helpers(tmp_path: Path):
    state = SparkBotTeamState.from_json(
        {
            "teamId": "team-a",
            "runId": "run-a",
            "members": [{"name": "builder", "role": "implementation"}],
            "sessionKey": "telegram:42",
        }
    )
    mail = SparkBotTeamMail.from_json(
        {"fromAgent": "lead", "toAgent": "builder", "content": "please continue"}
    )
    runtime = SparkBotTeamRuntime(
        session_key=state.session_key,
        run_dir=tmp_path,
        state=state,
    )

    assert state.members == [SparkBotTeamMember(name="builder", role="implementation")]
    assert state.session_key == "telegram:42"
    assert mail.from_agent == "lead"
    assert mail.to_agent == "builder"
    assert runtime.config_path == tmp_path / "config.json"
    assert runtime.tasks_path == tmp_path / "tasks.json"
    assert runtime.events_path == tmp_path / "events.jsonl"
    assert runtime.mailbox_path == tmp_path / "mailbox.jsonl"
