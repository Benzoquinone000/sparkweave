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


def test_validate_upload_still_rejects_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        DocumentValidator.validate_upload_safety(
            "script.exe",
            128,
            allowed_extensions={".py"},
        )

