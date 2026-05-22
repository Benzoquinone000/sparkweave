import type { EndpointProfile, ModelCatalog, ProviderChoice, ServiceCatalog } from "@/lib/types";

export type IflytekLlmAuthMode = "api_password" | "ak_sk";

export type LlmForm = {
  binding: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  iflytekAuthMode: IflytekLlmAuthMode;
  iflytekAppId: string;
  iflytekApiSecret: string;
};

export type EmbeddingForm = LlmForm & {
  dimension: string;
  iflytekAppId: string;
  iflytekApiSecret: string;
  iflytekDomain: string;
};

export type SearchForm = {
  provider: string;
  baseUrl: string;
  apiKey: string;
};

export type OcrForm = {
  provider: string;
  strategy: string;
  appId: string;
  apiKey: string;
  apiSecret: string;
  baseUrl: string;
  model: string;
  serviceId: string;
  category: string;
  timeout: string;
  maxPages: string;
  dpi: string;
  minTextChars: string;
};

export type FormulaOcrForm = {
  provider: string;
  appId: string;
  apiKey: string;
  apiSecret: string;
  baseUrl: string;
  ent: string;
  aue: string;
  timeout: string;
};

export type ImageUnderstandingForm = {
  provider: string;
  appId: string;
  apiKey: string;
  apiSecret: string;
  baseUrl: string;
  protocol: string;
  domain: string;
  maxTokens: string;
  temperature: string;
  topK: string;
  timeout: string;
  uid: string;
};

export type SpeechForm = {
  ttsProvider: string;
  ttsAppId: string;
  ttsApiKey: string;
  ttsApiSecret: string;
  ttsBaseUrl: string;
  ttsVoice: string;
  ttsEncoding: string;
  ttsSampleRate: string;
  ttsSpeed: string;
  ttsVolume: string;
  ttsPitch: string;
  asrProvider: string;
  asrAppId: string;
  asrApiKey: string;
  asrApiSecret: string;
  asrBaseUrl: string;
  asrLanguage: string;
  asrAccent: string;
  asrDomain: string;
  asrVadEos: string;
  speechEvalProvider: string;
  speechEvalAppId: string;
  speechEvalApiKey: string;
  speechEvalApiSecret: string;
  speechEvalBaseUrl: string;
  speechEvalCategory: string;
  speechEvalLanguage: string;
};

export type SharedCredentialsForm = {
  iflytekAppId: string;
  iflytekApiKey: string;
  iflytekApiSecret: string;
  iflytekApiPassword: string;
  siliconflowApiKey: string;
};

export function chooseProviderModel(currentModel: string, provider?: ProviderChoice, previousProvider?: ProviderChoice) {
  const defaultModel = provider?.default_model?.trim();
  if (!defaultModel) return currentModel;
  const previousDefault = previousProvider?.default_model?.trim();
  const previousOptions = previousProvider?.models ?? [];
  const normalizedCurrent = currentModel.trim();
  if (
    !normalizedCurrent ||
    normalizedCurrent === previousDefault ||
    previousOptions.includes(normalizedCurrent) ||
    normalizedCurrent === "gpt-4o-mini"
  ) {
    return defaultModel;
  }
  return currentModel;
}

export function fallbackOcrProviders(): ProviderChoice[] {
  return [
    {
      value: "iflytek",
      label: "讯飞图片文字识别",
      base_url: "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
    },
    {
      value: "siliconflow",
      label: "硅基流动文档识别",
      base_url: "https://api.siliconflow.cn/v1",
      default_model: "deepseek-ai/DeepSeek-OCR",
      models: ["deepseek-ai/DeepSeek-OCR"],
    },
    { value: "disabled", label: "停用", base_url: "" },
  ];
}

export function fallbackFormulaOcrProviders(): ProviderChoice[] {
  return [
    {
      value: "iflytek",
      label: "讯飞公式识别",
      base_url: "https://rest-api.xfyun.cn/v2/itr",
    },
    { value: "disabled", label: "停用", base_url: "" },
  ];
}

export function fallbackImageUnderstandingProviders(): ProviderChoice[] {
  return [
    {
      value: "iflytek",
      label: "讯飞图片理解",
      base_url: "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image",
    },
    { value: "disabled", label: "停用", base_url: "" },
  ];
}

