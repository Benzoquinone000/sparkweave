"""iFlytek TTS integration for multimodal narration resources."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import json
import os
from typing import Any
from urllib.parse import urlencode, urlparse

from websockets.asyncio.client import connect

XFYUN_TTS_URL = "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
XFYUN_TTS_VOICE = "x5_lingxiaoxuan_flow"
DEFAULT_ENCODING = "lame"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_CHANNELS = 1
DEFAULT_BIT_DEPTH = 16
DEFAULT_FRAME_SIZE = 0
DEFAULT_SPEED = 50
DEFAULT_VOLUME = 50
DEFAULT_PITCH = 50
DEFAULT_TIMEOUT = 30.0
TTS_SMOKE_TEST_TEXT = "SparkWeave 语音合成测试。"


class TtsUnavailable(RuntimeError):
    """Raised when TTS is not configured or the provider request fails."""


@dataclass(frozen=True)
class TtsSynthesisResult:
    audio: bytes
    content_type: str
    encoding: str
    sample_rate: int
    voice: str
    sid: str | None = None
    phonetic_text: str | None = None


@dataclass(frozen=True)
class XfyunTtsConfig:
    app_id: str
    api_key: str
    api_secret: str
    url: str = XFYUN_TTS_URL
    voice: str = XFYUN_TTS_VOICE
    encoding: str = DEFAULT_ENCODING
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    bit_depth: int = DEFAULT_BIT_DEPTH
    frame_size: int = DEFAULT_FRAME_SIZE
    speed: int = DEFAULT_SPEED
    volume: int = DEFAULT_VOLUME
    pitch: int = DEFAULT_PITCH
    timeout: float = DEFAULT_TIMEOUT
    oral_level: str = "mid"
    spark_assist: int = 1
    stop_split: int = 0
    remain: int = 0
    bgs: int = 0
    reg: int = 0
    rdn: int = 0
    rhy: int = 0

    @classmethod
    def from_env(cls) -> "XfyunTtsConfig | None":
        provider = _env("SPARKWEAVE_TTS_PROVIDER", "iflytek").strip().lower()
        if provider and provider not in {"iflytek", "xfyun", "xunfei"}:
            return None

        app_id = _first_env(
            "IFLYTEK_TTS_APPID",
            "IFLYTEK_TTS_APP_ID",
            "XFYUN_TTS_APPID",
        )
        api_key = _first_env(
            "IFLYTEK_TTS_API_KEY",
            "IFLYTEK_TTS_APIKEY",
            "XFYUN_TTS_API_KEY",
        )
        api_secret = _first_env(
            "IFLYTEK_TTS_API_SECRET",
            "IFLYTEK_TTS_APISECRET",
            "XFYUN_TTS_API_SECRET",
        )
        if not (app_id and api_key and api_secret):
            return None

        return cls(
            app_id=app_id.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            url=_env("IFLYTEK_TTS_URL", XFYUN_TTS_URL).strip() or XFYUN_TTS_URL,
            voice=_env("IFLYTEK_TTS_VOICE", XFYUN_TTS_VOICE).strip() or XFYUN_TTS_VOICE,
            encoding=_env("IFLYTEK_TTS_ENCODING", DEFAULT_ENCODING).strip() or DEFAULT_ENCODING,
            sample_rate=_env_int("IFLYTEK_TTS_SAMPLE_RATE", DEFAULT_SAMPLE_RATE),
            channels=_env_int("IFLYTEK_TTS_CHANNELS", DEFAULT_CHANNELS),
            bit_depth=_env_int("IFLYTEK_TTS_BIT_DEPTH", DEFAULT_BIT_DEPTH),
            frame_size=_env_int("IFLYTEK_TTS_FRAME_SIZE", DEFAULT_FRAME_SIZE),
            speed=_env_int("IFLYTEK_TTS_SPEED", DEFAULT_SPEED),
            volume=_env_int("IFLYTEK_TTS_VOLUME", DEFAULT_VOLUME),
            pitch=_env_int("IFLYTEK_TTS_PITCH", DEFAULT_PITCH),
            timeout=max(_env_float("SPARKWEAVE_TTS_TIMEOUT", DEFAULT_TIMEOUT), 1.0),
            oral_level=_env("IFLYTEK_TTS_ORAL_LEVEL", "mid").strip() or "mid",
            spark_assist=_env_int("IFLYTEK_TTS_SPARK_ASSIST", 1),
            stop_split=_env_int("IFLYTEK_TTS_STOP_SPLIT", 0),
            remain=_env_int("IFLYTEK_TTS_REMAIN", 0),
            bgs=_env_int("IFLYTEK_TTS_BGS", 0),
            reg=_env_int("IFLYTEK_TTS_REG", 0),
            rdn=_env_int("IFLYTEK_TTS_RDN", 0),
            rhy=_env_int("IFLYTEK_TTS_RHY", 0),
        )


def is_iflytek_tts_configured() -> bool:
    return XfyunTtsConfig.from_env() is not None


async def synthesize_speech_with_iflytek(
    text: str,
    *,
    config: XfyunTtsConfig | None = None,
) -> TtsSynthesisResult:
    resolved = config or XfyunTtsConfig.from_env()
    if resolved is None:
        raise TtsUnavailable("iFlytek TTS credentials are not configured")

    content = (text or "").strip()
    if not content:
        raise TtsUnavailable("iFlytek TTS requires non-empty text")

    request_url = _build_iflytek_ws_auth_url(resolved)
    payload = _build_tts_payload(resolved, content)
    audio_chunks: list[bytes] = []
    pybuf_parts: list[str] = []
    sid: str | None = None

    try:
        async with connect(request_url, open_timeout=resolved.timeout, close_timeout=resolved.timeout) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw_message = await websocket.recv()
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8", errors="replace")
                message = json.loads(raw_message)

                header = message.get("header") if isinstance(message, dict) else {}
                if isinstance(header, dict):
                    sid = str(header.get("sid") or sid or "")
                    code = int(header.get("code", 0))
                    if code != 0:
                        raise TtsUnavailable(
                            f"iFlytek TTS error: {header.get('message') or code}"
                        )

                payload_block = message.get("payload") if isinstance(message, dict) else {}
                audio_finished = False
                if isinstance(payload_block, dict):
                    audio_block = payload_block.get("audio")
                    if isinstance(audio_block, dict):
                        encoded_audio = audio_block.get("audio")
                        if isinstance(encoded_audio, str) and encoded_audio:
                            audio_chunks.append(base64.b64decode(encoded_audio))
                        if int(audio_block.get("status", -1)) == 2:
                            audio_finished = True

                    pybuf = payload_block.get("pybuf")
                    if isinstance(pybuf, dict):
                        encoded_text = pybuf.get("text")
                        if isinstance(encoded_text, str) and encoded_text:
                            pybuf_parts.append(
                                base64.b64decode(encoded_text).decode("utf-8", errors="replace")
                            )

                if audio_finished or (isinstance(header, dict) and int(header.get("status", -1)) == 2):
                    break
    except TtsUnavailable:
        raise
    except Exception as exc:
        raise TtsUnavailable(f"iFlytek TTS request failed: {exc}") from exc

    audio = b"".join(audio_chunks)
    if not audio:
        raise TtsUnavailable("iFlytek TTS returned no audio")

    return TtsSynthesisResult(
        audio=audio,
        content_type=_content_type_for_encoding(resolved.encoding),
        encoding=resolved.encoding,
        sample_rate=resolved.sample_rate,
        voice=resolved.voice,
        sid=sid or None,
        phonetic_text="".join(pybuf_parts).strip() or None,
    )


def _build_tts_payload(config: XfyunTtsConfig, text: str) -> dict[str, Any]:
    encoded_text = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return {
        "header": {
            "app_id": config.app_id,
            "status": 2,
        },
        "parameter": {
            "oral": {
                "oral_level": config.oral_level,
                "spark_assist": config.spark_assist,
                "stop_split": config.stop_split,
                "remain": config.remain,
            },
            "tts": {
                "vcn": config.voice,
                "speed": config.speed,
                "volume": config.volume,
                "pitch": config.pitch,
                "bgs": config.bgs,
                "reg": config.reg,
                "rdn": config.rdn,
                "rhy": config.rhy,
                "audio": {
                    "encoding": config.encoding,
                    "sample_rate": config.sample_rate,
                    "channels": config.channels,
                    "bit_depth": config.bit_depth,
                    "frame_size": config.frame_size,
                },
            },
        },
        "payload": {
            "text": {
                "encoding": "utf8",
                "compress": "raw",
                "format": "plain",
                "status": 2,
                "seq": 0,
                "text": encoded_text,
            }
        },
    }


def _build_iflytek_ws_auth_url(config: XfyunTtsConfig) -> str:
    parsed = urlparse(config.url)
    host = parsed.netloc
    path = parsed.path or "/"
    date = formatdate(usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        config.api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("ascii")
    authorization_origin = (
        f'api_key="{config.api_key}",algorithm="hmac-sha256",'
        f'headers="host date request-line",signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    query = urlencode(
        {
            "host": host,
            "date": date,
            "authorization": authorization,
        }
    )
    return f"{config.url}?{query}"


def _content_type_for_encoding(encoding: str) -> str:
    normalized = (encoding or "").strip().lower()
    if normalized == "lame":
        return "audio/mpeg"
    if normalized == "raw":
        return "audio/pcm"
    if normalized.startswith("opus"):
        return "audio/ogg"
    if normalized.startswith("speex"):
        return "audio/speex"
    return "application/octet-stream"


def _first_env(*names: str) -> str:
    for name in names:
        value = _env(name)
        if value.strip():
            return value
    return ""


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


__all__ = [
    "DEFAULT_ENCODING",
    "DEFAULT_SAMPLE_RATE",
    "TTS_SMOKE_TEST_TEXT",
    "TtsSynthesisResult",
    "TtsUnavailable",
    "XFYUN_TTS_URL",
    "XFYUN_TTS_VOICE",
    "XfyunTtsConfig",
    "is_iflytek_tts_configured",
    "synthesize_speech_with_iflytek",
]
