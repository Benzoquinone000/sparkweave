from __future__ import annotations

import asyncio
from email.message import EmailMessage
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

from sparkweave.core.tool_protocol import ToolResult
from sparkweave.services.sparkbot import (
    BotConfig,
    SparkBotAgentLoop,
    SparkBotCronSchedule,
    SparkBotCronService,
    SparkBotHeartbeatService,
    SparkBotInboundMessage,
    SparkBotInstance,
    SparkBotManager,
    SparkBotMessageBus,
    SparkBotOutboundMessage,
    SparkBotSkillsLoader,
    SparkBotTeamManager,
    SparkBotTeamTool,
    SparkBotTeamWorkerTool,
    mask_channel_secrets,
)
from sparkweave.sparkbot.mcp import MCPToolWrapper
from sparkweave.sparkbot.tools import WebFetchTool, build_sparkbot_agent_tool_registry
from sparkweave.sparkbot.transcription import GroqTranscriptionProvider


@pytest.fixture
def manager(tmp_path):
    mgr = SparkBotManager()
    mgr._path_service = SimpleNamespace(get_memory_dir=lambda: tmp_path / "memory")
    return mgr


def test_sparkbot_config_roundtrip_and_masking(manager):
    cfg = BotConfig(
        name="Demo",
        channels={"telegram": {"enabled": True, "token": "secret"}},
    )
    manager.save_bot_config("demo", cfg)

    assert manager.load_bot_config("demo") == cfg
    assert mask_channel_secrets(cfg.channels)["telegram"]["token"] == "***"


@pytest.mark.asyncio
async def test_sparkbot_agent_and_heartbeat_config_are_applied(manager):
    cfg = BotConfig(
        name="Demo",
        agent={
            "maxToolIterations": 9,
            "toolCallLimit": 2,
            "maxTokens": 1234,
            "contextWindowTokens": 4000,
            "temperature": 0.3,
            "reasoningEffort": "low",
            "memoryWindow": 3,
            "teamMaxWorkers": 2,
            "teamWorkerMaxIterations": 6,
        },
        heartbeat={"enabled": False, "intervalS": 7},
        tools={
            "exec": {"timeout": 17, "pathAppend": "custom-bin"},
            "web": {
                "proxy": "http://127.0.0.1:7890",
                "fetchMaxChars": 1234,
                "search": {"provider": "jina", "apiKey": "secret", "maxResults": 4},
            },
            "restrictToWorkspace": False,
        },
    )
    manager.save_bot_config("demo", cfg)

    loaded = manager.load_bot_config("demo")
    assert loaded.agent.max_tool_iterations == 9
    assert loaded.agent.tool_call_limit == 2
    assert loaded.agent.max_tokens == 1234
    assert loaded.agent.context_window_tokens == 4000
    assert loaded.agent.temperature == 0.3
    assert loaded.agent.reasoning_effort == "low"
    assert loaded.agent.memory_window is None
    assert loaded.agent.team_max_workers == 2
    assert loaded.agent.team_worker_max_iterations == 6
    assert loaded.heartbeat.enabled is False
    assert loaded.heartbeat.interval_s == 7
    assert loaded.tools.exec_config.timeout == 17
    assert loaded.tools.exec_config.path_append == "custom-bin"
    assert loaded.tools.web.proxy == "http://127.0.0.1:7890"
    assert loaded.tools.web.fetch_max_chars == 1234
    assert loaded.tools.web.search.provider == "jina"
    assert loaded.tools.web.search.api_key == "secret"
    assert loaded.tools.web.search.max_results == 4
    assert loaded.tools.restrict_to_workspace is False

    instance = await manager.start_bot("demo", loaded)
    try:
        assert instance.agent_loop.agent_tool_max_iterations == 9
        assert instance.agent_loop.agent_tool_call_limit == 2
        assert instance.agent_loop.agent_max_tokens == 1234
        assert instance.agent_loop.agent_context_window_tokens == 4000
        assert instance.agent_loop.session_history_limit == 2
        assert instance.agent_loop.agent_temperature == 0.3
        assert instance.agent_loop.agent_reasoning_effort == "low"
        assert instance.agent_loop.team.max_workers == 2
        assert instance.agent_loop.team.worker_max_iterations == 6
        assert instance.agent_loop.team.max_tokens == 1234
        assert instance.agent_loop.team.temperature == 0.3
        assert instance.agent_loop.team.reasoning_effort == "low"
        assert instance.heartbeat.enabled is False
        assert instance.heartbeat.interval_s == 7
        assert instance.heartbeat.task is None
        exec_tool = instance.agent_loop.agent_tools.get("exec")
        web_search_tool = instance.agent_loop.agent_tools.get("web_search")
        web_fetch_tool = instance.agent_loop.agent_tools.get("web_fetch")
        assert getattr(exec_tool, "default_timeout") == 17
        assert getattr(exec_tool, "path_append") == "custom-bin"
        assert getattr(web_search_tool, "provider") == "jina"
        assert getattr(web_search_tool, "api_key") == "secret"
        assert getattr(web_search_tool, "max_results") == 4
        assert getattr(web_search_tool, "proxy") == "http://127.0.0.1:7890"
        assert getattr(web_fetch_tool, "proxy") == "http://127.0.0.1:7890"
        assert getattr(web_fetch_tool, "max_chars") == 1234
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_start_applies_legacy_exec_runtime_defaults(manager):
    manager.save_bot_config("demo", BotConfig(name="Demo"))

    instance = await manager.start_bot("demo", manager.load_bot_config("demo"))
    try:
        exec_tool = instance.agent_loop.agent_tools.get("exec")
        assert getattr(exec_tool, "default_timeout") == 300
        assert getattr(exec_tool, "path_append") == str(Path(sys.executable).parent)
        saved = manager.load_bot_config("demo")
        assert saved.tools.exec_config.timeout == 300
        assert saved.tools.exec_config.path_append == str(Path(sys.executable).parent)
    finally:
        assert await manager.stop_bot("demo") is True


def test_sparkbot_workspace_files_seed_and_sync_persona(manager):
    cfg = BotConfig(name="Demo", persona="# Soul\n\nPatient math tutor.")
    manager.save_bot_config("demo", cfg)

    files = manager.read_all_bot_files("demo")
    assert set(files) == {"SOUL.md", "USER.md", "TOOLS.md", "AGENTS.md", "HEARTBEAT.md"}
    assert files["SOUL.md"] == "# Soul\n\nPatient math tutor."
    assert "learner" in files["USER.md"]

    assert manager.write_bot_file("demo", "SOUL.md", "# Soul\n\nUpdated.") is True
    assert manager.load_bot_config("demo").persona == "# Soul\n\nUpdated."
    assert manager.write_bot_file("demo", "notes.txt", "nope") is False


def test_sparkbot_workspace_seeds_builtin_skills_without_overwrite(manager):
    workspace = manager._workspace_dir("demo")
    custom_cron = workspace / "skills" / "cron"
    custom_cron.mkdir(parents=True)
    (custom_cron / "SKILL.md").write_text("custom cron skill", encoding="utf-8")

    manager.save_bot_config("demo", BotConfig(name="Demo"))

    assert (workspace / "skills" / "deep-solve" / "SKILL.md").exists()
    assert (workspace / "skills" / "skill-creator" / "scripts" / "init_skill.py").exists()
    assert (workspace / "skills" / "cron" / "SKILL.md").read_text(encoding="utf-8") == "custom cron skill"


@pytest.mark.asyncio
async def test_sparkbot_manager_migrates_legacy_bot_layouts(manager, tmp_path):
    legacy_bot = tmp_path / "sparkbot" / "bots" / "legacy"
    (legacy_bot / "workspace").mkdir(parents=True)
    (legacy_bot / "memory").mkdir()
    (legacy_bot / "config.yaml").write_text(
        "name: Legacy\npersona: Legacy soul\nauto_start: true\n",
        encoding="utf-8",
    )
    (legacy_bot / "workspace" / "notes.md").write_text("legacy notes", encoding="utf-8")
    (legacy_bot / "memory" / "MEMORY.md").write_text("legacy memory", encoding="utf-8")
    legacy_yaml = tmp_path / "sparkbot" / "bots" / "flat.yaml"
    legacy_yaml.write_text("name: Flat\n", encoding="utf-8")

    cfg = manager.load_bot_config("legacy")

    target = tmp_path / "memory" / "sparkbots" / "legacy"
    assert cfg.name == "Legacy"
    assert cfg.auto_start is True
    assert (target / "config.yaml").exists()
    assert (target / "workspace" / "notes.md").read_text(encoding="utf-8") == "legacy notes"
    assert (target / "workspace" / "memory" / "MEMORY.md").read_text(encoding="utf-8") == "legacy memory"
    assert not (legacy_bot / "config.yaml").exists()

    assert manager.load_bot_config("flat").name == "Flat"
    assert not legacy_yaml.exists()
    assert {item["bot_id"] for item in manager.list_bots()} >= {"legacy", "flat"}

    started = await manager.auto_start_bots()
    try:
        assert [instance.bot_id for instance in started] == ["legacy"]
    finally:
        assert await manager.stop_bot("legacy") is True


@pytest.mark.asyncio
async def test_sparkbot_prompt_includes_workspace_files_and_skills(monkeypatch, manager):
    prompts = []

    async def fake_complete(**kwargs):
        prompts.append(kwargs["prompt"])
        return "context aware"

    manager.save_bot_config(
        "demo",
        BotConfig(name="Demo", persona="# Soul\n\nPatient diagram tutor."),
    )
    assert manager.write_bot_file("demo", "USER.md", "# User\n\nLearner likes diagrams.") is True
    assert manager.write_bot_file("demo", "TOOLS.md", "# Tools\n\nPrefer local examples.") is True
    skill_dir = manager._workspace_dir("demo") / "skills" / "diagram-coach"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "description: Diagram coaching\n"
        "always: true\n"
        "---\n"
        "# Diagram Coach\n\nUse short visual analogies.",
        encoding="utf-8",
    )

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    instance = await manager.start_bot("demo", manager.load_bot_config("demo"))
    try:
        assert await manager.send_message("demo", "teach fractions", chat_id="web") == "context aware"
    finally:
        assert await manager.stop_bot("demo") is True

    prompt = prompts[-1]
    assert "## SOUL.md" in prompt
    assert "Patient diagram tutor" in prompt
    assert "Learner likes diagrams" in prompt
    assert "Prefer local examples" in prompt
    assert "### Skill: diagram-coach" in prompt
    assert "Use short visual analogies." in prompt
    assert "<skills>" in prompt
    assert "Current Time:" in prompt
    assert "Chat ID: web" in prompt