export function extractSharedCredentials(catalog: ModelCatalog): SharedCredentialsForm {
  const credentials = catalog.provider_credentials ?? {};
  const iflytek = credentials.iflytek ?? {};
  const siliconflow = credentials.siliconflow ?? {};

  const llmProfile = activeProfile(catalog.services.llm);
  const embeddingProfile = activeProfile(catalog.services.embedding);
  const searchProfile = activeProfile(catalog.services.search);
  const ocrProfile = catalog.services.ocr ? activeProfile(catalog.services.ocr) : undefined;
  const formulaOcrProfile = catalog.services.formula_ocr ? activeProfile(catalog.services.formula_ocr) : undefined;
  const imageUnderstandingProfile = catalog.services.image_understanding
    ? activeProfile(catalog.services.image_understanding)
    : undefined;
  const ttsProfile = catalog.services.tts ? activeProfile(catalog.services.tts) : undefined;
  const asrProfile = catalog.services.asr ? activeProfile(catalog.services.asr) : undefined;
  const speechEvalProfile = catalog.services.speech_eval ? activeProfile(catalog.services.speech_eval) : undefined;

  const iflytekFromAkSk = splitAkSk(
    llmProfile?.binding === "iflytek_spark_ws"
      ? llmProfile?.api_key
      : searchProfile?.provider === "iflytek_spark"
        ? searchProfile?.api_key
        : "",
  );

  return {
    iflytekAppId:
      iflytek.app_id ||
      embeddingProfile?.extra_headers?.app_id ||
      ocrProfile?.extra_headers?.app_id ||
      formulaOcrProfile?.extra_headers?.app_id ||
      imageUnderstandingProfile?.extra_headers?.app_id ||
      ttsProfile?.extra_headers?.app_id ||
      asrProfile?.extra_headers?.app_id ||
      speechEvalProfile?.extra_headers?.app_id ||
      "",
    iflytekApiKey:
      iflytek.api_key ||
      iflytekFromAkSk.apiKey ||
      (embeddingProfile?.binding === "iflytek_spark" ? embeddingProfile?.api_key : "") ||
      (ocrProfile?.provider === "iflytek" ? ocrProfile?.api_key : "") ||
      (formulaOcrProfile?.provider === "iflytek" ? formulaOcrProfile?.api_key : "") ||
      (imageUnderstandingProfile?.provider === "iflytek" ? imageUnderstandingProfile?.api_key : "") ||
      (ttsProfile?.provider === "iflytek" ? ttsProfile?.api_key : "") ||
      (asrProfile?.provider === "iflytek" ? asrProfile?.api_key : "") ||
      (speechEvalProfile?.provider === "iflytek" ? speechEvalProfile?.api_key : "") ||
      "",
    iflytekApiSecret:
      iflytek.api_secret ||
      iflytekFromAkSk.apiSecret ||
      embeddingProfile?.extra_headers?.api_secret ||
      ocrProfile?.extra_headers?.api_secret ||
      formulaOcrProfile?.extra_headers?.api_secret ||
      imageUnderstandingProfile?.extra_headers?.api_secret ||
      ttsProfile?.extra_headers?.api_secret ||
      asrProfile?.extra_headers?.api_secret ||
      speechEvalProfile?.extra_headers?.api_secret ||
      "",
    iflytekApiPassword:
      iflytek.api_password ||
      (llmProfile?.binding === "iflytek_spark_ws" ? llmProfile?.api_key : "") ||
      (searchProfile?.provider === "iflytek_spark" ? searchProfile?.api_key : "") ||
      "",
    siliconflowApiKey:
      siliconflow.api_key ||
      (profileUsesSiliconFlow(llmProfile) ? llmProfile?.api_key : "") ||
      (profileUsesSiliconFlow(embeddingProfile) ? embeddingProfile?.api_key : "") ||
      (ocrProfile?.provider === "siliconflow" ? ocrProfile?.api_key : "") ||
      "",
  };
}

export function effectiveSharedIflytekApiPassword(shared: SharedCredentialsForm) {
  if (shared.iflytekApiPassword.trim()) return shared.iflytekApiPassword;
  if (shared.iflytekApiKey.trim() && shared.iflytekApiSecret.trim()) {
    return `${shared.iflytekApiKey.trim()}:${shared.iflytekApiSecret.trim()}`;
  }
  return "";
}

