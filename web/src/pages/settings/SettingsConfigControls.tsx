import { ChevronDown } from "lucide-react";
import { useState, type ReactNode } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";

export type ConfigSectionId = "llm" | "embedding" | "search" | "ocr";

const CONFIG_SECTION_ITEMS: Array<{ id: ConfigSectionId; label: string; helper: string; dot: string }> = [
  { id: "llm", label: "问答模型", helper: "对话、导学、资源生成", dot: "bg-brand-purple" },
  { id: "embedding", label: "向量模型", helper: "知识库检索和语义理解", dot: "bg-brand-teal" },
  { id: "search", label: "联网搜索", helper: "外部资料和精选视频", dot: "bg-brand-orange" },
  { id: "ocr", label: "OCR 识别", helper: "扫描 PDF 与图片文字", dot: "bg-brand-blue" },
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
      <p className="px-2 pb-2 text-xs font-semibold text-steel">选择要配置的服务</p>
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
            >
              <span className={`h-2.5 w-2.5 shrink-0 ${item.dot}`} style={{ borderRadius: "50%" }} />
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
            {provider.label}
          </option>
        ))}
      </SelectInput>
    </FieldShell>
  );
}

export function PresetModelInput({
  id,
  value,
  options,
  onChange,
  testId,
  presetTestId,
}: {
  id: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  testId: string;
  presetTestId?: string;
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
        placeholder="输入模型 ID"
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
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-56 overflow-y-auto rounded-lg border border-line bg-white p-1 shadow-lg">
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
                {model}
              </button>
            ))
          ) : (
            <div className="px-3 py-2 text-sm text-slate-500">没有匹配的预设，继续手动输入。</div>
          )}
        </div>
      ) : null}
    </div>
  );
}
