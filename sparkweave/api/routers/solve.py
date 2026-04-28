"""
Solve API Router
================

WebSocket endpoint for real-time problem solving with streaming logs.
"""

import asyncio
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from sparkweave.api.session_bridge import (
    append_stream_event,
    build_session_id,
    delete_session_with_fallback,
    get_shared_session,
    list_merged_sessions,
)
from sparkweave.api.utils.log_interceptor import LogInterceptor
from sparkweave.api.utils.task_id_manager import TaskIDManager
from sparkweave.core.contracts import StreamEventType
from sparkweave.logging import get_logger
from sparkweave.services.config import PROJECT_ROOT, load_config_with_main
from sparkweave.services.llm import get_llm_config
from sparkweave.services.paths import get_path_service
from sparkweave.services.session_store import get_sqlite_session_store
from sparkweave.services.settings import get_ui_language
from sparkweave.services.solve_generation import (
    DeepSolveCapability,
    MainSolver,
    SolverSessionManager,
)

# Initialize logger with config
config = load_config_with_main("main.yaml", PROJECT_ROOT)
log_dir = config.get("paths", {}).get("user_log_dir") or config.get("logging", {}).get("log_dir")
logger = get_logger("SolveAPI", level="INFO", log_dir=log_dir)

router = APIRouter()

# Initialize session manager
solver_session_manager = SolverSessionManager()
_SOLVE_CAPABILITIES = {"deep_solve"}


def _solve_preferences(
    *,
    kb_name: str,
    enabled_tools: list[str],
    language: str,
    token_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "capability": "deep_solve",
        "tools": list(enabled_tools),
        "knowledge_bases": [kb_name] if kb_name else [],
        "language": language,
        "token_stats": token_stats or SolverSessionManager.DEFAULT_TOKEN_STATS.copy(),
    }


def _solve_kb_name(session: dict) -> str:
    preferences = session.get("preferences") if isinstance(session.get("preferences"), dict) else {}
    knowledge_bases = [
        str(item).strip() for item in preferences.get("knowledge_bases", []) or [] if str(item).strip()
    ]
    return knowledge_bases[0] if knowledge_bases else ""


def _solve_token_stats(session: dict) -> dict[str, Any]:
    preferences = session.get("preferences") if isinstance(session.get("preferences"), dict) else {}
    token_stats = preferences.get("token_stats")
    if isinstance(token_stats, dict):
        return {
            **SolverSessionManager.DEFAULT_TOKEN_STATS.copy(),
            **token_stats,
        }
    return SolverSessionManager.DEFAULT_TOKEN_STATS.copy()


def _map_solve_message(message: dict) -> dict:
    payload = dict(message)
    payload["timestamp"] = payload.get("created_at", 0)
    for event in payload.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        output_dir_name = str(metadata.get("output_dir_name") or "").strip()
        if output_dir_name:
            payload["output_dir"] = output_dir_name
            break
    return payload


def _map_solve_summary(session: dict) -> dict:
    return {
        "session_id": session.get("session_id"),
        "title": session.get("title"),
        "message_count": session.get("message_count", 0),
        "kb_name": _solve_kb_name(session),
        "token_stats": _solve_token_stats(session),
        "created_at": session.get("created_at", 0),
        "updated_at": session.get("updated_at", 0),
        "last_message": session.get("last_message", ""),
        "status": session.get("status", "idle"),
        "active_turn_id": session.get("active_turn_id", ""),
        "capability": session.get("capability", "deep_solve"),
    }


def _map_solve_detail(session: dict) -> dict:
    return {
        "session_id": session.get("session_id"),
        "title": session.get("title"),
        "messages": [_map_solve_message(item) for item in session.get("messages", []) or []],
        "kb_name": _solve_kb_name(session),
        "token_stats": _solve_token_stats(session),
        "created_at": session.get("created_at", 0),
        "updated_at": session.get("updated_at", 0),
        "status": session.get("status", "idle"),
        "active_turn_id": session.get("active_turn_id", ""),
        "active_turns": session.get("active_turns", []),
        "capability": session.get("capability", "deep_solve"),
    }


