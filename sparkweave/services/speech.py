"""iFlytek speech services for voice input and oral practice evidence."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree

from websockets.asyncio.client import connect

XFYUN_ASR_URL = "wss://iat-api.xfyun.cn/v2/iat"
XFYUN_ISE_URL = "wss://ise-api.xfyun.cn/v2/open-ise"
DEFAULT_ASR_TIMEOUT = 60.0
DEFAULT_SPEECH_EVAL_TIMEOUT = 60.0
DEFAULT_AUDIO_CHUNK_SIZE = 8_000


class SpeechUnavailable(RuntimeError):
    """Raised when a speech provider is not configured or fails."""


@dataclass(frozen=True)
class SpeechTranscriptionResult:
    text: str
    provider: str = "iflytek"
    sid: str | None = None
    language: str = "zh_cn"
    audio_encoding: str = "lame"
    audio_format: str = "audio/L16;rate=16000"


@dataclass(frozen=True)
class SpeechEvaluationResult:
    overall_score: float | None
    normalized_score: float | None
    dimensions: dict[str, float]
    provider: str = "iflytek"
    sid: str | None = None
    raw_text: str = ""


@dataclass(frozen=True)
class XfyunAsrConfig:
    app_id: str
    api_key: str
    api_secret: str
    url: str = XFYUN_ASR_URL
    language: str = "zh_cn"
    accent: str = "mandarin"
    domain: str = "iat"
    vad_eos: int = 3_000
    ptt: int = 1
    dwa: str = "wpgs"
    timeout: float = DEFAULT_ASR_TIMEOUT
    chunk_size: int = DEFAULT_AUDIO_CHUNK_SIZE

    @classmethod
    def from_env(cls) -> "XfyunAsrConfig | None":
        provider = _env("SPARKWEAVE_ASR_PROVIDER", "iflytek").strip().lower()
        if provider and provider not in {"iflytek", "xfyun", "xunfei"}:
            return None
        app_id = _first_env("IFLYTEK_ASR_APPID", "IFLYTEK_ASR_APP_ID", "IFLYTEK_APPID")
        api_key = _first_env("IFLYTEK_ASR_API_KEY", "IFLYTEK_ASR_APIKEY", "IFLYTEK_API_KEY")
        api_secret = _first_env("IFLYTEK_ASR_API_SECRET", "IFLYTEK_ASR_APISECRET", "IFLYTEK_API_SECRET")
        if not (app_id and api_key and api_secret):
            return None
        return cls(
            app_id=app_id.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            url=_env("IFLYTEK_ASR_URL", XFYUN_ASR_URL).strip() or XFYUN_ASR_URL,
            language=_env("IFLYTEK_ASR_LANGUAGE", "zh_cn").strip() or "zh_cn",
            accent=_env("IFLYTEK_ASR_ACCENT", "mandarin").strip() or "mandarin",
            domain=_env("IFLYTEK_ASR_DOMAIN", "iat").strip() or "iat",
            vad_eos=_env_int("IFLYTEK_ASR_VAD_EOS", 3_000),
            ptt=_env_int("IFLYTEK_ASR_PTT", 1),
            dwa=_env("IFLYTEK_ASR_DWA", "wpgs").strip(),
            timeout=max(_env_float("SPARKWEAVE_ASR_TIMEOUT", DEFAULT_ASR_TIMEOUT), 1.0),
            chunk_size=max(_env_int("IFLYTEK_ASR_CHUNK_SIZE", DEFAULT_AUDIO_CHUNK_SIZE), 1),
        )


@dataclass(frozen=True)
class XfyunSpeechEvalConfig:
    app_id: str
    api_key: str
    api_secret: str
    url: str = XFYUN_ISE_URL
    category: str = "read_sentence"
    language: str = "zh_cn"
    group: str = "pupil"
    accent: str = "mandarin"
    audio_format: str = "audio/L16;rate=16000"
    audio_encoding: str = "raw"
    result_encoding: str = "utf8"
    timeout: float = DEFAULT_SPEECH_EVAL_TIMEOUT
    chunk_size: int = DEFAULT_AUDIO_CHUNK_SIZE

    @classmethod
    def from_env(cls) -> "XfyunSpeechEvalConfig | None":
        provider = _env("SPARKWEAVE_SPEECH_EVAL_PROVIDER", "iflytek").strip().lower()
        if provider and provider not in {"iflytek", "xfyun", "xunfei"}:
            return None
        app_id = _first_env(
            "IFLYTEK_SPEECH_EVAL_APPID",
            "IFLYTEK_ISE_APPID",
            "IFLYTEK_APPID",
        )
        api_key = _first_env(
            "IFLYTEK_SPEECH_EVAL_API_KEY",
            "IFLYTEK_ISE_API_KEY",
            "IFLYTEK_API_KEY",
        )
        api_secret = _first_env(
            "IFLYTEK_SPEECH_EVAL_API_SECRET",
            "IFLYTEK_ISE_API_SECRET",
            "IFLYTEK_API_SECRET",
        )
        if not (app_id and api_key and api_secret):
            return None
        return cls(
            app_id=app_id.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            url=_env("IFLYTEK_SPEECH_EVAL_URL", XFYUN_ISE_URL).strip() or XFYUN_ISE_URL,
            category=_env("IFLYTEK_SPEECH_EVAL_CATEGORY", "read_sentence").strip() or "read_sentence",
            language=_env("IFLYTEK_SPEECH_EVAL_LANGUAGE", "zh_cn").strip() or "zh_cn",
            group=_env("IFLYTEK_SPEECH_EVAL_GROUP", "pupil").strip() or "pupil",
            accent=_env("IFLYTEK_SPEECH_EVAL_ACCENT", "mandarin").strip() or "mandarin",
            audio_format=_env("IFLYTEK_SPEECH_EVAL_AUDIO_FORMAT", "audio/L16;rate=16000").strip()
            or "audio/L16;rate=16000",
            audio_encoding=_env("IFLYTEK_SPEECH_EVAL_AUDIO_ENCODING", "raw").strip() or "raw",
            result_encoding=_env("IFLYTEK_SPEECH_EVAL_RESULT_ENCODING", "utf8").strip() or "utf8",
            timeout=max(_env_float("SPARKWEAVE_SPEECH_EVAL_TIMEOUT", DEFAULT_SPEECH_EVAL_TIMEOUT), 1.0),
            chunk_size=max(_env_int("IFLYTEK_SPEECH_EVAL_CHUNK_SIZE", DEFAULT_AUDIO_CHUNK_SIZE), 1),
        )


def is_iflytek_asr_configured() -> bool:
    return XfyunAsrConfig.from_env() is not None


def is_iflytek_speech_eval_configured() -> bool:
    return XfyunSpeechEvalConfig.from_env() is not None


def is_asr_or_offline_fallback_available() -> bool:
    if is_iflytek_asr_configured():
        return True
    from sparkweave.services.iflytek_offline import offline_fallback_enabled

    return offline_fallback_enabled()


def is_speech_eval_or_offline_fallback_available() -> bool:
    if is_iflytek_speech_eval_configured():
        return True
    from sparkweave.services.iflytek_offline import offline_fallback_enabled

    return offline_fallback_enabled()


async def transcribe_audio_with_iflytek(
    audio: bytes,
    *,
    config: XfyunAsrConfig | None = None,
    audio_encoding: str = "lame",
) -> SpeechTranscriptionResult:
    resolved = config or XfyunAsrConfig.from_env()
    if resolved is None:
        raise SpeechUnavailable("iFlytek ASR credentials are not configured")
    if not audio:
        raise SpeechUnavailable("iFlytek ASR requires non-empty audio")

    prepared_audio, prepared_encoding, audio_format = prepare_iflytek_asr_audio(
        audio,
        audio_encoding=audio_encoding,
    )
    request_url = _build_iflytek_ws_auth_url(resolved.url, resolved.api_key, resolved.api_secret)
    payloads = _build_asr_payloads(
        resolved,
        prepared_audio,
        audio_encoding=prepared_encoding,
        audio_format=audio_format,
    )
    segments: list[str] = []
    sid: str | None = None

    try:
        async with connect(request_url, open_timeout=resolved.timeout, close_timeout=resolved.timeout) as websocket:
            for payload in payloads:
                await websocket.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw_message = await websocket.recv()
                message = _loads_ws_message(raw_message)
                sid = _sid_from_message(message) or sid
                _raise_provider_error(message, "iFlytek ASR")
                result = _nested_dict(message, "data", "result")
                text = extract_iflytek_asr_text(result)
                if text:
                    _merge_asr_segment(segments, result, text)
                if _message_status(message) == 2:
                    break
    except SpeechUnavailable:
        raise
    except Exception as exc:
        raise SpeechUnavailable(f"iFlytek ASR request failed: {exc}") from exc

    return SpeechTranscriptionResult(
        text="".join(segments).strip(),
        sid=sid,
        language=resolved.language,
        audio_encoding=prepared_encoding,
        audio_format=audio_format,
    )


async def transcribe_audio_with_fallback(
    audio: bytes,
    *,
    config: XfyunAsrConfig | None = None,
    audio_encoding: str = "lame",
) -> SpeechTranscriptionResult:
    try:
        return await transcribe_audio_with_iflytek(audio, config=config, audio_encoding=audio_encoding)
    except SpeechUnavailable as exc:
        from sparkweave.services.iflytek_offline import (
            audio_descriptor,
            offline_fallback_enabled,
            offline_transcription_text,
        )

        if not offline_fallback_enabled():
            raise
        descriptor = audio_descriptor(audio, audio_encoding=audio_encoding)
        return SpeechTranscriptionResult(
            text=offline_transcription_text(audio, audio_encoding=audio_encoding, reason=exc),
            provider="offline_iflytek_fallback:asr",
            sid=f"offline-asr-{descriptor['digest']}",
            language=(config.language if config else "zh_cn"),
            audio_encoding=descriptor["encoding"],
            audio_format="offline",
        )


async def transcribe_audio_file_with_iflytek(
    file_path: str | Path,
    *,
    config: XfyunAsrConfig | None = None,
    audio_encoding: str | None = None,
) -> SpeechTranscriptionResult:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise SpeechUnavailable(f"Audio file not found: {file_path}")
    return await transcribe_audio_with_iflytek(
        path.read_bytes(),
        config=config,
        audio_encoding=audio_encoding or guess_iflytek_audio_encoding(path.name),
    )


async def evaluate_speech_with_iflytek(
    audio: bytes,
    *,
    reference_text: str,
    config: XfyunSpeechEvalConfig | None = None,
) -> SpeechEvaluationResult:
    resolved = config or XfyunSpeechEvalConfig.from_env()
    if resolved is None:
        raise SpeechUnavailable("iFlytek speech evaluation credentials are not configured")
    prompt = reference_text.strip()
    if not prompt:
        raise SpeechUnavailable("Speech evaluation requires reference text")
    if not audio:
        raise SpeechUnavailable("Speech evaluation requires non-empty audio")

    prepared_audio, audio_format, audio_encoding = prepare_iflytek_speech_eval_audio(
        audio,
        audio_format=resolved.audio_format,
        audio_encoding=resolved.audio_encoding,
    )
    request_url = _build_iflytek_ws_auth_url(resolved.url, resolved.api_key, resolved.api_secret)
    payloads = _build_speech_eval_payloads(
        resolved,
        prepared_audio,
        prompt,
        audio_format=audio_format,
        audio_encoding=audio_encoding,
    )
    encoded_results: list[str] = []
    sid: str | None = None

    try:
        async with connect(request_url, open_timeout=resolved.timeout, close_timeout=resolved.timeout) as websocket:
            for payload in payloads:
                await websocket.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw_message = await websocket.recv()
                message = _loads_ws_message(raw_message)
                sid = _sid_from_message(message) or sid
                _raise_provider_error(message, "iFlytek speech evaluation")
                encoded = _speech_eval_result_data(message)
                if encoded:
                    encoded_results.append(encoded)
                if _message_status(message) == 2:
                    break
    except SpeechUnavailable:
        raise
    except Exception as exc:
        raise SpeechUnavailable(f"iFlytek speech evaluation request failed: {exc}") from exc

    raw_text = _decode_speech_eval_results(encoded_results)
    dimensions = extract_speech_eval_scores(raw_text)
    overall_score = _overall_score(dimensions)
    normalized_score = round(overall_score / 100, 4) if overall_score is not None else None
    return SpeechEvaluationResult(
        overall_score=overall_score,
        normalized_score=normalized_score,
        dimensions=dimensions,
        sid=sid,
        raw_text=raw_text,
    )


async def evaluate_speech_with_fallback(
    audio: bytes,
    *,
    reference_text: str,
    config: XfyunSpeechEvalConfig | None = None,
) -> SpeechEvaluationResult:
    try:
        return await evaluate_speech_with_iflytek(audio, reference_text=reference_text, config=config)
    except SpeechUnavailable as exc:
        from sparkweave.services.iflytek_offline import (
            audio_descriptor,
            fallback_reason_text,
            offline_fallback_enabled,
            offline_speech_eval_result,
        )

        if not offline_fallback_enabled():
            raise
        descriptor = audio_descriptor(audio, audio_encoding=config.audio_encoding if config else "raw")
        fallback = offline_speech_eval_result(audio, reference_text=reference_text)
        return SpeechEvaluationResult(
            overall_score=fallback["overall_score"],
            normalized_score=fallback["normalized_score"],
            dimensions=fallback["dimensions"],
            provider="offline_iflytek_fallback:speech_eval",
            sid=f"offline-speech-eval-{descriptor['digest']}",
            raw_text=f"{fallback['raw_text']}\nreason={fallback_reason_text(exc)}",
        )


def extract_iflytek_asr_text(result: dict[str, Any] | None) -> str:
    if not isinstance(result, dict):
        return ""
    words = result.get("ws")
    if not isinstance(words, list):
        return ""
    parts: list[str] = []
    for word in words:
        if not isinstance(word, dict):
            continue
        candidates = word.get("cw")
        if not isinstance(candidates, list) or not candidates:
            continue
        first = candidates[0]
        if isinstance(first, dict) and first.get("w") is not None:
            parts.append(str(first.get("w") or ""))
    return "".join(parts)


def extract_speech_eval_scores(xml_text: str) -> dict[str, float]:
    text = xml_text.strip().lstrip("\ufeff")
    if not text:
        return {}
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise SpeechUnavailable("iFlytek speech evaluation returned invalid XML") from exc

    scores: dict[str, float] = {}
    for element in root.iter():
        for key, value in element.attrib.items():
            normalized_key = key.strip().lower()
            if not normalized_key.endswith("_score") and normalized_key not in {"score", "total"}:
                continue
            parsed = _float_or_none(value)
            if parsed is None:
                continue
            score_name = normalized_key.removesuffix("_score")
            if score_name and score_name not in scores:
                scores[score_name] = parsed
    return scores


def guess_iflytek_audio_encoding(filename_or_mime: str) -> str:
    value = (filename_or_mime or "").strip().lower()
    if "mp3" in value or value.endswith(".mp3") or value == "audio/mpeg":
        return "lame"
    if "speex" in value:
        return "speex-wb"
    if "wav" in value or value.endswith(".wav"):
        return "raw"
    return "raw"


def prepare_iflytek_asr_audio(
    audio: bytes,
    *,
    audio_encoding: str,
) -> tuple[bytes, str, str]:
    encoding = (audio_encoding or "raw").strip().lower()
    if audio.startswith(b"RIFF") and audio[8:12] == b"WAVE":
        payload, sample_rate, bit_depth = _extract_wav_pcm(audio)
        if bit_depth not in {8, 16}:
            raise SpeechUnavailable(f"Unsupported WAV bit depth for iFlytek ASR: {bit_depth}")
        return payload, "raw", f"audio/L16;rate={sample_rate}"
    if audio.startswith(b"\x1aE\xdf\xa3") or audio.startswith(b"OggS"):
        raise SpeechUnavailable("Unsupported browser audio container; record or upload PCM/WAV/MP3 audio")
    return audio, encoding, "audio/L16;rate=16000"


def prepare_iflytek_speech_eval_audio(
    audio: bytes,
    *,
    audio_format: str,
    audio_encoding: str,
) -> tuple[bytes, str, str]:
    encoding = (audio_encoding or "raw").strip().lower()
    if audio.startswith(b"RIFF") and audio[8:12] == b"WAVE":
        payload, sample_rate, bit_depth = _extract_wav_pcm(audio)
        if bit_depth != 16:
            raise SpeechUnavailable(f"Unsupported WAV bit depth for iFlytek speech evaluation: {bit_depth}")
        return payload, f"audio/L16;rate={sample_rate}", "raw"
    if audio.startswith(b"\x1aE\xdf\xa3") or audio.startswith(b"OggS"):
        raise SpeechUnavailable("Unsupported browser audio container; record or upload PCM/WAV audio")
    return audio, audio_format, encoding


def _build_asr_payloads(
    config: XfyunAsrConfig,
    audio: bytes,
    *,
    audio_encoding: str,
    audio_format: str,
) -> list[dict[str, Any]]:
    chunks = _audio_chunks(audio, config.chunk_size)
    payloads: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        status = 0 if index == 0 else 1
        if index == len(chunks) - 1:
            status = 2 if index == 0 else 2
        data = {
            "status": status,
            "format": audio_format,
            "encoding": audio_encoding,
            "audio": base64.b64encode(chunk).decode("ascii"),
        }
        if index == 0:
            business: dict[str, Any] = {
                "language": config.language,
                "domain": config.domain,
                "accent": config.accent,
                "vad_eos": config.vad_eos,
                "ptt": config.ptt,
            }
            if config.dwa:
                business["dwa"] = config.dwa
            payloads.append({"common": {"app_id": config.app_id}, "business": business, "data": data})
        else:
            payloads.append({"data": data})
    return payloads


def _build_speech_eval_payloads(
    config: XfyunSpeechEvalConfig,
    audio: bytes,
    reference_text: str,
    *,
    audio_format: str,
    audio_encoding: str,
) -> list[dict[str, Any]]:
    chunks = _audio_chunks(audio, config.chunk_size)
    text_b64 = base64.b64encode(reference_text.encode("utf-8")).decode("ascii")
    payloads: list[dict[str, Any]] = [
        {
            "common": {"app_id": config.app_id},
            "business": {
                "category": config.category,
                "sub": "ise",
                "ent": config.language,
                "cmd": "ssb",
                "auf": audio_format,
                "aue": audio_encoding,
                "rstcd": config.result_encoding,
                "group": config.group,
                "accent": config.accent,
                "tte": "utf-8",
                "text": text_b64,
            },
            "data": {"status": 0},
        }
    ]
    for index, chunk in enumerate(chunks):
        aus = 2 if index == len(chunks) - 1 else 1
        payloads.append(
            {
                "business": {"cmd": "auw", "aus": aus},
                "data": {
                    "status": 2 if aus == 2 else 1,
                    "data": base64.b64encode(chunk).decode("ascii"),
                },
            }
        )
    return payloads


def _build_iflytek_ws_auth_url(url: str, api_key: str, api_secret: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    date = formatdate(usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("ascii")
    authorization_origin = (
        f'api_key="{api_key}",algorithm="hmac-sha256",'
        f'headers="host date request-line",signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    separator = "&" if parsed.query else "?"
    return f"{url}{separator}{urlencode({'host': host, 'date': date, 'authorization': authorization})}"


def _audio_chunks(audio: bytes, chunk_size: int) -> list[bytes]:
    return [audio[index : index + chunk_size] for index in range(0, len(audio), chunk_size)] or [audio]


def _extract_wav_pcm(audio: bytes) -> tuple[bytes, int, int]:
    offset = 12
    sample_rate = 16_000
    bit_depth = 16
    data: bytes | None = None
    while offset + 8 <= len(audio):
        chunk_id = audio[offset : offset + 4]
        chunk_size = int.from_bytes(audio[offset + 4 : offset + 8], "little", signed=False)
        chunk_start = offset + 8
        chunk_end = min(chunk_start + chunk_size, len(audio))
        if chunk_id == b"fmt " and chunk_size >= 16:
            audio_format = int.from_bytes(audio[chunk_start : chunk_start + 2], "little", signed=False)
            if audio_format != 1:
                raise SpeechUnavailable("Only PCM WAV audio is supported for iFlytek ASR")
            sample_rate = int.from_bytes(audio[chunk_start + 4 : chunk_start + 8], "little", signed=False)
            bit_depth = int.from_bytes(audio[chunk_start + 14 : chunk_start + 16], "little", signed=False)
        elif chunk_id == b"data":
            data = audio[chunk_start:chunk_end]
            break
        offset = chunk_end + (chunk_size % 2)
    if data is None:
        raise SpeechUnavailable("WAV audio does not contain a data chunk")
    return data, sample_rate, bit_depth


def _loads_ws_message(raw_message: str | bytes) -> dict[str, Any]:
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8", errors="replace")
    data = json.loads(raw_message)
    if not isinstance(data, dict):
        raise SpeechUnavailable("iFlytek speech provider returned invalid response")
    return data


def _raise_provider_error(message: dict[str, Any], label: str) -> None:
    code = message.get("code")
    provider_message = message.get("message")
    header = message.get("header") if isinstance(message.get("header"), dict) else {}
    if code is None and isinstance(header, dict):
        code = header.get("code")
        provider_message = header.get("message") or provider_message
    try:
        parsed = int(code if code is not None else 0)
    except (TypeError, ValueError):
        parsed = 0
    if parsed != 0:
        raise SpeechUnavailable(f"{label} error: {provider_message or parsed}")


def _message_status(message: dict[str, Any]) -> int:
    for container in (message.get("data"), message.get("header")):
        if isinstance(container, dict) and container.get("status") is not None:
            try:
                return int(container.get("status"))
            except (TypeError, ValueError):
                return -1
    return -1


def _sid_from_message(message: dict[str, Any]) -> str | None:
    for container in (message, message.get("data"), message.get("header")):
        if isinstance(container, dict) and container.get("sid"):
            return str(container.get("sid"))
    return None


def _nested_dict(value: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, dict) else None


def _merge_asr_segment(segments: list[str], result: dict[str, Any] | None, text: str) -> None:
    if not isinstance(result, dict):
        segments.append(text)
        return
    pgs = str(result.get("pgs") or "")
    if pgs == "rpl" and isinstance(result.get("rg"), list) and len(result["rg"]) >= 2:
        start = max(_int_or_default(result["rg"][0], 1) - 1, 0)
        end = max(_int_or_default(result["rg"][1], start + 1), start + 1)
        segments[start:end] = [text]
        return
    sn = _int_or_default(result.get("sn"), len(segments) + 1)
    index = max(sn - 1, 0)
    if index < len(segments):
        segments[index] = text
    else:
        segments.append(text)


def _speech_eval_result_data(message: dict[str, Any]) -> str:
    data = message.get("data")
    if isinstance(data, dict):
        for key in ("data", "result"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _decode_speech_eval_results(encoded_parts: list[str]) -> str:
    if not encoded_parts:
        return ""
    decoded_parts: list[str] = []
    for encoded in encoded_parts:
        try:
            decoded_parts.append(base64.b64decode(encoded, validate=True).decode("utf-8", errors="replace"))
        except (binascii.Error, ValueError):
            decoded_parts.append(encoded)
    return "".join(decoded_parts)


def _overall_score(scores: dict[str, float]) -> float | None:
    for key in ("total", "overall", "final", "score"):
        if key in scores:
            return scores[key]
    if not scores:
        return None
    return round(sum(scores.values()) / len(scores), 2)


def _first_env(*names: str) -> str:
    for name in names:
        value = _env(name)
        if value.strip():
            return value
    return ""


def _env_int(name: str, default: int) -> int:
    return _int_or_default(_env(name, str(default)).strip(), default)


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


__all__ = [
    "DEFAULT_AUDIO_CHUNK_SIZE",
    "SpeechEvaluationResult",
    "SpeechTranscriptionResult",
    "SpeechUnavailable",
    "XFYUN_ASR_URL",
    "XFYUN_ISE_URL",
    "XfyunAsrConfig",
    "XfyunSpeechEvalConfig",
    "evaluate_speech_with_fallback",
    "evaluate_speech_with_iflytek",
    "extract_iflytek_asr_text",
    "extract_speech_eval_scores",
    "guess_iflytek_audio_encoding",
    "is_asr_or_offline_fallback_available",
    "is_iflytek_asr_configured",
    "is_iflytek_speech_eval_configured",
    "is_speech_eval_or_offline_fallback_available",
    "prepare_iflytek_asr_audio",
    "prepare_iflytek_speech_eval_audio",
    "transcribe_audio_with_fallback",
    "transcribe_audio_file_with_iflytek",
    "transcribe_audio_with_iflytek",
]
