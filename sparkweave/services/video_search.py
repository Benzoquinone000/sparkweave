"""Learning-video discovery and ranking for guided learning."""

from __future__ import annotations

from dataclasses import dataclass
import html
import re
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from sparkweave.services.search import web_search

VideoSearchEventSink = Callable[[str, dict[str, Any]], None]

SEARCH_CONTAINER_KEYS = {
    "search_results",
    "citations",
    "results",
    "organic",
    "items",
    "data",
    "videos",
    "video_results",
    "videoResults",
    "answer",
}
SEARCH_ITEM_KEYS = {
    "title",
    "name",
    "headline",
    "url",
    "link",
    "href",
    "video_url",
    "videoUrl",
    "source_url",
    "sourceUrl",
    "snippet",
    "content",
    "description",
    "body",
    "summary",
    "text",
}


@dataclass
class VideoCandidate:
    title: str
    url: str
    platform: str
    summary: str = ""
    thumbnail: str = ""
    embed_url: str = ""
    channel: str = ""
    duration_seconds: int | None = None
    published_at: str = ""
    why_recommended: str = ""
    score: float = 0.0
    kind: str = "video"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "platform": self.platform,
            "summary": self.summary,
            "thumbnail": self.thumbnail,
            "embed_url": self.embed_url,
            "channel": self.channel,
            "duration_seconds": self.duration_seconds,
            "published_at": self.published_at,
            "why_recommended": self.why_recommended,
            "score": round(self.score, 3),
            "kind": self.kind,
        }


async def recommend_learning_videos(
    *,
    topic: str,
    learner_hints: dict[str, Any] | None = None,
    prompt: str = "",
    language: str = "zh",
    max_results: int = 3,
    event_sink: VideoSearchEventSink | None = None,
) -> dict[str, Any]:
    """Search public web results and return a small set of learning-video cards.

    The service intentionally avoids downloading video content.  It only
    recommends public links and, where possible, returns embeddable player URLs.
    """

    hints = learner_hints or {}
    queries = _build_queries(topic=topic, hints=hints, prompt=prompt, language=language)
    candidates: dict[str, VideoCandidate] = {}
    errors: list[str] = []

    for query in queries:
        _emit(event_sink, "status", stage="searching", message=f"Searching learning videos: {query}", query=query)
        try:
            result = await web_search(query=query, max_results=8)
        except Exception as exc:  # pragma: no cover - provider-specific network failure
            errors.append(str(exc))
            continue
        for item in _iter_search_items(result):
            candidate = _candidate_from_item(item)
            if candidate is None:
                continue
            candidate.score = _score_candidate(candidate, topic=topic, hints=hints, language=language)
            candidate.why_recommended = _recommendation_reason(candidate, topic=topic, hints=hints)
            existing = candidates.get(candidate.url)
            if existing is None or candidate.score > existing.score:
                candidates[candidate.url] = candidate

    videos = sorted(candidates.values(), key=lambda item: item.score, reverse=True)[:max_results]
    fallback_search = False
    if not videos:
        videos = _fallback_search_cards(topic=topic, queries=queries, language=language, max_results=max_results)
        fallback_search = bool(videos)
    _emit(
        event_sink,
        "status",
        stage="ranked",
        message=f"Selected {len(videos)} learning video(s).",
        count=len(videos),
    )

    return {
        "success": True,
        "render_type": "external_video",
        "response": _build_response(videos, topic, fallback_search=fallback_search),
        "watch_plan": _build_watch_plan(videos, topic, fallback_search=fallback_search),
        "reflection_prompt": _build_reflection_prompt(topic, hints),
        "videos": [item.to_dict() for item in videos],
        "queries": queries,
        "search_errors": errors,
        "fallback_search": fallback_search,
        "learner_profile_hints": _public_learner_hints(hints),
        "agent_chain": [
            {"label": "画像智能体", "detail": "读取当前薄弱点、偏好和时间预算。"},
            {"label": "视频检索智能体", "detail": "从公开网页中检索候选视频并提取可播放链接。"},
            {"label": "筛选智能体", "detail": "按学习主题、短时长、入门友好和可嵌入性排序。"},
        ],
    }