export function effectiveLlmApiKey(profile: EndpointProfile | undefined, shared: SharedCredentialsForm) {
  if (profile?.binding === "iflytek_spark_ws") return iflytekCredentialForHttp(shared) || profile.api_key || "";
  if (profileUsesSiliconFlow(profile)) return shared.siliconflowApiKey || profile?.api_key || "";
  return profile?.api_key || "";
}

export function effectiveEmbeddingApiKey(profile: EndpointProfile | undefined, shared: SharedCredentialsForm) {
  if (profile?.binding === "iflytek_spark") return shared.iflytekApiKey || profile.api_key || "";
  if (profileUsesSiliconFlow(profile)) return shared.siliconflowApiKey || profile?.api_key || "";
  return profile?.api_key || "";
}

export function effectiveSearchApiKey(profile: EndpointProfile | undefined, shared: SharedCredentialsForm) {
  if (profile?.provider === "iflytek_spark") return iflytekCredentialForHttp(shared) || profile.api_key || "";
  return profile?.api_key || "";
}

export function effectiveOcrApiKey(profile: EndpointProfile | undefined, shared: SharedCredentialsForm) {
  if (profile?.provider === "iflytek") return shared.iflytekApiKey || profile.api_key || "";
  if (profile?.provider === "siliconflow") return shared.siliconflowApiKey || profile.api_key || "";
  return profile?.api_key || "";
}

export function effectiveIflytekServiceApiKey(profile: EndpointProfile | undefined, shared: SharedCredentialsForm) {
  if (profile?.provider === "iflytek") return shared.iflytekApiKey || profile.api_key || "";
  return profile?.api_key || "";
}

export function applySharedCredentials(catalog: ModelCatalog, form: SharedCredentialsForm) {
  catalog.provider_credentials = {
    ...(catalog.provider_credentials ?? {}),
    iflytek: {
      app_id: form.iflytekAppId.trim(),
      api_key: form.iflytekApiKey.trim(),
      api_secret: form.iflytekApiSecret.trim(),
      api_password: form.iflytekApiPassword.trim(),
    },
    siliconflow: {
      api_key: form.siliconflowApiKey.trim(),
    },
  };

  stripSharedCredentialDuplicates(catalog);
}

export function activeProfile(service: ServiceCatalog): EndpointProfile | undefined {
  return service.profiles.find((profile) => profile.id === service.active_profile_id) || service.profiles[0];
}

export function activeModel(service: ServiceCatalog, profile?: EndpointProfile) {
  return profile?.models?.find((model) => model.id === service.active_model_id) || profile?.models?.[0];
}

export function applyLlmForm(service: ServiceCatalog, form: LlmForm) {
  const profile = ensureProfile(service, "llm-profile-default");
  const model = ensureModel(service, profile, "llm-model-default");
  profile.binding = form.binding;
  profile.base_url = form.baseUrl.trim();
  const apiKey = buildLlmApiKey(form);
  if (apiKey) profile.api_key = apiKey;
  if (form.binding === "iflytek_spark_ws" && profile.extra_headers) {
    const extraHeaders = { ...profile.extra_headers };
    delete extraHeaders.app_id;
    delete extraHeaders.appid;
    delete extraHeaders.api_secret;
    delete extraHeaders.domain;
    profile.extra_headers = extraHeaders;
  }
  model.name = form.model.trim();
  model.model = form.model.trim();
}

export function applyEmbeddingForm(service: ServiceCatalog, form: EmbeddingForm) {
  const profile = ensureProfile(service, "embedding-profile-default");
  const model = ensureModel(service, profile, "embedding-model-default");
  profile.binding = form.binding;
  profile.base_url = form.baseUrl.trim();
  if (form.apiKey.trim()) profile.api_key = form.apiKey.trim();
  if (form.binding === "iflytek_spark") {
    const extraHeaders = { ...(profile.extra_headers || {}) };
    if (form.iflytekAppId.trim()) extraHeaders.app_id = form.iflytekAppId.trim();
    if (form.iflytekApiSecret.trim()) extraHeaders.api_secret = form.iflytekApiSecret.trim();
    extraHeaders.domain = form.iflytekDomain.trim() || "para";
    profile.extra_headers = extraHeaders;
  }
  model.name = form.model.trim();
  model.model = form.model.trim();
  model.dimension = form.dimension.trim();
}