@pytest.mark.asyncio
async def test_sparkbot_prompt_includes_memory_and_recent_history(monkeypatch, manager):
    prompts = []

    async def fake_complete(**kwargs):
        prompts.append(kwargs["prompt"])
        return "first reply" if len(prompts) == 1 else "second reply"

    memory_dir = manager._path_service.get_memory_dir()
    memory_dir.mkdir(parents=True)
    (memory_dir / "PROFILE.md").write_text("Learner likes visual explanations.", encoding="utf-8")
    (memory_dir / "SUMMARY.md").write_text("Currently reviewing fractions.", encoding="utf-8")

    manager.save_bot_config("demo", BotConfig(name="Demo"))
    bot_memory = manager._workspace_dir("demo") / "memory"
    bot_memory.mkdir(parents=True, exist_ok=True)
    (bot_memory / "MEMORY.md").write_text("Use diagram-first teaching.", encoding="utf-8")
    (bot_memory / "HISTORY.md").write_text("[2026-04-25] Practiced ratios.", encoding="utf-8")

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    instance = await manager.start_bot("demo", manager.load_bot_config("demo"))
    try:
        assert await manager.send_message("demo", "remember I like diagrams", chat_id="web") == "first reply"
        assert await manager.send_message("demo", "what should we do next?", chat_id="web") == "second reply"
    finally:
        assert await manager.stop_bot("demo") is True

    second_prompt = prompts[-1]
    assert "## User Profile" in second_prompt
    assert "Learner likes visual explanations." in second_prompt
    assert "## Learning Context" in second_prompt
    assert "Currently reviewing fractions." in second_prompt
    assert "## Bot Long-term Memory" in second_prompt
    assert "Use diagram-first teaching." in second_prompt
    assert "## Bot Memory History" in second_prompt
    assert "Practiced ratios." in second_prompt
    assert "# Recent Conversation" in second_prompt
    assert "User: remember I like diagrams" in second_prompt
    assert "SparkBot: first reply" in second_prompt


@pytest.mark.asyncio
async def test_sparkbot_prompt_includes_media_attachments(monkeypatch, manager):
    prompts = []

    async def fake_complete(**kwargs):
        prompts.append(kwargs["prompt"])
        return "saw attachment"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    manager.save_bot_config("demo", BotConfig(name="Demo"))
    instance = await manager.start_bot("demo", manager.load_bot_config("demo"))
    try:
        response = await manager.send_message(
            "demo",
            "please inspect this",
            chat_id="web",
            media=["file://local-diagram.png"],
            attachments=[{"type": "image", "path": "workspace/diagram.png", "name": "diagram"}],
        )
    finally:
        assert await manager.stop_bot("demo") is True

    assert response == "saw attachment"
    prompt = prompts[-1]
    assert "# Attachments" in prompt
    assert "file://local-diagram.png" in prompt
    assert "workspace/diagram.png" in prompt
    assert "diagram" in prompt


@pytest.mark.asyncio
async def test_sparkbot_inlines_local_image_media_for_vision_models(monkeypatch, manager):
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return "saw image pixels"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    manager.save_bot_config("demo", BotConfig(name="Demo"))
    image = manager._workspace_dir("demo") / "diagram.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage-bytes")

    instance = await manager.start_bot("demo", manager.load_bot_config("demo"))
    try:
        response = await manager.send_message(
            "demo",
            "please inspect the actual image",
            chat_id="web",
            media=[str(image)],
            attachments=[{"type": "image", "path": str(image), "name": "diagram"}],
        )
    finally:
        assert await manager.stop_bot("demo") is True

    assert response == "saw image pixels"
    payload = calls[-1]
    assert "please inspect the actual image" in payload["prompt"]
    content = payload["messages"][0]["content"]
    image_blocks = [item for item in content if item["type"] == "image_url"]
    assert len(image_blocks) == 1
    assert image_blocks[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[-1]["type"] == "text"
    assert "please inspect the actual image" in content[-1]["text"]


@pytest.mark.asyncio
async def test_sparkbot_agent_generation_config_is_forwarded(monkeypatch, manager):
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return "configured reply"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    manager.save_bot_config(
        "demo",
        BotConfig(
            name="Demo",
            agent={"maxTokens": 2345, "temperature": 0.2, "reasoningEffort": "medium"},
        ),
    )
    instance = await manager.start_bot("demo", manager.load_bot_config("demo"))
    try:
        response = await manager.send_message("demo", "use configured generation", chat_id="web")
    finally:
        assert await manager.stop_bot("demo") is True

    assert response == "configured reply"
    assert calls[-1]["max_tokens"] == 2345
    assert calls[-1]["temperature"] == 0.2
    assert calls[-1]["reasoning_effort"] == "medium"


def test_sparkbot_agent_history_window_uses_memory_window(tmp_path):
    workspace = tmp_path / "workspace"
    sessions = workspace / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "web.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "first question"}),
                json.dumps({"role": "assistant", "content": "first answer"}),
                json.dumps({"role": "user", "content": "second question"}),
                json.dumps({"role": "assistant", "content": "second answer"}),
            ]
        ),
        encoding="utf-8",
    )
    loop = SparkBotAgentLoop(
        config=BotConfig(name="Demo", agent={"memoryWindow": 2}),
        bus=SparkBotMessageBus(),
        workspace=workspace,
        default_session_key="bot:demo",
    )

    assert loop.session_history_limit == 2
    assert loop._load_session_history("web") == [
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": "second answer"},
    ]
    assert loop._load_session_history("web", limit=0) == []


@pytest.mark.asyncio
async def test_sparkbot_transcription_provider_returns_empty_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"audio")

    assert await GroqTranscriptionProvider().transcribe(audio) == ""
    assert await GroqTranscriptionProvider(api_key="secret").transcribe(tmp_path / "missing.ogg") == ""


@pytest.mark.asyncio
async def test_sparkbot_transcription_provider_posts_audio(monkeypatch, tmp_path):
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"audio")
    calls = []

    async def fake_post(self, path):
        calls.append((self.api_key, self.model, path.name))
        return {"text": " hello audio "}

    monkeypatch.setattr(GroqTranscriptionProvider, "_post", fake_post)

    result = await GroqTranscriptionProvider(api_key="secret").transcribe(audio)

    assert result == "hello audio"
    assert calls == [("secret", "whisper-large-v3", "voice.ogg")]


