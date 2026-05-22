"""Human-readable diagnostics for provider connection checks."""

from __future__ import annotations

import re


_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|api[_-]?secret|api[_-]?password|authorization|access[_-]?token|refresh[_-]?token|token|secret|password)\b"
    r"(\s*[:=]\s*)([\"']?)([^\"'\s,;}&]+)([\"']?)"
)
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:api[_-]?key|api[_-]?secret|api[_-]?password|access[_-]?token|refresh[_-]?token|token|secret|password)=)[^&\s]+"
)
_BEARER_SECRET_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/:-]{6,}")


def redact_sensitive_text(text: object) -> str:
    """Remove obvious credential values from operator-facing diagnostics."""

    value = str(text or "")
    value = _QUERY_SECRET_RE.sub(r"\1[REDACTED]", value)
    value = _BEARER_SECRET_RE.sub("Bearer [REDACTED]", value)
    return _ASSIGNMENT_SECRET_RE.sub(r"\1\2\3[REDACTED]\5", value)


def explain_provider_error(service: str, error: BaseException | str) -> str:
    """Return a short operator-facing explanation for common provider errors."""
    text = redact_sensitive_text(error)
    lower = text.lower()
    service_name = service.strip().lower()

    if "hmac secret key does not match" in lower and service_name == "llm":
        return (
            "讯飞星火 HTTP 鉴权的 secret 不匹配。"
            "请在问答模型密钥栏填写 HTTP APIPassword，"
            "或按 APIKey:APISecret 格式填写，不能只填 APIKey。"
        )

    if "hmac signature cannot be verified" in lower and "apikey not found" in lower:
        if service_name == "llm":
            return (
                "讯飞星火问答使用 OpenAI 兼容 HTTP 鉴权。"
                "请在设置页选择 iFlytek Spark X，并在密钥栏填写 HTTP APIPassword，"
                "或按 APIKey:APISecret 格式填写。"
            )
        if service_name == "search":
            return (
                "讯飞 ONE SEARCH 使用 APIPassword 鉴权。"
                "请在设置页选择 iFlytek ONE SEARCH，并在密钥栏填写 Search API 的 APIPassword。"
            )
        return (
            "讯飞签名鉴权失败。请确认当前服务使用的是对应产品的凭据，"
            "并按该服务要求填写 APIKey、APISecret 或 APIPassword。"
        )

    if "iflytek spark embedding requires app_id, api_key and api_secret" in lower:
        return (
            "讯飞向量模型需要 APPID、APIKey、APISecret 三项。"
            "请在设置页选择 iFlytek Spark Embedding 后填写 APPID 和 APISecret，"
            "并在密钥栏填写 Embedding APIKey。"
        )

    if "iflytek spark websocket requires app_id, api_key and api_secret" in lower:
        return (
            "讯飞星火问答已切换为 OpenAI 兼容 HTTP。"
            "请在设置页选择 iFlytek Spark X，并把密钥改为 HTTP APIPassword，"
            "或按 APIKey:APISecret 格式填写。"
        )

    if service_name == "embedding" and ("missing app_id" in lower or "api_secret" in lower):
        return (
            "讯飞向量模型缺少签名参数。"
            "请确认 APPID、Embedding APIKey、APISecret 都已保存并应用。"
        )

    if service_name == "ocr" and "credentials are not configured" in lower:
        return "讯飞 OCR 缺少 APPID、APIKey 或 APISecret。请在设置页的 OCR / 扫描 PDF 中填写并保存应用。"

    if service_name == "ocr" and ("hmac" in lower or "signature" in lower or "unauthorized" in lower):
        return "讯飞 OCR 鉴权失败。请确认 OCR APPID、APIKey、APISecret 属于同一个讯飞 OCR 应用。"

    return text
