import { useCallback, useRef } from "react";
import { ExternalLink, PlayCircle, Search, Timer } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { PersonalizationBrief } from "@/components/results/PersonalizationBrief";
import { appendLearnerEvidence } from "@/lib/api";
import type { ExternalVideoResult } from "@/lib/types";

function formatDuration(seconds?: number | null) {
  if (!seconds || !Number.isFinite(seconds)) return "";
  const minutes = Math.max(1, Math.round(seconds / 60));
  return `${minutes} 分钟`;
}

function safeEmbedUrl(url?: string) {
  if (!url || !/^https?:\/\//.test(url)) return "";
  return url;
}

function isFallbackVideo(video?: { kind?: string }) {
  return video?.kind === "search_fallback";
}

export function ExternalVideoViewer({ result }: { result: ExternalVideoResult }) {
  const videos = result.videos ?? [];
  const featured = videos.find((item) => safeEmbedUrl(item.embed_url)) ?? videos.find((item) => !isFallbackVideo(item)) ?? videos[0];
  const embedUrl = safeEmbedUrl(featured?.embed_url);
  const hasFallbackSearch = result.fallback_search || videos.some((item) => isFallbackVideo(item));
  const chain = (result.agent_chain ?? []).filter((item) => item.label || item.detail).slice(0, 4);
  const recordedVideoUrls = useRef(new Set<string>());

  const recordVideoViewed = useCallback(
    (video: (typeof videos)[number], index: number) => {
      if (!video.url || recordedVideoUrls.current.has(video.url)) return;
      recordedVideoUrls.current.add(video.url);
      void appendLearnerEvidence({
        source: "resource",
        source_id: `external_video:${video.url}`,
        actor: "learner",
        verb: "viewed",
        object_type: "resource",
        object_id: video.url,
        title: video.title || "External learning video",
        summary: video.why_recommended || video.summary || result.response || "",
        resource_type: "external_video",
        duration_seconds: video.duration_seconds ?? null,
        confidence: 0.48,
        weight: 0.6,
        metadata: {
          rank: index + 1,
          platform: video.platform || "",
          kind: video.kind || "video",
          fallback_search: result.fallback_search || false,
          query: result.queries?.[0] || "",
          style_hint: result.style_hint || "",
          learner_profile_hints: result.learner_profile_hints ?? {},
          agent_chain: result.agent_chain ?? [],
        },
      }).catch(() => {
        recordedVideoUrls.current.delete(video.url || "");
      });
    },
    [
      result.agent_chain,
      result.fallback_search,
      result.learner_profile_hints,
      result.queries,
      result.response,
      result.style_hint,
    ],
  );

  return (
    <div className="rounded-lg border border-line bg-canvas p-3" data-testid="external-video-viewer">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">{hasFallbackSearch ? "搜索入口" : "精选视频"}</Badge>
        <Badge tone="neutral">{videos.length ? `${videos.length} 个推荐` : "等待结果"}</Badge>
      </div>

      {result.response ? <p className="mt-3 text-sm leading-6 text-slate-600">{result.response}</p> : null}
      <PersonalizationBrief hints={result.learner_profile_hints} styleHint={result.style_hint} className="mt-3" />
      {featured ? (
        <div className="mt-3 rounded-lg border border-teal-100 bg-white p-3" data-testid="external-video-watch-plan">
          <p className="text-xs font-semibold text-brand-teal">建议用法</p>
          <p className="mt-1 text-sm leading-6 text-slate-700">
            {hasFallbackSearch
              ? "先打开一个平台搜索入口，选 1-2 个短讲解，看完后回到导学提交反思或做一组练习。"
              : "先看第一个视频，暂停记下一句仍不懂的地方，再回到导学提交反思或做一组练习。"}
          </p>
        </div>
      ) : null}
      {chain.length ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500" data-testid="external-video-chain">
          <span className="font-medium text-slate-600">筛选链路</span>
          {chain.map((item, index) => (
            <span key={`${item.label || item.detail}-${index}`} className="rounded-md border border-line bg-white px-2 py-1">
              {item.label || item.detail}
            </span>
          ))}
        </div>
      ) : null}

      {embedUrl ? (
        <div className="mt-4 overflow-hidden rounded-lg border border-line bg-black">
          <iframe
            title={featured?.title || "精选学习视频"}
            src={embedUrl}
            className="aspect-video w-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        </div>
      ) : null}

      {videos.length ? (
        <div className="mt-4 grid gap-3">
          {videos.map((video, index) => (
            <article key={`${video.url}-${index}`} className="rounded-lg border border-line bg-white p-3">
              <div className="grid gap-3 md:grid-cols-[9rem_minmax(0,1fr)]">
                {video.thumbnail ? (
                  <img
                    src={video.thumbnail}
                    alt=""
                    className="aspect-video w-full rounded-lg border border-line bg-slate-100 object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex aspect-video w-full items-center justify-center rounded-lg border border-line bg-teal-50 text-brand-teal">
                    {isFallbackVideo(video) ? <Search size={28} /> : <PlayCircle size={28} />}
                  </div>
                )}
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={index === 0 ? "brand" : "neutral"}>
                      {isFallbackVideo(video) ? "搜索入口" : index === 0 ? "建议先看" : video.platform || "视频"}
                    </Badge>
                    {video.platform ? <Badge tone="neutral">{video.platform}</Badge> : null}
                    {formatDuration(video.duration_seconds) ? (
                      <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                        <Timer size={13} />
                        {formatDuration(video.duration_seconds)}
                      </span>
                    ) : null}
                  </div>
                  <h4 className="mt-2 line-clamp-2 text-sm font-semibold leading-5 text-ink">{video.title || "学习视频"}</h4>
                  {video.why_recommended || video.summary ? (
                    <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">
                      {video.why_recommended || video.summary}
                    </p>
                  ) : null}
                  {video.url ? (
                    <a
                      href={video.url}
                      target="_blank"
                      rel="noreferrer"
                      data-testid={`external-video-open-${index}`}
                      onClick={() => recordVideoViewed(video, index)}
                      className="mt-3 inline-flex min-h-8 items-center gap-1 rounded-md border border-teal-200 bg-teal-50 px-2 text-xs font-medium text-brand-teal transition hover:bg-white"
                    >
                      <ExternalLink size={13} />
                      {isFallbackVideo(video) ? "打开搜索" : "打开观看"}
                    </a>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <Search size={16} />
          暂时没有找到稳定的视频链接，可以换一个更具体的关键词再试。
        </div>
      )}
    </div>
  );
}