@pytest.mark.asyncio
async def test_sparkbot_workspace_file_tools_are_workspace_scoped(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tools = build_sparkbot_agent_tool_registry(
        workspace,
        {
            "exec": {"timeout": 3, "pathAppend": "extra-bin"},
            "web": {
                "proxy": "http://127.0.0.1:7890",
                "fetchMaxChars": 321,
                "search": {"provider": "searxng", "baseUrl": "https://search.local", "maxResults": 4},
            },
        },
    )
    assert {"read_file", "write_file", "edit_file", "list_dir", "exec", "web_fetch", "code_execution"} <= set(
        tools.list_tools()
    )
    exec_tool = tools.get("exec")
    web_search_tool = tools.get("web_search")
    web_fetch_tool = tools.get("web_fetch")
    assert getattr(exec_tool, "default_timeout") == 3
    assert getattr(exec_tool, "path_append") == "extra-bin"
    assert getattr(web_search_tool, "provider") == "searxng"
    assert getattr(web_search_tool, "base_url") == "https://search.local"
    assert getattr(web_search_tool, "max_results") == 4
    assert getattr(web_search_tool, "proxy") == "http://127.0.0.1:7890"
    assert getattr(web_fetch_tool, "proxy") == "http://127.0.0.1:7890"
    assert getattr(web_fetch_tool, "max_chars") == 321

    written = await tools.execute("write_file", path="notes/plan.md", content="first draft")
    assert written.success is True
    assert (workspace / "notes" / "plan.md").read_text(encoding="utf-8") == "first draft"

    read = await tools.execute("read_file", path="notes/plan.md")
    assert "1| first draft" in read.content

    edited = await tools.execute(
        "edit_file",
        path="notes/plan.md",
        old_text="first",
        new_text="second",
    )
    assert edited.success is True
    near_miss = await tools.execute(
        "edit_file",
        path="notes/plan.md",
        old_text="secnd draft",
        new_text="third draft",
    )
    assert near_miss.success is False
    assert "Best match" in near_miss.content
    assert "old_text (provided)" in near_miss.content
    listing = await tools.execute("list_dir", path="notes")
    assert "plan.md" in listing.content

    nested_dir = workspace / "src" / "pkg"
    nested_dir.mkdir(parents=True)
    (nested_dir / "module.py").write_text("print('ok')", encoding="utf-8")
    noise_dir = workspace / "node_modules" / "leftpad"
    noise_dir.mkdir(parents=True)
    (noise_dir / "index.js").write_text("module.exports = 1", encoding="utf-8")
    recursive = await tools.execute("list_dir", path=".", recursive=True)
    assert recursive.metadata["recursive"] is True
    assert "src/pkg/module.py" in recursive.content
    assert "node_modules" not in recursive.content

    blocked = await tools.execute("write_file", path="../escape.txt", content="nope")
    assert blocked.success is False
    assert "outside the SparkBot workspace" in blocked.content
    assert not (tmp_path / "escape.txt").exists()

    shell = await tools.execute("exec", command='python -c "print(123)"')
    assert shell.success is True
    assert "123" in shell.content
    assert shell.metadata["timeout"] == 3

    blocked_shell = await tools.execute("exec", command="echo nope", working_dir="../")
    assert blocked_shell.success is False
    assert "outside the SparkBot workspace" in blocked_shell.content

    executed = await tools.execute("code_execution", code="print('ng sparkbot')", timeout=5)
    assert executed.success is True
    assert "ng sparkbot" in executed.content
    assert ".tool_runs" in executed.metadata["execution_dir"]


@pytest.mark.asyncio
async def test_sparkbot_web_fetch_tool_extracts_html(monkeypatch):
    async def fake_fetch_jina(self, url, *, max_chars):
        return None

    async def fake_fetch(self, url):
        return httpx.Response(
            200,
            text="<html><body><h1>Lesson</h1><p>Hello <a href='https://example.com/ref'>ref</a>.</p></body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(WebFetchTool, "_fetch_jina", fake_fetch_jina)
    monkeypatch.setattr(WebFetchTool, "_fetch", fake_fetch)

    fetched = await WebFetchTool().execute(url="https://example.com/lesson")
    assert fetched.success is True
    assert "# Lesson" in fetched.content
    assert "[ref](https://example.com/ref)" in fetched.content
    assert fetched.metadata["extractor"] == "html"

    blocked = await WebFetchTool().execute(url="file:///etc/passwd")
    assert blocked.success is False
    assert "Only http/https URLs are allowed" in blocked.content


@pytest.mark.asyncio
async def test_sparkbot_web_fetch_tool_prefers_jina_reader(monkeypatch):
    fetched = []

    async def fake_fetch_jina(self, url, *, max_chars):
        return ToolResult(
            content="# Reader\n\nClean article text",
            sources=[{"type": "url", "url": url}],
            metadata={"extractor": "jina", "truncated": False, "max_chars": max_chars},
        )

    async def fake_fetch(self, url):
        fetched.append(url)
        return httpx.Response(200, text="fallback")

    monkeypatch.setattr(WebFetchTool, "_fetch_jina", fake_fetch_jina)
    monkeypatch.setattr(WebFetchTool, "_fetch", fake_fetch)

    result = await WebFetchTool().execute(url="https://example.com/article", max_chars=500)

    assert result.content == "# Reader\n\nClean article text"
    assert result.metadata["extractor"] == "jina"
    assert result.metadata["max_chars"] == 500
    assert fetched == []


@pytest.mark.asyncio
async def test_sparkbot_web_search_tool_uses_bot_level_config(monkeypatch, tmp_path):
    from sparkweave.services.search_support.types import Citation, SearchResult, WebSearchResponse

    provider_calls = []
    search_calls = []

    class FakeProvider:
        def search(self, query, **kwargs):
            search_calls.append((query, kwargs))
            return WebSearchResponse(
                query=query,
                answer="",
                provider="jina",
                citations=[
                    Citation(
                        id=1,
                        reference="[1]",
                        url="https://example.com/langgraph",
                        title="LangGraph result",
                        snippet="Agent graph runtime",
                    )
                ],
                search_results=[
                    SearchResult(
                        title="LangGraph result",
                        url="https://example.com/langgraph",
                        snippet="Agent graph runtime",
                    )
                ],
            )

    def fake_get_provider(name, **kwargs):
        provider_calls.append((name, kwargs))
        return FakeProvider()

    monkeypatch.setattr("sparkweave.services.search_support.providers.get_provider", fake_get_provider)
    tools = build_sparkbot_agent_tool_registry(
        tmp_path,
        {
            "web": {
                "proxy": "http://127.0.0.1:7890",
                "search": {"provider": "jina", "apiKey": "secret", "maxResults": 4},
            }
        },
    )

    result = await tools.execute("web_search", query="langgraph", count=2)

    assert result.success is True
    assert provider_calls == [
        (
            "jina",
            {"max_results": 2, "api_key": "secret", "proxy": "http://127.0.0.1:7890"},
        )
    ]
    assert search_calls == [("langgraph", {"max_results": 2, "base_url": ""})]
    assert "LangGraph result" in result.content
    assert result.sources == [
        {"type": "web", "url": "https://example.com/langgraph", "title": "LangGraph result"}
    ]
    assert result.metadata["provider"] == "jina"


@pytest.mark.asyncio
async def test_sparkbot_agent_loop_runs_workspace_tool_calls(monkeypatch, manager):
    prompts = []

    async def fake_complete(**kwargs):
        prompt = kwargs["prompt"]
        prompts.append(prompt)
        if len(prompts) == 1:
            assert "Available SparkBot Tools" in prompt
            assert "write_file" in prompt
            assert "exec" in prompt
            assert "web_fetch" in prompt
            assert "code_execution" in prompt
            return {
                "tool_calls": [
                    {
                        "name": "write_file",
                        "arguments": {
                            "path": "notes/plan.md",
                            "content": "Study fractions with diagrams.",
                        },
                    },
                    {
                        "name": "read_file",
                        "arguments": {"path": "notes/plan.md"},
                    },
                ]
            }
        assert "SparkBot Tool Results" in prompt
        assert "Successfully wrote" in prompt
        assert "1| Study fractions with diagrams." in prompt
        return "I saved the study plan."

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    manager.save_bot_config("demo", BotConfig(name="Demo"))
    instance = await manager.start_bot("demo", manager.load_bot_config("demo"))
    try:
        response = await manager.send_message("demo", "save a study plan", chat_id="web")
    finally:
        assert await manager.stop_bot("demo") is True

    workspace = manager._workspace_dir("demo")
    assert response == "I saved the study plan."
    assert (workspace / "notes" / "plan.md").read_text(encoding="utf-8") == "Study fractions with diagrams."
    tool_log = (workspace / "logs" / "agent_tools.jsonl").read_text(encoding="utf-8")
    assert '"tool": "write_file"' in tool_log
    assert '"tool": "read_file"' in tool_log


@pytest.mark.asyncio
async def test_sparkbot_agent_loop_runs_runtime_tools(monkeypatch, tmp_path):
    prompts = []
    spawned = []

    async def fake_complete(**kwargs):
        prompt = kwargs["prompt"]
        prompts.append(prompt)
        if len(prompts) == 1:
            assert "Available SparkBot Tools" in prompt
            assert '"message"' in prompt
            assert '"spawn"' in prompt
            assert '"cron"' in prompt
            assert '"team"' in prompt
            return {
                "tool_calls": [
                    {
                        "name": "message",
                        "arguments": {"content": "Working on it.", "media": ["plot.png"]},
                    },
                    {
                        "name": "spawn",
                        "arguments": {"task": "compare note-taking methods", "label": "btw"},
                    },
                    {
                        "name": "cron",
                        "arguments": {
                            "action": "add",
                            "message": "review notes",
                            "every_seconds": 60,
                        },
                    },
                    {
                        "name": "team",
                        "arguments": {
                            "action": "create",
                            "team_id": "runtime",
                            "members": [],
                            "tasks": [],
                            "mission": "coordinate runtime tools",
                        },
                    },
                ]
            }
        assert "Message sent to telegram:chat-1" in prompt
        assert "BTW accepted" in prompt
        assert "Created job 'review notes'" in prompt
        assert "Team 'runtime' started" in prompt
        return "Runtime tools are wired."

    async def fake_spawn(**kwargs):
        spawned.append(kwargs)
        return "BTW accepted (id: stub). I'll send the result when it finishes."

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    bus = SparkBotMessageBus()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    loop = SparkBotAgentLoop(
        config=BotConfig(name="Demo"),
        bus=bus,
        workspace=workspace,
        default_session_key="bot:demo",
    )
    loop.cron_service = SparkBotCronService(store_path=tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr(loop.side_tasks, "spawn", fake_spawn)

    response = await loop.process_direct(
        "coordinate this",
        session_key="bot:demo",
        channel="telegram",
        chat_id="chat-1",
    )

    assert response == "Runtime tools are wired."
    outbound = await asyncio.wait_for(bus.consume_outbound(), timeout=1)
    assert outbound == SparkBotOutboundMessage(
        channel="telegram",
        chat_id="chat-1",
        content="Working on it.",
        media=["plot.png"],
        metadata={
            "agent_tool": "message",
            "session_key": "bot:demo",
            "media": ["plot.png"],
        },
    )
    assert spawned == [
        {
            "instruction": "compare note-taking methods",
            "label": "btw",
            "origin_channel": "telegram",
            "origin_chat_id": "chat-1",
            "session_key": "bot:demo",
        }
    ]
    jobs = loop.cron_service.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].payload.message == "review notes"
    assert jobs[0].payload.channel == "telegram"
    assert jobs[0].payload.to == "chat-1"
    assert loop.team.is_active("bot:demo") is True
    assert "coordinate runtime tools" in loop.team.status_text("bot:demo")


@pytest.mark.asyncio
async def test_sparkbot_mcp_tool_wrapper_exposes_schema_and_executes():
    calls = []

    class FakeSession:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return SimpleNamespace(content=[SimpleNamespace(text=f"remote says {arguments['query']}")])

    tool = MCPToolWrapper(
        FakeSession(),
        server_name="local",
        tool_def=SimpleNamespace(
            name="lookup",
            description="Lookup remote context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Lookup query"},
                    "limit": {"type": "integer", "description": "Result limit"},
                },
                "required": ["query"],
            },
        ),
        tool_timeout=5,
    )

    definition = tool.get_definition()
    assert definition.name == "mcp_local_lookup"
    assert [parameter.name for parameter in definition.parameters] == ["query", "limit"]
    assert definition.parameters[0].required is True
    assert definition.parameters[1].required is False

    result = await tool.execute(query="fractions", limit=2)

    assert result.success is True
    assert result.content == "remote says fractions"
    assert calls == [("lookup", {"query": "fractions", "limit": 2})]


@pytest.mark.asyncio
async def test_sparkbot_agent_loop_registers_configured_mcp_tools(monkeypatch, tmp_path):
    prompts = []
    connected = []

    class FakeSession:
        async def call_tool(self, name, arguments):
            return SimpleNamespace(content=[SimpleNamespace(text=f"MCP answer: {arguments['query']}")])

    async def fake_connect_mcp_servers(mcp_servers, registry, stack):
        connected.append(mcp_servers)
        registry.register(
            MCPToolWrapper(
                FakeSession(),
                server_name="local",
                tool_def=SimpleNamespace(
                    name="lookup",
                    description="Lookup remote context.",
                    inputSchema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                ),
            )
        )
        return {"connected": [{"server": "local", "tools": 1}], "errors": {}}

    async def fake_complete(**kwargs):
        prompt = kwargs["prompt"]
        prompts.append(prompt)
        if len(prompts) == 1:
            assert "mcp_local_lookup" in prompt
            return {
                "tool_calls": [
                    {
                        "name": "mcp_local_lookup",
                        "arguments": {"query": "fractions"},
                    }
                ]
            }
        assert "MCP answer: fractions" in prompt
        return "Used MCP."

    monkeypatch.setattr("sparkweave.services.sparkbot.connect_mcp_servers", fake_connect_mcp_servers)
    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    loop = SparkBotAgentLoop(
        config=BotConfig(
            name="Demo",
            tools={"mcpServers": {"local": {"command": "fake-mcp", "enabledTools": ["lookup"]}}},
        ),
        bus=SparkBotMessageBus(),
        workspace=tmp_path / "workspace",
        default_session_key="bot:demo",
    )
    loop.workspace.mkdir(exist_ok=True)
    try:
        response = await loop.process_direct("use remote context", session_key="bot:demo")
    finally:
        await loop.stop()

    assert response == "Used MCP."
    assert len(connected) == 1
    assert "local" in connected[0]
    assert connected[0]["local"].command == "fake-mcp"
    assert connected[0]["local"].enabled_tools == ["lookup"]


def test_sparkbot_default_souls_are_available(manager):
    souls = manager.list_souls()

    assert {soul["id"] for soul in souls} >= {"default-sparkbot", "math-tutor"}
    assert manager.get_soul("math-tutor")["name"] == "Math Tutor"


def test_sparkbot_builtin_skills_are_available(manager):
    manager.save_bot_config("demo", BotConfig(name="Demo"))

    loader = SparkBotSkillsLoader(manager._workspace_dir("demo"))
    skills = {skill["name"]: skill for skill in loader.list_skills(filter_unavailable=False)}

    assert {"cron", "deep-solve", "memory"} <= set(skills)
    assert skills["cron"]["source"] == "workspace"
    summary = loader.build_skills_summary()
    assert "<name>cron</name>" in summary


@pytest.mark.asyncio
async def test_sparkbot_heartbeat_tick_executes_and_notifies(monkeypatch, tmp_path):
    async def fake_complete(**_kwargs):
        return 'Decision: {"action": "run", "tasks": "review algebra reminders"}'

    executed = []
    notified = []

    async def execute(tasks: str) -> str:
        executed.append(tasks)
        return f"done: {tasks}"

    async def notify(response: str) -> None:
        notified.append(response)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "HEARTBEAT.md").write_text("Check algebra reminders.", encoding="utf-8")

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    heartbeat = SparkBotHeartbeatService(
        workspace=workspace,
        on_execute=execute,
        on_notify=notify,
    )

    response = await heartbeat.tick()

    assert response == "done: review algebra reminders"
    assert executed == ["review algebra reminders"]
    assert notified == ["done: review algebra reminders"]


@pytest.mark.asyncio
async def test_sparkbot_heartbeat_evaluator_can_suppress_notification(monkeypatch, tmp_path):
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs["prompt"])
        if len(calls) == 1:
            return {"action": "run", "tasks": "check routine status"}
        return {"should_notify": False, "reason": "routine check"}

    executed = []
    notified = []

    async def execute(tasks: str) -> str:
        executed.append(tasks)
        return "Everything is normal."

    async def notify(response: str) -> None:
        notified.append(response)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "HEARTBEAT.md").write_text("Check routine status.", encoding="utf-8")

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    heartbeat = SparkBotHeartbeatService(
        workspace=workspace,
        on_execute=execute,
        on_notify=notify,
    )

    response = await heartbeat.tick()

    assert response == "Everything is normal."
    assert executed == ["check routine status"]
    assert notified == []
    assert "notification gate" in calls[1]


@pytest.mark.asyncio
async def test_sparkbot_heartbeat_skip_does_not_execute(monkeypatch, tmp_path):
    async def fake_complete(**_kwargs):
        return {"action": "skip", "tasks": ""}

    executed = []

    async def execute(tasks: str) -> str:
        executed.append(tasks)
        return "should not run"

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "HEARTBEAT.md").write_text("No active reminders.", encoding="utf-8")

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    heartbeat = SparkBotHeartbeatService(workspace=workspace, on_execute=execute)

    assert await heartbeat.tick() is None
    assert executed == []