def _build_queries(*, topic: str, hints: dict[str, Any], prompt: str, language: str) -> list[str]:
    focus_terms = [topic, prompt, *_as_strings(hints.get("weak_points"))]
    focus = " ".join(item for item in focus_terms if item).strip() or "学习方法"
    time_budget = _coerce_minutes(hints.get("time_budget_minutes"))
    length_hint = "短讲解" if time_budget and time_budget <= 15 else "教程"
    if language.lower().startswith("zh"):
        return [
            f"{focus} 入门 直观 视频 {length_hint}",
            f"{focus} site:bilibili.com/video",
            f"{focus} site:youtube.com/watch",
        ]
    english_length_hint = "short" if time_budget and time_budget <= 15 else "tutorial"
    return [
        f"{focus} beginner intuition {english_length_hint} video",
        f"{focus} site:youtube.com/watch",
        f"{focus} site:bilibili.com/video",
    ]


def _iter_search_items(result: Any) -> list[dict[str, str]]:
    if not isinstance(result, dict):
        return []
    items: list[dict[str, str]] = []
    seen: set[int] = set()
    for raw in _collect_search_records(result):
        marker = id(raw)
        if marker in seen:
            continue
        seen.add(marker)
        items.append(
            {
                "title": _item_text(raw, "title", "name", "headline"),
                "url": _item_text(raw, "url", "link", "href", "video_url", "videoUrl", "source_url", "sourceUrl"),
                "snippet": _item_text(raw, "snippet", "content", "description", "body", "summary", "text"),
                "source": _item_text(raw, "source", "website", "platform", "site_name", "siteName"),
                "date": _item_text(raw, "date", "published_at", "published", "publishedAt", "published_date", "publishedDate"),
                "thumbnail": _item_text(raw, "thumbnail", "image", "thumbnail_url", "thumbnailUrl", "image_url", "imageUrl", "cover", "cover_url"),
                "channel": _item_text(raw, "channel", "author", "creator", "uploader", "owner", "publisher"),
                "duration": _item_text(raw, "duration", "length", "video_duration", "videoDuration"),
                "duration_seconds": _item_text(raw, "duration_seconds", "duration_sec", "durationSeconds", "length_seconds", "lengthSeconds"),
            }
        )
    return items


