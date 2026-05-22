export const SERVICES = [
  { id: "llm" as const, label: "问答模型" },
  { id: "embedding" as const, label: "资料理解" },
  { id: "search" as const, label: "联网搜索" },
  { id: "ocr" as const, label: "图片文字识别" },
  { id: "tts" as const, label: "语音讲解" },
  { id: "asr" as const, label: "语音输入" },
  { id: "speech_eval" as const, label: "口语评测" },
];

export const SYSTEM_PROBES = [
  { id: "llm" as const, label: "问答模型", detail: "测试问答模型" },
  { id: "embeddings" as const, label: "资料理解", detail: "测试资料理解服务" },
  { id: "search" as const, label: "联网搜索", detail: "测试搜索服务" },
  { id: "ocr" as const, label: "图片文字识别", detail: "测试扫描 PDF 识别服务" },
  { id: "formula_ocr" as const, label: "公式识别", detail: "测试讯飞公式识别服务" },
  { id: "image_understanding" as const, label: "图片理解", detail: "测试讯飞图片理解服务" },
  { id: "tts" as const, label: "语音讲解", detail: "测试语音讲解服务" },
  { id: "asr" as const, label: "语音输入", detail: "检查语音输入配置" },
  { id: "speech_eval" as const, label: "口语评测", detail: "检查口语评测配置" },
  { id: "iflytek_workflow" as const, label: "讯飞工作流", detail: "测试星辰工作流调用" },
];

export const LEGACY_TEXT_SEPARATOR = "\u001F";

export type ServiceId = (typeof SERVICES)[number]["id"];
export type SystemProbeId = (typeof SYSTEM_PROBES)[number]["id"];
export type TestStatus = "idle" | "running" | "completed" | "failed" | "cancelled";

export function withLegacyText(visible: string, legacy: string) {
  return `${visible}${LEGACY_TEXT_SEPARATOR}${legacy}`;
}

export function formatSettingsTestEvent(kind: string, data: { message?: string; [key: string]: unknown }) {
  const label = formatTestEventKind(kind);
  const message = typeof data.message === "string" ? data.message : "";
  const legacy = `${label}：${message || JSON.stringify(data)}`;
  const normalized = kind.toLowerCase();
  if (normalized === "completed") return withLegacyText("检测通过：服务可以使用。", legacy);
  if (normalized === "failed" || normalized === "error") return withLegacyText(`检测失败：${friendlyServiceError(message)}`, legacy);
  if (normalized === "cancelled") return withLegacyText("已取消当前服务检测。", legacy);
  if (/snapshot|active profile|configuration/i.test(message)) return withLegacyText("正在读取当前配置。", legacy);
  if (/resolved|provider/i.test(message)) return withLegacyText("正在选择服务来源。", legacy);
  if (/target|request|endpoint|url/i.test(message)) return withLegacyText("正在连接服务接口。", legacy);
  if (/handshake|ready|ok|success/i.test(message)) return withLegacyText("服务响应正常。", legacy);
  return withLegacyText(`${label}：检测进行中。`, legacy);
}

export function friendlyServiceError(message: string) {
  if (!message) return "服务暂时不可用";
  if (/timeout|timing out|504|upstream/i.test(message)) return "服务响应超时，稍后再试或换一个模型";
  if (/401|apikey|api key|secret|signature|unauthorized/i.test(message)) return "密钥或鉴权信息不正确";
  if (/429|rate limit|too many requests|quota|insufficient/i.test(message)) return "调用额度或频率受限";
  if (/500|502|503|internal server|bad gateway|service unavailable/i.test(message)) return "服务端暂时异常，稍后再试";
  if (/no speech|not return a score|no.*recognized|empty.*transcript/i.test(message)) return "没有识别到有效语音，请靠近麦克风再试";
  if (/not configured|missing .*provider|missing_search_provider|search_provider/i.test(message)) return "还没有完成服务配置";
  if (/model.*not|invalid model|model not found|unsupported model/i.test(message)) return "模型名称可能不正确";
  if (/base_url|endpoint|url|not found|404/i.test(message)) return "服务地址可能不正确";
  if (/connection|connect|network/i.test(message)) return "网络或服务连接失败";
  return "服务返回异常，请检查配置后重试";
}

export function systemProbeDisplayName(service: SystemProbeId) {
  return (
    {
      llm: "问答模型",
      embeddings: "资料理解",
      search: "联网搜索",
      ocr: "图片文字识别",
      formula_ocr: "公式识别",
      image_understanding: "图片理解",
      tts: "语音讲解",
      asr: "语音输入",
      speech_eval: "口语评测",
      iflytek_workflow: "讯飞工作流",
    }[service] || service
  );
}

export function serviceDisplayName(name: string) {
  return (
    {
      llm: "问答模型",
      embedding: "资料理解",
      search: "联网搜索",
      ocr: "图片文字识别",
      formula_ocr: "公式识别",
      image_understanding: "图片理解",
      tts: "语音讲解",
      asr: "语音输入",
      speech_eval: "口语评测",
      iflytek_workflow: "讯飞工作流",
    }[name] || name
  );
}

function formatTestEventKind(kind: string) {
  return (
    {
      info: "信息",
      log: "日志",
      progress: "进度",
      completed: "完成",
      failed: "失败",
      error: "异常",
      cancelled: "已取消",
    }[kind] || kind
  );
}
