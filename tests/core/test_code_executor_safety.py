from __future__ import annotations

import pytest

from sparkweave.services.code_execution import CodeExecutionError, ImportGuard


def test_import_guard_rejects_unsafe_builtin_calls() -> None:
    with pytest.raises(CodeExecutionError):
        ImportGuard.validate("print(open('secret.txt').read())", ["math"])


def test_import_guard_rejects_unsafe_module_access() -> None:
    with pytest.raises(CodeExecutionError):
        ImportGuard.validate("import math\nos.system('whoami')", ["math"])


def test_import_guard_rejects_dunder_introspection_escape() -> None:
    payload = "print((()).__class__.__mro__[1].__subclasses__())"
    with pytest.raises(CodeExecutionError):
        ImportGuard.validate(payload, ["math"])


def test_import_guard_rejects_dynamic_attribute_lookup() -> None:
    payload = "print(getattr((), '__class__'))"
    with pytest.raises(CodeExecutionError):
        ImportGuard.validate(payload, ["math"])


def test_import_guard_rejects_unsafe_module_alias_access() -> None:
    payload = "import os as harmless\nharmless.system('whoami')"
    with pytest.raises(CodeExecutionError):
        ImportGuard.validate(payload, ["os"])


def test_import_guard_rejects_unsafe_from_import_call() -> None:
    payload = "from os import system\nsystem('whoami')"
    with pytest.raises(CodeExecutionError):
        ImportGuard.validate(payload, ["os"])

