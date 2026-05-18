"""Learning-image discovery and ranking for guided learning."""

from __future__ import annotations

from dataclasses import dataclass, field
import html
import re
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from sparkweave.services.search import web_search

ImageSearchEventSink = Callable[[str, dict[str, Any]], None]

SEARCH_CONTAINER_KEYS = {
    "answer",
    "citations",
    "data",
    "image_results",
    "imageResults",
    "images",
    "inline_images",
    "inlineImages",
    "items",
    "media",
    "organic",
    "results",
    "search_results",
}
SEARCH_ITEM_KEYS = {
    "alt",
    "body",
    "content",
    "contentUrl",
    "description",
    "headline",
    "href",
    "image",
    "image_url",
    "imageUrl",
    "link",
    "media",
    "name",
    "original",
    "pageUrl",
    "page_url",
    "src",
    "summary",
    "text",
    "thumbnail",
    "thumbnailUrl",
    "thumbnail_url",
    "title",
    "url",
}
PAGE_URL_KEYS = ("url", "link", "href", "page_url", "pageUrl", "source_url", "sourceUrl", "contextLink")
IMAGE_URL_KEYS = (
    "image_url",
    "imageUrl",
    "image",
    "src",
    "contentUrl",
    "mediaUrl",
    "media_url",
    "original",
    "full",
    "full_size",
    "fullSize",
)
THUMBNAIL_KEYS = ("thumbnail", "thumbnail_url", "thumbnailUrl", "thumb", "thumbUrl", "preview", "previewUrl")


@dataclass
class ImageCandidate:
    title: str
    url: str
    image_url: str = ""
    thumbnail: str = ""
    source: str = ""
    summary: str = ""
    width: int | None = None
    height: int | None = None
    license: str = ""
    why_recommended: str = ""
    score: float = 0.0
    kind: str = "image"
    quality_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "image_url": self.image_url,
            "thumbnail": self.thumbnail,
            "source": self.source,
            "summary": self.summary,
            "width": self.width,
            "height": self.height,
            "license": self.license,
            "why_recommended": self.why_recommended,
            "score": round(self.score, 3),
            "kind": self.kind,
            "quality_signals": list(self.quality_signals),
        }


async def recommend_learning_images(
    *,
    topic: str,
    learner_hints: dict[str, Any] | None = None,
    prompt: str = "",
    language: str = "zh",
    max_results: int = 4,
    search_depth: int = 8,
    event_sink: ImageSearchEventSink | None = None,
) -> dict[str, Any]:
    """Search public web results and return a small set of learning-image cards."""

    hints = learner_hints or {}
    search_plan = _build_search_plan(topic=topic, hints=hints, prompt=prompt, language=language)
    queries = [item["query"] for item in search_plan]
    candidates: dict[str, ImageCandidate] = {}
    errors: list[str] = []
    depth = _clamp_search_depth(search_depth)

    for query in queries:
        _emit(event_sink, "status", stage="searching", message=f"Searching learning images: {query}", query=query)
        try:
            result = await web_search(query=query, max_results=depth)
        except Exception as exc:  # pragma: no cover - provider-specific network failure
            errors.append(str(exc))
            continue
        for item in _iter_search_items(result):
            candidate = _candidate_from_item(item)
            if candidate is None:
                continue
            candidate.score = _score_candidate(candidate, topic=topic, hints=hints)
            candidate.quality_signals = _quality_signals(candidate, topic=topic, hints=hints)
            candidate.why_recommended = _recommendation_reason(candidate, topic=topic, hints=hints)
            key = _candidate_key(candidate)
            existing = candidates.get(key)
            if existing is None or candidate.score > existing.score:
                candidates[key] = candidate

    images = sorted(candidates.values(), key=lambda item: item.score, reverse=True)[:max_results]
    fallback_search = False
    if not images:
        images = _fallback_search_cards(topic=topic, queries=queries, language=language, max_results=max_results)
        fallback_search = bool(images)

    _emit(
        event_sink,
        "status",
        stage="ranked",
        message=f"Selected {len(images)} learning image(s).",
        count=len(images),
    )

    return {
        "success": True,
        "render_type": "external_image",
        "response": _build_response(images, topic, fallback_search=fallback_search),
        "view_plan": _build_view_plan(images, topic, fallback_search=fallback_search),
        "reflection_prompt": _build_reflection_prompt(topic, hints),
        "images": [item.to_dict() for item in images],
        "queries": queries,
        "search_plan": search_plan,
        "quality_signals": _aggregate_quality_signals(images),
        "result_count": len(images),
        "search_errors": errors,
        "fallback_search": fallback_search,
        "learner_profile_hints": _public_learner_hints(hints),
        "agent_chain": [],
        "tool_chain": [
            {"label": "精选图片工具", "detail": "检索公开图片、图解和示意图候选链接。"},
            {"label": "排序筛选", "detail": "按学习主题、清晰度、可引用性和画像提示筛选。"},
        ],
    }


