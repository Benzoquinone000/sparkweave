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
      label: "讯飞 OCR for LLM",
      base_url: "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
    },
    {
      value: "siliconflow",
      label: "硅基流动 DeepSeek-OCR",
      base_url: "https://api.siliconflow.cn/v1",
      default_model: "deepseek-ai/DeepSeek-OCR",
      models: ["deepseek-ai/DeepSeek-OCR"],
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
  const ttsProfile = catalog.services.tts ? activeProfile(catalog.services.tts) : undefined;

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
      ttsProfile?.extra_headers?.app_id ||
      "",
    iflytekApiKey:
      iflytek.api_key ||
      iflytekFromAkSk.apiKey ||
      (embeddingProfile?.binding === "iflytek_spark" ? embeddingProfile?.api_key : "") ||
      (ocrProfile?.provider === "iflytek" ? ocrProfile?.api_key : "") ||
      (ttsProfile?.provider === "iflytek" ? ttsProfile?.api_key : "") ||
      "",
    iflytekApiSecret:
      iflytek.api_secret ||
      iflytekFromAkSk.apiSecret ||
      embeddingProfile?.extra_headers?.api_secret ||
      ocrProfile?.extra_headers?.api_secret ||
      ttsProfile?.extra_headers?.api_secret ||
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

export function optionalOcrSetting(value: string | undefined, ...defaultValues: string[]) {
  const normalized = String(value ?? "").trim();
  return normalized && !defaultValues.includes(normalized) ? normalized : "";
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

  const clearApiKey = (profile?: EndpointProfile) => {
    if (profile) profile.api_key = "";
  };
  const clearIflytekExtra = (profile?: EndpointProfile) => {
    if (!profile?.extra_headers) return;
    profile.extra_headers.app_id = "";
    profile.extra_headers.api_secret = "";
  };

  for (const profile of catalog.services.llm.profiles) {
    if (profile.binding === "iflytek_spark_ws" && hasIflytek) {
      clearApiKey(profile);
      clearIflytekExtra(profile);
    }
    if (profileUsesSiliconFlow(profile) && hasSiliconFlow) clearApiKey(profile);
  }
  for (const profile of catalog.services.embedding.profiles) {
    if (profile.binding === "iflytek_spark" && hasIflytek) {
      clearApiKey(profile);
      clearIflytekExtra(profile);
    }
    if (profileUsesSiliconFlow(profile) && hasSiliconFlow) clearApiKey(profile);
  }
  for (const profile of catalog.services.search.profiles) {
    if (profile.provider === "iflytek_spark" && hasIflytek) clearApiKey(profile);
  }
  for (const profile of catalog.services.ocr?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile);
      clearIflytekExtra(profile);
    }
    if (profile.provider === "siliconflow" && hasSiliconFlow) clearApiKey(profile);
  }
  for (const profile of catalog.services.tts?.profiles ?? []) {
    if (profile.provider === "iflytek" && hasIflytek) {
      clearApiKey(profile);
      clearIflytekExtra(profile);
    }
  }
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
