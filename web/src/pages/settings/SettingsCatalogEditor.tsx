import { Bot, Code2, Loader2, Mic2, Rocket, Save, ScanText, Settings2, Sparkles } from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { ModelCatalog, SettingsResponse } from "@/lib/types";
import { SharedCredentialsBlock } from "./SharedCredentialsBlock";
import { ConfigSectionRail, type ConfigSectionId } from "./SettingsConfigControls";
import { EmbeddingConfigPanel, LlmConfigPanel, OcrConfigPanel, SearchConfigPanel, SpeechConfigPanel } from "./SettingsServiceConfigPanels";
import {
  activeModel,
  activeProfile,
  applyEmbeddingForm,
  applyFormulaOcrForm,
  applyImageUnderstandingForm,
  applyLlmForm,
  applyOcrForm,
  applySearchForm,
  applySpeechForm,
  applySharedCredentials,
  effectiveEmbeddingApiKey,
  effectiveIflytekServiceApiKey,
  effectiveLlmApiKey,
  effectiveOcrApiKey,
  effectiveSearchApiKey,
  extractSharedCredentials,
  optionalOcrSetting,
  type EmbeddingForm,
  type FormulaOcrForm,
  type ImageUnderstandingForm,
  type LlmForm,
  type OcrForm,
  type SearchForm,
  type SharedCredentialsForm,
  type SpeechForm,
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
  const formulaOcrService = settings.catalog.services.formula_ocr ?? { active_profile_id: undefined, profiles: [] };
  const imageUnderstandingService = settings.catalog.services.image_understanding ?? { active_profile_id: undefined, profiles: [] };
  const ttsService = settings.catalog.services.tts ?? { active_profile_id: undefined, profiles: [] };
  const asrService = settings.catalog.services.asr ?? { active_profile_id: undefined, profiles: [] };
  const speechEvalService = settings.catalog.services.speech_eval ?? { active_profile_id: undefined, profiles: [] };
  const ocrProfile = activeProfile(ocrService);
  const formulaOcrProfile = activeProfile(formulaOcrService);
  const imageUnderstandingProfile = activeProfile(imageUnderstandingService);
  const ttsProfile = activeProfile(ttsService);
  const asrProfile = activeProfile(asrService);
  const speechEvalProfile = activeProfile(speechEvalService);
  const ttsExtra = ttsProfile?.extra_headers ?? {};
  const asrExtra = asrProfile?.extra_headers ?? {};
  const speechEvalExtra = speechEvalProfile?.extra_headers ?? {};
  const formulaOcrExtra = formulaOcrProfile?.extra_headers ?? {};
  const imageUnderstandingExtra = imageUnderstandingProfile?.extra_headers ?? {};
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
  const [formulaOcr, setFormulaOcr] = useState<FormulaOcrForm>({
    provider: formulaOcrProfile?.provider || "iflytek",
    appId: initialSharedCredentials.iflytekAppId || formulaOcrExtra.app_id || "",
    apiKey: effectiveIflytekServiceApiKey(formulaOcrProfile, initialSharedCredentials),
    apiSecret: initialSharedCredentials.iflytekApiSecret || formulaOcrExtra.api_secret || "",
    baseUrl: formulaOcrProfile?.base_url || "https://rest-api.xfyun.cn/v2/itr",
    ent: String(formulaOcrExtra.ent || "teach-photo-print"),
    aue: String(formulaOcrExtra.aue || "raw"),
    timeout: String(formulaOcrProfile?.timeout || "30"),
  });
  const [imageUnderstanding, setImageUnderstanding] = useState<ImageUnderstandingForm>({
    provider: imageUnderstandingProfile?.provider || "iflytek",
    appId: initialSharedCredentials.iflytekAppId || imageUnderstandingExtra.app_id || "",
    apiKey: effectiveIflytekServiceApiKey(imageUnderstandingProfile, initialSharedCredentials),
    apiSecret: initialSharedCredentials.iflytekApiSecret || imageUnderstandingExtra.api_secret || "",
    baseUrl: imageUnderstandingProfile?.base_url || "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image",
    protocol: String(imageUnderstandingExtra.protocol || "spark_image"),
    domain: String(imageUnderstandingExtra.domain || "imagev3"),
    maxTokens: String(imageUnderstandingExtra.max_tokens || "2048"),
    temperature: String(imageUnderstandingExtra.temperature || "0.2"),
    topK: String(imageUnderstandingExtra.top_k || "4"),
    timeout: String(imageUnderstandingProfile?.timeout || "45"),
    uid: String(imageUnderstandingExtra.uid || "sparkweave"),
  });
  const [speech, setSpeech] = useState<SpeechForm>({
    ttsProvider: ttsProfile?.provider || "iflytek",
    ttsAppId: String(ttsExtra.app_id || ""),
    ttsApiKey: ttsProfile?.api_key || "",
    ttsApiSecret: String(ttsExtra.api_secret || ""),
    ttsBaseUrl: ttsProfile?.base_url || "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6",
    ttsVoice: String(ttsExtra.voice || "x5_lingxiaoxuan_flow"),
    ttsEncoding: String(ttsExtra.encoding || "lame"),
    ttsSampleRate: String(ttsExtra.sample_rate || "24000"),
    ttsSpeed: String(ttsExtra.speed || "50"),
    ttsVolume: String(ttsExtra.volume || "50"),
    ttsPitch: String(ttsExtra.pitch || "50"),
    asrProvider: asrProfile?.provider || "iflytek",
    asrAppId: String(asrExtra.app_id || ""),
    asrApiKey: asrProfile?.api_key || "",
    asrApiSecret: String(asrExtra.api_secret || ""),
    asrBaseUrl: asrProfile?.base_url || "wss://iat-api.xfyun.cn/v2/iat",
    asrLanguage: String(asrExtra.language || "zh_cn"),
    asrAccent: String(asrExtra.accent || "mandarin"),
    asrDomain: String(asrExtra.domain || "iat"),
    asrVadEos: String(asrExtra.vad_eos || "3000"),
    speechEvalProvider: speechEvalProfile?.provider || "iflytek",
    speechEvalAppId: String(speechEvalExtra.app_id || ""),
    speechEvalApiKey: speechEvalProfile?.api_key || "",
    speechEvalApiSecret: String(speechEvalExtra.api_secret || ""),
    speechEvalBaseUrl: speechEvalProfile?.base_url || "wss://ise-api.xfyun.cn/v2/open-ise",
    speechEvalCategory: String(speechEvalExtra.category || "read_sentence"),
    speechEvalLanguage: String(speechEvalExtra.language || "zh_cn"),
  });
  const [activeConfigSection, setActiveConfigSection] = useState<ConfigSectionId>("llm");

  function applyIflytekCorePreset(focus: ConfigSectionId = "llm") {
    const sparkProvider = settings.providers.llm.find((provider) => provider.value === "iflytek_spark_ws");
    const embeddingProvider = settings.providers.embedding.find((provider) => provider.value === "iflytek_spark");
    const searchProvider = settings.providers.search.find((provider) => provider.value === "iflytek_spark");
    setLlm((current) => ({
      ...current,
      binding: "iflytek_spark_ws",
      baseUrl: sparkProvider?.base_url || "https://spark-api-open.xf-yun.com/x2/",
      model: sparkProvider?.default_model || "spark-x",
      iflytekAuthMode: "api_password",
    }));
    setEmbedding((current) => ({
      ...current,
      binding: "iflytek_spark",
      baseUrl: embeddingProvider?.base_url || "https://emb-cn-huabei-1.xf-yun.com/",
      model: embeddingProvider?.default_model || "llm-embedding",
      dimension: embeddingProvider?.default_dim || "2560",
      iflytekDomain: "para",
    }));
    setSearch((current) => ({
      ...current,
      provider: "iflytek_spark",
      baseUrl: searchProvider?.base_url || "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search",
    }));
    setActiveConfigSection(focus);
  }

  function applyIflytekVisionPreset(focus: ConfigSectionId = "ocr") {
    const ocrProvider = settings.providers.ocr?.find((provider) => provider.value === "iflytek");
    const formulaProvider = settings.providers.formula_ocr?.find((provider) => provider.value === "iflytek");
    const imageProvider = settings.providers.image_understanding?.find((provider) => provider.value === "iflytek");
    setOcr((current) => ({
      ...current,
      provider: "iflytek",
      strategy: "iflytek_first",
      baseUrl: ocrProvider?.base_url || "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
      serviceId: "se75ocrbm",
      category: "ch_en_public_cloud",
    }));
    setFormulaOcr((current) => ({
      ...current,
      provider: "iflytek",
      baseUrl: formulaProvider?.base_url || "https://rest-api.xfyun.cn/v2/itr",
      ent: "teach-photo-print",
      aue: "raw",
      timeout: "30",
    }));
    setImageUnderstanding((current) => ({
      ...current,
      provider: "iflytek",
      baseUrl: imageProvider?.base_url || "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image",
      protocol: "spark_image",
      domain: "imagev3",
      maxTokens: "2048",
      temperature: "0.2",
      topK: "4",
      timeout: "45",
      uid: "sparkweave",
    }));
    setActiveConfigSection(focus);
  }

  function applyIflytekSpeechPreset(focus: ConfigSectionId = "speech") {
    const ttsProvider = settings.providers.tts?.find((provider) => provider.value === "iflytek");
    const asrProvider = settings.providers.asr?.find((provider) => provider.value === "iflytek");
    const speechEvalProvider = settings.providers.speech_eval?.find((provider) => provider.value === "iflytek");
    setSpeech((current) => ({
      ...current,
      ttsProvider: "iflytek",
      ttsBaseUrl: ttsProvider?.base_url || "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6",
      ttsVoice: "x5_lingxiaoxuan_flow",
      ttsEncoding: "lame",
      ttsSampleRate: "24000",
      ttsSpeed: "50",
      ttsVolume: "50",
      ttsPitch: "50",
      asrProvider: "iflytek",
      asrBaseUrl: asrProvider?.base_url || "wss://iat-api.xfyun.cn/v2/iat",
      asrLanguage: "zh_cn",
      asrAccent: "mandarin",
      asrDomain: "iat",
      asrVadEos: "3000",
      speechEvalProvider: "iflytek",
      speechEvalBaseUrl: speechEvalProvider?.base_url || "wss://ise-api.xfyun.cn/v2/open-ise",
      speechEvalCategory: "read_sentence",
      speechEvalLanguage: "zh_cn",
    }));
    setActiveConfigSection(focus);
  }

  function applyIflytekCompetitionPreset() {
    applyIflytekCorePreset("llm");
    applyIflytekVisionPreset("llm");
    applyIflytekSpeechPreset("llm");
  }

  function applyIflytekMaasCodingPreset() {
    const maasProvider = settings.providers.llm.find((provider) => provider.value === "iflytek_maas_coding");
    setLlm((current) => ({
      ...current,
      binding: "iflytek_maas_coding",
      baseUrl: maasProvider?.base_url || "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2",
      model: maasProvider?.default_model || "astron-code-latest",
      iflytekAuthMode: "api_password",
    }));
    setActiveConfigSection("llm");
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextCatalog = structuredClone(settings.catalog);
    applyLlmForm(nextCatalog.services.llm, llm);
    applyEmbeddingForm(nextCatalog.services.embedding, embedding);
    applySearchForm(nextCatalog.services.search, search);
    applyOcrForm(nextCatalog, ocr);
    applyFormulaOcrForm(nextCatalog, formulaOcr);
    applyImageUnderstandingForm(nextCatalog, imageUnderstanding);
    applySpeechForm(nextCatalog, speech);
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
          <p className="mt-1 text-sm leading-6 text-slate-500">当前服务配置会显示在表单中，保存后立即生效。</p>
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

      <IflytekPresetBar
        onUseCorePreset={() => applyIflytekCorePreset()}
        onUseCompetitionPreset={applyIflytekCompetitionPreset}
        onUseMaasCodingPreset={applyIflytekMaasCodingPreset}
        onUseVisionPreset={() => applyIflytekVisionPreset()}
        onUseSpeechPreset={() => applyIflytekSpeechPreset()}
      />

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
            <OcrConfigPanel
              value={ocr}
              providers={settings.providers.ocr}
              formulaValue={formulaOcr}
              formulaProviders={settings.providers.formula_ocr}
              imageValue={imageUnderstanding}
              imageProviders={settings.providers.image_understanding}
              onChange={setOcr}
              onFormulaChange={setFormulaOcr}
              onImageChange={setImageUnderstanding}
            />
          </div>

          <div className={activeConfigSection === "speech" ? "" : "hidden"}>
            <SpeechConfigPanel
              value={speech}
              ttsProviders={settings.providers.tts}
              asrProviders={settings.providers.asr}
              speechEvalProviders={settings.providers.speech_eval}
              onChange={setSpeech}
            />
          </div>
        </div>
      </div>
    </form>
  );
}