export function applySearchForm(service: ServiceCatalog, form: SearchForm) {
  const profile = ensureProfile(service, "search-profile-default");
  profile.provider = form.provider;
  profile.base_url = form.baseUrl.trim();
  if (form.apiKey.trim()) profile.api_key = form.apiKey.trim();
}

export function applyOcrForm(catalog: ModelCatalog, form: OcrForm) {
  catalog.services.ocr = catalog.services.ocr ?? { active_profile_id: undefined, profiles: [] };
  const profile = ensureProfile(catalog.services.ocr, "ocr-profile-default");
  profile.provider = form.provider;
  profile.strategy = form.strategy;
  profile.base_url = form.baseUrl.trim();
  setOptionalOcrProfileValue(profile, "timeout", form.timeout);
  setOptionalOcrProfileValue(profile, "max_pages", form.maxPages);
  setOptionalOcrProfileValue(profile, "dpi", form.dpi);
  setOptionalOcrProfileValue(profile, "min_text_chars", form.minTextChars);
  if (form.apiKey.trim()) profile.api_key = form.apiKey.trim();
  const extraHeaders = { ...(profile.extra_headers || {}) };
  if (form.provider === "siliconflow") {
    extraHeaders.model = form.model.trim() || "deepseek-ai/DeepSeek-OCR";
    extraHeaders.prompt = extraHeaders.prompt || "<image>\n<|grounding|>Convert the document to markdown.";
    delete extraHeaders.app_id;
    delete extraHeaders.api_secret;
    delete extraHeaders.service_id;
    delete extraHeaders.category;
  } else {
    if (form.appId.trim()) extraHeaders.app_id = form.appId.trim();
    if (form.apiSecret.trim()) extraHeaders.api_secret = form.apiSecret.trim();
    extraHeaders.service_id = form.serviceId.trim() || "se75ocrbm";
    extraHeaders.category = form.category.trim() || "ch_en_public_cloud";
    delete extraHeaders.model;
    delete extraHeaders.prompt;
  }
  profile.extra_headers = extraHeaders;
  profile.models = [];
}

export function applyFormulaOcrForm(catalog: ModelCatalog, form: FormulaOcrForm) {
  catalog.services.formula_ocr = catalog.services.formula_ocr ?? { active_profile_id: undefined, profiles: [] };
  const profile = ensureProfile(catalog.services.formula_ocr, "formula-ocr-profile-default");
  profile.provider = form.provider;
  profile.base_url = form.baseUrl.trim();
  profile.timeout = form.timeout.trim();
  if (form.apiKey.trim()) profile.api_key = form.apiKey.trim();
  profile.extra_headers = {
    ...(profile.extra_headers || {}),
    app_id: form.appId.trim(),
    api_secret: form.apiSecret.trim(),
    ent: form.ent.trim() || "teach-photo-print",
    aue: form.aue.trim() || "raw",
  };
  profile.models = [];
}

export function applyImageUnderstandingForm(catalog: ModelCatalog, form: ImageUnderstandingForm) {
  catalog.services.image_understanding = catalog.services.image_understanding ?? {
    active_profile_id: undefined,
    profiles: [],
  };
  const profile = ensureProfile(catalog.services.image_understanding, "image-understanding-profile-default");
  profile.provider = form.provider;
  profile.base_url = form.baseUrl.trim();
  profile.timeout = form.timeout.trim();
  if (form.apiKey.trim()) profile.api_key = form.apiKey.trim();
  profile.extra_headers = {
    ...(profile.extra_headers || {}),
    app_id: form.appId.trim(),
    api_secret: form.apiSecret.trim(),
    protocol: form.protocol.trim() || "spark_image",
    domain: form.domain.trim() || "imagev3",
    max_tokens: form.maxTokens.trim() || "2048",
    temperature: form.temperature.trim() || "0.2",
    top_k: form.topK.trim() || "4",
    uid: form.uid.trim() || "sparkweave",
  };
  profile.models = [];
}

