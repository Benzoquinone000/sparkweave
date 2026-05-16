import { Loader2, Save } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea, TextInput } from "@/components/ui/Field";
import type { SparkBotChannelSchema, SparkBotFile } from "@/lib/types";
import { assistantWorkspaceFileMeta } from "./agentWorkspaceFiles";

export function GlobalChannelEditor({
  schema,
  currentChannels,
  pending,
  onSave,
}: {
  schema: Partial<SparkBotChannelSchema>;
  currentChannels?: Record<string, unknown>;
  pending: boolean;
  onSave: (config: Record<string, unknown>) => Promise<void>;
}) {
  const globalSchema: SparkBotChannelSchema = {
    name: "global",
    display_name: "全局渠道行为",
    default_config: defaultsFromSchema(schema.json_schema),
    secret_fields: schema.secret_fields ?? [],
    json_schema: schema.json_schema ?? { type: "object", properties: {} },
  };
  const currentConfig = pickSchemaConfig(currentChannels, globalSchema);
  return (
    <div className="border-t border-line pt-3" data-testid="sparkbot-global-channel-editor">
      <ChannelEditor schema={globalSchema} currentConfig={currentConfig} pending={pending} onSave={onSave} submitLabel="保存全局" />
    </div>
  );
}

export function ChannelEditor({
  schema,
  currentConfig,
  pending,
  onSave,
  submitLabel = "保存渠道",
}: {
  schema: SparkBotChannelSchema;
  currentConfig?: Record<string, unknown>;
  pending: boolean;
  onSave: (config: Record<string, unknown>) => Promise<void>;
  submitLabel?: string;
}) {
  const initialConfig = useMemo(() => ({ ...(schema.default_config ?? {}), ...(currentConfig ?? {}) }), [currentConfig, schema.default_config]);
  const schemaProperties = useMemo(() => getSchemaProperties(schema), [schema]);
  const [formValues, setFormValues] = useState<Record<string, unknown>>(initialConfig);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [value, setValue] = useState(JSON.stringify(initialConfig, null, 2));
  const [error, setError] = useState("");
  const updateValue = (key: string, nextValue: unknown) => {
    setFormValues((current) => ({ ...current, [key]: nextValue }));
  };
  const parsedConfig = () => {
    if (advancedMode || !schemaProperties.length) return JSON.parse(value) as Record<string, unknown>;
    const next = { ...initialConfig };
    for (const property of schemaProperties) {
      next[property.key] = normalizeChannelValue(formValues[property.key], property);
    }
    return next;
  };

  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        try {
          const parsed = parsedConfig();
          setError("");
          void onSave(parsed);
        } catch (parseError) {
          setError(parseError instanceof Error ? parseError.message : "JSON 解析失败");
        }
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{schema.display_name || schema.name}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{schemaProperties.length ? "根据渠道字段生成表单。" : "这个渠道没有公开字段，使用高级配置。"}</p>
        </div>
        <Button
          tone="quiet"
          className="min-h-8 px-2 text-xs"
          type="button"
          onClick={() => {
            if (!advancedMode) setValue(JSON.stringify({ ...initialConfig, ...formValues }, null, 2));
            setAdvancedMode((current) => !current);
          }}
        >
          {advancedMode ? "表单模式" : "高级模式"}
        </Button>
      </div>
      {!advancedMode && schemaProperties.length ? (
        <div className="grid gap-3 border-t border-line pt-3">
          {schemaProperties.map((property) => (
            <ChannelSchemaField
              key={property.key}
              property={property}
              secret={schema.secret_fields?.includes(property.key)}
              value={formValues[property.key]}
              onChange={(nextValue) => updateValue(property.key, nextValue)}
            />
          ))}
        </div>
      ) : (
        <FieldShell label={schema.display_name || schema.name} hint={schema.secret_fields?.length ? `敏感字段：${schema.secret_fields.join(", ")}` : undefined}>
          <TextArea value={value} onChange={(event) => setValue(event.target.value)} className="min-h-64 font-mono text-xs" />
        </FieldShell>
      )}
      {error ? <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-brand-red">{error}</p> : null}
      <Button tone="secondary" type="submit" disabled={pending}>
        {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
        {submitLabel}
      </Button>
    </form>
  );
}

type ChannelSchemaProperty = {
  key: string;
  label: string;
  description?: string;
  type?: string;
  enum?: string[];
  default?: unknown;
};

function ChannelSchemaField({
  property,
  secret,
  value,
  onChange,
}: {
  property: ChannelSchemaProperty;
  secret?: boolean;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const label = property.label || property.key;
  const valueString = value == null ? "" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  if (property.type === "boolean") {
    return (
      <label className="flex items-start gap-3 rounded-lg border border-line bg-white p-3">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-1 size-4 rounded border-line text-brand-purple focus:ring-brand-purple"
          data-testid={`channel-field-${property.key}`}
        />
        <span>
          <span className="block text-sm font-medium text-ink">{label}</span>
          {property.description ? <span className="mt-1 block text-xs leading-5 text-slate-500">{property.description}</span> : null}
        </span>
      </label>
    );
  }
  if (property.enum?.length) {
    return (
      <FieldShell label={label} hint={property.description}>
        <SelectInput value={valueString} onChange={(event) => onChange(event.target.value)} data-testid={`channel-field-${property.key}`}>
          {property.enum.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </SelectInput>
      </FieldShell>
    );
  }
  if (property.type === "object" || property.type === "array") {
    return (
      <FieldShell label={label} hint={property.description}>
        <TextArea
          value={valueString}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-24 font-mono text-xs"
          data-testid={`channel-field-${property.key}`}
        />
      </FieldShell>
    );
  }
  return (
    <FieldShell label={label} hint={secret ? `${property.description || ""} secret`.trim() : property.description}>
      <TextInput
        type={secret ? "password" : property.type === "number" || property.type === "integer" ? "number" : "text"}
        value={valueString}
        onChange={(event) => onChange(event.target.value)}
        data-testid={`channel-field-${property.key}`}
      />
    </FieldShell>
  );
}

export function FileEditor({
  filename,
  file,
  fallbackContent,
  pending,
  onSave,
}: {
  botId: string;
  filename: string;
  file?: SparkBotFile;
  fallbackContent?: string;
  pending: boolean;
  onSave: (content: string) => Promise<unknown>;
}) {
  const [content, setContent] = useState(file?.content ?? fallbackContent ?? "");
  const meta = assistantWorkspaceFileMeta(filename);
  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave(content);
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="brand">{filename}</Badge>
            <Badge tone={meta.tone}>{meta.label}</Badge>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">{meta.detail}</p>
        </div>
        <Button tone="primary" type="submit" disabled={pending} data-testid="sparkbot-file-save">
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存文件
        </Button>
      </div>
      <TextArea value={content} onChange={(event) => setContent(event.target.value)} className="min-h-96 font-mono text-xs" data-testid="sparkbot-file-content" />
    </form>
  );
}

function getSchemaProperties(schema: SparkBotChannelSchema): ChannelSchemaProperty[] {
  const jsonSchema = isRecord(schema.json_schema) ? schema.json_schema : {};
  const properties = isRecord(jsonSchema.properties) ? jsonSchema.properties : {};
  return Object.entries(properties).map(([key, raw]) => {
    const property = isRecord(raw) ? raw : {};
    const enumValues = Array.isArray(property.enum) ? property.enum.map(String) : undefined;
    return {
      key,
      label: String(property.title || key),
      description: typeof property.description === "string" ? property.description : undefined,
      type: typeof property.type === "string" ? property.type : undefined,
      enum: enumValues,
      default: property.default,
    };
  });
}

function defaultsFromSchema(schema: unknown) {
  const jsonSchema = isRecord(schema) ? schema : {};
  const properties = isRecord(jsonSchema.properties) ? jsonSchema.properties : {};
  return Object.fromEntries(
    Object.entries(properties).map(([key, raw]) => {
      const property = isRecord(raw) ? raw : {};
      return [key, property.default ?? defaultValueForSchemaType(property.type)];
    }),
  );
}

function defaultValueForSchemaType(type: unknown) {
  if (type === "boolean") return false;
  if (type === "integer" || type === "number") return 0;
  if (type === "array") return [];
  if (type === "object") return {};
  return "";
}

function pickSchemaConfig(source: Record<string, unknown> | undefined, schema: SparkBotChannelSchema) {
  if (!source) return undefined;
  const keys = new Set(getSchemaProperties(schema).map((property) => property.key));
  return Object.fromEntries(Object.entries(source).filter(([key]) => keys.has(key)));
}

function normalizeChannelValue(value: unknown, property: ChannelSchemaProperty) {
  if (property.type === "boolean") return Boolean(value);
  if (property.type === "number") {
    if (value === "" || value == null) return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : value;
  }
  if (property.type === "integer") {
    if (value === "" || value == null) return undefined;
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? parsed : value;
  }
  if (property.type === "object" || property.type === "array") {
    if (typeof value !== "string") return value;
    const trimmed = value.trim();
    if (!trimmed) return property.type === "array" ? [] : {};
    return JSON.parse(trimmed) as unknown;
  }
  return value ?? "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
