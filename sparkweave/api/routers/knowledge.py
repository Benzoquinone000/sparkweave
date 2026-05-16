"""
Knowledge Base API Router
=========================

Handles knowledge base CRUD operations, file uploads, and initialization.
"""

from datetime import datetime
import json
import traceback

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
)
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from sparkweave.api.routers.knowledge_catalog import (
    list_knowledge_base_summaries as _list_knowledge_base_summaries,
)
from sparkweave.api.routers.knowledge_document_ops import (
    delete_document_for_kb as _delete_document_for_kb,
)
from sparkweave.api.routers.knowledge_document_ops import (
    delete_vector_for_kb as _delete_vector_for_kb,
)
from sparkweave.api.routers.knowledge_document_ops import (
    list_documents_for_kb as _list_documents_for_kb,
)
from sparkweave.api.routers.knowledge_document_ops import (
    list_vectors_for_kb as _list_vectors_for_kb,
)
from sparkweave.api.routers.knowledge_document_ops import (
    preview_document_for_kb as _preview_document_for_kb,
)
from sparkweave.api.routers.knowledge_eval_reports import (
    evaluation_strategies_or_default as _evaluation_strategies_or_default,
)
from sparkweave.api.routers.knowledge_eval_reports import (
    model_dump as _model_dump,
)
from sparkweave.api.routers.knowledge_eval_reports import (
    rag_eval_report_path as _rag_eval_report_path,
)
from sparkweave.api.routers.knowledge_eval_reports import (
    save_latest_rag_eval_report as _save_latest_rag_eval_report,
)
from sparkweave.api.routers.knowledge_folder_ops import (
    get_linked_folders_for_kb as _get_linked_folders_for_kb,
)
from sparkweave.api.routers.knowledge_folder_ops import (
    link_folder_for_kb as _link_folder_for_kb,
)
from sparkweave.api.routers.knowledge_folder_ops import (
    prepare_folder_sync_plan as _prepare_folder_sync_plan,
)
from sparkweave.api.routers.knowledge_folder_ops import (
    unlink_folder_for_kb as _unlink_folder_for_kb,
)
from sparkweave.api.routers.knowledge_guards import (
    assert_kb_writable_or_409 as _assert_kb_writable_or_409,
)
from sparkweave.api.routers.knowledge_guards import (
    load_kb_entry_or_404 as _load_kb_entry_or_404,
)
from sparkweave.api.routers.knowledge_guards import (
    validate_registered_provider as _validate_registered_provider,
)
from sparkweave.api.routers.knowledge_jobs import (
    run_initialization_job as _run_initialization_job,
)
from sparkweave.api.routers.knowledge_jobs import (
    run_reindex_processing_job as _run_reindex_processing_job,
)
from sparkweave.api.routers.knowledge_jobs import (
    run_upload_processing_job as _run_upload_processing_job,
)
from sparkweave.api.routers.knowledge_models import (
    KnowledgeBaseInfo,
    KnowledgeDocumentDeleteRequest,
    LinkedFolderInfo,
    LinkFolderRequest,
    RagEvaluationRequest,
    RagSearchTestRequest,
    ReindexKnowledgeBaseRequest,
)
from sparkweave.api.routers.knowledge_progress import (
    handle_progress_websocket as _handle_progress_websocket,
)
from sparkweave.api.routers.knowledge_rag_ops import (
    run_rag_evaluation_report as _run_rag_evaluation_report,
)
from sparkweave.api.routers.knowledge_rag_ops import (
    run_rag_search_test as _run_rag_search_test,
)
from sparkweave.api.routers.knowledge_tasking import (
    build_unique_task_id as _build_unique_task_id,
)
from sparkweave.api.routers.knowledge_tasking import (
    schedule_kb_task as _schedule_kb_task,
)
from sparkweave.api.routers.knowledge_tasking import (
    task_log as _task_log,
)
from sparkweave.api.routers.knowledge_uploads import (
    cleanup_upload_staging as _cleanup_upload_staging,
)
from sparkweave.api.routers.knowledge_uploads import (
    save_uploaded_files as _save_uploaded_files,
)
from sparkweave.api.utils.task_id_manager import TaskIDManager
from sparkweave.api.utils.task_log_stream import get_task_stream_manager
from sparkweave.knowledge.add_documents import DocumentAdder
from sparkweave.knowledge.initializer import KnowledgeBaseInitializer
from sparkweave.knowledge.manager import KnowledgeBaseManager
from sparkweave.knowledge.progress_tracker import ProgressStage, ProgressTracker
from sparkweave.knowledge.reindex import reindex_knowledge_base as rebuild_knowledge_index
from sparkweave.logging import get_logger
from sparkweave.services.config import PROJECT_ROOT, get_kb_config_service, load_config_with_main
from sparkweave.services.rag import RAGService
from sparkweave.services.rag_support.diagnostics import diagnose_rag, preflight_rag_environment
from sparkweave.services.rag_support.evaluation import (
    run_evaluation,
    summarize_dataset_profile,
)
from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER
from sparkweave.services.rag_support.file_routing import FileTypeRouter
from sparkweave.utils.error_utils import format_exception_message