def _collect_search_records(value: Any, *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 5:
        return []
    if isinstance(value, list):
        records: list[dict[str, Any]] = []
        for item in value:
            records.extend(_collect_search_records(item, depth=depth + 1))
        return records
    if not isinstance(value, dict):
        return []

    records = [value] if _looks_like_search_item(value) else []
    for key, nested in value.items():
        if key in SEARCH_CONTAINER_KEYS or isinstance(nested, list):
            records.extend(_collect_search_records(nested, depth=depth + 1))
    return records


def _looks_like_search_item(raw: dict[str, Any]) -> bool:
    if not SEARCH_ITEM_KEYS.intersection(raw):
        return False
    return bool(
        _item_text(raw, "url", "link", "href", "video_url", "videoUrl", "source_url", "sourceUrl")
        or _item_text(raw, "title", "name", "headline")
        or _item_text(raw, "snippet", "content", "description", "body", "summary", "text")
    )


def _candidate_from_item(item: dict[str, str]) -> VideoCandidate | None:
    url = _find_video_url(" ".join([item.get("url", ""), item.get("snippet", "")]))
    if not url:
        return None
    platform, canonical_url, embed_url, thumbnail = _parse_video_url(url)
    if not platform:
        return None
    title = item.get("title") or "学习视频"
    snippet = item.get("snippet") or ""
    return VideoCandidate(
        title=title,
        url=canonical_url,
        platform=platform,
        summary=snippet,
        thumbnail=item.get("thumbnail") or thumbnail,
        embed_url=embed_url,
        channel=item.get("channel") or item.get("source", ""),
        published_at=item.get("date", ""),
        duration_seconds=_duration_from_item(item, f"{title} {snippet}"),
    )


def _fallback_search_cards(
    *,
    topic: str,
    queries: list[str],
    language: str,
    max_results: int,
) -> list[VideoCandidate]:
    focus = topic.strip() or (queries[0] if queries else "学习主题")
    encoded = quote_plus(focus)
    cards = [
        VideoCandidate(
            title=f"在 Bilibili 搜索：{focus}",
            url=f"https://search.bilibili.com/all?keyword={encoded}",
            platform="Bilibili",
            summary="没有拿到稳定视频直链，先打开平台搜索页，从前几条高相关结果里选择一个短讲解。",
            why_recommended="这是兜底搜索入口，不是已筛好的单个视频。建议只看 1-2 个结果，再回到导学提交反思。",
            score=0.22,
            kind="search_fallback",
        ),
        VideoCandidate(
            title=f"在 YouTube 搜索：{focus}",
            url=f"https://www.youtube.com/results?search_query={encoded}",
            platform="YouTube",
            summary="没有拿到稳定视频直链时，用平台搜索页继续找公开讲解。",
            why_recommended="这是兜底搜索入口。优先选择入门、直观、时长适中的讲解。",
            score=0.2,
            kind="search_fallback",
        ),
    ]
    if language.lower().startswith("zh"):
        return cards[: max(1, max_results)]
    return [cards[1], cards[0]][: max(1, max_results)]


def _parse_video_url(raw_url: str) -> tuple[str, str, str, str]:
    url = _unwrap_redirect_url(unquote(raw_url.strip()))
    bvid_only = re.fullmatch(r"BV[0-9A-Za-z]{8,}", url)
    if bvid_only:
        bvid = bvid_only.group(0)
        canonical = f"https://www.bilibili.com/video/{bvid}"
        return (
            "Bilibili",
            canonical,
            f"https://player.bilibili.com/player.html?bvid={bvid}&poster=1&danmaku=0",
            "",
        )
    avid_only = re.fullmatch(r"av(\d+)", url, flags=re.IGNORECASE)
    if avid_only:
        aid = avid_only.group(1)
        canonical = f"https://www.bilibili.com/video/av{aid}"
        return (
            "Bilibili",
            canonical,
            f"https://player.bilibili.com/player.html?aid={aid}&poster=1&danmaku=0",
            "",
        )
    normalized = url if re.match(r"^https?://", url) else f"https:{url}" if url.startswith("//") else f"https://{url}"
    parsed = urlparse(normalized)
    host = parsed.netloc.lower()

    if "youtu.be" in host or "youtube.com" in host:
        video_id = ""
        if "youtu.be" in host:
            video_id = parsed.path.strip("/").split("/")[0]
        elif parsed.path.startswith("/watch"):
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/", "/live/")):
            parts = parsed.path.strip("/").split("/")
            video_id = parts[1] if len(parts) > 1 else ""
        video_id = re.sub(r"[^A-Za-z0-9_-]", "", video_id)
        if not video_id:
            return "", "", "", ""
        canonical = f"https://www.youtube.com/watch?v={video_id}"
        return (
            "YouTube",
            canonical,
            f"https://www.youtube.com/embed/{video_id}",
            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        )

    if "bilibili.com" in host:
        match = re.search(r"(BV[0-9A-Za-z]{8,})", url)
        if match:
            bvid = match.group(1)
            canonical = f"https://www.bilibili.com/video/{bvid}"
            return (
                "Bilibili",
                canonical,
                f"https://player.bilibili.com/player.html?bvid={bvid}&poster=1&danmaku=0",
                "",
            )
        aid_match = re.search(r"(?:/video/)?av(\d+)", url, flags=re.IGNORECASE)
        if not aid_match:
            return "", "", "", ""
        aid = aid_match.group(1)
        canonical = f"https://www.bilibili.com/video/av{aid}"
        return (
            "Bilibili",
            canonical,
            f"https://player.bilibili.com/player.html?aid={aid}&poster=1&danmaku=0",
            "",
        )

    return "", "", "", ""


def _find_video_url(text: str) -> str:
    candidates: list[str] = []
    candidates.extend(re.findall(r"https?://[^\s<>'\")]+", text))
    candidates.extend(re.findall(r"(?:www\.)?(?:youtube\.com|youtu\.be|bilibili\.com)/[^\s<>'\")]+", text, flags=re.IGNORECASE))
    candidates.extend(re.findall(r"(?:BV[0-9A-Za-z]{8,}|av\d{4,})", text, flags=re.IGNORECASE))
    if not candidates and text.strip():
        candidates.append(text.strip())
    for candidate in candidates:
        cleaned = candidate.strip().rstrip(".,，。；;)")
        if not cleaned:
            continue
        platform, canonical, _embed, _thumbnail = _parse_video_url(cleaned)
        if platform and canonical:
            return cleaned
    return ""


def _unwrap_redirect_url(raw_url: str) -> str:
    current = raw_url.strip()
    for _ in range(2):
        normalized = current if re.match(r"^https?://", current) else f"https://{current}"
        parsed = urlparse(normalized)
        query = parse_qs(parsed.query)
        redirected = ""
        for key in ("url", "u", "q", "target", "to", "redirect", "uddg"):
            values = query.get(key) or []
            if values and re.match(r"^https?://", values[0], flags=re.IGNORECASE):
                redirected = unquote(values[0])
                break
        if not redirected or redirected == current:
            return current
        current = redirected
    return current


def _score_candidate(candidate: VideoCandidate, *, topic: str, hints: dict[str, Any], language: str) -> float:
    haystack = f"{candidate.title} {candidate.summary}".lower()
    time_budget = _coerce_minutes(hints.get("time_budget_minutes"))
    score = 0.45
    for term in _important_terms(topic, hints):
        if term and term.lower() in haystack:
            score += 0.08
    if re.search(r"入门|直观|可视化|动画|图解|例子|基础|讲解|intuition|beginner|visual|explained", haystack):
        score += 0.14
    if re.search(r"课程|大学|高校|公开课|lecture|course", haystack):
        score += 0.05
    if candidate.platform == "Bilibili" and language.lower().startswith("zh"):
        score += 0.05
    if candidate.embed_url:
        score += 0.04
    if candidate.duration_seconds is not None:
        minutes = max(1, candidate.duration_seconds / 60)
        if 240 <= candidate.duration_seconds <= 1200:
            score += 0.1
        elif candidate.duration_seconds > 2400:
            score -= 0.12
        if time_budget:
            if minutes <= max(5, time_budget * 1.2):
                score += 0.07
            elif minutes > max(12, time_budget * 2):
                score -= 0.1
    if re.search(r"直播|合集|完整版|广告|reaction|shorts|预告", haystack):
        score -= 0.12
    return max(0.0, min(score, 1.0))


def _recommendation_reason(candidate: VideoCandidate, *, topic: str, hints: dict[str, Any]) -> str:
    weak_points = _as_strings(hints.get("weak_points"))[:2]
    preferences = _as_strings(hints.get("preferences"))[:2]
    time_budget = _coerce_minutes(hints.get("time_budget_minutes"))
    reason = f"围绕「{topic}」筛选，适合先建立直观理解。"
    if weak_points:
        reason += f" 也贴合当前卡点：{'、'.join(weak_points)}。"
    if preferences:
        reason += f" 已参考学习偏好：{'、'.join(preferences)}。"
    if candidate.duration_seconds:
        reason += f" 时长约 {max(1, round(candidate.duration_seconds / 60))} 分钟，适合碎片学习。"
    if time_budget and candidate.duration_seconds and candidate.duration_seconds / 60 <= max(5, time_budget * 1.2):
        reason += f" 符合你当前约 {time_budget} 分钟的学习窗口。"
    return reason


def _build_response(videos: list[VideoCandidate], topic: str, *, fallback_search: bool = False) -> str:
    if not videos:
        return f"暂时没有找到足够稳定的「{topic}」学习视频。可以换一个更具体的关键词再试。"
    if fallback_search:
        return f"暂时没有拿到稳定的视频直链，我先为「{topic}」准备了公开视频平台搜索入口。建议只打开一个平台，选 1-2 个短讲解后回到导学提交反思。"
    lead = f"已为「{topic}」筛选 {len(videos)} 个公开视频，优先选择短时长、入门友好、可嵌入播放的内容。"
    first = videos[0]
    return f"{lead} 推荐先看《{first.title}》，再回到当前任务提交一句反思。"


def _build_watch_plan(videos: list[VideoCandidate], topic: str, *, fallback_search: bool = False) -> list[str]:
    if not videos:
        return [
            f"把关键词缩小到「{topic}」里的一个概念，例如公式含义、直观例子或常见误区。",
            "重新检索后只保留 1 个最短、最清楚的视频，不要连续刷推荐列表。",
            "看完立刻回到导学提交一句反思，让系统判断是否需要补练习。",
        ]
    if fallback_search:
        return [
            "只打开一个平台搜索入口，优先选择标题里有“入门”“直观”“例题”的短讲解。",
            "最多看 1-2 个结果；如果 3 分钟内没有讲到当前卡点，就换下一个。",
            "看完用一句话写下“我现在懂了什么、还卡在哪里”，再回到导学提交。",
        ]
    featured = videos[0]
    duration = _duration_label(featured.duration_seconds)
    title = featured.title or "第一个视频"
    first_step = f"先看《{title}》"
    if duration:
        first_step += f"，预计 {duration}"
    first_step += "；只关注它是否解释清楚当前任务的核心卡点。"
    return [
        first_step,
        "看到关键公式、图示或例题时暂停 10 秒，用自己的话复述一遍。",
        "看完不要继续刷视频，回到导学提交反思或做一组小练习，让系统更新画像。",
    ]


def _build_reflection_prompt(topic: str, hints: dict[str, Any]) -> str:
    weak_points = _as_strings(hints.get("weak_points"))[:2]
    if weak_points:
        return f"看完后用一句话回答：关于「{topic}」，{ '、'.join(weak_points) } 是否已经清楚？如果还不清楚，卡在哪一步？"
    return f"看完后用一句话回答：关于「{topic}」，你现在能讲清楚什么？还需要系统继续补哪一块？"


def _duration_label(seconds: int | None) -> str:
    if seconds is None or seconds <= 0:
        return ""
    minutes = max(1, round(seconds / 60))
    return f"{minutes} 分钟"


def _public_learner_hints(hints: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "current_focus",
        "summary",
        "level",
        "time_budget_minutes",
        "goals",
        "preferences",
        "strengths",
        "weak_points",
        "mastery_needs_attention",
        "concepts",
        "next_action",
    }
    return {key: hints[key] for key in allowed if key in hints}


def _important_terms(topic: str, hints: dict[str, Any]) -> list[str]:
    terms = _as_strings([topic, *_as_strings(hints.get("weak_points")), *_as_strings(hints.get("concepts"))])
    split_terms: list[str] = []
    for term in terms:
        split_terms.extend(re.split(r"[\s,，;；/]+", term))
    return [item.strip() for item in split_terms if len(item.strip()) >= 2][:12]


def _duration_from_text(text: str) -> int | None:
    match = re.search(r"(?:(\d{1,2})[:：])?(\d{1,2})[:：](\d{2})", text)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    match = re.search(
        r"(?:(\d{1,2})\s*(?:小时|小時|h|hr|hrs|hours?)\s*)?(\d{1,3})\s*(?:分钟|分鐘|分|mins?|minutes?|m\b)(?:\s*(\d{1,2})\s*(?:秒|sec|secs|seconds?))?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
    return None


def _duration_from_item(item: dict[str, str], fallback_text: str) -> int | None:
    seconds_text = item.get("duration_seconds", "")
    if seconds_text:
        try:
            seconds = int(float(seconds_text))
        except ValueError:
            seconds = 0
        if seconds > 0:
            return seconds
    duration_text = item.get("duration", "")
    return _duration_from_text(duration_text) or _duration_from_text(fallback_text)


def _coerce_minutes(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    minutes = int(match.group(0))
    return minutes if minutes > 0 else None


def _clean_text(value: Any) -> str:
    return html.unescape(str(value or "")).strip()


def _item_text(raw: dict[str, Any], *keys: str) -> str:
    containers: list[dict[str, Any]] = [raw]
    for nested_key in ("attributes", "metadata", "meta", "video", "image"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            containers.append(nested)
    for container in containers:
        for key in keys:
            value = container.get(key)
            if value not in (None, ""):
                return _clean_text(value)
    return ""


def _as_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _emit(event_sink: VideoSearchEventSink | None, event: str, **payload: Any) -> None:
    if event_sink:
        event_sink(event, payload)


__all__ = ["recommend_learning_videos"]
