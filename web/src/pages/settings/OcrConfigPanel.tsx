import type { Dispatch, SetStateAction } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";
import { ConfigBlock, PresetModelInput, ProviderQuickNote, ProviderSelect } from "./SettingsConfigControls";
import {
  fallbackFormulaOcrProviders,
  fallbackImageUnderstandingProviders,
  fallbackOcrProviders,
  type FormulaOcrForm,
  type ImageUnderstandingForm,
  type OcrForm,
} from "./settingsCatalogUtils";

type FormSetter<T> = Dispatch<SetStateAction<T>>;

export function OcrConfigPanel({
  value,
  providers,
  formulaValue,
  formulaProviders,
  imageValue,
  imageProviders,
  onChange,
  onFormulaChange,
  onImageChange,
}: {
  value: OcrForm;
  providers?: ProviderChoice[];
  formulaValue: FormulaOcrForm;
  formulaProviders?: ProviderChoice[];
  imageValue: ImageUnderstandingForm;
  imageProviders?: ProviderChoice[];
  onChange: FormSetter<OcrForm>;
  onFormulaChange: FormSetter<FormulaOcrForm>;
  onImageChange: FormSetter<ImageUnderstandingForm>;
}) {
  const providerOptions = providers ?? fallbackOcrProviders();
  const activeProvider = providerOptions.find((provider) => provider.value === value.provider);
  const isSiliconFlow = value.provider === "siliconflow";
  const isIflytek = value.provider === "iflytek";
  const modelOptions = activeProvider?.models ?? [];

  return (
    <ConfigBlock title="图片文字识别" summary="用于扫描版 PDF、图片文字和导入资料的兜底识别。">
      <ProviderSelect
        label="识别服务"
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
      <ProviderQuickNote provider={activeProvider} />
      <FieldShell label="PDF 识别策略">
        <SelectInput
          value={value.strategy}
          onChange={(event) => onChange((current) => ({ ...current, strategy: event.target.value }))}
          data-testid="settings-ocr-strategy"
        >
          <option value="auto">自动：文本过少时识别</option>
          <option value="iflytek_first">优先识别：扫描版 PDF 推荐</option>
        </SelectInput>
      </FieldShell>
      {isIflytek ? (
        <FieldShell label="应用 ID" hint="当前生效的讯飞 APPID">
          <TextInput
            value={value.appId}
            onChange={(event) => onChange((current) => ({ ...current, appId: event.target.value }))}
            disabled={value.provider === "disabled"}
            data-testid="settings-ocr-appid"
          />
        </FieldShell>
      ) : null}
      <FieldShell label="访问密钥" hint={isSiliconFlow ? "当前生效的硅基流动访问密钥" : "当前生效的讯飞访问密钥"}>
        <TextInput
          type="password"
          autoComplete="off"
          value={value.apiKey}
          onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
          disabled={value.provider === "disabled"}
          data-testid="settings-ocr-api-key"
        />
      </FieldShell>
      {isIflytek ? (
        <FieldShell label="密钥 Secret" hint="当前生效的讯飞 Secret">
          <TextInput
            type="password"
            autoComplete="off"
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
        <FieldShell label="模型名称" hint={modelOptions.length ? "可选择预设，也可以直接输入模型名称" : "输入硅基流动模型名称"}>
          <PresetModelInput
            id="settings-ocr-model"
            value={value.model}
            options={modelOptions}
            recommendedModel={activeProvider?.default_model}
            onChange={(model) => onChange((current) => ({ ...current, model }))}
            testId="settings-ocr-model"
            presetTestId="settings-ocr-model-select"
          />
        </FieldShell>
      ) : null}

      <div className="grid gap-3 xl:grid-cols-2">
        <FormulaOcrPresetCard
          value={formulaValue}
          providers={formulaProviders ?? fallbackFormulaOcrProviders()}
          onChange={onFormulaChange}
        />
        <ImageUnderstandingPresetCard
          value={imageValue}
          providers={imageProviders ?? fallbackImageUnderstandingProviders()}
          onChange={onImageChange}
        />
      </div>

      <details className="rounded-lg border border-line bg-canvas p-3">
        <summary className="cursor-pointer select-none text-sm font-semibold text-ink">
          少用设置，通常不用改
        </summary>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          留空时不写入配置，识别服务会使用默认值。只有在扫描 PDF 很大、识别超时或图片过糊时再调整。
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

function FormulaOcrPresetCard({
  value,
  providers,
  onChange,
}: {
  value: FormulaOcrForm;
  providers: ProviderChoice[];
  onChange: FormSetter<FormulaOcrForm>;
}) {
  const activeProvider = providers.find((provider) => provider.value === value.provider);
  const disabled = value.provider === "disabled";
  return (
    <section className="rounded-lg border border-line bg-canvas p-3">
      <h4 className="text-sm font-semibold text-ink">公式识别</h4>
      <p className="mt-1 text-xs leading-5 text-steel">把题图、手写公式转成可检索、可解题的公式文本。</p>
      <div className="mt-3 grid gap-3">
        <ProviderSelect
          label="公式服务"
          value={value.provider}
          providers={providers}
          testId="settings-formula-ocr-provider"
          onChange={(providerValue, provider) =>
            onChange((current) => ({
              ...current,
              provider: providerValue,
              baseUrl: provider?.base_url ?? current.baseUrl,
            }))
          }
        />
        <ProviderQuickNote provider={activeProvider} />
        <FieldShell label="服务地址">
          <TextInput
            value={value.baseUrl}
            onChange={(event) => onChange((current) => ({ ...current, baseUrl: event.target.value }))}
            disabled={disabled}
            data-testid="settings-formula-ocr-base-url"
          />
        </FieldShell>
        <details className="rounded-lg border border-line bg-white p-3">
          <summary className="cursor-pointer select-none text-sm font-semibold text-ink">
            单独密钥与识别参数
          </summary>
          <p className="mt-2 text-xs leading-5 text-slate-500">默认复用上方科大讯飞共享密钥；只有单独开通服务时再填写。</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <FieldShell label="应用 ID">
              <TextInput
                value={value.appId}
                onChange={(event) => onChange((current) => ({ ...current, appId: event.target.value }))}
                disabled={disabled}
                data-testid="settings-formula-ocr-appid"
              />
            </FieldShell>
            <FieldShell label="访问密钥">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.apiKey}
                onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
                disabled={disabled}
                data-testid="settings-formula-ocr-api-key"
              />
            </FieldShell>
            <FieldShell label="密钥 Secret">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.apiSecret}
                onChange={(event) => onChange((current) => ({ ...current, apiSecret: event.target.value }))}
                disabled={disabled}
                data-testid="settings-formula-ocr-api-secret"
              />
            </FieldShell>
            <FieldShell label="识别场景">
              <SelectInput
                value={value.ent}
                onChange={(event) => onChange((current) => ({ ...current, ent: event.target.value }))}
                disabled={disabled}
                data-testid="settings-formula-ocr-ent"
              >
                <option value="teach-photo-print">拍照印刷公式</option>
                <option value="teach-photo-hand">拍照手写公式</option>
              </SelectInput>
            </FieldShell>
            <FieldShell label="音频/图片编码">
              <SelectInput
                value={value.aue}
                onChange={(event) => onChange((current) => ({ ...current, aue: event.target.value }))}
                disabled={disabled}
                data-testid="settings-formula-ocr-aue"
              >
                <option value="raw">raw</option>
              </SelectInput>
            </FieldShell>
            <FieldShell label="超时秒数">
              <TextInput
                value={value.timeout}
                onChange={(event) => onChange((current) => ({ ...current, timeout: event.target.value }))}
                disabled={disabled}
                data-testid="settings-formula-ocr-timeout"
              />
            </FieldShell>
          </div>
        </details>
      </div>
    </section>
  );
}