@pytest.mark.asyncio
async def test_sparkbot_cron_service_persists_and_runs_jobs(tmp_path):
    ran = []

    async def on_job(job):
        ran.append(job.payload.message)
        return "ok"

    store_path = tmp_path / "cron" / "jobs.json"
    cron = SparkBotCronService(store_path=store_path, on_job=on_job)
    job = cron.add_job(
        name="Study",
        schedule=SparkBotCronSchedule(kind="every", every_ms=60_000),
        message="review notes",
    )

    assert store_path.exists()
    assert cron.status()["jobs"] == 1
    assert await cron.run_job(job.id) is True
    assert ran == ["review notes"]

    reloaded = SparkBotCronService(store_path=store_path)
    jobs = reloaded.list_jobs(include_disabled=True)
    assert jobs[0].id == job.id
    assert jobs[0].state.last_status == "ok"
    assert cron.remove_job(job.id) is True
    assert cron.list_jobs(include_disabled=True) == []


@pytest.mark.asyncio
async def test_sparkbot_channel_manager_builds_enabled_channels(monkeypatch, manager):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "send_progress": False,
                "transcription_api_key": "groq-secret",
                "telegram": {
                    "enabled": True,
                    "token": "secret",
                    "allow_from": ["*"],
                },
            },
        ),
        bus,
        bot_id="demo",
    )

    assert channel_manager is not None
    assert channel_manager.enabled_channels == ["telegram"]
    channel = channel_manager.get_channel("telegram")
    assert channel is not None
    assert channel.default_config()["enabled"] is False
    assert channel.is_allowed("anyone") is True
    assert channel.transcription_api_key == "groq-secret"

    transcription_calls = []

    async def fake_transcribe(self, file_path):
        transcription_calls.append((self.api_key, str(file_path)))
        return "voice text"

    monkeypatch.setattr(GroqTranscriptionProvider, "transcribe", fake_transcribe)
    assert await channel.transcribe_audio("voice.ogg") == "voice text"
    assert transcription_calls == [("groq-secret", "voice.ogg")]

    handled = await channel._handle_message(
        sender_id="anyone",
        chat_id="chat-1",
        content="hello",
        media=["file://image.png"],
        attachments=[{"type": "image", "path": "diagram.png"}],
        metadata={"source": "test"},
    )
    inbound = await bus.consume_inbound()

    assert handled is True
    assert inbound.channel == "telegram"
    assert inbound.chat_id == "chat-1"
    assert inbound.content == "hello"
    assert inbound.media == ["file://image.png", "diagram.png"]
    assert inbound.attachments == [{"type": "image", "path": "diagram.png"}]
    assert inbound.metadata == {"source": "test"}


@pytest.mark.asyncio
async def test_sparkbot_outbound_router_filters_tool_hints_by_default(manager):
    class FakeChannel:
        def __init__(self):
            self.sent = []

        async def send(self, msg):
            self.sent.append(msg)

    bus = SparkBotMessageBus()
    fake_channel = FakeChannel()
    instance = SparkBotInstance("demo", BotConfig(name="Demo"))
    instance.channel_manager = SimpleNamespace(channels={"telegram": fake_channel})
    router_task = asyncio.create_task(manager._outbound_router("demo", bus, instance))
    try:
        await bus.publish_outbound(
            SparkBotOutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Using tools: web_search",
                metadata={"_progress": True, "_tool_hint": True},
            )
        )
        await asyncio.sleep(0.05)
        assert fake_channel.sent == []

        await bus.publish_outbound(
            SparkBotOutboundMessage(
                channel="telegram",
                chat_id="chat-1",
                content="Thinking...",
                metadata={"_progress": True},
            )
        )
        for _ in range(20):
            if fake_channel.sent:
                break
            await asyncio.sleep(0.01)
        assert len(fake_channel.sent) == 1
        assert fake_channel.sent[0].content == "Thinking..."
    finally:
        router_task.cancel()
        await asyncio.wait_for(router_task, timeout=1)


def test_sparkbot_channel_manager_rejects_empty_allow_from(manager):
    with pytest.raises(ValueError, match="empty allow_from"):
        manager._build_channel_manager(
            BotConfig(
                name="Demo",
                channels={
                    "telegram": {
                        "enabled": True,
                        "token": "secret",
                    },
                },
            ),
            SparkBotMessageBus(),
            bot_id="demo",
        )


class FakeTelegramFile:
    def __init__(self, payload=b"image"):
        self.payload = payload

    async def download_to_drive(self, path):
        with open(path, "wb") as handle:
            handle.write(self.payload)


class FakeTelegramBot:
    def __init__(self):
        self.messages = []
        self.photos = []
        self.documents = []
        self.files = {}
        self.actions = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)

    async def send_photo(self, **kwargs):
        self.photos.append(kwargs)

    async def send_document(self, **kwargs):
        self.documents.append(kwargs)

    async def send_voice(self, **kwargs):
        self.documents.append(kwargs)

    async def send_audio(self, **kwargs):
        self.documents.append(kwargs)

    async def get_file(self, file_id):
        return self.files.get(file_id, FakeTelegramFile())

    async def get_me(self):
        return SimpleNamespace(id=99, username="DeepSparkBot")

    async def send_chat_action(self, **kwargs):
        self.actions.append(kwargs)