function IflytekPresetBar({
  onUseCorePreset,
  onUseCompetitionPreset,
  onUseMaasCodingPreset,
  onUseVisionPreset,
  onUseSpeechPreset,
}: {
  onUseCorePreset: () => void;
  onUseCompetitionPreset: () => void;
  onUseMaasCodingPreset: () => void;
  onUseVisionPreset: () => void;
  onUseSpeechPreset: () => void;
}) {
  return (
    <section className="mt-5 rounded-lg border border-brand-purple-200 bg-canvas p-3" data-testid="settings-iflytek-presets">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-brand-purple" />
            <h3 className="text-sm font-semibold text-ink">科大讯飞学习智能体套件</h3>
          </div>
          <p className="mt-1 text-xs leading-5 text-steel">把赛题要求里的大模型、搜索、OCR、多模态和语音能力集中在这里配置。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone="brand">不覆盖密钥</Badge>
          <Badge tone="neutral">离线替补默认启用</Badge>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2 xl:grid-cols-5">
        <IflytekPresetCard
          title="星火学习底座"
          detail="问答模型、Embedding、ONE SEARCH"
          tags={["LLM", "资料", "搜索"]}
          icon={<Bot size={17} />}
          testId="settings-preset-iflytek-core"
          onClick={onUseCorePreset}
        />
        <IflytekPresetCard
          title="比赛全链路"
          detail="一键切到讯飞主线交付配置"
          tags={["赛题", "多模态", "语音"]}
          icon={<Sparkles size={17} />}
          tone="primary"
          testId="settings-preset-iflytek-full"
          onClick={onUseCompetitionPreset}
        />
        <IflytekPresetCard
          title="多模态解题"
          detail="图片文字、公式识别、图片理解"
          tags={["OCR", "公式", "视觉"]}
          icon={<ScanText size={17} />}
          testId="settings-preset-iflytek-vision"
          onClick={onUseVisionPreset}
        />
        <IflytekPresetCard
          title="语音学习链"
          detail="讲解、听写、朗读评测"
          tags={["TTS", "ASR", "评测"]}
          icon={<Mic2 size={17} />}
          testId="settings-preset-iflytek-speech"
          onClick={onUseSpeechPreset}
        />
        <IflytekPresetCard
          title="Astron Code"
          detail="MaaS Coding 工程智能体"
          tags={["MaaS", "代码"]}
          icon={<Code2 size={17} />}
          testId="settings-preset-maas-coding"
          onClick={onUseMaasCodingPreset}
        />
      </div>
      <p className="mt-3 rounded-md border border-line bg-white px-3 py-2 text-xs leading-5 text-steel">
        当讯飞密钥、网络或产品权限不可用时，系统会自动切到本地替补：保留学习流程、生成演示音频或占位分析，并在结果中标记为离线替补。
      </p>
    </section>
  );
}

function IflytekPresetCard({
  title,
  detail,
  tags,
  icon,
  tone = "secondary",
  testId,
  onClick,
}: {
  title: string;
  detail: string;
  tags: string[];
  icon: ReactNode;
  tone?: "primary" | "secondary";
  testId: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`dt-interactive flex min-h-36 flex-col items-start justify-between rounded-lg border p-3 text-left transition ${
        tone === "primary" ? "border-brand-purple-300 bg-white shadow-[0_10px_24px_rgba(15,23,42,0.06)]" : "border-line bg-white"
      }`}
      onClick={onClick}
      data-testid={testId}
    >
      <span className="flex w-full items-start justify-between gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-tint-lavender text-brand-purple">
          {icon}
        </span>
        <span className="text-xs font-medium text-brand-purple">{tone === "primary" ? "推荐" : "预设"}</span>
      </span>
      <span className="mt-3 block">
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="mt-1 block text-xs leading-5 text-steel">{detail}</span>
      </span>
      <span className="mt-3 flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <span key={tag} className="rounded-sm bg-canvas px-1.5 py-0.5 text-[11px] font-medium text-slate-500">
            {tag}
          </span>
        ))}
      </span>
    </button>
  );
}