function ImageUnderstandingPresetCard({
  value,
  providers,
  onChange,
}: {
  value: ImageUnderstandingForm;
  providers: ProviderChoice[];
  onChange: FormSetter<ImageUnderstandingForm>;
}) {
  const activeProvider = providers.find((provider) => provider.value === value.provider);
  const disabled = value.provider === "disabled";
  return (
    <section className="rounded-lg border border-line bg-canvas p-3">
      <h4 className="text-sm font-semibold text-ink">图片理解</h4>
      <p className="mt-1 text-xs leading-5 text-steel">把板书、截图、示意图解释成智能辅导可用的上下文。</p>
      <div className="mt-3 grid gap-3">
        <ProviderSelect
          label="理解服务"
          value={value.provider}
          providers={providers}
          testId="settings-image-understanding-provider"
          onChange={(providerValue, provider) =>
            onChange((current) => ({
              ...current,
              provider: providerValue,
              baseUrl: provider?.base_url ?? current.baseUrl,
            }))
          }
        />
        <ProviderQuickNote provider={activeProvider} />
        <FieldShell label="服务地址">
          <TextInput
            value={value.baseUrl}
            onChange={(event) => onChange((current) => ({ ...current, baseUrl: event.target.value }))}
            disabled={disabled}
            data-testid="settings-image-understanding-base-url"
          />
        </FieldShell>
        <FieldShell label="协议">
          <SelectInput
            value={value.protocol}
            onChange={(event) => onChange((current) => ({ ...current, protocol: event.target.value }))}
            disabled={disabled}
            data-testid="settings-image-understanding-protocol"
          >
            <option value="spark_image">星火图片理解</option>
            <option value="maas_vl">MaaS 多模态</option>
          </SelectInput>
        </FieldShell>
        <details className="rounded-lg border border-line bg-white p-3">
          <summary className="cursor-pointer select-none text-sm font-semibold text-ink">
            单独密钥与生成参数
          </summary>
          <p className="mt-2 text-xs leading-5 text-slate-500">默认复用上方科大讯飞共享密钥；切换 MaaS 多模态时再改协议和地址。</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <FieldShell label="应用 ID">
              <TextInput
                value={value.appId}
                onChange={(event) => onChange((current) => ({ ...current, appId: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-appid"
              />
            </FieldShell>
            <FieldShell label="访问密钥">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.apiKey}
                onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-api-key"
              />
            </FieldShell>
            <FieldShell label="密钥 Secret">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.apiSecret}
                onChange={(event) => onChange((current) => ({ ...current, apiSecret: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-api-secret"
              />
            </FieldShell>
            <FieldShell label="模型域">
              <TextInput
                value={value.domain}
                onChange={(event) => onChange((current) => ({ ...current, domain: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-domain"
              />
            </FieldShell>
            <FieldShell label="最大输出">
              <TextInput
                value={value.maxTokens}
                onChange={(event) => onChange((current) => ({ ...current, maxTokens: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-max-tokens"
              />
            </FieldShell>
            <FieldShell label="温度">
              <TextInput
                value={value.temperature}
                onChange={(event) => onChange((current) => ({ ...current, temperature: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-temperature"
              />
            </FieldShell>
            <FieldShell label="Top K">
              <TextInput
                value={value.topK}
                onChange={(event) => onChange((current) => ({ ...current, topK: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-top-k"
              />
            </FieldShell>
            <FieldShell label="超时秒数">
              <TextInput
                value={value.timeout}
                onChange={(event) => onChange((current) => ({ ...current, timeout: event.target.value }))}
                disabled={disabled}
                data-testid="settings-image-understanding-timeout"
              />
            </FieldShell>
          </div>
        </details>
      </div>
    </section>
  );
}