# Initialize logger with config
config = load_config_with_main("main.yaml", PROJECT_ROOT)
log_dir = config.get("paths", {}).get("user_log_dir") or config.get("logging", {}).get("log_dir")
logger = get_logger("Knowledge", level="INFO", log_dir=log_dir)

router = APIRouter()

_kb_base_dir = PROJECT_ROOT / "data" / "knowledge_bases"

# Lazy initialization
kb_manager = None

def get_kb_manager():
    """Get KnowledgeBaseManager instance (lazy init)"""
    global kb_manager
    if kb_manager is None:
        kb_manager = KnowledgeBaseManager(base_dir=str(_kb_base_dir))
    return kb_manager


async def run_initialization_task(initializer: KnowledgeBaseInitializer, task_id: str):
    """Background task for knowledge base initialization."""
    await _run_initialization_job(
        initializer,
        task_id,
        manager_factory=get_kb_manager,
        task_log=_task_log,
    )


async def run_upload_processing_task(
    kb_name: str,
    base_dir: str,
    uploaded_file_paths: list[str],
    task_id: str,
    rag_provider: str = None,
    folder_id: str = None,
):
    """Background task for processing uploaded files."""
    await _run_upload_processing_job(
        kb_name=kb_name,
        base_dir=base_dir,
        uploaded_file_paths=uploaded_file_paths,
        task_id=task_id,
        manager_factory=get_kb_manager,
        document_adder_cls=DocumentAdder,
        cleanup_upload_staging=_cleanup_upload_staging,
        task_log=_task_log,
        rag_provider=rag_provider,
        folder_id=folder_id,
    )


