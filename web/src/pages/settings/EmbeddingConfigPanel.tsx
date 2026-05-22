import type { Dispatch, SetStateAction } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";
import { ConfigBlock, PresetModelInput, ProviderQuickNote, ProviderSelect } from "./SettingsConfigControls";
import type { EmbeddingForm } from "./settingsCatalogUtils";

type FormSetter<T> = Dispatch<SetStateAction<T>>;

export function EmbeddingConfigPanel({
  value,
  providers,
  onChange,
}: {
  value: EmbeddingForm;
  providers: ProviderChoice[];
  onChange: FormSetter<EmbeddingForm>;
}) {
  const activeProvider = providers.find((provider) => provider.value === value.binding);
  const modelOptions = activeProvider?.models ?? [];

  return (
    <ConfigBlock title="资料理解" summary="负责资料入库、资料问答和相似内容匹配。">
      <ProviderSelect
        label="服务提供方"
        value={value.binding}
        providers={providers}
        testId="settings-embedding-provider"
        onChange={(binding, provider) =>
          onChange((current) => ({
            ...current,
            binding,
            baseUrl: provider?.base_url ?? "",
            model: provider?.default_model || provider?.models?.[0] || "",
            dimension: provider?.default_dim ?? "",
            iflytekDomain: binding === "iflytek_spark" ? current.iflytekDomain || "para" : current.iflytekDomain,
          }))
        }
      />
      <ProviderQuickNote provider={activeProvider} />
      <FieldShell label="服务地址">
        <TextInput
          value={value.baseUrl}
          onChange={(event) => onChange((current) => ({ ...current, baseUrl: event.target.value }))}
          data-testid="settings-embedding-base-url"
        />
      </FieldShell>
      <FieldShell label="模型名称" hint={modelOptions.length ? "可选择预设，也可以直接输入模型名称" : undefined}>
        <PresetModelInput
          id="settings-embedding-model"
          value={value.model}
          options={modelOptions}
          recommendedModel={activeProvider?.default_model}
          onChange={(model) => onChange((current) => ({ ...current, model }))}
          testId="settings-embedding-model"
          presetTestId="settings-embedding-model-select"
        />
      </FieldShell>
      <FieldShell label="匹配维度">
        <TextInput
          value={value.dimension}
          onChange={(event) => onChange((current) => ({ ...current, dimension: event.target.value }))}
          data-testid="settings-embedding-dimension"
        />
      </FieldShell>
      {value.binding === "iflytek_spark" ? (
        <>
          <FieldShell label="讯飞应用 ID" hint="资料理解签名必填">
            <TextInput
              value={value.iflytekAppId}
              onChange={(event) => onChange((current) => ({ ...current, iflytekAppId: event.target.value }))}
              data-testid="settings-embedding-iflytek-appid"
            />
          </FieldShell>
          <FieldShell label="讯飞密钥 Secret" hint="当前生效的资料理解 Secret">
            <TextInput
              type="password"
              autoComplete="off"
              value={value.iflytekApiSecret}
              onChange={(event) => onChange((current) => ({ ...current, iflytekApiSecret: event.target.value }))}
              data-testid="settings-embedding-iflytek-api-secret"
            />
          </FieldShell>
          <FieldShell label="讯飞用途">
            <SelectInput
              value={value.iflytekDomain}
              onChange={(event) => onChange((current) => ({ ...current, iflytekDomain: event.target.value }))}
              data-testid="settings-embedding-iflytek-domain"
            >
              <option value="para">para：资料入库</option>
              <option value="query">query：问题匹配</option>
            </SelectInput>
          </FieldShell>
        </>
      ) : null}
      <FieldShell label="访问密钥" hint="当前生效的资料理解密钥">
        <TextInput
          type="password"
          autoComplete="off"
          value={value.apiKey}
          onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
          data-testid="settings-embedding-api-key"
        />
      </FieldShell>
    </ConfigBlock>
  );
}
