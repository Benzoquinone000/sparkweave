import { ChevronDown, ChevronRight, Loader2, PlugZap, Save, Settings2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotChannelSchema, SparkBotSchemas, SparkBotSummary } from "@/lib/types";
import { McpServersEditor, SkillsManagerPanel } from "./SparkBotToolsPanel";
import { JsonEditor } from "./SparkBotWorkspacePanels";

type ChannelMcpPanelProps = {
  botId: string;
  bot?: SparkBotSummary;
  schemas?: SparkBotSchemas;
  defaultChannels: Record<string, unknown>;
  defaultTools: Record<string, unknown>;
  pending: boolean;
  onSaveChannels: (channels: Record<string, unknown>) => Promise<unknown>;
  onSaveTools: (tools: Record<string, unknown>) => Promise<unknown>;
  onSaveSkill: (skillName: string, content: string) => Promise<unknown>;
  onUploadSkill: (file: File, skillName?: string) => Promise<unknown>;
};

export function ChannelMcpPanel({
  botId,
  bot,
  schemas,
  defaultChannels,
  defaultTools,
  pending,
  onSaveChannels,
  onSaveTools,
  onSaveSkill,
  onUploadSkill,
}: ChannelMcpPanelProps) {
  const channels = bot?.channels ?? defaultChannels;
  const tools = bot?.tools ?? defaultTools;
  const [showAdvanced, setShowAdvanced] = useState(false);
  const configuredChannels = Object.entries(channels)
    .filter(([, value]) => isRecord(value) && value.enabled)
    .map(([key]) => key);
  const availableChannels = Object.keys(schemas?.channels ?? {}).sort();
  return (
    <div className="grid gap-4" data-testid="sparkbot-channel-toggle">
      <section className="rounded-lg border border-line bg-white p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <PlugZap size={18} className="text-brand-purple" />
            <h2 className="text-base font-semibold text-ink">消息入口</h2>
          </div>
          <Badge tone={bot?.running ? "success" : "neutral"}>{bot?.running ? "运行中" : "停止"}</Badge>
        </div>
        <div className="mt-4 grid gap-3 border-t border-line pt-4">
          <ChannelBadges title="已连接入口" values={configuredChannels} fallback="未启用" />
          <ChannelBadges title="可连接入口" values={availableChannels.length ? availableChannels : ["feishu", "qq", "slack", "discord"]} />
        </div>
      </section>

      <ChannelConfigPanel schemas={schemas} channels={channels} pending={pending} onSave={onSaveChannels} />

      <section className="border-t border-line pt-2">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 rounded-lg bg-canvas px-3 py-2 text-left"
          onClick={() => setShowAdvanced((current) => !current)}
          data-testid="sparkbot-advanced-toggle"
        >
          <span className="flex min-w-0 items-center gap-2">
            <Settings2 size={18} className="text-brand-purple" />
            <span className="text-base font-semibold text-ink">高级能力</span>
          </span>
          {showAdvanced ? <ChevronDown size={17} className="text-slate-500" /> : <ChevronRight size={17} className="text-slate-500" />}
        </button>
        {showAdvanced ? (
          <div className="mt-3 grid gap-4">
            <SkillsManagerPanel botId={botId} pending={pending} onSave={onSaveSkill} onUpload={onUploadSkill} />
            <McpServersEditor tools={tools} pending={pending} onSave={onSaveTools} />
            <JsonEditor
              title="消息入口 JSON"
              value={channels}
              pending={pending}
              testId="sparkbot-channel-json-editor"
              onSave={onSaveChannels}
            />
            <JsonEditor
              title="外部连接规则"
              value={tools}
              pending={pending}
              onSave={onSaveTools}
            />
          </div>
        ) : null}
      </section>
    </div>
  );
}

type ChannelConfigPanelProps = {
  schemas?: SparkBotSchemas;
  channels: Record<string, unknown>;
  pending: boolean;
  onSave: (channels: Record<string, unknown>) => Promise<unknown>;
};

