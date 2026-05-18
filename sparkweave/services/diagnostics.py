"""Human-readable diagnostics for provider connection checks."""

from __future__ import annotations


def explain_provider_error(service: str, error: BaseException | str) -> str:
    """Return a short operator-facing explanation for common provider errors."""
    text = str(error)
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
