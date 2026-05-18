import pytest

from sparkweave.utils.document_validator import DocumentValidator


def test_validate_upload_allows_python_text_mime_for_supported_rag_extension():
    assert (
        DocumentValidator.validate_upload_safety(
            "py_tf_listener.py",
            128,
            allowed_extensions={".py"},
        )
        == "py_tf_listener.py"
    )


def test_validate_upload_allows_image_mime_for_supported_rag_extension():
    assert (
        DocumentValidator.validate_upload_safety(
            "ocr_smoke.png",
            128,
            allowed_extensions={".png"},
        )
        == "ocr_smoke.png"
    )


def test_validate_upload_still_rejects_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        DocumentValidator.validate_upload_safety(
            "script.exe",
            128,
            allowed_extensions={".py"},
        )


def test_validate_upload_normalizes_cross_platform_paths():
    assert DocumentValidator.validate_upload_safety(r"..\lesson.pdf", 128) == "lesson.pdf"
    assert DocumentValidator.validate_upload_safety("../../notes.md ", 128) == "notes.md"


@pytest.mark.parametrize("filename", ["CON.txt", "aux.pdf", "LPT1.md"])
def test_validate_upload_rejects_windows_reserved_names(filename: str):
    with pytest.raises(ValueError, match="Reserved filename"):
        DocumentValidator.validate_upload_safety(filename, 128)


def test_validate_upload_rejects_declared_mime_extension_mismatch():
    with pytest.raises(ValueError, match="does not match file extension"):
        DocumentValidator.validate_upload_safety("lesson.pdf", 128, content_type="text/html")


def test_validate_upload_allows_generic_browser_mime_for_supported_extension():
    assert (
        DocumentValidator.validate_upload_safety(
            "lesson.pdf",
            128,
            content_type="application/octet-stream",
        )
        == "lesson.pdf"
    )


def test_validate_upload_allows_plain_text_mime_for_text_documents():
    assert (
        DocumentValidator.validate_upload_safety(
            "lesson.json",
            128,
            content_type="text/plain",
        )
        == "lesson.json"
    )


def test_validate_upload_truncates_long_filename_without_losing_extension():
    name = f"{'a' * 240}.txt"
    safe = DocumentValidator.validate_upload_safety(name, 128)

    assert len(safe) == DocumentValidator.MAX_FILENAME_LENGTH
    assert safe.endswith(".txt")

