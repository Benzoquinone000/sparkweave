"""Progress streaming helpers for knowledge-base API routes."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


async def handle_progress_websocket(
    websocket: WebSocket,
    kb_name: str,
    *,
    broadcaster: Any,
    progress_tracker: Any,
    manager_factory: Any,
    logger: Any,
) -> None:
    """Stream knowledge-base indexing progress to a WebSocket client."""
    await websocket.accept()

    try:
        await broadcaster.connect(kb_name, websocket)

        initial_progress = progress_tracker.get_progress()
        expected_task_id = websocket.query_params.get("task_id")

        try:
            kb_info = manager_factory().get_info(kb_name)
            kb_is_ready = (
                kb_info.get("status") == "ready"
                and bool((kb_info.get("statistics") or {}).get("rag_initialized"))
            )
        except Exception:
            kb_is_ready = False

        has_active_task = False
        if initial_progress:
            stage = initial_progress.get("stage")
            if stage not in ("completed", "error", None):
                ts = initial_progress.get("timestamp")
                if ts:
                    try:
                        age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
                        has_active_task = age < 120
                    except Exception:
                        pass

        if not has_active_task and not expected_task_id:
            if kb_is_ready:
                await websocket.send_json({
                    "type": "progress",
                    "data": {
                        "stage": "completed",
                        "message": "Knowledge base is ready.",
                        "percent": 100,
                        "current": 1,
                        "total": 1,
                    },
                })
            else:
                await websocket.send_json({
                    "type": "progress",
                    "data": initial_progress
                    or {
                        "stage": "error",
                        "message": "Knowledge base needs reindex or initialization.",
                    },
                })
            return

        if initial_progress:
            stage = initial_progress.get("stage")
            timestamp = initial_progress.get("timestamp")
            progress_task_id = initial_progress.get("task_id")

            should_send = False
            if expected_task_id and progress_task_id and progress_task_id != expected_task_id:
                should_send = False
            elif stage == "error" or not kb_is_ready:
                should_send = True
            elif stage != "completed" and timestamp:
                try:
                    progress_time = datetime.fromisoformat(timestamp)
                    now = datetime.now()
                    age_seconds = (now - progress_time).total_seconds()
                    if age_seconds < 300:
                        should_send = True
                except Exception:
                    pass

            if should_send:
                await websocket.send_json({"type": "progress", "data": initial_progress})

        last_timestamp = initial_progress.get("timestamp") if initial_progress else None

        while True:
            try:
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                except asyncio.TimeoutError:
                    current_progress = progress_tracker.get_progress()
                    if current_progress:
                        progress_task_id = current_progress.get("task_id")
                        if expected_task_id and progress_task_id and progress_task_id != expected_task_id:
                            continue
                        current_timestamp = current_progress.get("timestamp")
                        if current_timestamp != last_timestamp:
                            await websocket.send_json(
                                {"type": "progress", "data": current_progress}
                            )
                            last_timestamp = current_timestamp

                            if current_progress.get("stage") in ["completed", "error"]:
                                await asyncio.sleep(3)
                                break
                    continue

            except WebSocketDisconnect:
                break
            except Exception:
                break

    except Exception as exc:
        logger.debug("Progress WS error: %s", exc)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        await broadcaster.disconnect(kb_name, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