export function applySpeechForm(catalog: ModelCatalog, form: SpeechForm) {
  catalog.services.tts = catalog.services.tts ?? { active_profile_id: undefined, profiles: [] };
  catalog.services.asr = catalog.services.asr ?? { active_profile_id: undefined, profiles: [] };
  catalog.services.speech_eval = catalog.services.speech_eval ?? { active_profile_id: undefined, profiles: [] };

  const tts = ensureProfile(catalog.services.tts, "tts-profile-default");
  tts.provider = form.ttsProvider;
  tts.base_url = form.ttsBaseUrl.trim();
  tts.timeout = "";
  tts.api_key = form.ttsApiKey.trim();
  tts.models = [];
  tts.extra_headers = {
    ...(tts.extra_headers || {}),
    app_id: form.ttsAppId.trim(),
    api_secret: form.ttsApiSecret.trim(),
    voice: form.ttsVoice.trim() || "x5_lingxiaoxuan_flow",
    encoding: form.ttsEncoding.trim() || "lame",
    sample_rate: form.ttsSampleRate.trim() || "24000",
    channels: "1",
    bit_depth: "16",
    frame_size: "0",
    speed: normalizeSpeechRange(form.ttsSpeed),
    volume: normalizeSpeechRange(form.ttsVolume),
    pitch: normalizeSpeechRange(form.ttsPitch),
  };

  const asr = ensureProfile(catalog.services.asr, "asr-profile-default");
  asr.provider = form.asrProvider;
  asr.base_url = form.asrBaseUrl.trim();
  asr.timeout = "";
  asr.api_key = form.asrApiKey.trim();
  asr.models = [];
  asr.extra_headers = {
    ...(asr.extra_headers || {}),
    app_id: form.asrAppId.trim(),
    api_secret: form.asrApiSecret.trim(),
    language: form.asrLanguage.trim() || "zh_cn",
    accent: form.asrAccent.trim() || "mandarin",
    domain: form.asrDomain.trim() || "iat",
    vad_eos: form.asrVadEos.trim() || "3000",
  };

  const speechEval = ensureProfile(catalog.services.speech_eval, "speech-eval-profile-default");
  speechEval.provider = form.speechEvalProvider;
  speechEval.base_url = form.speechEvalBaseUrl.trim();
  speechEval.timeout = "";
  speechEval.api_key = form.speechEvalApiKey.trim();
  speechEval.models = [];
  speechEval.extra_headers = {
    ...(speechEval.extra_headers || {}),
    app_id: form.speechEvalAppId.trim(),
    api_secret: form.speechEvalApiSecret.trim(),
    category: form.speechEvalCategory.trim() || "read_sentence",
    language: form.speechEvalLanguage.trim() || "zh_cn",
  };
}

export function optionalOcrSetting(value: string | undefined, ...defaultValues: string[]) {
  const normalized = String(value ?? "").trim();
  return normalized && !defaultValues.includes(normalized) ? normalized : "";
}

function normalizeSpeechRange(value: string) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return "50";
  return String(Math.max(0, Math.min(100, parsed)));
}

function splitAkSk(value?: string) {
  const text = (value || "").trim();
  if (!text.includes(":")) return { apiKey: "", apiSecret: "" };
  const [apiKey, apiSecret] = text.split(":", 2);
  return { apiKey: apiKey.trim(), apiSecret: apiSecret.trim() };
}

function iflytekCredentialForHttp(shared: SharedCredentialsForm) {
  return effectiveSharedIflytekApiPassword(shared).trim() || shared.iflytekApiKey.trim();
}

function profileUsesSiliconFlow(profile?: EndpointProfile) {
  const binding = (profile?.binding || "").trim();
  const provider = (profile?.provider || "").trim();
  const baseUrl = (profile?.base_url || "").toLowerCase();
  return binding === "siliconflow" || provider === "siliconflow" || baseUrl.includes("siliconflow");
}