function ChannelConfigPanel({ schemas, channels, pending, onSave }: ChannelConfigPanelProps) {
  const schemaChannels = schemas?.channels ?? {};
  const channelNames = orderChannelNames(Object.keys(schemaChannels));
  const configuredNames = Object.entries(channels)
    .filter(([, value]) => isRecord(value) && value.enabled)
    .map(([name]) => name);
  const [selectedName, setSelectedName] = useState(() => configuredNames[0] || (channelNames.includes("qq") ? "qq" : channelNames[0] || ""));
  const effectiveName = selectedName && channelNames.includes(selectedName) ? selectedName : channelNames.includes("qq") ? "qq" : channelNames[0] || "";

  if (!schemas || !channelNames.length) {
    return (
      <section className="rounded-lg border border-line bg-white p-3">
        <div className="flex items-center gap-2">
          <PlugZap size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">消息入口配置</h2>
        </div>
        <p className="mt-3 rounded-lg border border-dashed border-line bg-canvas p-3 text-sm text-slate-500">
          渠道配置清单正在加载。需要时可以先使用下方高级 JSON。
        </p>
      </section>
    );
  }

  const selectedSchema = schemaChannels[effectiveName];

  return (
    <section className="rounded-lg border border-line bg-white p-3" data-testid="sparkbot-channel-config-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <PlugZap size={18} className="text-brand-purple" />
          <h2 className="text-base font-semibold text-ink">消息入口配置</h2>
        </div>
        <Badge tone="neutral">{configuredNames.length ? `${configuredNames.length} 个已启用` : "未启用"}</Badge>
      </div>

      <ChannelGlobalEditor
        schema={schemas.global}
        channels={channels}
        pending={pending}
        onSave={onSave}
      />

      <div className="mt-4 border-t border-line pt-4">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {channelNames.map((name) => {
            const schema = schemaChannels[name];
            const config = isRecord(channels[name]) ? channels[name] : schema.default_config;
            const enabled = isRecord(config) && config.enabled === true;
            return (
              <button
                key={name}
                type="button"
                onClick={() => setSelectedName(name)}
                className={`shrink-0 rounded-lg border px-3 py-2 text-left text-sm transition ${
                  effectiveName === name
                    ? "border-brand-purple-300 bg-tint-lavender text-brand-purple"
                    : "border-line bg-white text-slate-600 hover:border-brand-purple-300"
                }`}
                data-testid={`sparkbot-channel-card-${name}`}
              >
                <span className="block font-medium">{channelDisplayName(name, schema)}</span>
                <span className="mt-1 block text-xs text-slate-500">{enabled ? "已启用" : "未启用"}</span>
              </button>
            );
          })}
        </div>

        {selectedSchema ? (
          <ChannelDetailEditor
            key={effectiveName}
            name={effectiveName}
            schema={selectedSchema}
            channels={channels}
            pending={pending}
            onSave={onSave}
          />
        ) : null}
      </div>
    </section>
  );
}

type ChannelGlobalEditorProps = {
  schema?: SparkBotChannelSchema;
  channels: Record<string, unknown>;
  pending: boolean;
  onSave: (channels: Record<string, unknown>) => Promise<unknown>;
};

function ChannelGlobalEditor({ schema, channels, pending, onSave }: ChannelGlobalEditorProps) {
  const properties = schemaProperties(schema?.json_schema);
  const initialDraft = useMemo(() => {
    const draft: Record<string, unknown> = {};
    for (const [name, propSchema] of Object.entries(properties)) {
      draft[name] = channels[name] ?? schemaDefaultValue(propSchema);
    }
    return draft;
  }, [channels, properties]);

  return (
    <ChannelSchemaForm
      title="全局规则"
      submitLabel="保存全局"
      channelName="global"
      draftKey={JSON.stringify(initialDraft)}
      initialDraft={initialDraft}
      properties={properties}
      secretFields={schema?.secret_fields ?? []}
      pending={pending}
      testId="sparkbot-global-channel-editor"
      onSubmit={(draft) => onSave({ ...channels, ...normalizeSchemaDraft(draft, properties) })}
    />
  );
}