async def _mirror_fallback_solve_session(store, fallback_session: dict) -> dict | None:  # noqa: ANN001
    session_id = str(fallback_session.get("session_id") or "").strip()
    if not session_id:
        return None
    existing = await get_shared_session(
        store=store,
        session_id=session_id,
        capability_names=_SOLVE_CAPABILITIES,
    )
    if existing is not None:
        return existing

    kb_name = str(fallback_session.get("kb_name") or "")
    token_stats = fallback_session.get("token_stats")
    inferred_tools = ["rag"] if kb_name else []
    await store.create_session(
        title=str(fallback_session.get("title") or "New Solver Session"),
        session_id=session_id,
    )
    await store.update_session_preferences(
        session_id,
        _solve_preferences(
            kb_name=kb_name,
            enabled_tools=inferred_tools,
            language="en",
            token_stats=token_stats if isinstance(token_stats, dict) else None,
        ),
    )
    for message in fallback_session.get("messages", []) or []:
        output_dir = str(message.get("output_dir") or "").strip()
        events = (
            [{"type": "result", "metadata": {"output_dir_name": output_dir}}]
            if output_dir
            else None
        )
        await store.add_message(
            session_id=session_id,
            role=str(message.get("role") or "assistant"),
            content=str(message.get("content") or ""),
            capability="deep_solve",
            events=events,
        )
    return await store.get_session_with_messages(session_id)


async def _load_or_create_solve_session(  # noqa: ANN001, ANN202
    *,
    store,
    requested_session_id: str | None,
    question: str,
    kb_name: str | None,
    enabled_tools: list[str],
    language: str,
):
    preferences = _solve_preferences(
        kb_name=str(kb_name or ""),
        enabled_tools=enabled_tools,
        language=language,
    )
    requested = str(requested_session_id or "").strip()
    if requested:
        session = await get_shared_session(
            store=store,
            session_id=requested,
            capability_names=_SOLVE_CAPABILITIES,
        )
        if session is None:
            fallback_session = solver_session_manager.get_session(requested)
            if fallback_session is not None:
                session = await _mirror_fallback_solve_session(store, fallback_session)
        if session is not None:
            await store.update_session_preferences(session["id"], preferences)
            return await store.get_session_with_messages(session["id"])

    session_id = build_session_id("solve_")
    title = question[:50] + ("..." if len(question) > 50 else "")
    await store.create_session(title=title, session_id=session_id)
    await store.update_session_preferences(session_id, preferences)
    return await store.get_session_with_messages(session_id)


# =============================================================================
# REST Endpoints for Session Management
# =============================================================================


@router.get("/solve/sessions")
async def list_solver_sessions(limit: int = 20):
    """
    List recent solver sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of session summaries
    """
    store = get_sqlite_session_store()
    fallback_sessions = solver_session_manager.list_sessions(limit=limit, include_messages=False)
    return await list_merged_sessions(
        store=store,
        capability_names=_SOLVE_CAPABILITIES,
        limit=limit,
        fallback_sessions=fallback_sessions,
        map_shared_summary=_map_solve_summary,
    )


@router.get("/solve/sessions/{session_id}")
async def get_solver_session(session_id: str):
    """
    Get a specific solver session with full message history.

    Args:
        session_id: Session identifier

    Returns:
        Complete session data including messages
    """
    store = get_sqlite_session_store()
    session = await get_shared_session(
        store=store,
        session_id=session_id,
        capability_names=_SOLVE_CAPABILITIES,
    )
    if session is not None:
        return _map_solve_detail(session)
    fallback_session = solver_session_manager.get_session(session_id)
    if fallback_session:
        return fallback_session
    raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/solve/sessions/{session_id}")
