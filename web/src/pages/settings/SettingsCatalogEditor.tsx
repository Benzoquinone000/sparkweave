import { Loader2, Rocket, Save, Settings2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import type { ModelCatalog, SettingsResponse } from "@/lib/types";
import { SharedCredentialsBlock } from "./SharedCredentialsBlock";
import { ConfigSectionRail, type ConfigSectionId } from "./SettingsConfigControls";
import { EmbeddingConfigPanel, LlmConfigPanel, OcrConfigPanel, SearchConfigPanel } from "./SettingsServiceConfigPanels";
import {
  activeModel,
  activeProfile,
  applyEmbeddingForm,
  applyLlmForm,
  applyOcrForm,
  applySearchForm,
  applySharedCredentials,
  effectiveEmbeddingApiKey,
  effectiveLlmApiKey,
  effectiveOcrApiKey,
  effectiveSearchApiKey,
  extractSharedCredentials,
  optionalOcrSetting,
  type EmbeddingForm,
  type LlmForm,
  type OcrForm,
  type SearchForm,
  type SharedCredentialsForm,
} from "./settingsCatalogUtils";

export function SettingsCatalogEditor({
  settings,
  pending,
  tourMode = false,
  tourCompleted = false,
  tourPending = false,
  onSave,
  onCompleteTour,
}: {
  settings: SettingsResponse;
  pending: boolean;
  tourMode?: boolean;
  tourCompleted?: boolean;
  tourPending?: boolean;
  onSave: (catalog: ModelCatalog, ui: Partial<SettingsResponse["ui"]>) => Promise<void>;
  onCompleteTour?: (catalog: ModelCatalog, ui: Partial<SettingsResponse["ui"]>) => Promise<void>;
}) {
  const llmProfile = activeProfile(settings.catalog.services.llm);
  const embeddingProfile = activeProfile(settings.catalog.services.embedding);
  const searchProfile = activeProfile(settings.catalog.services.search);
  const ocrService = settings.catalog.services.ocr ?? { active_profile_id: undefined, profiles: [] };
  const ocrProfile = activeProfile(ocrService);
  const llmModel = activeModel(settings.catalog.services.llm, llmProfile);
  const embeddingModel = activeModel(settings.catalog.services.embedding, embeddingProfile);
  const initialLlmBinding = llmProfile?.binding || "openai";
  const initialLlmProvider = settings.providers.llm.find((provider) => provider.value === initialLlmBinding);
  const initialLlmKeyShape = (llmProfile?.api_key || "").includes(":") ? "ak_sk" : "api_password";
  const initialEmbeddingBinding = embeddingProfile?.binding || "openai";
  const initialEmbeddingProvider = settings.providers.embedding.find((provider) => provider.value === initialEmbeddingBinding);
  const initialSharedCredentials = useMemo(() => extractSharedCredentials(settings.catalog), [settings.catalog]);
  const [sharedCredentials, setSharedCredentials] = useState<SharedCredentialsForm>(initialSharedCredentials);
  const [llm, setLlm] = useState<LlmForm>({
    binding: initialLlmBinding,
    baseUrl: llmProfile?.base_url || "",
    apiKey: effectiveLlmApiKey(llmProfile, initialSharedCredentials),
    model: llmModel?.model || initialLlmProvider?.default_model || initialLlmProvider?.models?.[0] || "",
    iflytekAuthMode: initialLlmKeyShape,
    iflytekAppId: initialSharedCredentials.iflytekAppId || llmProfile?.extra_headers?.app_id || "",
    iflytekApiSecret: initialSharedCredentials.iflytekApiSecret || llmProfile?.extra_headers?.api_secret || "",
  });
  const [embedding, setEmbedding] = useState<EmbeddingForm>({
    binding: initialEmbeddingBinding,
    baseUrl: embeddingProfile?.base_url || "",
    apiKey: effectiveEmbeddingApiKey(embeddingProfile, initialSharedCredentials),
    model: embeddingModel?.model || initialEmbeddingProvider?.default_model || initialEmbeddingProvider?.models?.[0] || "",
    dimension: embeddingModel?.dimension || initialEmbeddingProvider?.default_dim || "",
    iflytekAuthMode: "api_password",
    iflytekAppId: initialSharedCredentials.iflytekAppId || embeddingProfile?.extra_headers?.app_id || "",
    iflytekApiSecret: initialSharedCredentials.iflytekApiSecret || embeddingProfile?.extra_headers?.api_secret || "",
    iflytekDomain: embeddingProfile?.extra_headers?.domain || "para",
  });
  const [search, setSearch] = useState<SearchForm>({
    provider: searchProfile?.provider || "tavily",
    baseUrl: searchProfile?.base_url || "",
    apiKey: effectiveSearchApiKey(searchProfile, initialSharedCredentials),
  });
  const [ocr, setOcr] = useState<OcrForm>({
    provider: ocrProfile?.provider || "iflytek",
    strategy: ocrProfile?.strategy || "auto",
    appId: initialSharedCredentials.iflytekAppId || ocrProfile?.extra_headers?.app_id || "",
    apiKey: effectiveOcrApiKey(ocrProfile, initialSharedCredentials),
    apiSecret: initialSharedCredentials.iflytekApiSecret || ocrProfile?.extra_headers?.api_secret || "",
    baseUrl: ocrProfile?.base_url || "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
    model: ocrProfile?.extra_headers?.model || "deepseek-ai/DeepSeek-OCR",
    serviceId: ocrProfile?.extra_headers?.service_id || "se75ocrbm",
    category: ocrProfile?.extra_headers?.category || "ch_en_public_cloud",
    timeout: optionalOcrSetting(ocrProfile?.timeout, "90"),
    maxPages: optionalOcrSetting(ocrProfile?.max_pages, "80", "0"),
    dpi: optionalOcrSetting(ocrProfile?.dpi, "200"),
    minTextChars: optionalOcrSetting(ocrProfile?.min_text_chars, "40"),
  });
  const [activeConfigSection, setActiveConfigSection] = useState<ConfigSectionId>("llm");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextCatalog = structuredClone(settings.catalog);
    applyLlmForm(nextCatalog.services.llm, llm);
    applyEmbeddingForm(nextCatalog.services.embedding, embedding);
    applySearchForm(nextCatalog.services.search, search);
    applyOcrForm(nextCatalog, ocr);
    applySharedCredentials(nextCatalog, sharedCredentials);
    const ui = { language: settings.ui.language, theme: settings.ui.theme };
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLElement | null;
    if (submitter?.dataset.action === "complete-tour" && onCompleteTour) {
      await onCompleteTour(nextCatalog, ui);
      return;
    }
    await onSave(nextCatalog, ui);
  };

  return (
    <form className="rounded-lg border border-line bg-white p-3" onSubmit={submit}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Settings2 size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">模型配置</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">当前密钥会直接显示在表单中，保存后立即生效。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button tone="primary" type="submit" disabled={pending || tourPending} data-testid="settings-save-apply">
            {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            保存并应用
          </Button>
          {tourMode ? (
            <Button
              tone="primary"
              type="submit"
              data-action="complete-tour"
              aria-label={tourCompleted ? "启动向导已完成" : "完成并启动"}
              disabled={pending || tourPending || tourCompleted}
              className="border-brand-red bg-brand-red hover:bg-red-700"
            >
              {tourPending ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
              {tourCompleted ? "已完成" : "完成并启动"}
            </Button>
          ) : null}
        </div>
      </div>

      <SharedCredentialsBlock value={sharedCredentials} onChange={setSharedCredentials} />

      <div className="mt-5 grid gap-4 lg:grid-cols-[236px_minmax(0,1fr)]">
        <ConfigSectionRail active={activeConfigSection} onChange={setActiveConfigSection} />
        <div className="min-w-0">
          <div className={activeConfigSection === "llm" ? "" : "hidden"}>
            <LlmConfigPanel value={llm} providers={settings.providers.llm} onChange={setLlm} />
          </div>

          <div className={activeConfigSection === "embedding" ? "" : "hidden"}>
            <EmbeddingConfigPanel value={embedding} providers={settings.providers.embedding} onChange={setEmbedding} />
          </div>

          <div className={activeConfigSection === "search" ? "" : "hidden"}>
            <SearchConfigPanel value={search} providers={settings.providers.search} onChange={setSearch} />
          </div>

          <div className={activeConfigSection === "ocr" ? "" : "hidden"}>
            <OcrConfigPanel value={ocr} providers={settings.providers.ocr} onChange={setOcr} />
          </div>
        </div>
      </div>
    </form>
  );
}