@pytest.mark.asyncio
async def test_sparkbot_telegram_send_html_media_and_thread(tmp_path, manager):
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "telegram": {
                    "enabled": True,
                    "token": "telegram-token",
                    "allow_from": ["*"],
                    "reply_to_message": True,
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("telegram")
    fake_bot = FakeTelegramBot()
    channel._app = SimpleNamespace(bot=fake_bot)
    media = tmp_path / "diagram.png"
    media.write_bytes(b"png")
    channel._message_threads[("123", 10)] = 77

    msg = SparkBotOutboundMessage(
        channel="telegram",
        chat_id="123",
        content="# Title\n\n**Bold** and `code`",
        reply_to="10",
        media=[str(media)],
    )
    await channel.send(msg)

    assert len(fake_bot.photos) == 1
    assert fake_bot.photos[0]["chat_id"] == 123
    assert fake_bot.photos[0]["message_thread_id"] == 77
    assert len(fake_bot.messages) == 1
    assert fake_bot.messages[0]["text"] == "Title\n\n<b>Bold</b> and <code>code</code>"
    assert fake_bot.messages[0]["parse_mode"] == "HTML"
    assert fake_bot.messages[0]["message_thread_id"] == 77
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_telegram_group_message_downloads_media_and_topic_session(
    monkeypatch,
    tmp_path,
    manager,
):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "telegram": {
                    "enabled": True,
                    "token": "telegram-token",
                    "allow_from": ["12345"],
                    "group_policy": "mention",
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("telegram")
    fake_bot = FakeTelegramBot()
    fake_bot.files["file-1"] = FakeTelegramFile(b"png")
    channel._app = SimpleNamespace(bot=fake_bot)
    channel._bot_user_id = 99
    channel._bot_username = "DeepSparkBot"
    monkeypatch.setattr(channel, "_start_typing", lambda _chat_id: None)
    monkeypatch.setattr("sparkweave.services.sparkbot._sparkbot_media_dir", lambda _channel: tmp_path)

    user = SimpleNamespace(id=12345, username="learner", first_name="Ada")
    photo = SimpleNamespace(file_id="file-1", file_unique_id="unique-photo")
    chat = SimpleNamespace(type="supergroup", is_forum=True)
    entity = SimpleNamespace(type="mention", offset=0, length=13)
    message = SimpleNamespace(
        message_id=20,
        chat_id=-100,
        chat=chat,
        text="@DeepSparkBot explain this",
        caption=None,
        entities=[entity],
        caption_entities=[],
        photo=[photo],
        voice=None,
        audio=None,
        document=None,
        video=None,
        video_note=None,
        animation=None,
        reply_to_message=None,
        message_thread_id=7,
        media_group_id=None,
    )

    await channel._on_message(SimpleNamespace(message=message, effective_user=user), None)

    inbound = await bus.consume_inbound()
    assert inbound.channel == "telegram"
    assert inbound.sender_id == "12345|learner"
    assert inbound.chat_id == "-100"
    assert inbound.session_key == "telegram:-100:topic:7"
    assert "@DeepSparkBot explain this" in inbound.content
    assert "unique-photo.jpg" in inbound.content
    assert inbound.media == [str(tmp_path / "unique-photo.jpg")]
    assert inbound.metadata["message_id"] == 20
    assert inbound.metadata["message_thread_id"] == 7
    assert (tmp_path / "unique-photo.jpg").read_bytes() == b"png"


class FakeDingTalkResponse:
    def __init__(
        self,
        *,
        content=b"file",
        status_code=200,
        json_data=None,
        headers=None,
        text="",
    ):
        self.content = content
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


class FakeDingTalkHTTP:
    def __init__(self):
        self.posts = []
        self.gets = []

    async def post(self, url, json=None, headers=None, files=None):
        self.posts.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "files": bool(files),
            }
        )
        if url.endswith("/oauth2/accessToken"):
            return FakeDingTalkResponse(json_data={"accessToken": "token-1", "expireIn": 7200})
        if "media/upload" in url:
            return FakeDingTalkResponse(json_data={"errcode": 0, "media_id": "media-1"})
        return FakeDingTalkResponse(json_data={"errcode": 0})

    async def get(self, url, follow_redirects=False):
        self.gets.append((url, follow_redirects))
        return FakeDingTalkResponse(
            content=b"downloaded",
            headers={"content-type": "image/png"},
        )

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_sparkbot_dingtalk_send_markdown_and_media(tmp_path, manager):
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "dingtalk": {
                    "enabled": True,
                    "client_id": "app-key",
                    "client_secret": "app-secret",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("dingtalk")
    fake_http = FakeDingTalkHTTP()
    channel._http = fake_http
    media = tmp_path / "diagram.png"
    media.write_bytes(b"png")

    msg = SparkBotOutboundMessage(
        channel="dingtalk",
        chat_id="group:conv-1",
        content="# Proof\n\nUse common denominators.",
        media=[str(media)],
    )
    await channel.send(msg)

    assert fake_http.posts[0]["json"] == {
        "appKey": "app-key",
        "appSecret": "app-secret",
    }
    assert fake_http.posts[1]["url"].endswith("/robot/groupMessages/send")
    assert fake_http.posts[1]["headers"] == {"x-acs-dingtalk-access-token": "token-1"}
    assert fake_http.posts[1]["json"]["openConversationId"] == "conv-1"
    assert fake_http.posts[1]["json"]["msgKey"] == "sampleMarkdown"
    assert json.loads(fake_http.posts[1]["json"]["msgParam"]) == {
        "title": "SparkWeave Reply",
        "text": "# Proof\n\nUse common denominators.",
    }
    assert fake_http.posts[2]["files"] is True
    assert "type=image" in fake_http.posts[2]["url"]
    assert fake_http.posts[3]["json"]["msgKey"] == "sampleImageMsg"
    assert json.loads(fake_http.posts[3]["json"]["msgParam"]) == {"photoURL": "media-1"}
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_dingtalk_stream_message_group_session(manager):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "dingtalk": {
                    "enabled": True,
                    "client_id": "app-key",
                    "client_secret": "app-secret",
                    "allow_from": ["staff-1"],
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("dingtalk")

    handled = await channel._handle_stream_message(
        {
            "msgId": "msg-1",
            "text": {"content": "解释这个公式"},
            "senderStaffId": "staff-1",
            "senderNick": "Ada",
            "conversationType": "2",
            "openConversationId": "conv-1",
        }
    )

    inbound = await bus.consume_inbound()
    assert handled is True
    assert inbound.channel == "dingtalk"
    assert inbound.sender_id == "staff-1"
    assert inbound.chat_id == "group:conv-1"
    assert inbound.content == "解释这个公式"
    assert inbound.session_key == "dingtalk:group:conv-1"
    assert inbound.metadata == {
        "sender_name": "Ada",
        "platform": "dingtalk",
        "conversation_type": "2",
        "conversation_id": "conv-1",
        "message_id": "msg-1",
    }


@pytest.mark.asyncio
async def test_sparkbot_feishu_send_card_and_media(tmp_path, monkeypatch, manager):
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "feishu": {
                    "enabled": True,
                    "app_id": "cli_app",
                    "app_secret": "app_secret",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("feishu")
    channel._client = object()
    media = tmp_path / "diagram.png"
    media.write_bytes(b"png")
    sent = []

    monkeypatch.setattr(channel, "_upload_image_sync", lambda file_path: "image-key")

    def fake_send(receive_id_type, receive_id, msg_type, content):
        sent.append(
            {
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": json.loads(content),
            }
        )
        return True

    monkeypatch.setattr(channel, "_send_message_sync", fake_send)
    msg = SparkBotOutboundMessage(
        channel="feishu",
        chat_id="oc_chat_1",
        content="# Plan\n\n| Step | Value |\n| --- | --- |\n| one | two |",
        media=[str(media)],
    )

    await channel.send(msg)

    assert sent[0] == {
        "receive_id_type": "chat_id",
        "receive_id": "oc_chat_1",
        "msg_type": "image",
        "content": {"image_key": "image-key"},
    }
    assert sent[1]["msg_type"] == "interactive"
    assert sent[1]["content"]["config"] == {"wide_screen_mode": True}
    assert sent[1]["content"]["elements"][0]["tag"] == "div"
    assert sent[1]["content"]["elements"][1]["tag"] == "table"
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_feishu_group_message_policy_and_dedup(monkeypatch, manager):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "feishu": {
                    "enabled": True,
                    "app_id": "cli_app",
                    "app_secret": "app_secret",
                    "allow_from": ["ou_user_1"],
                    "group_policy": "mention",
                    "react_emoji": "EYES",
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("feishu")
    reactions = []

    async def fake_reaction(message_id, emoji_type):
        reactions.append((message_id, emoji_type))

    monkeypatch.setattr(channel, "_add_reaction", fake_reaction)
    sender = SimpleNamespace(
        sender_type="user",
        sender_id=SimpleNamespace(open_id="ou_user_1"),
    )

    unmentioned = SimpleNamespace(
        event=SimpleNamespace(
            sender=sender,
            message=SimpleNamespace(
                message_id="m-ignored",
                chat_id="oc_chat_1",
                chat_type="group",
                message_type="text",
                content=json.dumps({"text": "hello"}, ensure_ascii=False),
                mentions=[],
            ),
        )
    )
    assert await channel._on_message(unmentioned) is False
    assert bus.inbound.empty()

    mentioned = SimpleNamespace(
        event=SimpleNamespace(
            sender=sender,
            message=SimpleNamespace(
                message_id="m-1",
                chat_id="oc_chat_1",
                chat_type="group",
                message_type="post",
                content=json.dumps(
                    {
                        "zh_cn": {
                            "title": "Fractions",
                            "content": [[{"tag": "text", "text": "Explain 1/2 + 1/3"}]],
                        }
                    },
                    ensure_ascii=False,
                ),
                mentions=[
                    SimpleNamespace(id=SimpleNamespace(open_id="ou_bot_1", user_id="")),
                ],
            ),
        )
    )

    assert await channel._on_message(mentioned) is True
    inbound = await bus.consume_inbound()
    assert inbound.channel == "feishu"
    assert inbound.sender_id == "ou_user_1"
    assert inbound.chat_id == "oc_chat_1"
    assert inbound.content == "Fractions Explain 1/2 + 1/3"
    assert inbound.session_key == "feishu:oc_chat_1"
    assert inbound.metadata == {
        "message_id": "m-1",
        "chat_type": "group",
        "msg_type": "post",
    }
    assert reactions == [("m-1", "EYES")]

    assert await channel._on_message(mentioned) is False
    assert bus.inbound.empty()


class FakeMatrixUploadResponse:
    def __init__(self, content_uri):
        self.content_uri = content_uri


class FakeMatrixClient:
    def __init__(self):
        self.room_sends = []
        self.uploads = []
        self.typing = []
        self.rooms = {}

    async def upload(self, handle, **kwargs):
        self.uploads.append({**kwargs, "payload": handle.read()})
        return FakeMatrixUploadResponse(f"mxc://server/{kwargs['filename']}")

    async def room_send(self, **kwargs):
        self.room_sends.append(kwargs)

    async def room_typing(self, **kwargs):
        self.typing.append(kwargs)

    async def content_repository_config(self):
        return SimpleNamespace(upload_size=10_000_000)

    async def download(self, mxc):
        return SimpleNamespace(body=b"downloaded")


@pytest.mark.asyncio
async def test_sparkbot_matrix_send_uploads_media_and_threads(tmp_path, manager):
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "matrix": {
                    "enabled": True,
                    "homeserver": "https://matrix.example",
                    "access_token": "matrix-token",
                    "user_id": "@bot:matrix.example",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("matrix")
    fake_client = FakeMatrixClient()
    channel.client = fake_client
    media = tmp_path / "diagram.png"
    media.write_bytes(b"png")

    msg = SparkBotOutboundMessage(
        channel="matrix",
        chat_id="!room:matrix.example",
        content="**Done**",
        media=[str(media), str(media)],
        metadata={
            "thread_root_event_id": "$root",
            "thread_reply_to_event_id": "$reply",
        },
    )

    await channel.send(msg)

    assert len(fake_client.uploads) == 1
    assert fake_client.uploads[0]["filename"] == "diagram.png"
    assert fake_client.uploads[0]["content_type"] == "image/png"
    assert len(fake_client.room_sends) == 2
    media_content = fake_client.room_sends[0]["content"]
    assert media_content["msgtype"] == "m.image"
    assert media_content["url"] == "mxc://server/diagram.png"
    assert media_content["m.relates_to"] == {
        "rel_type": "m.thread",
        "event_id": "$root",
        "m.in_reply_to": {"event_id": "$reply"},
        "is_falling_back": True,
    }
    assert fake_client.room_sends[1]["content"]["body"] == "**Done**"
    assert fake_client.typing[-1]["typing_state"] is False
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_matrix_media_message_policy_and_download(
    monkeypatch,
    tmp_path,
    manager,
):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "matrix": {
                    "enabled": True,
                    "homeserver": "https://matrix.example",
                    "access_token": "matrix-token",
                    "user_id": "@bot:matrix.example",
                    "allow_from": ["@alice:matrix.example"],
                    "group_policy": "mention",
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("matrix")
    fake_client = FakeMatrixClient()
    channel.client = fake_client
    monkeypatch.setattr("sparkweave.services.sparkbot._sparkbot_media_dir", lambda _channel: tmp_path)
    room = SimpleNamespace(room_id="!room:matrix.example", display_name="Study Room", member_count=5)

    unmentioned = SimpleNamespace(
        sender="@alice:matrix.example",
        event_id="$ignored",
        body="diagram.png",
        url="mxc://server/ignored",
        source={"content": {"msgtype": "m.image", "info": {"size": 10}}},
    )
    assert await channel._on_media_message(room, unmentioned) is False
    assert bus.inbound.empty()

    mentioned = SimpleNamespace(
        sender="@alice:matrix.example",
        event_id="$event1",
        body="diagram.png",
        url="mxc://server/file",
        source={
            "content": {
                "msgtype": "m.image",
                "info": {"size": 10, "mimetype": "image/png"},
                "m.mentions": {"user_ids": ["@bot:matrix.example"]},
            }
        },
    )
    assert await channel._on_media_message(room, mentioned) is True

    inbound = await bus.consume_inbound()
    assert inbound.channel == "matrix"
    assert inbound.sender_id == "@alice:matrix.example"
    assert inbound.chat_id == "!room:matrix.example"
    assert inbound.session_key == "matrix:!room:matrix.example"
    assert "diagram.png" in inbound.content
    assert "event1_diagram.png" in inbound.content
    assert inbound.media == [str(tmp_path / "event1_diagram.png")]
    assert inbound.attachments[0]["type"] == "image"
    assert inbound.attachments[0]["mime"] == "image/png"
    assert inbound.metadata["room"] == "Study Room"
    assert inbound.metadata["event_id"] == "$event1"
    assert (tmp_path / "event1_diagram.png").read_bytes() == b"downloaded"


class FakeMochatResponse:
    status_code = 200
    is_success = True
    text = "{}"

    def __init__(self, json_data=None):
        self._json_data = json_data or {"code": 200, "data": {}}

    def json(self):
        return self._json_data


class FakeMochatHTTP:
    def __init__(self):
        self.posts = []

    async def post(self, url, headers=None, json=None):
        self.posts.append({"url": url, "headers": headers, "json": json})
        return FakeMochatResponse()

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_sparkbot_mochat_send_panel_payload(manager):
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "mochat": {
                    "enabled": True,
                    "base_url": "https://mochat.example",
                    "claw_token": "claw-token",
                    "allow_from": ["*"],
                    "panels": ["panel-1"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("mochat")
    fake_http = FakeMochatHTTP()
    channel._http = fake_http

    msg = SparkBotOutboundMessage(
        channel="mochat",
        chat_id="panel:panel-1",
        content="reply",
        reply_to="msg-1",
        media=["diagram.png"],
        metadata={"group_id": "group-1"},
    )
    await channel.send(msg)

    assert fake_http.posts == [
        {
            "url": "https://mochat.example/api/claw/groups/panels/send",
            "headers": {"Content-Type": "application/json", "X-Claw-Token": "claw-token"},
            "json": {
                "panelId": "panel-1",
                "content": "reply\ndiagram.png",
                "replyTo": "msg-1",
                "groupId": "group-1",
            },
        }
    ]
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_mochat_panel_delay_flushes_on_mention(manager):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "mochat": {
                    "enabled": True,
                    "claw_token": "claw-token",
                    "agent_user_id": "agent-1",
                    "allow_from": ["user-a", "user-b"],
                    "mention": {"require_in_groups": True},
                    "groups": {"group-1": {"require_mention": True}},
                    "reply_delay_mode": "non-mention",
                    "reply_delay_ms": 60_000,
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("mochat")

    first_event = {
        "type": "message.add",
        "timestamp": "2026-04-25T12:00:00Z",
        "payload": {
            "messageId": "m-1",
            "author": "user-a",
            "content": "first",
            "groupId": "group-1",
            "authorInfo": {"nickname": "Alice"},
        },
    }
    await channel._process_inbound_event("panel-1", first_event, "panel")
    assert bus.inbound.empty()

    mentioned_event = {
        "type": "message.add",
        "timestamp": "2026-04-25T12:00:01Z",
        "payload": {
            "messageId": "m-2",
            "author": "user-b",
            "content": "second <@agent-1>",
            "groupId": "group-1",
            "meta": {"mentions": [{"id": "agent-1"}]},
            "authorInfo": {"nickname": "Bob"},
        },
    }
    await channel._process_inbound_event("panel-1", mentioned_event, "panel")

    inbound = await bus.consume_inbound()
    assert inbound.channel == "mochat"
    assert inbound.sender_id == "user-b"
    assert inbound.chat_id == "panel-1"
    assert inbound.session_key == "mochat:panel-1"
    assert inbound.content == "Alice: first\nBob: second <@agent-1>"
    assert inbound.metadata["message_id"] == "m-2"
    assert inbound.metadata["is_group"] is True
    assert inbound.metadata["group_id"] == "group-1"
    assert inbound.metadata["target_kind"] == "panel"
    assert inbound.metadata["was_mentioned"] is True
    assert inbound.metadata["buffered_count"] == 2
    assert bus.inbound.empty()
    await channel._cancel_delay_timers()


class FakeQQAPI:
    def __init__(self):
        self.group_messages = []
        self.c2c_messages = []

    async def post_group_message(self, **kwargs):
        self.group_messages.append(kwargs)

    async def post_c2c_message(self, **kwargs):
        self.c2c_messages.append(kwargs)


class FakeQQClient:
    def __init__(self):
        self.api = FakeQQAPI()


@pytest.mark.asyncio
async def test_sparkbot_qq_group_inbound_and_markdown_reply(manager):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "qq": {
                    "enabled": True,
                    "app_id": "app-id",
                    "secret": "secret",
                    "allow_from": ["member-1"],
                    "msg_format": "markdown",
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("qq")
    channel._client = FakeQQClient()
    message = SimpleNamespace(
        id="qq-1",
        content=" explain fractions ",
        group_openid="group-1",
        author=SimpleNamespace(member_openid="member-1"),
    )

    assert await channel._on_message(message, is_group=True) is True
    inbound = await bus.consume_inbound()
    assert inbound.channel == "qq"
    assert inbound.sender_id == "member-1"
    assert inbound.chat_id == "group-1"
    assert inbound.content == "explain fractions"
    assert inbound.session_key == "qq:group-1"
    assert inbound.metadata == {"message_id": "qq-1"}

    assert await channel._on_message(message, is_group=True) is False
    assert bus.inbound.empty()

    outbound = SparkBotOutboundMessage(
        channel="qq",
        chat_id="group-1",
        content="**1/2 + 1/3 = 5/6**",
        metadata={"message_id": "qq-1"},
    )
    await channel.send(outbound)

    assert channel._client.api.group_messages == [
        {
            "group_openid": "group-1",
            "msg_type": 2,
            "msg_id": "qq-1",
            "msg_seq": 2,
            "markdown": {"content": "**1/2 + 1/3 = 5/6**"},
        }
    ]
    assert channel.sent_messages == [outbound]


class FakeWeComClient:
    def __init__(self):
        self.streams = []
        self.welcomes = []

    async def download_file(self, file_url, aes_key):
        return b"image-bytes", "remote.png"

    async def reply_stream(self, frame, stream_id, content, finish=True):
        self.streams.append(
            {
                "frame": frame,
                "stream_id": stream_id,
                "content": content,
                "finish": finish,
            }
        )

    async def reply_welcome(self, frame, payload):
        self.welcomes.append({"frame": frame, "payload": payload})


@pytest.mark.asyncio
async def test_sparkbot_wecom_image_inbound_and_stream_reply(
    monkeypatch,
    tmp_path,
    manager,
):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "wecom": {
                    "enabled": True,
                    "bot_id": "bot-id",
                    "secret": "secret",
                    "allow_from": ["user-1"],
                    "welcome_message": "Welcome",
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("wecom")
    channel._client = FakeWeComClient()
    channel._generate_req_id = lambda prefix: f"{prefix}-1"
    monkeypatch.setattr("sparkweave.services.sparkbot._sparkbot_media_dir", lambda _channel: tmp_path)
    frame = SimpleNamespace(
        body={
            "msgid": "wc-1",
            "from": {"userid": "user-1"},
            "chattype": "group",
            "chatid": "chat-1",
            "image": {"url": "https://files.example/image", "aeskey": "aes"},
        }
    )

    assert await channel._process_message(frame, "image") is True
    inbound = await bus.consume_inbound()
    assert inbound.channel == "wecom"
    assert inbound.sender_id == "user-1"
    assert inbound.chat_id == "chat-1"
    assert inbound.session_key == "wecom:chat-1"
    assert "[image: remote.png]" in inbound.content
    assert inbound.media == [str(tmp_path / "remote.png")]
    assert inbound.metadata == {
        "message_id": "wc-1",
        "msg_type": "image",
        "chat_type": "group",
    }
    assert (tmp_path / "remote.png").read_bytes() == b"image-bytes"

    await channel.send(
        SparkBotOutboundMessage(channel="wecom", chat_id="chat-1", content="reply")
    )
    assert channel._client.streams == [
        {"frame": frame, "stream_id": "stream-1", "content": "reply", "finish": True}
    ]

    await channel._on_enter_chat(SimpleNamespace(body={"chatid": "chat-2"}))
    assert channel._client.welcomes == [
        {
            "frame": SimpleNamespace(body={"chatid": "chat-2"}),
            "payload": {"msgtype": "text", "text": {"content": "Welcome"}},
        }
    ]


class FakeIMAPClient:
    instances = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.stored = []
        self.searches = []
        self.logged_out = False
        FakeIMAPClient.instances.append(self)

    def login(self, username, password):
        self.username = username
        self.password = password
        return "OK", []

    def select(self, mailbox):
        self.mailbox = mailbox
        return "OK", []

    def search(self, charset, *criteria):
        self.searches.append(criteria)
        return "OK", [b"1"]

    def fetch(self, imap_id, query):
        msg = EmailMessage()
        msg["From"] = "Learner <learner@example.com>"
        msg["Subject"] = "Fractions"
        msg["Date"] = "Sat, 25 Apr 2026 12:00:00 +0000"
        msg["Message-ID"] = "<mail-1@example.com>"
        msg.set_content("Please explain 1/2 + 1/3.")
        return "OK", [(b"1 (UID 42 BODY[])", msg.as_bytes())]

    def store(self, imap_id, command, flag):
        self.stored.append((imap_id, command, flag))
        return "OK", []

    def logout(self):
        self.logged_out = True
        return "BYE", []


def test_sparkbot_email_fetches_unread_messages(monkeypatch, manager):
    FakeIMAPClient.instances.clear()
    monkeypatch.setattr("sparkweave.services.sparkbot.imaplib.IMAP4_SSL", FakeIMAPClient)
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "email": {
                    "enabled": True,
                    "consent_granted": True,
                    "imap_host": "imap.example.com",
                    "imap_username": "bot@example.com",
                    "imap_password": "imap-secret",
                    "smtp_host": "smtp.example.com",
                    "smtp_username": "bot@example.com",
                    "smtp_password": "smtp-secret",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("email")

    messages = channel._fetch_new_messages()
    assert len(messages) == 1
    assert messages[0]["sender"] == "learner@example.com"
    assert messages[0]["subject"] == "Fractions"
    assert "Please explain 1/2 + 1/3." in messages[0]["content"]
    assert messages[0]["metadata"]["uid"] == "42"
    assert channel._fetch_new_messages() == []

    imap = FakeIMAPClient.instances[0]
    assert imap.host == "imap.example.com"
    assert imap.mailbox == "INBOX"
    assert imap.stored == [(b"1", "+FLAGS", "\\Seen")]
    assert imap.logged_out is True


@pytest.mark.asyncio
async def test_sparkbot_email_send_replies_with_thread_headers(monkeypatch, manager):
    sent = []
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "email": {
                    "enabled": True,
                    "consent_granted": True,
                    "imap_host": "imap.example.com",
                    "imap_username": "bot@example.com",
                    "imap_password": "imap-secret",
                    "smtp_host": "smtp.example.com",
                    "smtp_username": "bot@example.com",
                    "smtp_password": "smtp-secret",
                    "from_address": "SparkBot <bot@example.com>",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("email")
    channel._last_subject_by_chat["learner@example.com"] = "Fractions"
    channel._last_message_id_by_chat["learner@example.com"] = "<mail-1@example.com>"

    def fake_smtp_send(msg):
        sent.append(msg)

    monkeypatch.setattr(channel, "_smtp_send", fake_smtp_send)
    outbound = SparkBotOutboundMessage(
        channel="email",
        chat_id="learner@example.com",
        content="1/2 + 1/3 = 5/6",
    )

    await channel.send(outbound)

    assert len(sent) == 1
    message = sent[0]
    assert message["From"] == "SparkBot <bot@example.com>"
    assert message["To"] == "learner@example.com"
    assert message["Subject"] == "Re: Fractions"
    assert message["In-Reply-To"] == "<mail-1@example.com>"
    assert message["References"] == "<mail-1@example.com>"
    assert message.get_content().strip() == "1/2 + 1/3 = 5/6"
    assert channel.sent_messages == [outbound]


class FakeSlackWebClient:
    def __init__(self):
        self.messages = []
        self.files = []
        self.reactions = []

    async def chat_postMessage(self, **kwargs):
        self.messages.append(kwargs)

    async def files_upload_v2(self, **kwargs):
        self.files.append(kwargs)

    async def reactions_add(self, **kwargs):
        self.reactions.append(kwargs)


class FakeSlackSocketClient:
    def __init__(self):
        self.responses = []

    async def send_socket_mode_response(self, response):
        self.responses.append(response)


class FakeSlackRequest:
    type = "events_api"
    envelope_id = "env-1"

    def __init__(self, event):
        self.payload = {"event": event}


@pytest.mark.asyncio
async def test_sparkbot_slack_send_uses_thread_and_uploads_media(tmp_path, manager):
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "slack": {
                    "enabled": True,
                    "bot_token": "xoxb-token",
                    "app_token": "xapp-token",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("slack")
    fake_web = FakeSlackWebClient()
    channel._web_client = fake_web
    media = tmp_path / "diagram.png"
    media.write_bytes(b"png")

    msg = SparkBotOutboundMessage(
        channel="slack",
        chat_id="C1",
        content="# Title\n\n**Important**",
        media=[str(media)],
        metadata={"slack": {"thread_ts": "171.1", "channel_type": "channel"}},
    )
    await channel.send(msg)

    assert fake_web.messages == [
        {
            "channel": "C1",
            "text": "*Title*\n\n*Important*",
            "thread_ts": "171.1",
        }
    ]
    assert fake_web.files == [
        {
            "channel": "C1",
            "file": str(media),
            "thread_ts": "171.1",
        }
    ]
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_slack_socket_request_mentions_thread_session(manager):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "slack": {
                    "enabled": True,
                    "bot_token": "xoxb-token",
                    "app_token": "xapp-token",
                    "allow_from": ["*"],
                    "group_policy": "mention",
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("slack")
    channel._bot_user_id = "B1"
    channel._web_client = FakeSlackWebClient()
    client = FakeSlackSocketClient()

    await channel._on_socket_request(
        client,
        FakeSlackRequest(
            {
                "type": "app_mention",
                "user": "U1",
                "channel": "C1",
                "channel_type": "channel",
                "text": "<@B1> please help",
                "ts": "171.1",
            }
        ),
    )

    inbound = await bus.consume_inbound()
    assert len(client.responses) == 1
    assert inbound.channel == "slack"
    assert inbound.sender_id == "U1"
    assert inbound.chat_id == "C1"
    assert inbound.content == "please help"
    assert inbound.session_key == "slack:C1:171.1"
    assert inbound.metadata["slack"]["thread_ts"] == "171.1"
    assert inbound.metadata["slack"]["channel_type"] == "channel"
    assert channel._web_client.reactions == [
        {"channel": "C1", "name": "eyes", "timestamp": "171.1"}
    ]


class FakeDiscordResponse:
    def __init__(self, *, content=b"file", status_code=200, json_data=None):
        self.content = content
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        return None


class FakeDiscordHTTP:
    def __init__(self):
        self.posts = []
        self.gets = []

    async def post(self, url, headers=None, json=None, files=None, data=None):
        self.posts.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "files": bool(files),
                "data": data,
            }
        )
        return FakeDiscordResponse()

    async def get(self, url):
        self.gets.append(url)
        return FakeDiscordResponse(content=b"downloaded")

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_sparkbot_discord_send_splits_text_and_sends_attachments(tmp_path, manager):
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "discord": {
                    "enabled": True,
                    "token": "discord-token",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("discord")
    fake_http = FakeDiscordHTTP()
    channel._http = fake_http
    media = tmp_path / "proof.txt"
    media.write_text("attachment", encoding="utf-8")

    msg = SparkBotOutboundMessage(
        channel="discord",
        chat_id="channel-1",
        content="a" * 2105,
        reply_to="message-1",
        media=[str(media)],
    )
    await channel.send(msg)

    assert len(fake_http.posts) == 3
    assert fake_http.posts[0]["files"] is True
    assert json.loads(fake_http.posts[0]["data"]["payload_json"]) == {
        "message_reference": {"message_id": "message-1"},
        "allowed_mentions": {"replied_user": False},
    }
    assert fake_http.posts[1]["json"] == {"content": "a" * 2000}
    assert fake_http.posts[2]["json"] == {"content": "a" * 105}
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_discord_gateway_message_policy_and_attachment(
    monkeypatch,
    tmp_path,
    manager,
):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "discord": {
                    "enabled": True,
                    "token": "discord-token",
                    "allow_from": ["user-1"],
                    "group_policy": "mention",
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("discord")
    channel._http = FakeDiscordHTTP()
    channel._bot_user_id = "bot-1"
    channel._running = True
    monkeypatch.setattr(
        "sparkweave.services.sparkbot._sparkbot_media_dir",
        lambda _channel: tmp_path,
    )

    await channel._handle_message_create(
        {
            "id": "ignored",
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "author": {"id": "user-1"},
            "content": "hello",
            "mentions": [],
        }
    )
    assert bus.inbound.empty()

    await channel._handle_message_create(
        {
            "id": "message-2",
            "channel_id": "channel-1",
            "guild_id": "guild-1",
            "author": {"id": "user-1"},
            "content": "<@bot-1> check this",
            "mentions": [{"id": "bot-1"}],
            "attachments": [
                {
                    "id": "att-1",
                    "filename": "diagram.png",
                    "url": "https://cdn.discord.test/diagram.png",
                    "size": 10,
                }
            ],
            "referenced_message": {"id": "reply-source"},
        }
    )

    inbound = await bus.consume_inbound()
    assert inbound.channel == "discord"
    assert inbound.sender_id == "user-1"
    assert inbound.chat_id == "channel-1"
    assert "<@bot-1> check this" in inbound.content
    assert "att-1_diagram.png" in inbound.content
    assert inbound.media == [str(tmp_path / "att-1_diagram.png")]
    assert inbound.metadata == {
        "message_id": "message-2",
        "guild_id": "guild-1",
        "reply_to": "reply-source",
    }
    assert (tmp_path / "att-1_diagram.png").read_bytes() == b"downloaded"
    await channel._stop_typing("channel-1")


@pytest.mark.asyncio
async def test_sparkbot_whatsapp_bridge_inbound_media_and_dedup(manager):
    bus = SparkBotMessageBus()
    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "whatsapp": {
                    "enabled": True,
                    "bridge_url": "ws://bridge.local",
                    "allow_from": ["12345"],
                },
            },
        ),
        bus,
        bot_id="demo",
    )
    channel = channel_manager.get_channel("whatsapp")

    await channel._handle_bridge_message(
        json.dumps(
            {
                "type": "message",
                "id": "wa-1",
                "sender": "12345@s.whatsapp.net",
                "content": "hello",
                "media": ["photo.png", "notes.pdf"],
                "timestamp": 123,
                "isGroup": True,
            }
        )
    )

    inbound = await bus.consume_inbound()
    assert inbound.channel == "whatsapp"
    assert inbound.sender_id == "12345"
    assert inbound.chat_id == "12345@s.whatsapp.net"
    assert "hello" in inbound.content
    assert "[image: photo.png]" in inbound.content
    assert "[file: notes.pdf]" in inbound.content
    assert inbound.media == ["photo.png", "notes.pdf"]
    assert inbound.metadata == {"message_id": "wa-1", "timestamp": 123, "is_group": True}

    await channel._handle_bridge_message(
        json.dumps({"type": "message", "id": "wa-1", "sender": "12345@s.whatsapp.net"})
    )
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_sparkbot_whatsapp_bridge_send_payload(manager):
    class FakeBridgeWebSocket:
        def __init__(self):
            self.sent = []

        async def send(self, payload):
            self.sent.append(json.loads(payload))

    channel_manager = manager._build_channel_manager(
        BotConfig(
            name="Demo",
            channels={
                "whatsapp": {
                    "enabled": True,
                    "bridge_url": "ws://bridge.local",
                    "allow_from": ["*"],
                },
            },
        ),
        SparkBotMessageBus(),
        bot_id="demo",
    )
    channel = channel_manager.get_channel("whatsapp")
    fake_ws = FakeBridgeWebSocket()
    channel._ws = fake_ws
    channel._connected = True

    msg = SparkBotOutboundMessage(
        channel="whatsapp",
        chat_id="12345@s.whatsapp.net",
        content="hello",
        reply_to="wa-1",
        media=["photo.png"],
    )
    await channel.send(msg)

    assert fake_ws.sent == [
        {
            "type": "send",
            "to": "12345@s.whatsapp.net",
            "text": "hello",
            "replyTo": "wa-1",
            "media": ["photo.png"],
        }
    ]
    assert channel.sent_messages == [msg]


@pytest.mark.asyncio
async def test_sparkbot_start_stop_and_send_message(monkeypatch, manager):
    async def fake_complete(**_kwargs):
        return "hello back"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    instance = await manager.start_bot("demo", BotConfig(name="Demo"))
    response = await manager.send_message("demo", "hi")

    assert isinstance(instance, SparkBotInstance)
    assert isinstance(instance.heartbeat, SparkBotHeartbeatService)
    assert isinstance(instance.cron_service, SparkBotCronService)
    assert response == "hello back"
    assert manager.get_bot_history("demo")[0]["assistant"] == "hello back"
    assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_commands_help_new_and_cron(monkeypatch, manager):
    async def fake_complete(**_kwargs):
        return "scheduled work complete"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    instance = await manager.start_bot("demo", BotConfig(name="Demo"))
    try:
        help_text = await manager.send_message("demo", "/help")
        assert "/cron add every" in help_text

        await manager.send_message("demo", "remember me", chat_id="web")
        assert "remember me" in (manager._workspace_dir("demo") / "sessions" / "web.jsonl").read_text(
            encoding="utf-8"
        )
        assert await manager.send_message("demo", "/new", chat_id="web") == "New session started."
        session_text = (manager._workspace_dir("demo") / "sessions" / "web.jsonl").read_text(
            encoding="utf-8"
        )
        assert "remember me" not in session_text
        archived = (manager._path_service.get_memory_dir() / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        assert "[SESSION ROLLOVER] web:web" in archived
        assert "remember me" in archived
        first_line = session_text.splitlines()[0]
        metadata = json.loads(first_line)
        assert metadata["_type"] == "metadata"
        assert metadata["key"] == "web:web"
        assert metadata["last_consolidated"] == 0

        created = await manager.send_message("demo", "/cron add every 60 review notes")
        assert created.startswith("Created job")
        jobs = instance.cron_service.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].payload.message == "review notes"

        listing = await manager.send_message("demo", "/cron list")
        assert "review notes" in listing
        assert await manager.send_message("demo", f"/cron run {jobs[0].id}") == f"Ran job {jobs[0].id}"
        assert await asyncio.wait_for(instance.notify_queue.get(), timeout=1) == "scheduled work complete"
        assert await manager.send_message("demo", f"/cron remove {jobs[0].id}") == f"Removed job {jobs[0].id}"
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_team_commands_persist_state(monkeypatch, manager):
    async def fake_complete(**kwargs):
        prompt = kwargs["prompt"]
        if "Task: t1" in prompt:
            return "t1 analysis complete"
        if "Task: t2" in prompt:
            return "t2 execution complete"
        return "team worker complete"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    instance = await manager.start_bot("demo", BotConfig(name="Demo"))
    try:
        help_text = await manager.send_message("demo", "/help")
        assert "/team <goal>" in help_text

        started = await manager.send_message("demo", "/team migrate the sparkbot team mode")
        assert started.startswith("Nano team started")
        worker_notice = await asyncio.wait_for(instance.notify_queue.get(), timeout=1)
        assert "Team lead:" in worker_notice

        status = await manager.send_message("demo", "/team status")
        assert "migrate the sparkbot team mode" in status
        assert "Tasks:" in status

        queued = await manager.send_message("demo", "/teams add a handoff summary")
        assert queued == "Queued 1 task(s): t3."

        approved = await manager.send_message("demo", "/team approve t1")
        assert approved == "Updated task t1 to in_progress"

        manual = await manager.send_message("demo", "/team manual t1 add regression tests")
        assert manual == "Requested changes for t1."

        blocked = await manager.send_message("demo", "plain message while team is active")
        assert "Team mode is active" in blocked

        log_text = await manager.send_message("demo", "/team log 50")
        assert "team_started" in log_text
        assert "task_change_requested" in log_text

        reloaded = SparkBotTeamManager(manager._workspace_dir("demo"), auto_start_workers=False)
        persisted = reloaded.status_text("bot:demo")
        assert "migrate the sparkbot team mode" in persisted
        assert "t1" in reloaded.render_board("bot:demo")
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_team_tools_and_worker_actions(manager):
    team = SparkBotTeamManager(manager._workspace_dir("demo"), auto_start_workers=False)
    tool = SparkBotTeamTool(team, session_key="bot:demo")

    created = await tool.execute(
        action="create",
        team_id="research",
        members=[{"name": "analyst", "role": "analysis"}],
        tasks=[
            {
                "id": "t1",
                "title": "Plan",
                "owner": "analyst",
                "requires_approval": True,
            }
        ],
        mission="research plan",
    )
    assert created.content == "Team 'research' started with 1 teammates."

    worker = SparkBotTeamWorkerTool(team, worker_name="analyst", session_key="bot:demo")
    claimed = await worker.execute(action="claim", task_id="t1")
    assert claimed.content == "Claimed task t1"

    planned = await worker.execute(action="submit_plan", task_id="t1", plan="Check sources first.")
    assert planned.content == "Submitted plan for t1"

    board = await tool.execute(action="board")
    assert "awaiting_approval" in board.content

    assert team.handle_approval_reply("bot:demo", "批准 t1") == "Updated task t1 to in_progress"

    completed = await worker.execute(action="complete", task_id="t1", result="Done")
    assert completed.content == "Updated task t1 to completed"

    sent = await tool.execute(action="message", to="analyst", content="Nice work")
    assert sent.content == "Sent message to analyst"
    unread = await worker.execute(action="mail_read")
    assert "Nice work" in unread.content


@pytest.mark.asyncio
async def test_sparkbot_team_worker_runs_ng_tools(manager, tmp_path):
    calls = []
    source_file = tmp_path / "code.py"
    output_log = tmp_path / "output.log"
    artifact_path = tmp_path / "plot.png"

    class FakeRegistry:
        async def execute(self, name, **kwargs):
            calls.append((name, kwargs))
            return ToolResult(
                content="tool answer: 42",
                sources=[{"type": "code", "file": "plot.png"}],
                metadata={
                    "args": kwargs,
                    "source_file": source_file,
                    "output_log": output_log,
                    "artifacts": ["plot.png"],
                    "artifact_paths": [artifact_path],
                },
            )

    team = SparkBotTeamManager(
        manager._workspace_dir("demo"),
        auto_start_workers=False,
        tool_registry=FakeRegistry(),
    )
    tool = SparkBotTeamTool(team, session_key="bot:demo")
    worker = SparkBotTeamWorkerTool(team, worker_name="analyst", session_key="bot:demo")

    await tool.execute(
        action="create",
        team_id="tools",
        members=[{"name": "analyst", "role": "tool runner"}],
        tasks=[
            {
                "id": "t1",
                "title": "Compute a value",
                "owner": "analyst",
                "tool_calls": [
                    {
                        "name": "code_execution",
                        "arguments": {"code": "print(6 * 7)"},
                    }
                ],
            }
        ],
        mission="use tools",
    )

    assert await worker.execute(action="claim", task_id="t1")
    ran = await worker.execute(
        action="run_tool",
        task_id="t1",
        tool_name="code_execution",
        arguments={"code": "print(2 + 2)"},
    )
    assert ran.content == "tool answer: 42"
    assert calls[-1][0] == "code_execution"
    assert calls[-1][1]["code"] == "print(2 + 2)"
    assert calls[-1][1]["workspace_dir"].endswith("workers\\analyst") or calls[-1][1][
        "workspace_dir"
    ].endswith("workers/analyst")

    runtime = team._runtime("bot:demo", auto_attach=True)
    assert runtime is not None
    task = team._load_tasks(runtime)[0]
    assert task.tool_results[-1]["tool"] == "code_execution"
    assert task.tool_results[-1]["success"] is True
    assert task.tool_results[-1]["metadata"]["source_file"] == str(source_file)
    assert {artifact["filename"] for artifact in task.artifacts if "filename" in artifact} >= {
        "code.py",
        "output.log",
        "plot.png",
    }
    board = team.render_board("bot:demo")
    assert "code_execution (1 run)" in board
    assert "plot.png" in board

    result = await team._complete_task_with_llm(
        runtime,
        runtime.state.members[0],
        task,
    )
    assert "Tool results:" in result
    assert "tool answer: 42" in result
    assert calls[-1][1]["task_id"] == "t1"
    assert len(team._load_tasks(runtime)[0].tool_results) == 2


@pytest.mark.asyncio
async def test_sparkbot_team_worker_autoplans_ng_tools(monkeypatch, manager):
    calls = []

    class FakeRegistry:
        async def execute(self, name, **kwargs):
            calls.append((name, kwargs))
            return ToolResult(content="calculated 42")

    async def fake_complete(**kwargs):
        prompt = kwargs["prompt"]
        if "# Tool Planning" in prompt:
            return {
                "tool_calls": [
                    {
                        "name": "code_execution",
                        "arguments": {"code": "print(6 * 7)"},
                    }
                ]
            }
        if "Use the tool results" in prompt:
            assert "calculated 42" in prompt
            return "Final answer from tool: 42"
        return "plain answer"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    team = SparkBotTeamManager(
        manager._workspace_dir("demo"),
        auto_start_workers=False,
        tool_registry=FakeRegistry(),
    )
    await SparkBotTeamTool(team, session_key="bot:demo").execute(
        action="create",
        team_id="auto-tools",
        members=[{"name": "analyst", "role": "calculation"}],
        tasks=[
            {
                "id": "t1",
                "title": "Calculate 6 * 7",
                "owner": "analyst",
            }
        ],
        mission="calculate",
    )

    runtime = team._runtime("bot:demo", auto_attach=True)
    assert runtime is not None
    result = await team._complete_task_with_llm(
        runtime,
        runtime.state.members[0],
        team._load_tasks(runtime)[0],
    )

    assert result == "Final answer from tool: 42"
    assert calls[0][0] == "code_execution"
    assert calls[0][1]["code"] == "print(6 * 7)"
    task = team._load_tasks(runtime)[0]
    assert task.tool_calls[0]["name"] == "code_execution"
    assert task.tool_results[0]["tool"] == "code_execution"
    assert task.tool_results[0]["content"] == "calculated 42"


@pytest.mark.asyncio
async def test_sparkbot_stop_cancels_active_team(monkeypatch, manager):
    started = asyncio.Event()

    async def fake_complete(**_kwargs):
        started.set()
        await asyncio.sleep(30)
        return "too late"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    await manager.start_bot("demo", BotConfig(name="Demo"))
    try:
        assert (await manager.send_message("demo", "/team build a study plan")).startswith(
            "Nano team started"
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        assert await manager.send_message("demo", "/stop") == "Stopped 1 task(s)."
        assert "No active nano team" in await manager.send_message("demo", "/team status")
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_btw_side_task_notifies_when_done(monkeypatch, manager):
    async def fake_complete(**kwargs):
        assert "Background side task" in kwargs["prompt"]
        assert "compare note-taking methods" in kwargs["prompt"]
        return "Use Cornell notes for review-heavy topics."

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    instance = await manager.start_bot("demo", BotConfig(name="Demo"))
    try:
        accepted = await manager.send_message("demo", "/btw compare note-taking methods")
        assert accepted.startswith("BTW accepted")

        notification = await asyncio.wait_for(instance.notify_queue.get(), timeout=1)
        assert "BTW result" in notification
        assert "Cornell notes" in notification

        status = await manager.send_message("demo", "/btw status")
        assert "compare note-taking methods" in status
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_stop_cancels_btw_side_task(monkeypatch, manager):
    started = asyncio.Event()

    async def fake_complete(**_kwargs):
        started.set()
        await asyncio.sleep(30)
        return "too late"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    instance = await manager.start_bot("demo", BotConfig(name="Demo"))
    try:
        accepted = await manager.send_message("demo", "/btw slow background task")
        assert accepted.startswith("BTW accepted")
        await asyncio.wait_for(started.wait(), timeout=1)

        assert await manager.send_message("demo", "/stop") == "Stopped 1 task(s)."
        assert "cancelled" in await manager.send_message("demo", "/btw status")
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_channel_stop_cancels_active_task(monkeypatch, manager):
    started = asyncio.Event()

    async def fake_complete(**_kwargs):
        started.set()
        await asyncio.sleep(30)
        return "too late"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    instance = await manager.start_bot(
        "demo",
        BotConfig(
            name="Demo",
            channels={"telegram": {"enabled": True, "allow_from": ["*"]}},
        ),
    )
    try:
        await instance.agent_loop.bus.publish_inbound(
            SparkBotInboundMessage(
                channel="telegram",
                sender_id="u1",
                chat_id="chat-1",
                content="slow work",
            )
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        await instance.agent_loop.bus.publish_inbound(
            SparkBotInboundMessage(
                channel="telegram",
                sender_id="u1",
                chat_id="chat-1",
                content="/stop",
            )
        )

        assert await asyncio.wait_for(instance.notify_queue.get(), timeout=1) == "Stopped 1 task(s)."
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_cron_job_delivers_to_web_and_channel(monkeypatch, manager):
    async def fake_complete(**_kwargs):
        return "cron reply"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    instance = await manager.start_bot(
        "demo",
        BotConfig(
            name="Demo",
            channels={"telegram": {"enabled": True, "allow_from": ["*"]}},
        ),
    )
    try:
        channel = instance.channel_manager.get_channel("telegram")
        job = instance.cron_service.add_job(
            name="One shot",
            schedule=SparkBotCronSchedule(kind="at", at_ms=4_102_444_800_000),
            message="run scheduled check",
            deliver=True,
            channel="telegram",
            to="chat-1",
            delete_after_run=True,
        )

        assert await instance.cron_service.run_job(job.id, force=True) is True
        assert await asyncio.wait_for(instance.notify_queue.get(), timeout=1) == "cron reply"
        assert channel.sent_messages[-1] == SparkBotOutboundMessage(
            channel="telegram",
            chat_id="chat-1",
            content="cron reply",
        )
        assert instance.cron_service.list_jobs(include_disabled=True) == []
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_channel_bus_routes_inbound_messages(monkeypatch, manager):
    async def fake_complete(**_kwargs):
        return "channel reply"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    from sparkweave.events.event_bus import get_event_bus

    instance = await manager.start_bot(
        "demo",
        BotConfig(
            name="Demo",
            channels={"telegram": {"enabled": True, "allow_from": ["*"]}},
        ),
    )
    try:
        channel = instance.channel_manager.get_channel("telegram")
        assert channel is not None
        await instance.agent_loop.bus.publish_inbound(
            SparkBotInboundMessage(
                channel="telegram",
                sender_id="u1",
                chat_id="chat-1",
                content="hello from chat",
            )
        )

        assert await asyncio.wait_for(instance.notify_queue.get(), timeout=1) == "channel reply"
        assert channel.sent_messages[-1].content == "channel reply"
        assert channel.sent_messages[-1].chat_id == "chat-1"
        assert instance.channel_bindings["telegram"] == "chat-1"
        assert any(
            item.get("assistant") == "channel reply" or item.get("content") == "channel reply"
            for item in manager.get_bot_history("demo")
        )
    finally:
        assert await manager.stop_bot("demo") is True
        await get_event_bus().stop()


@pytest.mark.asyncio
async def test_sparkbot_web_reply_forwards_to_bound_channels(monkeypatch, manager):
    async def fake_complete(**_kwargs):
        return "web reply"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)

    instance = await manager.start_bot(
        "demo",
        BotConfig(
            name="Demo",
            channels={"telegram": {"enabled": True, "allow_from": ["*"]}},
        ),
    )
    try:
        instance.channel_bindings["telegram"] = "chat-1"
        channel = instance.channel_manager.get_channel("telegram")

        response = await manager.send_message("demo", "from web")

        assert response == "web reply"
        assert channel.sent_messages[-1] == SparkBotOutboundMessage(
            channel="telegram",
            chat_id="chat-1",
            content="web reply",
        )
    finally:
        assert await manager.stop_bot("demo") is True


@pytest.mark.asyncio
async def test_sparkbot_auto_start_recent_and_destroy(monkeypatch, tmp_path, manager):
    async def fake_complete(**_kwargs):
        return "hello again"

    monkeypatch.setattr("sparkweave.services.sparkbot.llm_complete", fake_complete)
    manager.save_bot_config("auto", BotConfig(name="Auto", auto_start=True))

    started = await manager.auto_start_bots()
    assert [instance.bot_id for instance in started] == ["auto"]

    await manager.send_message("auto", "ping", chat_id="web")
    recent = manager.get_recent_active_bots(limit=1)
    assert recent[0]["bot_id"] == "auto"
    assert recent[0]["last_message"] == "hello again"

    assert await manager.stop_bot("auto") is True
    assert manager.load_bot_config("auto").auto_start is False
    assert await manager.destroy_bot("auto") is True
    assert not (tmp_path / "memory" / "sparkbots" / "auto").exists()


def test_sparkbot_instance_to_dict_masks_secrets():
    instance = SparkBotInstance(
        "demo",
        BotConfig(name="Demo", channels={"telegram": {"token": "secret"}}),
    )

    assert instance.to_dict()["channels"] == ["telegram"]
    assert instance.to_dict(mask_secrets=True)["channels"]["telegram"]["token"] == "***"
    assert instance.to_dict(include_secrets=True)["channels"]["telegram"]["token"] == "secret"

