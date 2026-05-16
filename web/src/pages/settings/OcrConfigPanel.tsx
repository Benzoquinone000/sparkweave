import type { Dispatch, SetStateAction } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";
import { ConfigBlock, PresetModelInput, ProviderSelect } from "./SettingsConfigControls";
import { fallbackOcrProviders, type OcrForm } from "./settingsCatalogUtils";

type FormSetter<T> = Dispatch<SetStateAction<T>>;

export function OcrConfigPanel({
  value,
  providers,
  onChange,
}: {
  value: OcrForm;
  providers?: ProviderChoice[];
  onChange: FormSetter<OcrForm>;
}) {
  const providerOptions = providers ?? fallbackOcrProviders();
  const activeProvider = providerOptions.find((provider) => provider.value === value.provider);
  const isSiliconFlow = value.provider === "siliconflow";
  const isIflytek = value.provider === "iflytek";
  const modelOptions = activeProvider?.models ?? [];

  return (
    <ConfigBlock title="OCR / 扫描 PDF" summary="用于扫描版 PDF、图片文字和导入资料的兜底识别。">
      <ProviderSelect
        label="OCR 提供方"
        value={value.provider}
        providers={providerOptions}
        testId="settings-ocr-provider"
        onChange={(providerValue, provider) =>
          onChange((current) => ({
            ...current,
            provider: providerValue,
            baseUrl: provider?.base_url ?? current.baseUrl,
            model: provider?.default_model || provider?.models?.[0] || current.model,
            strategy: providerValue === "disabled" ? "auto" : current.strategy,
          }))
        }
      />
      <FieldShell label="PDF OCR 策略">
        <SelectInput
          value={value.strategy}
          onChange={(event) => onChange((current) => ({ ...current, strategy: event.target.value }))}
          data-testid="settings-ocr-strategy"
        >
          <option value="auto">自动：文本过少时 OCR</option>
          <option value="iflytek_first">优先 OCR：扫描版 PDF 推荐</option>
        </SelectInput>
      </FieldShell>
      {isIflytek ? (
        <FieldShell label="APPID" hint="当前生效的 OCR APPID">
          <TextInput
            value={value.appId}
            onChange={(event) => onChange((current) => ({ ...current, appId: event.target.value }))}
            disabled={value.provider === "disabled"}
            data-testid="settings-ocr-appid"
          />
        </FieldShell>
      ) : null}
      <FieldShell label="APIKey" hint={isSiliconFlow ? "当前生效的硅基流动 OCR APIKey" : "当前生效的讯飞 OCR APIKey"}>
        <TextInput
          value={value.apiKey}
          onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
          disabled={value.provider === "disabled"}
          data-testid="settings-ocr-api-key"
        />
      </FieldShell>
      {isIflytek ? (
        <FieldShell label="APISecret" hint="当前生效的 OCR APISecret">
          <TextInput
            value={value.apiSecret}
            onChange={(event) => onChange((current) => ({ ...current, apiSecret: event.target.value }))}
            disabled={value.provider === "disabled"}
            data-testid="settings-ocr-api-secret"
          />
        </FieldShell>
      ) : null}
      <FieldShell label="服务地址">
        <TextInput
          value={value.baseUrl}
          onChange={(event) => onChange((current) => ({ ...current, baseUrl: event.target.value }))}
          disabled={value.provider === "disabled"}
          data-testid="settings-ocr-base-url"
        />
      </FieldShell>
      {isSiliconFlow ? (
        <FieldShell label="模型名称" hint={modelOptions.length ? "可选择预设，也可以直接输入模型 ID" : "输入硅基流动模型 ID"}>
          <PresetModelInput
            id="settings-ocr-model"
            value={value.model}
            options={modelOptions}
            onChange={(model) => onChange((current) => ({ ...current, model }))}
            testId="settings-ocr-model"
            presetTestId="settings-ocr-model-select"
          />
        </FieldShell>
      ) : null}
      <details className="rounded-lg border border-line bg-canvas p-3">
        <summary className="cursor-pointer select-none text-sm font-semibold text-ink">
          高级参数，通常不用填写
        </summary>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          留空时不写入配置，OCR 会使用服务和运行时默认值。只有在扫描 PDF 很大、识别超时或图片过糊时再调整。
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <FieldShell label="最大页数" hint="留空则不限制页数">
            <TextInput
              value={value.maxPages}
              placeholder="默认"
              onChange={(event) => onChange((current) => ({ ...current, maxPages: event.target.value }))}
              data-testid="settings-ocr-max-pages"
            />
          </FieldShell>
          <FieldShell label="DPI" hint="留空使用默认渲染清晰度">
            <TextInput
              value={value.dpi}
              placeholder="默认"
              onChange={(event) => onChange((current) => ({ ...current, dpi: event.target.value }))}
              data-testid="settings-ocr-dpi"
            />
          </FieldShell>
          <FieldShell label="超时秒数" hint="留空使用默认请求超时">
            <TextInput
              value={value.timeout}
              placeholder="默认"
              onChange={(event) => onChange((current) => ({ ...current, timeout: event.target.value }))}
              data-testid="settings-ocr-timeout"
            />
          </FieldShell>
          <FieldShell label="触发字符数" hint="留空使用默认扫描 PDF 判断">
            <TextInput
              value={value.minTextChars}
              placeholder="默认"
              onChange={(event) => onChange((current) => ({ ...current, minTextChars: event.target.value }))}
              data-testid="settings-ocr-min-text-chars"
            />
          </FieldShell>
        </div>
        {isIflytek ? (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <FieldShell label="服务 ID">
              <TextInput
                value={value.serviceId}
                onChange={(event) => onChange((current) => ({ ...current, serviceId: event.target.value }))}
                disabled={value.provider === "disabled"}
                data-testid="settings-ocr-service-id"
              />
            </FieldShell>
            <FieldShell label="分类">
              <TextInput
                value={value.category}
                onChange={(event) => onChange((current) => ({ ...current, category: event.target.value }))}
                disabled={value.provider === "disabled"}
                data-testid="settings-ocr-category"
              />
            </FieldShell>
          </div>
        ) : null}
      </details>
    </ConfigBlock>
  );
}