type ChannelDetailEditorProps = {
  name: string;
  schema: SparkBotChannelSchema;
  channels: Record<string, unknown>;
  pending: boolean;
  onSave: (channels: Record<string, unknown>) => Promise<unknown>;
};

function ChannelDetailEditor({ name, schema, channels, pending, onSave }: ChannelDetailEditorProps) {
  const properties = schemaProperties(schema.json_schema);
  const initialDraft = useMemo(
    () => ({ ...(schema.default_config ?? {}), ...(isRecord(channels[name]) ? channels[name] : {}) }),
    [channels, name, schema.default_config],
  );

  return (
    <ChannelSchemaForm
      title={channelDisplayName(name, schema)}
      submitLabel="保存渠道"
      channelName={name}
      draftKey={`${name}:${JSON.stringify(initialDraft)}`}
      initialDraft={initialDraft}
      properties={properties}
      secretFields={schema.secret_fields ?? []}
      pending={pending}
      testId={`sparkbot-channel-editor-${name}`}
      onSubmit={(draft) => {
        const nextConfig = normalizeChannelConfig(normalizeSchemaDraft(draft, properties), properties);
        return onSave({ ...channels, [name]: nextConfig });
      }}
    />
  );
}

type ChannelSchemaFormProps = {
  title: string;
  submitLabel: string;
  channelName: string;
  draftKey: string;
  initialDraft: Record<string, unknown>;
  properties: Record<string, Record<string, unknown>>;
  secretFields: string[];
  pending: boolean;
  testId?: string;
  onSubmit: (draft: Record<string, unknown>) => Promise<unknown>;
};

function ChannelSchemaForm({
  title,
  submitLabel,
  channelName,
  draftKey,
  initialDraft,
  properties,
  secretFields,
  pending,
  testId,
  onSubmit,
}: ChannelSchemaFormProps) {
  return (
    <ChannelSchemaFormDraft
      key={draftKey}
      title={title}
      submitLabel={submitLabel}
      channelName={channelName}
      initialDraft={initialDraft}
      properties={properties}
      secretFields={secretFields}
      pending={pending}
      testId={testId}
      onSubmit={onSubmit}
    />
  );
}

type ChannelSchemaFormDraftProps = {
  title: string;
  submitLabel: string;
  channelName: string;
  initialDraft: Record<string, unknown>;
  properties: Record<string, Record<string, unknown>>;
  secretFields: string[];
  pending: boolean;
  testId?: string;
  onSubmit: (draft: Record<string, unknown>) => Promise<unknown>;
};