async def run_reindex_processing_task(
    kb_name: str,
    base_dir: str,
    task_id: str,
    rag_provider: str,
    backup: bool = True,
):
    """Background task for rebuilding an existing knowledge-base index."""
    await _run_reindex_processing_job(
        kb_name=kb_name,
        base_dir=base_dir,
        task_id=task_id,
        rag_provider=rag_provider,
        rebuild_index=rebuild_knowledge_index,
        task_log=_task_log,
        backup=backup,
    )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        manager = get_kb_manager()
        config_exists = manager.config_file.exists()
        kb_count = len(manager.list_knowledge_bases())
        rag = diagnose_rag(kb_base_dir=_kb_base_dir, check_connection=False)
        return {
            "status": "ok",
            "config_file": str(manager.config_file),
            "config_exists": config_exists,
            "base_dir": str(manager.base_dir),
            "base_dir_exists": manager.base_dir.exists(),
            "knowledge_bases_count": kb_count,
            "rag": rag,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@router.get("/diagnostics")
async def get_knowledge_diagnostics(check_connection: bool = True):
    """Return RAG diagnostics for the active provider."""
    try:
        manager = get_kb_manager()
        return diagnose_rag(
            kb_base_dir=manager.base_dir,
            check_connection=check_connection,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/preflight")
async def get_knowledge_rag_preflight(check_connection: bool = True, check_docker: bool = True):
    """Return an operator-focused RAG runtime preflight."""
    try:
        manager = get_kb_manager()
        return preflight_rag_environment(
            kb_base_dir=manager.base_dir,
            check_connection=check_connection,
            check_docker=check_docker,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/rag-providers")
async def get_rag_providers():
    """Get list of available RAG providers."""
    try:
        providers = RAGService.list_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"Error getting RAG providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs")
async def get_all_kb_configs():
    """Get all knowledge base configurations from centralized config file."""
    try:
        service = get_kb_config_service()
        return service.get_all_configs()
    except Exception as e:
        logger.error(f"Error getting KB configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs/audit")
async def audit_kb_configs():
    """Audit KB config entries against on-disk knowledge-base directories."""
    try:
        manager = get_kb_manager()
        return manager.audit_registry()
    except Exception as e:
        logger.error(f"Error auditing KB configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_name}/config")
async def get_kb_config(kb_name: str):
    """Get configuration for a specific knowledge base."""
    try:
        service = get_kb_config_service()
        config = service.get_kb_config(kb_name)
        return {"kb_name": kb_name, "config": config}
    except Exception as e:
        logger.error(f"Error getting config for KB '{kb_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{kb_name}/config")
async def update_kb_config(kb_name: str, config: dict):
    """Update configuration for a specific knowledge base."""
    try:
        if "rag_provider" in config:
            config["rag_provider"] = _validate_registered_provider(config.get("rag_provider"))

        service = get_kb_config_service()
        service.set_kb_config(kb_name, config)
        return {"status": "success", "kb_name": kb_name, "config": service.get_kb_config(kb_name)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating config for KB '{kb_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configs/sync")
async def sync_configs_from_metadata():
    """Sync all KB configurations from their metadata.json files to centralized config."""
    try:
        service = get_kb_config_service()
        service.sync_all_from_metadata(_kb_base_dir)
        return {"status": "success", "message": "Configurations synced from metadata files"}
    except Exception as e:
        logger.error(f"Error syncing configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configs/prune-missing")
async def prune_missing_kb_configs(dry_run: bool = Query(False)):
    """Prune stale config entries whose KB directory no longer exists."""
    try:
        manager = get_kb_manager()
        result = manager.prune_missing_configs(dry_run=dry_run)
        try:
            get_kb_config_service().reload()
        except Exception:
            logger.debug("KB config service reload failed after prune.", exc_info=True)
        return result
    except Exception as e:
        logger.error(f"Error pruning missing KB configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/default")
async def get_default_kb():
    """Get the default knowledge base."""
    try:
        manager = get_kb_manager()
        default_kb = manager.get_default()
        return {"default_kb": default_kb}
    except Exception as e:
        logger.error(f"Error getting default KB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/default/{kb_name}")
async def set_default_kb(kb_name: str):
    """Set the default knowledge base."""
    try:
        manager = get_kb_manager()

        # Verify KB exists
        if kb_name not in manager.list_knowledge_bases():
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")

        manager.set_default(kb_name)
        return {"status": "success", "default_kb": kb_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default KB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=list[KnowledgeBaseInfo])
async def list_knowledge_bases():
    """List all available knowledge bases with their details."""
    try:
        manager = get_kb_manager()
        return _list_knowledge_base_summaries(manager, logger)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error listing knowledge bases: {e}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list knowledge bases: {e!s}")


@router.get("/{kb_name}/documents")
async def list_knowledge_base_documents(kb_name: str, include_vectors: bool = True):
    """List raw documents with cached OCR/Markdown and vector counts."""
    try:
        manager = get_kb_manager()
        kb_entry = _load_kb_entry_or_404(manager, kb_name)
        return await _list_documents_for_kb(
            manager=manager,
            kb_name=kb_name,
            kb_entry=kb_entry,
            include_vectors=include_vectors,
            validate_provider=_validate_registered_provider,
            default_provider=DEFAULT_PROVIDER,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{kb_name}/documents/{document_id}/preview")
async def preview_knowledge_base_document(
    kb_name: str,
    document_id: str,
    max_chars: int = Query(24000, ge=1000, le=200000),
    force_refresh: bool = False,
):
    """Return a Markdown preview for one raw document."""
    try:
        manager = get_kb_manager()
        _load_kb_entry_or_404(manager, kb_name)
        return await _preview_document_for_kb(
            manager=manager,
            kb_name=kb_name,
            document_id=document_id,
            max_chars=max_chars,
            force_refresh=force_refresh,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{kb_name}/vectors")
async def list_knowledge_base_vectors(
    kb_name: str,
    document_id: str | None = None,
    limit: int = Query(80, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List vector chunks stored for a KB or for one raw document."""
    try:
        manager = get_kb_manager()
        kb_entry = _load_kb_entry_or_404(manager, kb_name)
        return await _list_vectors_for_kb(
            manager=manager,
            kb_name=kb_name,
            kb_entry=kb_entry,
            document_id=document_id,
            limit=limit,
            offset=offset,
            validate_provider=_validate_registered_provider,
            default_provider=DEFAULT_PROVIDER,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{kb_name}/documents/{document_id}")
async def delete_knowledge_base_document(
    kb_name: str,
    document_id: str,
    request: KnowledgeDocumentDeleteRequest | None = None,
):
    """Delete one raw document and/or the vector rows derived from it."""
    options = request or KnowledgeDocumentDeleteRequest()
    try:
        manager = get_kb_manager()
        _load_kb_entry_or_404(manager, kb_name)
        return await _delete_document_for_kb(
            manager=manager,
            kb_name=kb_name,
            document_id=document_id,
            remove_raw=options.remove_raw,
            remove_vectors=options.remove_vectors,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{kb_name}/vectors/{node_id}")
async def delete_knowledge_base_vector(kb_name: str, node_id: str):
    """Delete one vector chunk by node id."""
    try:
        manager = get_kb_manager()
        _load_kb_entry_or_404(manager, kb_name)
        result = await _delete_vector_for_kb(manager=manager, kb_name=kb_name, node_id=node_id)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=str(result["error"]))
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{kb_name}")
async def get_knowledge_base_details(kb_name: str):
    """Get detailed info for a specific KB."""
    try:
        manager = get_kb_manager()
        return manager.get_info(kb_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_name}/diagnostics")
async def get_knowledge_base_diagnostics(kb_name: str, check_connection: bool = True):
    """Return RAG diagnostics for a specific knowledge base."""
    try:
        manager = get_kb_manager()
        _load_kb_entry_or_404(manager, kb_name)
        return diagnose_rag(
            kb_base_dir=manager.base_dir,
            kb_name=kb_name,
            check_connection=check_connection,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{kb_name}/preflight")
async def get_knowledge_base_rag_preflight(kb_name: str, check_connection: bool = True, check_docker: bool = True):
    """Return an operator-focused RAG runtime preflight for a knowledge base."""
    try:
        manager = get_kb_manager()
        _load_kb_entry_or_404(manager, kb_name)
        return preflight_rag_environment(
            kb_base_dir=manager.base_dir,
            kb_name=kb_name,
            check_connection=check_connection,
            check_docker=check_docker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{kb_name}/rag-test")
async def test_knowledge_base_rag_search(kb_name: str, request: RagSearchTestRequest):
    """Run one retrieval-only RAG query for the knowledge-base UI."""
    try:
        manager = get_kb_manager()
        kb_entry = _load_kb_entry_or_404(manager, kb_name)
        return await _run_rag_search_test(
            kb_name=kb_name,
            request=request,
            manager=manager,
            kb_entry=kb_entry,
            default_provider=DEFAULT_PROVIDER,
            validate_provider=_validate_registered_provider,
            rag_service_cls=RAGService,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{kb_name}/rag-eval")
async def evaluate_knowledge_base_rag(kb_name: str, request: RagEvaluationRequest):
    """Run a small retrieval quality evaluation against one knowledge base."""
    try:
        manager = get_kb_manager()
        kb_entry = _load_kb_entry_or_404(manager, kb_name)
        return await _run_rag_evaluation_report(
            kb_name=kb_name,
            request=request,
            manager=manager,
            kb_entry=kb_entry,
            default_provider=DEFAULT_PROVIDER,
            validate_provider=_validate_registered_provider,
            evaluation_strategies_or_default=_evaluation_strategies_or_default,
            model_dump=_model_dump,
            run_evaluation=run_evaluation,
            summarize_dataset_profile=summarize_dataset_profile,
            save_latest_report=_save_latest_rag_eval_report,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{kb_name}/rag-eval/latest")
async def get_latest_knowledge_base_rag_eval(kb_name: str):
    """Return the latest persisted retrieval quality report for one KB."""
    try:
        manager = get_kb_manager()
        _load_kb_entry_or_404(manager, kb_name)
        path = _rag_eval_report_path(manager, kb_name)
        if not path.exists():
            return {"kb_name": kb_name, "available": False, "report": None}
        return {"kb_name": kb_name, "available": True, "report": json.loads(path.read_text(encoding="utf-8"))}
    except HTTPException:
        raise
    except ValueError:
        return {"kb_name": kb_name, "available": False, "report": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{kb_name}")
async def delete_knowledge_base(kb_name: str):
    """Delete a knowledge base."""
    try:
        manager = get_kb_manager()
        success = manager.delete_knowledge_base(kb_name, confirm=True)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to delete knowledge base")
        logger.info(f"KB '{kb_name}' deleted")
        return {"message": f"Knowledge base '{kb_name}' deleted successfully"}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_name}/reindex")
async def reindex_knowledge_base(
    kb_name: str,
    background_tasks: BackgroundTasks,
    request: ReindexKnowledgeBaseRequest | None = None,
):
    """Rebuild an existing knowledge base from its raw files."""
    try:
        manager = get_kb_manager()
        kb_entry = _load_kb_entry_or_404(manager, kb_name)
        payload = request or ReindexKnowledgeBaseRequest()
        rag_provider = _validate_registered_provider(
            payload.rag_provider or kb_entry.get("rag_provider") or DEFAULT_PROVIDER
        )

        task_id = _build_unique_task_id("kb_reindex", kb_name)
        get_task_stream_manager().ensure_task(task_id)

        manager.update_kb_status(
            name=kb_name,
            status="processing",
            progress={
                "stage": "reindexing",
                "message": "正在重建知识库索引...",
                "percent": 0,
                "current": 0,
                "total": 0,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
            },
        )
        manager.config = manager._load_config()
        entry = manager.config.setdefault("knowledge_bases", {}).setdefault(kb_name, {})
        entry["rag_provider"] = rag_provider
        manager._save_config()

        _ = background_tasks
        _schedule_kb_task(
            task_id,
            run_reindex_processing_task,
            kb_name=kb_name,
            base_dir=str(_kb_base_dir),
            task_id=task_id,
            rag_provider=rag_provider,
            backup=payload.backup,
        )

        return {
            "message": f"Knowledge base '{kb_name}' reindex started.",
            "name": kb_name,
            "task_id": task_id,
            "rag_provider": rag_provider,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tasks/{task_id}/stream")
async def stream_task_logs(task_id: str):
    """Stream task-specific logs for knowledge-base operations."""
    manager = get_task_stream_manager()
    manager.ensure_task(task_id)
    return StreamingResponse(
        manager.stream(task_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Return an in-memory status snapshot for a knowledge-base task."""
    task_metadata = TaskIDManager.get_instance().get_task_metadata(task_id)
    stream_snapshot = get_task_stream_manager().snapshot(task_id)
    if not task_metadata and stream_snapshot["event_count"] == 0:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {
        "task_id": task_id,
        "known": task_metadata is not None,
        "metadata": task_metadata or {},
        "stream": stream_snapshot,
    }


@router.post("/{kb_name}/upload")
async def upload_files(
    kb_name: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    rag_provider: str = Form(None),
):
    """Upload files to a knowledge base and process them in background."""
    try:
        manager = get_kb_manager()
        kb_path = manager.get_knowledge_base_path(kb_name)
        raw_dir = kb_path / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        requested_provider = None
        if rag_provider is not None and str(rag_provider).strip():
            requested_provider = _validate_registered_provider(rag_provider)

        kb_entry = _load_kb_entry_or_404(manager, kb_name)
        _assert_kb_writable_or_409(kb_name, kb_entry)
        kb_provider = _validate_registered_provider(kb_entry.get("rag_provider") or DEFAULT_PROVIDER)
        if requested_provider and requested_provider != kb_provider:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Requested provider '{requested_provider}' does not match KB provider '{kb_provider}'. "
                    "Update KB config first."
                ),
            )
        task_id = _build_unique_task_id("kb_upload", kb_name)
        get_task_stream_manager().ensure_task(task_id)

        allowed_extensions = FileTypeRouter.get_supported_extensions()
        staging_dir = kb_path / ".uploads" / task_id
        uploaded_files, uploaded_file_paths = await run_in_threadpool(
            _save_uploaded_files,
            files, staging_dir, allowed_extensions=allowed_extensions
        )

        logger.info(f"Uploading {len(uploaded_files)} files to KB '{kb_name}'")

        _ = background_tasks
        _schedule_kb_task(
            task_id,
            run_upload_processing_task,
            kb_name=kb_name,
            base_dir=str(_kb_base_dir),
            uploaded_file_paths=uploaded_file_paths,
            task_id=task_id,
            rag_provider=kb_provider,
        )

        return {
            "message": f"Uploaded {len(uploaded_files)} files. Processing in background.",
            "files": uploaded_files,
            "task_id": task_id,
        }
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    except Exception as e:
        # Unexpected failure (Server error)
        formatted_error = format_exception_message(e)
        raise HTTPException(status_code=500, detail=formatted_error) from e


@router.post("/create")
async def create_knowledge_base(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    files: list[UploadFile] = File(...),
    rag_provider: str = Form(DEFAULT_PROVIDER),
):
    """Create a new knowledge base and initialize it with files."""
    try:
        manager = get_kb_manager()
        if name in manager.list_knowledge_bases():
            raise HTTPException(status_code=400, detail=f"Knowledge base '{name}' already exists")

        rag_provider = _validate_registered_provider(rag_provider)

        logger.info(f"Creating KB: {name}")
        task_id = _build_unique_task_id("kb_init", name)
        get_task_stream_manager().ensure_task(task_id)

        # Register KB to kb_config.json immediately with "initializing" status
        # This ensures the KB appears in the list right away
        manager.update_kb_status(
            name=name,
            status="initializing",
            progress={
                "stage": "initializing",
                "message": "Initializing knowledge base...",
                "percent": 0,
                "current": 0,
                "total": len(files),
                "task_id": task_id,
            },
        )
        # Also store rag_provider in config (reload and update)
        manager.config = manager._load_config()
        if name in manager.config.get("knowledge_bases", {}):
            manager.config["knowledge_bases"][name]["rag_provider"] = rag_provider
            manager.config["knowledge_bases"][name]["needs_reindex"] = False
            manager._save_config()

        progress_tracker = ProgressTracker(name, _kb_base_dir)

        initializer = KnowledgeBaseInitializer(
            kb_name=name,
            base_dir=str(_kb_base_dir),
            progress_tracker=progress_tracker,
            rag_provider=rag_provider,
        )

        initializer.create_directory_structure()
        progress_tracker.task_id = task_id

        manager = get_kb_manager()
        if name not in manager.list_knowledge_bases():
            logger.warning(f"KB {name} not found in config, registering manually")
            initializer._register_to_config()

        allowed_extensions = FileTypeRouter.get_supported_extensions()
        uploaded_files, _ = await run_in_threadpool(
            _save_uploaded_files,
            files, initializer.raw_dir, allowed_extensions=allowed_extensions
        )

        progress_tracker.update(
            ProgressStage.PROCESSING_DOCUMENTS,
            f"Saved {len(uploaded_files)} files, preparing to process...",
            current=0,
            total=len(uploaded_files),
        )

        _ = background_tasks
        _schedule_kb_task(task_id, run_initialization_task, initializer, task_id)

        logger.success(f"KB '{name}' created, processing {len(uploaded_files)} files in background")

        return {
            "message": f"Knowledge base '{name}' created. Processing {len(uploaded_files)} files in background.",
            "name": name,
            "files": uploaded_files,
            "task_id": task_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create KB: {e}")
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_name}/progress")
async def get_progress(kb_name: str):
    """Get initialization progress for a knowledge base"""
    try:
        progress_tracker = ProgressTracker(kb_name, _kb_base_dir)
        progress = progress_tracker.get_progress()

        if progress is None:
            return {"status": "not_started", "message": "Initialization not started"}

        return progress
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_name}/progress/clear")
async def clear_progress(kb_name: str):
    """Clear progress file for a knowledge base (useful for stuck states)"""
    try:
        progress_tracker = ProgressTracker(kb_name, _kb_base_dir)
        progress_tracker.clear()
        return {"status": "success", "message": f"Progress cleared for {kb_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/{kb_name}/progress/ws")
async def websocket_progress(websocket: WebSocket, kb_name: str):
    """WebSocket endpoint for real-time progress updates"""
    from sparkweave.api.utils.progress_broadcaster import ProgressBroadcaster

    await _handle_progress_websocket(
        websocket,
        kb_name,
        broadcaster=ProgressBroadcaster.get_instance(),
        progress_tracker=ProgressTracker(kb_name, _kb_base_dir),
        manager_factory=get_kb_manager,
        logger=logger,
    )


@router.post("/{kb_name}/link-folder", response_model=LinkedFolderInfo)
async def link_folder(kb_name: str, request: LinkFolderRequest):
    """
    Link a local folder to a knowledge base.

    This allows syncing documents from a local folder (which can be
    synced with SharePoint, Google Drive, OneLake, etc.) to the KB.

    The folder path supports:
    - Absolute paths: /Users/name/Documents or C:\\Users\\name\\Documents
    - Home directory: ~/Documents
    - Relative paths (resolved from server working directory)
    """
    try:
        manager = get_kb_manager()
        folder_info = _link_folder_for_kb(manager, kb_name, request.folder_path)
        logger.info(f"Linked folder '{request.folder_path}' to KB '{kb_name}'")
        return LinkedFolderInfo(**folder_info)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_name}/linked-folders", response_model=list[LinkedFolderInfo])
async def get_linked_folders(kb_name: str):
    """Get list of linked folders for a knowledge base."""
    try:
        manager = get_kb_manager()
        folders = _get_linked_folders_for_kb(manager, kb_name)
        return [LinkedFolderInfo(**f) for f in folders]
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_name}/linked-folders/{folder_id}")
async def unlink_folder(kb_name: str, folder_id: str):
    """Unlink a folder from a knowledge base."""
    try:
        manager = get_kb_manager()
        result = _unlink_folder_for_kb(manager, kb_name, folder_id)
        logger.info(f"Unlinked folder '{folder_id}' from KB '{kb_name}'")
        return result
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_name}/sync-folder/{folder_id}")
async def sync_folder(kb_name: str, folder_id: str, background_tasks: BackgroundTasks):
    """
    Sync files from a linked folder to the knowledge base.

    This scans the linked folder for supported documents and processes
    any new files that haven't been added yet.
    """
    try:
        manager = get_kb_manager()
        kb_entry = _load_kb_entry_or_404(manager, kb_name)
        _assert_kb_writable_or_409(kb_name, kb_entry)
        sync_plan = _prepare_folder_sync_plan(
            manager=manager,
            kb_name=kb_name,
            folder_id=folder_id,
            kb_entry=kb_entry,
            validate_provider=_validate_registered_provider,
            default_provider=DEFAULT_PROVIDER,
            build_task_id=_build_unique_task_id,
            ensure_task=get_task_stream_manager().ensure_task,
            logger=logger,
        )

        if not sync_plan["should_schedule"]:
            return sync_plan["response"]

        # NOTE: We DO NOT update sync state here anymore.
        # It is updated in run_upload_processing_task only after successful processing.
        # This prevents marking files as synced if processing fails (race condition fix).

        # Add background task to process files
        _ = background_tasks
        _schedule_kb_task(
            sync_plan["task_id"],
            run_upload_processing_task,
            kb_name=kb_name,
            base_dir=str(_kb_base_dir),
            uploaded_file_paths=sync_plan["files_to_process"],
            task_id=sync_plan["task_id"],
            rag_provider=sync_plan["kb_provider"],
            folder_id=folder_id,  # Pass folder_id to update state on success
        )

        return sync_plan["response"]
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