def _build_search_plan(*, topic: str, hints: dict[str, Any], prompt: str, language: str) -> list[dict[str, str]]:
    focus_terms = [topic, prompt, *_as_strings(hints.get("weak_points")), *_as_strings(hints.get("concepts"))]
    focus = " ".join(_unique_strings(focus_terms)) or "学习概念"
    if language.lower().startswith("zh"):
        return [
            {
                "query": f"{focus} 图解 示意图 图片",
                "purpose": "find concise visual explanations",
                "asset_type": "diagram",
            },
            {
                "query": f"{focus} 概念图 结构图 可视化",
                "purpose": "find structured concept visuals",
                "asset_type": "concept_map",
            },
            {
                "query": f"{focus} diagram visual explanation image",
                "purpose": "include English educational diagrams",
                "asset_type": "diagram",
            },
            {
                "query": f"{focus} site:commons.wikimedia.org diagram",
                "purpose": "prefer reusable public educational assets when available",
                "asset_type": "public_asset",
            },
        ]
    return [
        {
            "query": f"{focus} diagram visual explanation image",
            "purpose": "find concise visual explanations",
            "asset_type": "diagram",
        },
        {
            "query": f"{focus} concept map illustration",
            "purpose": "find structured concept visuals",
            "asset_type": "concept_map",
        },
        {
            "query": f"{focus} infographic educational diagram",
            "purpose": "find learner-friendly infographic style images",
            "asset_type": "infographic",
        },
        {
            "query": f"{focus} site:commons.wikimedia.org diagram",
            "purpose": "prefer reusable public educational assets when available",
            "asset_type": "public_asset",
        },
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
                "title": _item_text(raw, "title", "name", "headline", "alt"),
                "url": _item_text(raw, *PAGE_URL_KEYS),
                "image_url": _item_text(raw, *IMAGE_URL_KEYS),
                "thumbnail": _item_text(raw, *THUMBNAIL_KEYS),
                "summary": _item_text(raw, "snippet", "content", "description", "body", "summary", "text"),
                "source": _item_text(raw, "source", "website", "site_name", "siteName", "publisher", "provider"),
                "width": _item_text(raw, "width", "imageWidth", "thumbnailWidth"),
                "height": _item_text(raw, "height", "imageHeight", "thumbnailHeight"),
                "license": _item_text(raw, "license", "license_name", "licenseName", "rights", "usageRights"),
            }
        )
    return items