function stripSharedCredentialDuplicates(catalog: ModelCatalog) {
  const iflytek = catalog.provider_credentials?.iflytek;
  const siliconflow = catalog.provider_credentials?.siliconflow;
  const hasIflytek = Boolean(iflytek?.app_id || iflytek?.api_key || iflytek?.api_secret || iflytek?.api_password);
  const hasSiliconFlow = Boolean(siliconflow?.api_key);

  const clearApiKey = (profile: EndpointProfile | undefined, candidates: Array<string | undefined>) => {
    if (profile && candidates.some((candidate) => sameNonEmptySecret(profile.api_key, candidate))) profile.api_key = "";
  };
  const clearIflytekExtra = (profile?: EndpointProfile) => {
    if (!profile?.extra_headers) return;
    if (sameNonEmptySecret(profile.extra_headers.app_id, iflytek?.app_id)) profile.extra_headers.app_id = "";
    if (sameNonEmptySecret(profile.extra_headers.api_secret, iflytek?.api_secret)) {
      profile.extra_headers.api_secret = "";
    }
  };
  const iflytekCredentialCandidates = [
    iflytek?.api_key,
    iflytek?.api_password,
    iflytek?.api_key && iflytek?.api_secret ? `${iflytek.api_key}:${iflytek.api_secret}` : undefined,
  ];

  for (const profile of catalog.services.llm.profiles) {
    if (profile.binding === "iflytek_spark_ws" && hasIflytek) {
      clearApiKey(profile, iflytekCredentialCandidates);
      clearIflytekExtra(profile);
    }
    if (profileUsesSiliconFlow(profile) && hasSiliconFlow) clearApiKey(profile, [siliconflow?.api_key]);
  }
  for (const profile of catalog.services.embedding.profiles) {
    if (profile.binding === "iflytek_spark" && hasIflytek) {
      clearApiKey(profile, iflytekCredentialCandidates);
      clearIflytekExtra(profile);
    }
    if (profileUsesSiliconFlow(profile) && hasSiliconFlow) clearApiKey(profile, [siliconflow?.api_key]);
  }
  for (const profile of catalog.services.search.profiles) {
    if (profile.provider === "iflytek_spark" && hasIflytek) clearApiKey(profile, iflytekCredentialCandidates);
  }
  for (const profile of catalog.services.ocr?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile, [iflytek?.api_key]);
      clearIflytekExtra(profile);
    }
    if (profile.provider === "siliconflow" && hasSiliconFlow) clearApiKey(profile, [siliconflow?.api_key]);
  }
  for (const profile of catalog.services.formula_ocr?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile, [iflytek?.api_key]);
      clearIflytekExtra(profile);
    }
  }
  for (const profile of catalog.services.image_understanding?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile, [iflytek?.api_key]);
      clearIflytekExtra(profile);
    }
  }
  for (const profile of catalog.services.tts?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile, [iflytek?.api_key]);
      clearIflytekExtra(profile);
    }
  }
  for (const profile of catalog.services.asr?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile, [iflytek?.api_key]);
      clearIflytekExtra(profile);
    }
  }
  for (const profile of catalog.services.speech_eval?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile, [iflytek?.api_key]);
      clearIflytekExtra(profile);
    }
  }
}

function sameNonEmptySecret(value: unknown, candidate: unknown) {
  const left = String(value ?? "").trim();
  const right = String(candidate ?? "").trim();
  if (isRedactedSecret(left) || isRedactedSecret(right)) return false;
  return Boolean(left && right && left === right);
}

function isRedactedSecret(value: string) {
  return value === "********";
}

function ensureProfile(service: ServiceCatalog, fallbackId: string) {
  let profile = activeProfile(service);
  if (!profile) {
    profile = { id: fallbackId, name: "Default", models: [] };
    service.profiles = [profile];
    service.active_profile_id = fallbackId;
  }
  return profile;
}

function ensureModel(service: ServiceCatalog, profile: EndpointProfile, fallbackId: string) {
  profile.models = profile.models ?? [];
  let model = activeModel(service, profile);
  if (!model) {
    model = { id: fallbackId, name: "Default Model", model: "" };
    profile.models.push(model);
    service.active_model_id = fallbackId;
  }
  return model;
}

function buildLlmApiKey(form: LlmForm) {
  const apiKey = form.apiKey.trim();
  if (form.binding !== "iflytek_spark_ws") return apiKey;
  if (form.iflytekAuthMode === "api_password") return apiKey;
  if (apiKey.includes(":")) return apiKey;
  const apiSecret = form.iflytekApiSecret.trim();
  if (!apiKey || !apiSecret) return "";
  return `${apiKey}:${apiSecret}`;
}

function setOptionalOcrProfileValue(
  target: EndpointProfile,
  key: "timeout" | "max_pages" | "dpi" | "min_text_chars",
  value: string,
) {
  const normalized = value.trim();
  if (normalized) {
    target[key] = normalized;
    return;
  }
  delete target[key];
}