function ChannelSchemaFormDraft({
  title,
  submitLabel,
  channelName,
  initialDraft,
  properties,
  secretFields,
  pending,
  testId,
  onSubmit,
}: ChannelSchemaFormDraftProps) {
  const [draft, setDraft] = useState(initialDraft);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const updateField = (name: string, value: unknown) => {
    setDraft((current) => ({ ...current, [name]: value }));
    setSaved(false);
  };

  return (
    <form
      className="mt-4 grid gap-3"
      data-testid={testId}
      onSubmit={async (event) => {
        event.preventDefault();
        try {
          setError("");
          setSaved(false);
          await onSubmit(draft);
          setSaved(true);
        } catch (submitError) {
          setError(submitError instanceof Error ? submitError.message : "保存渠道配置失败。");
        }
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <Button tone="secondary" type="submit" disabled={pending}>
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          {submitLabel}
        </Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {orderChannelFields(Object.entries(properties), channelName).map(([name, propSchema]) => (
          <ChannelField
            key={name}
            channelName={channelName}
            name={name}
            schema={propSchema}
            value={draft[name] ?? schemaDefaultValue(propSchema)}
            secret={secretFields.includes(name)}
            onChange={(value) => updateField(name, value)}
          />
        ))}
      </div>
      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      {saved ? <p className="text-sm text-emerald-700">已保存。</p> : null}
    </form>
  );
}

type ChannelFieldProps = {
  channelName: string;
  name: string;
  schema: Record<string, unknown>;
  value: unknown;
  secret: boolean;
  onChange: (value: unknown) => void;
};

function ChannelField({ channelName, name, schema, value, secret, onChange }: ChannelFieldProps) {
  const label = channelFieldLabel(name, schema);
  const hint = channelFieldHint(channelName, name, schema);
  const enumValues = Array.isArray(schema.enum) ? schema.enum.map(String) : [];
  const type = schemaType(schema);
  const testId = `channel-field-${name.replaceAll(".", "-")}`;

  if (type === "boolean") {
    return (
      <label className="flex min-h-16 items-start gap-2 rounded-lg border border-line bg-canvas/70 p-3 text-sm text-slate-600">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-1"
          data-testid={testId}
        />
        <span>
          <span className="block font-medium text-ink">{label}</span>
          {hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
        </span>
      </label>
    );
  }

  if (enumValues.length) {
    return (
      <FieldShell label={label} hint={hint}>
        <SelectInput value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} data-testid={testId}>
          {enumValues.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </SelectInput>
      </FieldShell>
    );
  }

  if (type === "array") {
    return (
      <FieldShell label={label} hint={hint || "多个值用逗号或换行分隔"}>
        <TextArea
          value={arrayFieldText(value)}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-16"
          data-testid={testId}
        />
      </FieldShell>
    );
  }

  if (type === "object") {
    return (
      <FieldShell label={label} hint={hint || "结构化配置，保存时按 JSON 解析"}>
        <TextArea
          value={objectFieldText(value)}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-24 font-mono text-xs sm:col-span-2"
          data-testid={testId}
        />
      </FieldShell>
    );
  }

  return (
    <FieldShell label={label} hint={hint}>
      <TextInput
        type={type === "number" || type === "integer" ? "number" : secret ? "password" : "text"}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        data-testid={testId}
      />
    </FieldShell>
  );
}

function ChannelBadges({ title, values, fallback }: { title: string; values: string[]; fallback?: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.length ? values.map((value) => <Badge key={value} tone="neutral">{value}</Badge>) : <Badge tone="neutral">{fallback || "暂无"}</Badge>}
      </div>
    </div>
  );
}

function schemaProperties(schema?: Record<string, unknown>) {
  const properties = isRecord(schema?.properties) ? schema.properties : {};
  return Object.fromEntries(
    Object.entries(properties).filter((entry): entry is [string, Record<string, unknown>] => isRecord(entry[1])),
  );
}

function schemaType(schema: Record<string, unknown>): string {
  const rawType = schema.type;
  if (typeof rawType === "string") return rawType;
  if (Array.isArray(rawType)) {
    const first = rawType.find((item) => item !== "null");
    if (typeof first === "string") return first;
  }
  const variants = Array.isArray(schema.anyOf) ? schema.anyOf : Array.isArray(schema.oneOf) ? schema.oneOf : [];
  for (const variant of variants) {
    if (!isRecord(variant)) continue;
    const variantType = schemaType(variant);
    if (variantType && variantType !== "null") return variantType;
  }
  if (Array.isArray(schema.enum)) return "string";
  if (isRecord(schema.properties)) return "object";
  return "string";
}

function schemaDefaultValue(schema: Record<string, unknown>) {
  if ("default" in schema) return schema.default;
  const type = schemaType(schema);
  if (type === "boolean") return false;
  if (type === "array") return [];
  if (type === "object") return {};
  if (type === "number" || type === "integer") return "";
  const enumValues = Array.isArray(schema.enum) ? schema.enum : [];
  if (enumValues.length) return enumValues[0];
  return "";
}

function normalizeSchemaDraft(draft: Record<string, unknown>, properties: Record<string, Record<string, unknown>>) {
  const normalized: Record<string, unknown> = { ...draft };
  for (const [name, schema] of Object.entries(properties)) {
    normalized[name] = normalizeSchemaValue(name, draft[name] ?? schemaDefaultValue(schema), schema);
  }
  return normalized;
}

function normalizeSchemaValue(name: string, value: unknown, schema: Record<string, unknown>): unknown {
  const type = schemaType(schema);
  if (type === "boolean") return value === true;
  if (type === "integer") {
    const text = String(value ?? "").trim();
    if (!text && "default" in schema) return schema.default;
    const parsed = Number(text);
    if (!Number.isFinite(parsed)) throw new Error(`${channelFieldLabel(name, schema)} 必须是数字。`);
    return Math.trunc(parsed);
  }
  if (type === "number") {
    const text = String(value ?? "").trim();
    if (!text && "default" in schema) return schema.default;
    const parsed = Number(text);
    if (!Number.isFinite(parsed)) throw new Error(`${channelFieldLabel(name, schema)} 必须是数字。`);
    return parsed;
  }
  if (type === "array") {
    if (Array.isArray(value)) return value.map(String).map((item) => item.trim()).filter(Boolean);
    return String(value ?? "")
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (type === "object") {
    if (isRecord(value)) return value;
    const text = String(value ?? "").trim();
    if (!text) return {};
    const parsed = JSON.parse(text) as unknown;
    if (!isRecord(parsed)) throw new Error(`${channelFieldLabel(name, schema)} 必须是 JSON 对象。`);
    return parsed;
  }
  return String(value ?? "");
}

function normalizeChannelConfig(config: Record<string, unknown>, properties: Record<string, Record<string, unknown>>) {
  const next = { ...config };
  if (next.enabled === true && properties.allow_from && (!Array.isArray(next.allow_from) || next.allow_from.length === 0)) {
    next.allow_from = ["*"];
  }
  return next;
}

function orderChannelFields(
  entries: Array<[string, Record<string, unknown>]>,
  channelName: string,
) {
  const priorityByChannel: Record<string, string[]> = {
    global: ["send_progress", "send_tool_hints"],
    qq: ["enabled", "app_id", "secret", "msg_format", "allow_from"],
    feishu: ["enabled", "app_id", "app_secret", "verification_token", "encrypt_key", "group_policy", "allow_from"],
    wecom: ["enabled", "bot_id", "secret", "welcome_message", "allow_from"],
    dingtalk: ["enabled", "client_id", "client_secret", "robot_code", "allow_from"],
    telegram: ["enabled", "token", "proxy", "reply_to_message", "allow_from"],
    slack: ["enabled", "bot_token", "app_token", "mode", "allow_from"],
    discord: ["enabled", "token", "guild_id", "channel_ids", "allow_from"],
    email: ["enabled", "imap_host", "imap_username", "imap_password", "smtp_host", "smtp_username", "smtp_password", "from_address", "consent_granted", "allow_from"],
    web: ["enabled", "welcome_text", "rate_limit"],
  };
  const priority = priorityByChannel[channelName] ?? ["enabled", "token", "bot_token", "app_id", "secret", "allow_from"];
  return [...entries].sort(([nameA, schemaA], [nameB, schemaB]) => {
    const ai = priority.indexOf(nameA);
    const bi = priority.indexOf(nameB);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    const typeA = schemaType(schemaA);
    const typeB = schemaType(schemaB);
    if (typeA === "object" && typeB !== "object") return 1;
    if (typeB === "object" && typeA !== "object") return -1;
    if (typeA === "array" && typeB !== "array") return 1;
    if (typeB === "array" && typeA !== "array") return -1;
    return nameA.localeCompare(nameB);
  });
}

function arrayFieldText(value: unknown) {
  return Array.isArray(value) ? value.map(String).join("\n") : String(value ?? "");
}

function objectFieldText(value: unknown) {
  if (!value) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function channelDisplayName(name: string, schema?: SparkBotChannelSchema) {
  const labels: Record<string, string> = {
    dingtalk: "钉钉",
    discord: "Discord",
    email: "邮箱",
    feishu: "飞书",
    matrix: "Matrix",
    mochat: "Mochat",
    qq: "QQ",
    slack: "Slack",
    telegram: "Telegram",
    web: "网页",
    wecom: "企业微信",
    whatsapp: "WhatsApp",
  };
  return labels[name] || schema?.display_name || name;
}

function channelFieldLabel(name: string, schema: Record<string, unknown>) {
  const labels: Record<string, string> = {
    access_token: "访问令牌",
    allow_from: "允许来源",
    app_id: "App ID",
    app_secret: "App Secret",
    app_token: "App Token",
    base_url: "服务地址",
    bot_id: "机器人 ID",
    bot_token: "Bot Token",
    client_id: "Client ID",
    client_secret: "Client Secret",
    enabled: "启用",
    encrypt_key: "加密 Key",
    group_policy: "群聊规则",
    imap_host: "IMAP 主机",
    imap_password: "IMAP 密码",
    imap_username: "IMAP 用户名",
    msg_format: "消息格式",
    rate_limit: "频率限制",
    secret: "Secret",
    send_progress: "发送进度",
    send_tool_hints: "发送工具提示",
    smtp_host: "SMTP 主机",
    smtp_password: "SMTP 密码",
    smtp_username: "SMTP 用户名",
    token: "Token",
    transcription_api_key: "语音转写 Key",
    verification_token: "Verification Token",
    webhook_url: "Webhook URL",
    welcome_text: "欢迎语",
  };
  return labels[name] || String(schema.title || name);
}

function channelFieldHint(channelName: string, name: string, schema: Record<string, unknown>) {
  const contextualHints: Record<string, string> = {
    "discord.gateway_url": "默认使用 Discord Gateway v10；只有自建代理时才需要改。",
    "discord.guild_id": "可选：限制到指定服务器；不填则按机器人加入的服务器接收事件。",
    "discord.intents": "默认包含消息内容权限；还需要在 Discord Developer Portal 开启 Message Content Intent。",
    "discord.token": "Discord Developer Portal 的 Bot Token；保存后按敏感字段处理。",
    "dingtalk.client_id": "钉钉开放平台应用凭证，部分页面也叫 AppKey 或 Client ID；Stream 模式必填。",
    "dingtalk.client_secret": "钉钉开放平台应用密钥，部分页面也叫 AppSecret 或 Client Secret。",
    "email.consent_granted": "确认该邮箱允许 SparkBot 自动读取并回复；未确认时不要启用。",
    "email.from_address": "外发显示地址；通常与 SMTP 用户名一致。",
    "email.imap_host": "邮箱收件服务器，例如 imap.example.com；需要账号开启 IMAP。",
    "email.imap_password": "建议使用邮箱应用专用密码，不要填写网页登录密码。",
    "email.smtp_host": "邮箱发件服务器，例如 smtp.example.com。",
    "email.smtp_password": "建议使用邮箱应用专用密码，不要填写网页登录密码。",
    "feishu.app_id": "飞书开放平台应用的 App ID；长连接事件订阅和发消息共用。",
    "feishu.app_secret": "飞书开放平台应用的 App Secret；保存后按敏感字段处理。",
    "feishu.encrypt_key": "飞书事件订阅的 Encrypt Key；未开启事件加密时可留空。",
    "feishu.verification_token": "飞书事件订阅的 Verification Token；长连接事件校验使用。",
    "matrix.access_token": "Matrix 账号访问令牌；建议使用专用机器人账号生成。",
    "matrix.device_id": "可选：生成令牌时的设备 ID；启用加密房间时建议填写并保留 store。",
    "matrix.e2ee_enabled": "默认关闭以保证安装稳定；加密房间需要额外安装 matrix-nio[e2e] 和 python-olm。",
    "matrix.homeserver": "Matrix homeserver 地址，例如 https://matrix.org 或你的自建服务。",
    "matrix.user_id": "机器人 Matrix 用户 ID，例如 @bot:matrix.org。",
    "mochat.base_url": "Mochat/ClawHub HTTP 服务地址；不是通用聊天平台配置。",
    "mochat.claw_token": "Mochat/ClawHub 接入令牌；保存后按敏感字段处理。",
    "mochat.socket_url": "Mochat/ClawHub Socket.IO 地址；留空时使用服务默认地址。",
    "qq.app_id": "QQ 机器人开放平台的 AppID；需要开通对应消息事件权限。",
    "qq.msg_format": "plain 更稳；markdown 需要 QQ 平台侧模板/消息能力支持。",
    "qq.secret": "QQ 机器人开放平台 Secret；保存后按敏感字段处理。",
    "slack.app_token": "Slack Socket Mode 的 App-Level Token，通常以 xapp- 开头并包含 connections:write。",
    "slack.bot_token": "Slack Bot Token，通常以 xoxb- 开头；需要 chat:write、app_mentions:read、im/history 等权限。",
    "slack.mode": "当前实现支持 Socket Mode；需要在 Slack 应用中开启 Socket Mode 和事件订阅。",
    "slack.user_token_read_only": "预留只读用户令牌开关；当前核心收发仍以 Bot Token 为主。",
    "telegram.proxy": "可选 HTTP/SOCKS 代理；只在本机访问 Telegram 受限时填写。",
    "telegram.reply_to_message": "开启后外部回复更像原平台线程；部分群聊可保持关闭。",
    "telegram.token": "BotFather 创建机器人后给出的 Bot Token；保存后按敏感字段处理。",
    "web.rate_limit": "网页试问入口的每分钟限流；比赛演示保持 8 左右即可。",
    "web.welcome_text": "网页试问入口的默认欢迎语，建议写成学习下一步而不是功能介绍。",
    "wecom.bot_id": "企业微信 Bot ID；用于 SDK WebSocket 鉴权。",
    "wecom.secret": "企业微信 Secret；保存后按敏感字段处理。",
    "wecom.welcome_message": "进入会话事件触发的欢迎语，需要企业微信侧支持该事件。",
    "whatsapp.bridge_token": "本地或第三方 WhatsApp WebSocket 桥接服务的认证 Token。",
    "whatsapp.bridge_url": "当前实现连接 WebSocket 桥接服务，不是 Meta WhatsApp Cloud API 直连。",
  };
  const hints: Record<string, string> = {
    allow_from: "测试可填 *；上线建议填写指定用户或群 ID",
    app_id: "在对应开放平台创建机器人后获得",
    app_secret: "在对应开放平台创建机器人后获得；保存后按敏感字段处理",
    bot_token: "平台机器人 Token；保存后按敏感字段处理",
    client_id: "开放平台应用凭证；按渠道官方页面填写",
    client_secret: "开放平台应用密钥；保存后按敏感字段处理",
    secret: "保存后会按敏感字段处理",
    send_progress: "开启后会把助教执行过程同步到外部入口",
    send_tool_hints: "通常比赛演示关闭，调试时可开启",
    token: "平台机器人 Token；保存后按敏感字段处理",
    transcription_api_key: "用于外部语音消息转写；不填则使用环境变量或关闭语音转写",
  };
  const contextual = contextualHints[`${channelName}.${name}`];
  if (contextual) return contextual;
  return hints[name] || (typeof schema.description === "string" ? schema.description : undefined);
}

function orderChannelNames(names: string[]) {
  const priority = ["qq", "feishu", "wecom", "dingtalk", "telegram", "slack", "discord", "email", "whatsapp", "matrix", "mochat", "web"];
  return [...names].sort((a, b) => {
    const ai = priority.indexOf(a);
    const bi = priority.indexOf(b);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return a.localeCompare(b);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