def _collect_search_records(value: Any, *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 6:
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
        elif key in {"attributes", "metadata", "meta", "image", "thumbnail", "media", "pagemap"} and isinstance(nested, dict):
            records.extend(_collect_search_records(nested, depth=depth + 1))
    return records


def _looks_like_search_item(raw: dict[str, Any]) -> bool:
    if not SEARCH_ITEM_KEYS.intersection(raw):
        return False
    return bool(
        _item_text(raw, *PAGE_URL_KEYS)
        or _item_text(raw, *IMAGE_URL_KEYS)
        or _item_text(raw, *THUMBNAIL_KEYS)
        or _item_text(raw, "title", "name", "headline", "alt")
    )


def _candidate_from_item(item: dict[str, str]) -> ImageCandidate | None:
    page_url = _normalize_url(item.get("url", ""))
    image_url = _normalize_url(item.get("image_url", ""))
    thumbnail = _normalize_url(item.get("thumbnail", ""))
    if not image_url and _is_direct_image_url(page_url):
        image_url = page_url
    if not image_url and not thumbnail:
        return None
    if not page_url:
        page_url = image_url or thumbnail
    title = item.get("title") or "学习图片"
    source = item.get("source") or _domain(page_url or image_url or thumbnail)
    return ImageCandidate(
        title=title,
        url=page_url,
        image_url=image_url,
        thumbnail=thumbnail,
        source=source,
        summary=item.get("summary", ""),
        width=_coerce_int(item.get("width")),
        height=_coerce_int(item.get("height")),
        license=item.get("license", ""),
    )


def _fallback_search_cards(
    *,
    topic: str,
    queries: list[str],
    language: str,
    max_results: int,
) -> list[ImageCandidate]:
    focus = topic.strip() or (queries[0] if queries else "学习主题")
    encoded = quote_plus(focus)
    cards = [
        ImageCandidate(
            title=f"在 Bing 图片搜索：{focus}",
            url=f"https://www.bing.com/images/search?q={encoded}",
            source="Bing Images",
            summary="没有拿到稳定图片直链，先打开图片搜索页，从前几张高相关示意图里选择清晰版本。",
            why_recommended="这是兜底图片搜索入口，不是已筛好的单张图片。建议优先选择来源清楚、文字不拥挤的图。",
            score=0.22,
            kind="search_fallback",
        ),
        ImageCandidate(
            title=f"在 Google 图片搜索：{focus}",
            url=f"https://www.google.com/search?tbm=isch&q={encoded}",
            source="Google Images",
            summary="用通用图片搜索继续找公开示意图、概念图或配图参考。",
            why_recommended="这是兜底图片搜索入口。优先选择教育站点、百科或公开课来源。",
            score=0.2,
            kind="search_fallback",
        ),
        ImageCandidate(
            title=f"在 DuckDuckGo 图片搜索：{focus}",
            url=f"https://duckduckgo.com/?q={encoded}&iax=images&ia=images",
            source="DuckDuckGo Images",
            summary="备用图片搜索入口，适合继续寻找公开配图和图解参考。",
            why_recommended="这是兜底图片搜索入口。打开后只挑 1-2 张最能解释当前卡点的图。",
            score=0.18,
            kind="search_fallback",
        ),
    ]
    if language.lower().startswith("zh"):
        cards.insert(
            1,
            ImageCandidate(
                title=f"在百度图片搜索：{focus}",
                url=f"https://image.baidu.com/search/index?tn=baiduimage&word={encoded}",
                source="Baidu Images",
                summary="中文图片搜索入口，适合找本地化教材图、中文示意图和课堂配图。",
                why_recommended="这是兜底图片搜索入口。注意选择来源可信、没有明显水印或广告遮挡的图片。",
                score=0.21,
                kind="search_fallback",
            ),
        )
    return cards[: max(1, max_results)]


def _score_candidate(candidate: ImageCandidate, *, topic: str, hints: dict[str, Any]) -> float:
    haystack = f"{candidate.title} {candidate.summary} {candidate.source}".lower()
    score = 0.42
    for term in _important_terms(topic, hints):
        if term and term.lower() in haystack:
            score += 0.07
    if re.search(r"图解|示意图|概念图|结构图|可视化|diagram|visual|concept map|illustration|infographic", haystack):
        score += 0.16
    if re.search(r"教程|课程|百科|wikipedia|wikimedia|khan academy|mit|stanford|university|official|edu", haystack):
        score += 0.05
    if candidate.image_url:
        score += 0.08
    if candidate.thumbnail:
        score += 0.03
    if candidate.width and candidate.height:
        score += 0.04
        if candidate.width >= 600 and candidate.height >= 360:
            score += 0.03
    if candidate.license:
        score += 0.03
    if re.search(r"stock|wallpaper|壁纸|头像|表情包|广告|logo|下载站", haystack):
        score -= 0.12
    return max(0.0, min(score, 1.0))


def _quality_signals(candidate: ImageCandidate, *, topic: str, hints: dict[str, Any]) -> list[str]:
    haystack = f"{candidate.title} {candidate.summary} {candidate.source}".lower()
    signals: list[str] = []
    if any(term and term.lower() in haystack for term in _important_terms(topic, hints)):
        signals.append("topic_match")
    if re.search(r"图解|示意图|diagram|visual|concept map|illustration|infographic", haystack):
        signals.append("educational_visual")
    if candidate.image_url:
        signals.append("direct_image_url")
    if candidate.width and candidate.height:
        signals.append("has_dimensions")
    if candidate.license:
        signals.append("license_metadata")
    if re.search(r"wikipedia|wikimedia|edu|university|official|百科|公开课", haystack):
        signals.append("credible_source")
    return signals[:6]


def _aggregate_quality_signals(images: list[ImageCandidate]) -> list[str]:
    signals: list[str] = []
    for image in images:
        for signal in image.quality_signals:
            if signal not in signals:
                signals.append(signal)
    return signals


def _recommendation_reason(candidate: ImageCandidate, *, topic: str, hints: dict[str, Any]) -> str:
    weak_points = _as_strings(hints.get("weak_points"))[:2]
    reason = f"围绕「{topic}」筛选，优先选择能直接帮助建立图像化理解的资料。"
    if weak_points:
        reason += f" 也贴合当前卡点：{'、'.join(weak_points)}。"
    if candidate.width and candidate.height:
        reason += f" 图片尺寸约 {candidate.width}x{candidate.height}，适合放大查看。"
    if candidate.license:
        reason += f" 检索结果包含授权信息：{candidate.license}。"
    return reason


def _build_response(images: list[ImageCandidate], topic: str, *, fallback_search: bool = False) -> str:
    if not images:
        return f"暂时没有找到足够稳定的「{topic}」学习图片。可以换一个更具体的关键词再试。"
    if fallback_search:
        return f"暂时没有拿到稳定的图片直链，我先为「{topic}」准备了公开图片搜索入口。建议只挑 1-2 张最清晰的图，回到导学里说明它帮你理解了什么。"
    first = images[0]
    return f"已为「{topic}」筛选 {len(images)} 张公开学习图片。建议先看《{first.title}》，重点观察图中变量、箭头和结构关系。"


def _build_view_plan(images: list[ImageCandidate], topic: str, *, fallback_search: bool = False) -> list[str]:
    if not images:
        return [
            f"把关键词缩小到「{topic}」里的一个对象，例如公式结构、流程步骤或几何关系。",
            "重新检索时优先选择“示意图 / diagram / concept map”等关键词。",
            "找到图后用一句话说清楚它解释了哪个关系，再继续学习。",
        ]
    if fallback_search:
        return [
            "只打开一个图片搜索入口，优先选择来源清楚、文字不拥挤、主体完整的图。",
            "最多看 1-2 张；如果一眼看不出变量或结构关系，就换下一张。",
            "回到导学里写一句“这张图让我看清了什么关系”，让系统继续安排练习。",
        ]
    return [
        "先看第一张图的标题和来源，确认它确实对应当前概念。",
        "沿着图里的箭头、变量或区域关系复述一遍，不要只看颜色和布局。",
        "选出最能解释卡点的一张图，回到导学里用一句话描述它的核心关系。",
    ]


def _build_reflection_prompt(topic: str, hints: dict[str, Any]) -> str:
    weak_points = _as_strings(hints.get("weak_points"))[:2]
    if weak_points:
        return f"看完图片后用一句话回答：关于「{topic}」，{ '、'.join(weak_points) } 有没有被图说明白？还缺哪一步？"
    return f"看完图片后用一句话回答：关于「{topic}」，这张图帮你看清了哪个关系？"


def _candidate_key(candidate: ImageCandidate) -> str:
    return (candidate.image_url or candidate.thumbnail or candidate.url).strip().lower()


def _normalize_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    url = _unwrap_redirect_url(unquote(raw_url.strip()))
    if url.startswith("//"):
        url = f"https:{url}"
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        return ""
    return url


def _unwrap_redirect_url(raw_url: str) -> str:
    current = raw_url.strip()
    for _ in range(2):
        normalized = current if re.match(r"^https?://", current) else f"https://{current}"
        parsed = urlparse(normalized)
        query = parse_qs(parsed.query)
        redirected = ""
        for key in ("url", "u", "q", "target", "to", "redirect", "uddg", "imgurl", "mediaurl"):
            values = query.get(key) or []
            if values and re.match(r"^https?://", values[0], flags=re.IGNORECASE):
                redirected = unquote(values[0])
                break
        if not redirected or redirected == current:
            return current
        current = redirected
    return current


def _is_direct_image_url(url: str) -> bool:
    return bool(re.search(r"\.(?:png|jpe?g|webp|gif|svg)(?:[?#].*)?$", url, flags=re.IGNORECASE))


def _domain(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.lower()


def _public_learner_hints(hints: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "concepts",
        "current_focus",
        "goals",
        "level",
        "mastery_needs_attention",
        "next_action",
        "preferences",
        "strengths",
        "summary",
        "time_budget_minutes",
        "weak_points",
    }
    return {key: hints[key] for key in allowed if key in hints}


def _important_terms(topic: str, hints: dict[str, Any]) -> list[str]:
    terms = _as_strings(topic) + _as_strings(hints.get("weak_points")) + _as_strings(hints.get("concepts"))
    split_terms: list[str] = []
    for term in terms:
        split_terms.extend(re.split(r"[\s,，;；/]+", term))
    return [item.strip() for item in split_terms if len(item.strip()) >= 2][:12]


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    number = int(match.group(0))
    return number if number > 0 else None


def _clamp_search_depth(value: Any) -> int:
    try:
        depth = int(value)
    except (TypeError, ValueError):
        depth = 8
    return max(4, min(depth, 12))


def _item_text(raw: dict[str, Any], *keys: str) -> str:
    for container in _containers(raw):
        for key in keys:
            text = _string_from_value(container.get(key))
            if text:
                return html.unescape(text).strip()
    return ""


def _containers(raw: dict[str, Any]) -> list[dict[str, Any]]:
    containers = [raw]
    for nested_key in ("attributes", "metadata", "meta", "image", "thumbnail", "media"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            containers.append(nested)
            for child_key in ("image", "thumbnail", "media"):
                child = nested.get(child_key)
                if isinstance(child, dict):
                    containers.append(child)
    return containers


def _string_from_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    if isinstance(value, dict):
        for key in (*IMAGE_URL_KEYS, *THUMBNAIL_KEYS, *PAGE_URL_KEYS, "title", "name", "text"):
            text = _string_from_value(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, list):
        for item in value:
            text = _string_from_value(item)
            if text:
                return text
    return ""


def _as_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    return [str(value).strip()] if str(value).strip() else []


def _unique_strings(values: list[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        for text in _as_strings(value):
            if text not in items:
                items.append(text)
    return items


def _emit(event_sink: ImageSearchEventSink | None, event: str, **payload: Any) -> None:
    if event_sink:
        event_sink(event, payload)


__all__ = ["recommend_learning_images"]
