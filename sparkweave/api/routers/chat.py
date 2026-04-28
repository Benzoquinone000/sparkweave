"""
Chat API Router
================

WebSocket endpoint for lightweight chat with session management.
REST endpoints for session operations.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from sparkweave.api.session_bridge import (
    append_stream_event,
    build_session_id,
    delete_session_with_fallback,
    get_shared_session,
    list_merged_sessions,
)
from sparkweave.core.contracts import StreamEventType
from sparkweave.logging import get_logger
from sparkweave.services.chat_generation import ChatAgent, SessionManager
from sparkweave.services.config import PROJECT_ROOT, load_config_with_main
from sparkweave.services.llm import get_llm_config
from sparkweave.services.session_store import get_sqlite_session_store
from sparkweave.services.settings import get_ui_language

# Initialize logger
config = load_config_with_main("main.yaml", PROJECT_ROOT)
log_dir = config.get("paths", {}).get("user_log_dir") or config.get("logging", {}).get("log_dir")
logger = get_logger("ChatAPI", level="INFO", log_dir=log_dir)

router = APIRouter()

# Initialize session manager
session_manager = SessionManager()
_CHAT_CAPABILITIES = {"", "chat"}


def _chat_preferences(
    *,
    kb_name: str,
    enable_rag: bool,
    enable_web_search: bool,
    language: str,
) -> dict:
    tools: list[str] = []
    if enable_rag:
        tools.append("rag")
    if enable_web_search:
        tools.append("web_search")
    knowledge_bases = [kb_name] if enable_rag and kb_name else []
    return {
        "capability": "chat",
        "tools": tools,
        "knowledge_bases": knowledge_bases,
        "language": language,
    }


def _chat_settings_from_preferences(session: dict) -> dict:
    preferences = session.get("preferences") if isinstance(session.get("preferences"), dict) else {}
    tools = {str(item) for item in preferences.get("tools", []) or []}
    knowledge_bases = [
        str(item).strip() for item in preferences.get("knowledge_bases", []) or [] if str(item).strip()
    ]
    settings = {
        "kb_name": knowledge_bases[0] if knowledge_bases else "",
        "enable_rag": "rag" in tools,
        "enable_web_search": "web_search" in tools,
    }
    language = str(preferences.get("language") or "").strip()
    if language:
        settings["language"] = language
    return settings


def _map_chat_message(message: dict) -> dict:
    payload = dict(message)
    payload["timestamp"] = payload.get("created_at", 0)
    sources = None
    for event in payload.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if isinstance(metadata.get("sources"), dict):
            sources = metadata["sources"]
            break
    if sources:
        payload["sources"] = sources
    return payload


def _map_chat_summary(session: dict) -> dict:
    return {
        "session_id": session.get("session_id"),
        "title": session.get("title"),
        "message_count": session.get("message_count", 0),
        "settings": _chat_settings_from_preferences(session),
        "created_at": session.get("created_at", 0),
        "updated_at": session.get("updated_at", 0),
        "last_message": session.get("last_message", ""),
        "status": session.get("status", "idle"),
        "active_turn_id": session.get("active_turn_id", ""),
        "capability": session.get("capability", "chat"),
    }


def _map_chat_detail(session: dict) -> dict:
    return {
        "session_id": session.get("session_id"),
        "title": session.get("title"),
        "messages": [_map_chat_message(item) for item in session.get("messages", []) or []],
        "settings": _chat_settings_from_preferences(session),
        "created_at": session.get("created_at", 0),
        "updated_at": session.get("updated_at", 0),
        "status": session.get("status", "idle"),
        "active_turn_id": session.get("active_turn_id", ""),
        "active_turns": session.get("active_turns", []),
        "capability": session.get("capability", "chat"),
    }


async def _mirror_fallback_chat_session(store, fallback_session: dict) -> dict | None:  # noqa: ANN001
    session_id = str(fallback_session.get("session_id") or "").strip()
    if not session_id:
        return None
    existing = await get_shared_session(
        store=store,
        session_id=session_id,
        capability_names=_CHAT_CAPABILITIES,
    )
    if existing is not None:
        return existing

    settings = (
        fallback_session.get("settings")
        if isinstance(fallback_session.get("settings"), dict)
        else {}
    )
    await store.create_session(
        title=str(fallback_session.get("title") or "New Chat"),
        session_id=session_id,
    )
    await store.update_session_preferences(
        session_id,
        _chat_preferences(
            kb_name=str(settings.get("kb_name") or ""),
            enable_rag=bool(settings.get("enable_rag")),
            enable_web_search=bool(settings.get("enable_web_search")),
            language=str(settings.get("language") or "en"),
        ),
    )
    for message in fallback_session.get("messages", []) or []:
        sources = message.get("sources") if isinstance(message.get("sources"), dict) else None
        events = [{"type": "result", "metadata": {"sources": sources}}] if sources else None
        await store.add_message(
            session_id=session_id,
            role=str(message.get("role") or "assistant"),
            content=str(message.get("content") or ""),
            capability="chat",
            events=events,
        )
    return await store.get_session_with_messages(session_id)


async def _load_or_create_chat_session(  # noqa: ANN001, ANN202
    *,
    store,
    requested_session_id: str | None,
    message: str,
    kb_name: str,
    enable_rag: bool,
    enable_web_search: bool,
    language: str,
):
    preferences = _chat_preferences(
        kb_name=kb_name,
        enable_rag=enable_rag,
        enable_web_search=enable_web_search,
        language=language,
    )
    requested = str(requested_session_id or "").strip()
    if requested:
        session = await get_shared_session(
            store=store,
            session_id=requested,
            capability_names=_CHAT_CAPABILITIES,
        )
        if session is None:
            fallback_session = session_manager.get_session(requested)
            if fallback_session is not None:
                session = await _mirror_fallback_chat_session(store, fallback_session)
        if session is not None:
            await store.update_session_preferences(session["id"], preferences)
            return await store.get_session_with_messages(session["id"])

    session_id = build_session_id("chat_")
    title = message[:50] + ("..." if len(message) > 50 else "")
    await store.create_session(title=title, session_id=session_id)
    await store.update_session_preferences(session_id, preferences)
    return await store.get_session_with_messages(session_id)


# =============================================================================
# REST Endpoints for Session Management
# =============================================================================


@router.get("/chat/sessions")
async def list_sessions(limit: int = 20):
    """
    List recent chat sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of session summaries
    """
    store = get_sqlite_session_store()
    fallback_sessions = session_manager.list_sessions(limit=limit, include_messages=False)
    return await list_merged_sessions(
        store=store,
        capability_names=_CHAT_CAPABILITIES,
        limit=limit,
        fallback_sessions=fallback_sessions,
        map_shared_summary=_map_chat_summary,
    )


@router.get("/chat/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get a specific chat session with full message history.

    Args:
        session_id: Session identifier

    Returns:
        Complete session data including messages
    """
    store = get_sqlite_session_store()
    session = await get_shared_session(
        store=store,
        session_id=session_id,
        capability_names=_CHAT_CAPABILITIES,
    )
    if session is not None:
        return _map_chat_detail(session)
    fallback_session = session_manager.get_session(session_id)
    if fallback_session:
        return fallback_session
    raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a chat session.

    Args:
        session_id: Session identifier

    Returns:
        Success message
    """
    store = get_sqlite_session_store()
    deleted = await delete_session_with_fallback(
        store=store,
        session_id=session_id,
        capability_names=_CHAT_CAPABILITIES,
        delete_fallback=session_manager.delete_session,
    )
    if deleted:
        return {"status": "deleted", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


# =============================================================================
# WebSocket Endpoint for Chat
# =============================================================================


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for chat with session and context management.

    Message format:
    {
        "message": str,              # User message
        "session_id": str | null,    # Session ID (null for new session)
        "history": [...] | null,     # Optional: explicit history override
        "kb_name": str,              # Knowledge base name (for RAG)
        "enable_rag": bool,          # Enable RAG retrieval
        "enable_web_search": bool    # Enable Web Search
    }

    Response format:
    - {"type": "session", "session_id": str}           # Session ID (new or existing)
    - {"type": "status", "stage": str, "message": str} # Status updates
    - {"type": "stream", "content": str}               # Streaming response chunks
    - {"type": "sources", "rag": list, "web": list}    # Source citations
    - {"type": "result", "content": str}               # Final complete response
    - {"type": "error", "message": str}                # Error message
    """
    await websocket.accept()
    store = get_sqlite_session_store()

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            # Use current UI language (fallback to config/main.yaml system.language)
            language = get_ui_language(default=config.get("system", {}).get("language", "en"))
            message = data.get("message", "").strip()
            session_id = data.get("session_id")
            explicit_history = data.get("history")  # Optional override
            kb_name = data.get("kb_name", "")
            enable_rag = data.get("enable_rag", False)
            enable_web_search = data.get("enable_web_search", False)

            if not message:
                await websocket.send_json({"type": "error", "message": "Message is required"})
                continue

            logger.info(
                f"Chat request: session={session_id}, "
                f"message={message[:50]}..., rag={enable_rag}, web={enable_web_search}"
            )

            turn = None
            try:
                session = await _load_or_create_chat_session(
                    store=store,
                    requested_session_id=session_id,
                    message=message,
                    kb_name=kb_name,
                    enable_rag=enable_rag,
                    enable_web_search=enable_web_search,
                    language=language,
                )
                session_id = str(session.get("session_id") or session.get("id") or "")
                turn = await store.create_turn(session_id, capability="chat")
                await append_stream_event(
                    store=store,
                    turn_id=turn["id"],
                    session_id=session_id,
                    event_type=StreamEventType.SESSION,
                    source="chat",
                    metadata={
                        "runtime": "ng_service",
                        "entrypoint": "chat_ws",
                        "capability": "chat",
                        "knowledge_base": kb_name if enable_rag else "",
                        "tools": [
                            name
                            for name, enabled in (
                                ("rag", enable_rag and bool(kb_name)),
                                ("web_search", enable_web_search),
                            )
                            if enabled
                        ],
                    },
                )

                # Send session ID to frontend
                await websocket.send_json(
                    {
                        "type": "session",
                        "session_id": session_id,
                    }
                )

                # Build history from session or explicit override
                if explicit_history is not None:
                    history = explicit_history
                else:
                    # Get history from session messages
                    history = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in session.get("messages", [])
                    ]

                # Add user message to session
                await store.add_message(
                    session_id=session_id,
                    role="user",
                    content=message,
                    capability="chat",
                )

                # Initialize ChatAgent
                try:
                    llm_config = get_llm_config()
                    api_key = llm_config.api_key
                    base_url = llm_config.base_url
                    api_version = getattr(llm_config, "api_version", None)
                except Exception:
                    api_key = None
                    base_url = None
                    api_version = None

                agent = ChatAgent(
                    language=language,
                    config=config,
                    api_key=api_key,
                    base_url=base_url,
                    api_version=api_version,
                )

                # Send status updates
                if enable_rag and kb_name:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "stage": "rag",
                            "message": f"Searching knowledge base: {kb_name}...",
                        }
                    )

                if enable_web_search:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "stage": "web",
                            "message": "Searching the web...",
                        }
                    )

                await websocket.send_json(
                    {
                        "type": "status",
                        "stage": "generating",
                        "message": "Generating response...",
                    }
                )

                # Process with streaming
                full_response = ""
                sources = {"rag": [], "web": []}

                stream_generator = await agent.process(
                    message=message,
                    history=history,
                    kb_name=kb_name,
                    enable_rag=enable_rag,
                    enable_web_search=enable_web_search,
                    stream=True,
                )

                async for chunk_data in stream_generator:
                    if chunk_data["type"] == "chunk":
                        await append_stream_event(
                            store=store,
                            turn_id=turn["id"],
                            session_id=session_id,
                            event_type=StreamEventType.CONTENT,
                            source="chat",
                            stage="responding",
                            content=chunk_data["content"],
                        )
                        await websocket.send_json(
                            {
                                "type": "stream",
                                "content": chunk_data["content"],
                            }
                        )
                        full_response += chunk_data["content"]
                    elif chunk_data["type"] == "complete":
                        full_response = chunk_data["response"]
                        sources = chunk_data.get("sources", {"rag": [], "web": []})

                # Send sources if any
                if sources.get("rag") or sources.get("web"):
                    await append_stream_event(
                        store=store,
                        turn_id=turn["id"],
                        session_id=session_id,
                        event_type=StreamEventType.SOURCES,
                        source="chat",
                        stage="responding",
                        metadata={"sources": sources},
                    )
                    await websocket.send_json({"type": "sources", **sources})

                # Save assistant message to session
                assistant_events = (
                    [{"type": "result", "metadata": {"sources": sources}}]
                    if (sources.get("rag") or sources.get("web"))
                    else None
                )
                await store.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    capability="chat",
                    events=assistant_events,
                )
                await append_stream_event(
                    store=store,
                    turn_id=turn["id"],
                    session_id=session_id,
                    event_type=StreamEventType.RESULT,
                    source="chat",
                    metadata={"response": full_response},
                )
                await append_stream_event(
                    store=store,
                    turn_id=turn["id"],
                    session_id=session_id,
                    event_type=StreamEventType.DONE,
                    source="chat",
                    metadata={"status": "completed"},
                )
                await store.update_turn_status(turn["id"], "completed")

                # Send final result after persistence so history endpoints are in sync.
                await websocket.send_json(
                    {
                        "type": "result",
                        "content": full_response,
                    }
                )

                logger.info(f"Chat completed: session={session_id}, {len(full_response)} chars")

            except Exception as e:
                logger.error(f"Chat processing error: {e}")
                if turn is not None:
                    try:
                        await append_stream_event(
                            store=store,
                            turn_id=turn["id"],
                            session_id=session_id,
                            event_type=StreamEventType.ERROR,
                            source="chat",
                            content=str(e),
                            metadata={"status": "failed"},
                        )
                        await append_stream_event(
                            store=store,
                            turn_id=turn["id"],
                            session_id=session_id,
                            event_type=StreamEventType.DONE,
                            source="chat",
                            metadata={"status": "failed"},
                        )
                        await store.update_turn_status(turn["id"], "failed", str(e))
                    except Exception:
                        logger.debug("Failed to update chat turn status", exc_info=True)
                await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        logger.debug("Client disconnected from chat")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


