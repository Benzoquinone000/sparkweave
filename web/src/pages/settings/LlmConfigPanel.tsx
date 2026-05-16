import type { Dispatch, SetStateAction } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";
import { ConfigBlock, PresetModelInput, ProviderSelect } from "./SettingsConfigControls";
import { chooseProviderModel, type IflytekLlmAuthMode, type LlmForm } from "./settingsCatalogUtils";

type FormSetter<T> = Dispatch<SetStateAction<T>>;

export function LlmConfigPanel({
  value,
  providers,
  onChange,
}: {
  value: LlmForm;
  providers: ProviderChoice[];
  onChange: FormSetter<LlmForm>;
}) {
  const activeProvider = providers.find((provider) => provider.value === value.binding);
  const modelOptions = activeProvider?.models ?? [];
  const isIflytek = value.binding === "iflytek_spark_ws";

  return (
    <ConfigBlock title="问答模型" summary="决定对话、导学和资源生成质量，先把这里配置稳定。">
      <ProviderSelect
        label="服务提供方"
        value={value.binding}
        providers={providers}
        onChange={(binding, provider) =>
          onChange((current) => ({
            ...current,
            binding,
            baseUrl: provider?.base_url || current.baseUrl,
            iflytekAuthMode: binding === "iflytek_spark_ws" ? current.iflytekAuthMode : "api_password",
            model: chooseProviderModel(
              current.model,
              provider,
              providers.find((item) => item.value === current.binding),
            ),
          }))
        }
      />
      <FieldShell label="服务地址">
        <TextInput
          value={value.baseUrl}
          onChange={(event) => onChange((current) => ({ ...current, baseUrl: event.target.value }))}
          data-testid="settings-llm-base-url"
        />
      </FieldShell>
      <FieldShell label="模型名称" hint={modelOptions.length ? "可选择预设，也可以直接输入模型 ID" : "输入模型 ID"}>
        <PresetModelInput
          id="settings-llm-model"
          value={value.model}
          options={modelOptions}
          onChange={(model) => onChange((current) => ({ ...current, model }))}
          testId="settings-llm-model"
          presetTestId="settings-llm-model-select"
        />
      </FieldShell>
      {isIflytek ? (
        <>
          <FieldShell label="讯飞鉴权方式" hint="HTTP APIPassword 或 APIKey + APISecret">
            <SelectInput
              value={value.iflytekAuthMode}
              onChange={(event) =>
                onChange((current) => ({
                  ...current,
                  iflytekAuthMode: event.target.value as IflytekLlmAuthMode,
                  apiKey: "",
                  iflytekApiSecret: "",
                }))
              }
              data-testid="settings-llm-iflytek-auth-mode"
            >
              <option value="api_password">HTTP APIPassword</option>
              <option value="ak_sk">APIKey + APISecret</option>
            </SelectInput>
          </FieldShell>
          {value.iflytekAuthMode === "api_password" ? (
            <FieldShell label="APIPassword" hint="当前生效的 HTTP 协议 APIPassword">
              <TextInput
                value={value.apiKey}
                onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
                data-testid="settings-llm-api-key"
              />
            </FieldShell>
          ) : (
            <>
              <FieldShell label="APIKey" hint="保存时自动拼接为 APIKey:APISecret">
                <TextInput
                  value={value.apiKey}
                  onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
                  data-testid="settings-llm-api-key"
                />
              </FieldShell>
              <FieldShell label="APISecret" hint="当前生效的 APISecret">
                <TextInput
                  value={value.iflytekApiSecret}
                  onChange={(event) => onChange((current) => ({ ...current, iflytekApiSecret: event.target.value }))}
                  data-testid="settings-llm-iflytek-api-secret"
                />
              </FieldShell>
            </>
          )}
        </>
      ) : (
        <FieldShell label="密钥" hint="当前生效的模型访问密钥">
          <TextInput
            value={value.apiKey}
            onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
            data-testid="settings-llm-api-key"
          />
        </FieldShell>
      )}
    </ConfigBlock>
  );
}
