import type { Dispatch, SetStateAction } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";
import { ConfigBlock, PresetModelInput, ProviderQuickNote, ProviderSelect } from "./SettingsConfigControls";
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
  const isIflytekMaas = value.binding === "iflytek_maas_coding";

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
      <ProviderQuickNote provider={activeProvider} />
      <FieldShell label="服务地址">
        <TextInput
          value={value.baseUrl}
          onChange={(event) => onChange((current) => ({ ...current, baseUrl: event.target.value }))}
          data-testid="settings-llm-base-url"
        />
      </FieldShell>
      <FieldShell label="模型名称" hint={modelOptions.length ? "可选择预设，也可以直接输入模型名称" : "输入模型名称"}>
        <PresetModelInput
          id="settings-llm-model"
          value={value.model}
          options={modelOptions}
          recommendedModel={activeProvider?.default_model}
          onChange={(model) => onChange((current) => ({ ...current, model }))}
          testId="settings-llm-model"
          presetTestId="settings-llm-model-select"
        />
      </FieldShell>
      {isIflytek ? (
        <>
          <FieldShell label="讯飞连接方式" hint="通常选择连接密码；老版密钥可选择访问密钥 + Secret">
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
              <option value="api_password">连接密码</option>
              <option value="ak_sk">访问密钥 + Secret</option>
            </SelectInput>
          </FieldShell>
          {value.iflytekAuthMode === "api_password" ? (
            <FieldShell label="连接密码" hint="当前生效的 HTTP 连接密码">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.apiKey}
                onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
                data-testid="settings-llm-api-key"
              />
            </FieldShell>
          ) : (
            <>
              <FieldShell label="访问密钥" hint="保存时自动拼接为访问密钥:Secret">
                <TextInput
                  type="password"
                  autoComplete="off"
                  value={value.apiKey}
                  onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
                  data-testid="settings-llm-api-key"
                />
              </FieldShell>
              <FieldShell label="密钥 Secret" hint="当前生效的 Secret">
                <TextInput
                  type="password"
                  autoComplete="off"
                  value={value.iflytekApiSecret}
                  onChange={(event) => onChange((current) => ({ ...current, iflytekApiSecret: event.target.value }))}
                  data-testid="settings-llm-iflytek-api-secret"
                />
              </FieldShell>
            </>
          )}
        </>
      ) : (
        <FieldShell
          label={isIflytekMaas ? "MaaS 连接密码" : "密钥"}
          hint={isIflytekMaas ? "填写 MaaS APIPassword，通常形如访问密钥:Secret" : "当前生效的模型访问密钥"}
        >
          <TextInput
            type="password"
            autoComplete="off"
            value={value.apiKey}
            onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
            data-testid="settings-llm-api-key"
          />
        </FieldShell>
      )}
    </ConfigBlock>
  );
}