async def delete_solver_session(session_id: str):
    """
    Delete a solver session.

    Args:
        session_id: Session identifier

    Returns:
        Success message
    """
    store = get_sqlite_session_store()
    deleted = await delete_session_with_fallback(
        store=store,
        session_id=session_id,
        capability_names=_SOLVE_CAPABILITIES,
        delete_fallback=solver_session_manager.delete_session,
    )
    if deleted:
        return {"status": "deleted", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


# =============================================================================
# WebSocket Endpoint for Solving
# =============================================================================


@router.websocket("/solve")
async def websocket_solve(websocket: WebSocket):
    await websocket.accept()

    store = get_sqlite_session_store()
    task_manager = TaskIDManager.get_instance()
    connection_closed = asyncio.Event()
    log_queue = asyncio.Queue()
    pusher_task = None

    async def safe_send_json(data: dict[str, Any]):
        """Safely send JSON to WebSocket, checking if connection is closed"""
        if connection_closed.is_set():
            return False
        try:
            await websocket.send_json(data)
            return True
        except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
            logger.debug(f"WebSocket connection closed: {e}")
            connection_closed.set()
            return False
        except Exception as e:
            logger.debug(f"Error sending WebSocket message: {e}")
            return False

    async def log_pusher():
        while not connection_closed.is_set():
            try:
                # Use timeout to periodically check if connection is closed
                entry = await asyncio.wait_for(log_queue.get(), timeout=0.5)
                try:
                    await websocket.send_json(entry)
                except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                    # Connection closed, stop pushing
                    logger.debug(f"WebSocket connection closed in log_pusher: {e}")
                    connection_closed.set()
                    log_queue.task_done()
                    break
                except Exception as e:
                    logger.debug(f"Error sending log entry: {e}")
                    # Continue to next entry
                log_queue.task_done()
            except asyncio.TimeoutError:
                # Timeout, check if connection is still open
                continue
            except Exception as e:
                logger.debug(f"Error in log_pusher: {e}")
                break

    session_id = None  # Track session for this connection
    turn = None

    try:
        # 1. Wait for the initial message with the question and config
        data = await websocket.receive_json()
        question = data.get("question")
        tools = data.get("tools")
        enabled_tools = (
            list(DeepSolveCapability.manifest.tools_used)
            if tools is None
            else [str(name) for name in tools]
        )
        rag_enabled = "rag" in enabled_tools
        kb_name = data.get("kb_name", "ai-textbook") if rag_enabled else None
        session_id = data.get("session_id")  # Optional session ID
        detailed_answer = data.get("detailed_answer", False)  # Iterative detailed mode

        if not question:
            await websocket.send_json({"type": "error", "content": "Question is required"})
            return

        ui_language = get_ui_language(default=config.get("system", {}).get("language", "en"))
        session = await _load_or_create_solve_session(
            store=store,
            requested_session_id=session_id,
            question=question,
            kb_name=kb_name,
            enabled_tools=enabled_tools,
            language=ui_language,
        )
        session_id = str(session.get("session_id") or session.get("id") or "")
        turn = await store.create_turn(session_id, capability="deep_solve")
        await append_stream_event(
            store=store,
            turn_id=turn["id"],
            session_id=session_id,
            event_type=StreamEventType.SESSION,
            source="deep_solve",
            metadata={
                "runtime": "ng_service",
                "entrypoint": "solve_ws",
                "capability": "deep_solve",
                "knowledge_base": kb_name or "",
                "tools": enabled_tools,
            },
        )

        # Send session ID to frontend
        await websocket.send_json({"type": "session", "session_id": session_id})

        # Add user message to session
        await store.add_message(
            session_id=session_id,
            role="user",
            content=question,
            capability="deep_solve",
        )

        task_key = f"solve_{kb_name}_{hash(str(question))}"
        task_id = task_manager.generate_task_id("solve", task_key)

        await websocket.send_json({"type": "task_id", "task_id": task_id})

        # 2. Initialize Solver
        path_service = get_path_service()
        output_base = path_service.get_solve_dir()

        try:
            llm_config = get_llm_config()
            api_key = llm_config.api_key
            base_url = llm_config.base_url
            api_version = getattr(llm_config, "api_version", None)
        except Exception as e:
            logger.error(f"Failed to get LLM config: {e}", exc_info=True)
            await websocket.send_json({"type": "error", "content": f"LLM configuration error: {e}"})
            return

        solver = MainSolver(
            kb_name=kb_name,
            output_base_dir=str(output_base),
            api_key=api_key,
            base_url=base_url,
            api_version=api_version,
            language=ui_language,
            enabled_tools=enabled_tools,
            disable_planner_retrieve=not (rag_enabled and kb_name),
        )

        # Complete async initialization
        await solver.ainit()

        logger.info(f"[{task_id}] Solving: {question[:50]}...")

        target_logger = solver.logger.logger

        # Note: System log forwarder removed - all logs now go to unified log file
        # The main logger already writes to data/user/logs/ai_tutor_YYYYMMDD.log

        # 3. Setup Log Queue
        # log_queue already initialized

        # 4. Setup status update mechanism
        display_manager = None
        if hasattr(solver.logger, "display_manager") and solver.logger.display_manager:
            display_manager = solver.logger.display_manager

            original_set_status = display_manager.set_agent_status

            def wrapped_set_status(agent_name: str, status: str):
                original_set_status(agent_name, status)
                try:
                    log_queue.put_nowait(
                        {
                            "type": "agent_status",
                            "agent": agent_name,
                            "status": status,
                            "all_agents": display_manager.agents_status.copy(),
                        }
                    )
                except Exception:
                    pass

            display_manager.set_agent_status = wrapped_set_status

            original_update_stats = display_manager.update_token_stats

            def wrapped_update_stats(summary: dict[str, Any]):
                original_update_stats(summary)
                try:
                    stats_copy = display_manager.stats.copy()
                    logger.debug(
                        f"Sending token_stats: model={stats_copy.get('model')}, calls={stats_copy.get('calls')}, cost={stats_copy.get('cost')}"
                    )
                    log_queue.put_nowait({"type": "token_stats", "stats": stats_copy})
                except Exception as e:
                    logger.debug(f"Failed to send token_stats: {e}")

            display_manager.update_token_stats = wrapped_update_stats

            # Re-register the callback to use the wrapped method
            # (The callback was set before wrapping in main_solver.py)
            if hasattr(solver, "token_tracker") and solver.token_tracker:
                solver.token_tracker.set_on_usage_added_callback(wrapped_update_stats)

        def send_progress_update(stage: str, progress: dict[str, Any]):
            """Send progress update to frontend"""
            try:
                log_queue.put_nowait({"type": "progress", "stage": stage, "progress": progress})
            except Exception:
                pass

        solver._send_progress_update = send_progress_update

        # 5. Background task to push logs to WebSocket
        pusher_task = asyncio.create_task(log_pusher())

        # 6. Run Solver within the LogInterceptor context
        interceptor = LogInterceptor(target_logger, log_queue)
        with interceptor:
            await safe_send_json({"type": "status", "content": "started"})

            if display_manager:
                await safe_send_json(
                    {
                        "type": "agent_status",
                        "agent": "all",
                        "status": "initial",
                        "all_agents": display_manager.agents_status.copy(),
                    }
                )
                await safe_send_json({"type": "token_stats", "stats": display_manager.stats.copy()})

            logger.progress(f"[{task_id}] Solving started")

            result = await solver.solve(question, verbose=True, detailed=detailed_answer)

            logger.success(f"[{task_id}] Solving completed")
            task_manager.update_task_status(task_id, "completed")

            # Process Markdown content to fix image paths
            final_answer = result.get("final_answer", "")
            output_dir_str = result.get("output_dir", "")

            if output_dir_str and final_answer:
                try:
                    output_dir = Path(output_dir_str)

                    if not output_dir.is_absolute():
                        output_dir = output_dir.resolve()

                    path_str = str(output_dir).replace("\\", "/")
                    parts = path_str.split("/")

                    if "user" in parts:
                        idx = parts.index("user")
                        rel_path = "/".join(parts[idx + 1 :])
                        base_url = f"/api/outputs/{rel_path}"

                        pattern = r"\]\(artifacts/([^)]+)\)"
                        replacement = rf"]({base_url}/artifacts/\1)"
                        final_answer = re.sub(pattern, replacement, final_answer)
                except Exception as e:
                    logger.debug(f"Error processing image paths: {e}")

            # Send final agent status update
            if display_manager:
                final_agent_status = dict.fromkeys(display_manager.agents_status.keys(), "done")
                await safe_send_json(
                    {
                        "type": "agent_status",
                        "agent": "all",
                        "status": "complete",
                        "all_agents": final_agent_status,
                    }
                )

            # Send final result
            # Extract relative path from output_dir for frontend use
            dir_name = ""
            if output_dir_str:
                parts = output_dir_str.replace("\\", "/").split("/")
                dir_name = parts[-1] if parts else ""

            # Save assistant message to session
            if session_id:
                await store.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=final_answer,
                    capability="deep_solve",
                    events=[
                        {
                            "type": "result",
                            "metadata": {
                                "output_dir": output_dir_str,
                                "output_dir_name": dir_name,
                            },
                        }
                    ],
                )
                # Update token stats in session
                if display_manager:
                    await store.update_session_preferences(
                        session_id=session_id,
                        preferences={
                            "token_stats": display_manager.stats.copy(),
                        },
                    )
                if turn is not None:
                    await append_stream_event(
                        store=store,
                        turn_id=turn["id"],
                        session_id=session_id,
                        event_type=StreamEventType.RESULT,
                        source="deep_solve",
                        metadata={
                            "response": final_answer,
                            "output_dir": output_dir_str,
                            "output_dir_name": dir_name,
                            "result_metadata": result.get("metadata"),
                        },
                    )
                    await append_stream_event(
                        store=store,
                        turn_id=turn["id"],
                        session_id=session_id,
                        event_type=StreamEventType.DONE,
                        source="deep_solve",
                        metadata={"status": "completed"},
                    )
                    await store.update_turn_status(turn["id"], "completed")

            final_res = {
                "type": "result",
                "session_id": session_id,
                "final_answer": final_answer,
                "output_dir": output_dir_str,
                "output_dir_name": dir_name,
                "metadata": result.get("metadata"),
            }
            await safe_send_json(final_res)

    except Exception as e:
        # Mark connection as closed before sending error (to prevent log_pusher from interfering)
        connection_closed.set()
        if turn is not None:
            try:
                await append_stream_event(
                    store=store,
                    turn_id=turn["id"],
                    session_id=session_id or "",
                    event_type=StreamEventType.ERROR,
                    source="deep_solve",
                    content=str(e),
                    metadata={"status": "failed"},
                )
                await append_stream_event(
                    store=store,
                    turn_id=turn["id"],
                    session_id=session_id or "",
                    event_type=StreamEventType.DONE,
                    source="deep_solve",
                    metadata={"status": "failed"},
                )
                await store.update_turn_status(turn["id"], "failed", str(e))
            except Exception:
                logger.debug("Failed to update solve turn status", exc_info=True)
        await safe_send_json({"type": "error", "content": str(e)})
        logger.error(f"[{task_id if 'task_id' in locals() else 'unknown'}] Solving failed: {e}")
        if "task_id" in locals():
            task_manager.update_task_status(task_id, "error", error=str(e))
    finally:
        # Stop log pusher first
        connection_closed.set()
        if pusher_task:
            pusher_task.cancel()
            try:
                await pusher_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"Error waiting for pusher task: {e}")

        # Close WebSocket connection
        try:
            # Check if connection is still open before closing
            if hasattr(websocket, "client_state"):
                state = websocket.client_state
                if hasattr(state, "name") and state.name != "DISCONNECTED":
                    await websocket.close()
            else:
                # Fallback: try to close anyway
                await websocket.close()
        except (WebSocketDisconnect, RuntimeError, ConnectionError):
            # Connection already closed, ignore
            pass
        except Exception as e:
            logger.debug(f"Error closing WebSocket: {e}")


