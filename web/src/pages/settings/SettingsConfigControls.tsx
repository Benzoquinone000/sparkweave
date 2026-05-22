import { ChevronDown, ExternalLink } from "lucide-react";
import { useState, type ReactNode } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";

export type ConfigSectionId = "llm" | "embedding" | "search" | "ocr" | "speech";

const CONFIG_SECTION_ITEMS: Array<{ id: ConfigSectionId; label: string; helper: string; dot: string }> = [
  { id: "llm", label: "问答模型", helper: "对话、导学、资源生成", dot: "bg-brand-purple" },
  { id: "embedding", label: "资料理解", helper: "资料入库和相似内容匹配", dot: "bg-brand-teal" },
  { id: "search", label: "联网搜索", helper: "外部资料和精选视频", dot: "bg-brand-orange" },
  { id: "ocr", label: "图片文字识别", helper: "扫描 PDF 与图片文字", dot: "bg-brand-blue" },
  { id: "speech", label: "语音学习", helper: "讲解、输入和口语评测", dot: "bg-brand-red" },
];

export function ConfigSectionRail({
  active,
  onChange,
}: {
  active: ConfigSectionId;
  onChange: (id: ConfigSectionId) => void;
}) {
  return (
    <aside className="dt-interactive rounded-lg border border-line bg-canvas p-2">
      <p className="px-2 pb-2 text-xs font-semibold text-steel">选择要连接的服务</p>
      <div className="grid gap-1">
        {CONFIG_SECTION_ITEMS.map((item) => {
          const selected = active === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={`dt-interactive flex min-h-14 items-center gap-3 rounded-md px-3 text-left transition ${
                selected
                  ? "border border-brand-purple-300 bg-tint-lavender text-ink shadow-[0_1px_2px_rgba(15,15,15,0.04)]"
                  : "border border-transparent text-charcoal hover:border-line hover:bg-white"
              }`}
              aria-pressed={selected}
              data-testid={`settings-config-section-${item.id}`}
            >
              <span className={`h-2.5 w-2.5 shrink-0 rounded-sm ${item.dot}`} />
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold">{item.label}</span>
                <span className="mt-0.5 block truncate text-xs text-steel">{item.helper}</span>
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

export function ConfigBlock({ title, summary, children }: { title: string; summary?: string; children: ReactNode }) {
  return (
    <section className="dt-interactive rounded-lg border border-line bg-white p-4 hover:border-brand-purple-300">
      <div>
        <h3 className="font-semibold text-ink">{title}</h3>
        {summary ? <p className="mt-1 text-sm leading-6 text-slate-500">{summary}</p> : null}
      </div>
      <div className="mt-4 grid gap-4">{children}</div>
    </section>
  );
}

export function ProviderSelect({
  label,
  value,
  providers,
  onChange,
  testId,
}: {
  label: string;
  value: string;
  providers: ProviderChoice[];
  onChange: (value: string, provider?: ProviderChoice) => void;
  testId?: string;
}) {
  return (
    <FieldShell label={label}>
      <SelectInput
        value={value}
        data-testid={testId}
        onChange={(event) => {
          const provider = providers.find((item) => item.value === event.target.value);
          onChange(event.target.value, provider);
        }}
      >
        {providers.map((provider) => (
          <option key={provider.value} value={provider.value}>
            {friendlyProviderLabel(provider.label)}
          </option>
        ))}
      </SelectInput>
    </FieldShell>
  );
}

function friendlyProviderLabel(label: string) {
  const normalized = label.trim();
  const labels: Record<string, string> = {
    "iFlytek Spark X": "讯飞星火 X",
    "iFlytek MaaS Coding": "讯飞 MaaS Coding",
    "iFlytek Spark Embedding": "讯飞星火 Embedding",
    "iFlytek ONE SEARCH": "讯飞 ONE SEARCH",
    "iFlytek OCR for LLM": "讯飞图片文字识别",
    "iFlytek Formula Recognition": "讯飞公式识别",
    "iFlytek Spark Image Understanding": "讯飞图片理解",
    "iFlytek Super Smart TTS": "讯飞语音合成",
    "iFlytek Voice Dictation": "讯飞语音听写",
    "iFlytek Speech Evaluation": "讯飞语音评测",
    "SiliconFlow DeepSeek-OCR": "硅基流动文档识别",
  };
  return labels[normalized] || normalized;
}

export function ProviderQuickNote({ provider }: { provider?: ProviderChoice }) {
  if (!provider) return null;
  const parts = [
    provider.credential_hint ? `密钥要求：${friendlyCredentialHint(provider.credential_hint)}` : "",
    friendlyModelHint(provider.model_hint || ""),
  ].filter(Boolean);
  if (!parts.length && !provider.docs_url) return null;
  return (
    <p className="text-xs leading-5 text-steel">
      {parts.join(" · ")}
      {provider.docs_url ? (
        <a
          className="ml-2 inline-flex items-center gap-1 font-medium text-brand-purple hover:text-brand-purple-700"
          href={provider.docs_url}
          target="_blank"
          rel="noreferrer"
        >
          官方文档
          <ExternalLink size={12} />
        </a>
      ) : null}
    </p>
  );
}

function friendlyCredentialHint(hint: string) {
  return hint
    .trim()
    .replace(/\b[A-Z0-9]+(?:_[A-Z0-9]+)*_API_KEY\b/g, "访问密钥")
    .replace(/\b[A-Z0-9]+(?:_[A-Z0-9]+)*_API_SECRET\b/g, "Secret")
    .replace(/\b[A-Z0-9]+(?:_[A-Z0-9]+)*_API_PASSWORD\b/g, "连接密码")
    .replace(/\b[A-Z0-9]+(?:_[A-Z0-9]+)*_APPID\b/g, "AppID")
    .replace(/APIKey/gi, "访问密钥")
    .replace(/API Key/gi, "访问密钥")
    .replace(/APISecret/gi, "Secret")
    .replace(/APIPassword/gi, "连接密码")
    .replace(/\s*\/\s*/g, " / ")
    .replace(/\s*\+\s*/g, " + ")
    .replace(/\b访问密钥\s*\/\s*访问密钥\b/g, "访问密钥")
    .replace(/\bSecret\s*\/\s*Secret\b/g, "Secret")
    .replace(/\b连接密码\s*\/\s*连接密码\b/g, "连接密码");
}

function friendlyModelHint(hint: string) {
  return hint
    .trim()
    .replace(/model ID/gi, "模型名称")
    .replace(/模型 ID/g, "模型名称")
    .replace(/deployment name/gi, "部署名称")
    .replace(/OpenAI-compatible/gi, "OpenAI 兼容")
    .replace(/endpoint/gi, "服务地址")
    .replace(/\bAgentic\b/gi, "多步骤")
    .replace(/\bAgent\b/g, "长任务")
    .replace(/\bRAG\b/g, "资料问答");
}

export function PresetModelInput({
  id,
  value,
  options,
  recommendedModel,
  onChange,
  testId,
  presetTestId,
  placeholder = "选择预设或输入模型名称",
}: {
  id: string;
  value: string;
  options: string[];
  recommendedModel?: string;
  onChange: (value: string) => void;
  testId: string;
  presetTestId?: string;
  placeholder?: string;
}) {
  const uniqueOptions = Array.from(new Set(options.filter(Boolean)));
  const [open, setOpen] = useState(false);
  const query = value.trim().toLowerCase();
  const visibleOptions = query
    ? uniqueOptions.filter((model) => model.toLowerCase().includes(query))
    : uniqueOptions;
  return (
    <div className="relative">
      <TextInput
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onFocus={() => {
          if (uniqueOptions.length) setOpen(true);
        }}
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 120);
        }}
        placeholder={placeholder}
        className={uniqueOptions.length ? "pr-10" : undefined}
        data-testid={testId}
      />
      {uniqueOptions.length ? (
        <button
          type="button"
          className="absolute right-1 top-1 flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-ink"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => setOpen((current) => !current)}
          aria-label="选择预设模型"
          data-testid={presetTestId}
        >
          <ChevronDown size={16} className={open ? "rotate-180 transition" : "transition"} />
        </button>
      ) : null}
      {uniqueOptions.length && open ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-56 overflow-y-auto rounded-lg border border-line bg-white p-1 shadow-soft">
          {visibleOptions.length ? (
            visibleOptions.map((model) => (
              <button
                key={model}
                type="button"
                className={`block w-full rounded-md px-3 py-2 text-left text-sm transition hover:bg-tint-lavender ${
                  model === value ? "bg-tint-lavender text-brand-purple" : "text-ink"
                }`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(model);
                  setOpen(false);
                }}
              >
                <span className="flex min-w-0 items-center justify-between gap-2">
                  <span className="truncate">{model}</span>
                  {model === recommendedModel ? (
                    <span className="shrink-0 rounded-sm bg-tint-lavender px-1.5 py-0.5 text-[11px] font-medium text-brand-purple">
                      推荐
                    </span>
                  ) : null}
                </span>
              </button>
            ))
          ) : (
            <div className="px-3 py-2 text-sm text-slate-500">没有匹配的预设，可继续手动输入模型名称。</div>
          )}
        </div>
      ) : null}
    </div>
  );
}
