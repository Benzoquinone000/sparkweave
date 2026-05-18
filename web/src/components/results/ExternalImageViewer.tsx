import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Image as ImageIcon, Search } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { PersonalizationBrief } from "@/components/results/PersonalizationBrief";
import { appendLearningEffectEvent } from "@/lib/api";
import { invalidateLearningQueries } from "@/lib/queryInvalidation";
import type { ExternalImageResult } from "@/lib/types";

function parseHttpUrl(url?: string) {
  const raw = (url || "").trim();
  if (!raw) return null;
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed : null;
  } catch {
    return null;
  }
}

function safeExternalUrl(url?: string) {
  return parseHttpUrl(url)?.toString() ?? "";
}

function bestImageUrl(image: NonNullable<ExternalImageResult["images"]>[number]) {
  return safeExternalUrl(image.image_url) || safeExternalUrl(image.thumbnail);
}

function isFallbackImage(image?: { kind?: string }) {
  return image?.kind === "search_fallback";
}

function dimensionLabel(width?: number | null, height?: number | null) {
  if (!width || !height) return "";
  return `${width}x${height}`;
}

export function ExternalImageViewer({ result }: { result: ExternalImageResult }) {
  const queryClient = useQueryClient();
  const images = result.images ?? [];
  const featured = images.find((item) => bestImageUrl(item) && !isFallbackImage(item)) ?? images[0];
  const featuredUrl = safeExternalUrl(featured?.url || featured?.image_url || featured?.thumbnail);
  const featuredImageUrl = featured ? bestImageUrl(featured) : "";
  const hasFallbackSearch = result.fallback_search || images.some((item) => isFallbackImage(item));
  const chain = (result.tool_chain ?? result.agent_chain ?? []).filter((item) => item.label || item.detail).slice(0, 4);
  const viewPlan = (result.view_plan ?? []).filter(Boolean).slice(0, 3);
  const recordedImageUrls = useRef(new Set<string>());
  const [viewedImageUrls, setViewedImageUrls] = useState<Set<string>>(() => new Set());

  const recordImageViewed = useCallback(
    (image: (typeof images)[number], index: number) => {
      const url = safeExternalUrl(image.url || image.image_url || image.thumbnail);
      if (!url || recordedImageUrls.current.has(url)) return;
      recordedImageUrls.current.add(url);
      setViewedImageUrls((prev) => new Set(prev).add(url));
      void appendLearningEffectEvent({
        source: "resource",
        source_id: `external_image:${url}`,
        actor: "learner",
        verb: "viewed",
        object_type: "resource",
        object_id: url,
        title: image.title || "External learning image",
        summary: image.why_recommended || image.summary || result.response || "",
        resource_type: "external_image",
        duration_seconds: null,
        confidence: 0.46,
        weight: 0.55,
        metadata: {
          rank: index + 1,
          source: image.source || "",
          kind: image.kind || "image",
          fallback_search: result.fallback_search || false,
          query: result.queries?.[0] || "",
          view_plan: result.view_plan ?? [],
          reflection_prompt: result.reflection_prompt || "",
          style_hint: result.style_hint || "",
          learner_profile_hints: result.learner_profile_hints ?? {},
          agent_chain: result.agent_chain ?? [],
          tool_chain: result.tool_chain ?? [],
        },
      })
        .then(() => {
          invalidateLearningQueries(queryClient);
        })
        .catch(() => {
          recordedImageUrls.current.delete(url);
          setViewedImageUrls((prev) => {
            const next = new Set(prev);
            next.delete(url);
            return next;
          });
        });
    },
    [
      queryClient,
      result.agent_chain,
      result.fallback_search,
      result.learner_profile_hints,
      result.queries,
      result.reflection_prompt,
      result.response,
      result.style_hint,
      result.tool_chain,
      result.view_plan,
    ],
  );

  return (
    <div className="rounded-lg border border-line bg-surface p-2.5" data-testid="external-image-viewer">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">{hasFallbackSearch ? "搜索入口" : "精选图片"}</Badge>
        <Badge tone="neutral">{images.length ? `${images.length} 张推荐` : "等待结果"}</Badge>
      </div>

      {result.response ? <p className="mt-2.5 text-xs leading-5 text-charcoal">{result.response}</p> : null}
      <PersonalizationBrief hints={result.learner_profile_hints} styleHint={result.style_hint} className="mt-3" />

      {featured ? (
        <div className="mt-3 rounded-lg border border-line bg-tint-yellow p-2.5" data-testid="external-image-view-plan">
          <p className="text-xs font-semibold text-ink">建议用法</p>
          {viewPlan.length ? (
            <ol className="mt-2 grid gap-1.5 text-xs leading-5 text-charcoal">
              {viewPlan.map((step, index) => (
                <li key={`${step}-${index}`} className="flex gap-2">
                  <span className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-white text-xs font-semibold text-brand-purple">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-1 text-xs leading-5 text-charcoal">
              先看第一张图的结构关系，再挑一张最能解释卡点的图，回到导学里写一句自己的理解。
            </p>
          )}
          {result.reflection_prompt ? (
            <p className="mt-3 rounded-md border border-line bg-white px-3 py-2 text-xs leading-5 text-charcoal">
              {result.reflection_prompt}
            </p>
          ) : null}
        </div>
      ) : null}

      {chain.length ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-steel" data-testid="external-image-chain">
          <span className="font-medium text-charcoal">工具处理</span>
          {chain.map((item, index) => (
            <span key={`${item.label || item.detail}-${index}`} className="rounded-md border border-line bg-white px-2 py-1">
              {item.label || item.detail}
            </span>
          ))}
        </div>
      ) : null}

      {featured && featuredImageUrl ? (
        <div className="mt-3 max-w-xl overflow-hidden rounded-lg border border-line bg-white">
          <a href={featuredUrl || featuredImageUrl} target="_blank" rel="noreferrer" onClick={() => recordImageViewed(featured, 0)}>
            <img
              src={featuredImageUrl}
              alt={featured?.title || "精选学习图片"}
              className="max-h-[28rem] w-full bg-white object-contain"
              loading="lazy"
              referrerPolicy="no-referrer"
              data-testid="external-image-featured"
            />
          </a>
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
            <p className="text-xs leading-5 text-steel">打开或查看后，系统会把这种资源偏好写回画像。</p>
            {featuredUrl || featuredImageUrl ? (
              <button
                type="button"
                data-testid="external-image-mark-viewed"
                onClick={() => recordImageViewed(featured, 0)}
                disabled={viewedImageUrls.has(featuredUrl || featuredImageUrl)}
                className="inline-flex min-h-8 items-center rounded-md border border-line bg-ink px-2 text-xs font-medium text-white transition hover:bg-brand-purple disabled:cursor-default disabled:bg-canvas disabled:text-steel"
              >
                {viewedImageUrls.has(featuredUrl || featuredImageUrl) ? "已记入画像依据" : "我看了这个，记入画像"}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {images.length ? (
        <div className="mt-3 grid gap-2.5 md:grid-cols-2">
          {images.map((image, index) => {
            const pageUrl = safeExternalUrl(image.url || image.image_url || image.thumbnail);
            const imageUrl = bestImageUrl(image);
            const viewedKey = pageUrl || imageUrl;

            return (
              <article key={`${pageUrl || imageUrl || "image"}-${index}`} className="rounded-lg border border-line bg-white p-2.5">
                {imageUrl ? (
                  <img
                    src={imageUrl}
                    alt={image.title || "学习图片"}
                    className="aspect-[4/3] w-full rounded-lg border border-line bg-surface object-contain"
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="flex aspect-[4/3] w-full items-center justify-center rounded-lg border border-line bg-tint-lavender text-brand-purple">
                    {isFallbackImage(image) ? <Search size={24} /> : <ImageIcon size={24} />}
                  </div>
                )}
                <div className="mt-2 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={index === 0 ? "brand" : "neutral"}>
                      {isFallbackImage(image) ? "搜索入口" : index === 0 ? "建议先看" : image.source || "图片"}
                    </Badge>
                    {image.source ? <Badge tone="neutral">{image.source}</Badge> : null}
                    {dimensionLabel(image.width, image.height) ? (
                      <span className="text-xs text-steel">{dimensionLabel(image.width, image.height)}</span>
                    ) : null}
                  </div>
                  <h4 className="mt-1.5 line-clamp-2 text-sm font-semibold leading-5 text-ink">{image.title || "学习图片"}</h4>
                  {image.why_recommended || image.summary ? (
                    <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-charcoal">
                      {image.why_recommended || image.summary}
                    </p>
                  ) : null}
                  {pageUrl ? (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <a
                        href={pageUrl}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={`external-image-open-${index}`}
                        onClick={() => recordImageViewed(image, index)}
                        className="inline-flex min-h-8 items-center gap-1 rounded-md border border-line bg-white px-2 text-xs font-medium text-ink transition hover:border-brand-purple hover:text-brand-purple"
                      >
                        <ExternalLink size={13} />
                        {isFallbackImage(image) ? "打开搜索" : "打开查看"}
                      </a>
                      {viewedKey && viewedImageUrls.has(viewedKey) ? (
                        <span
                          className="inline-flex min-h-8 items-center rounded-md border border-line bg-canvas px-2 text-xs text-slate-500"
                          data-testid={`external-image-evidence-${index}`}
                        >
                          已记入画像依据
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-800">
          <Search size={16} />
          暂时没有找到稳定的图片链接，可以换一个更具体的关键词再试。
        </div>
      )}
    </div>
  );
}
