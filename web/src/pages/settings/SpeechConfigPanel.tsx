import type { Dispatch, SetStateAction } from "react";

import { FieldShell, SelectInput, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";
import { ConfigBlock, ProviderQuickNote, ProviderSelect } from "./SettingsConfigControls";
import type { SpeechForm } from "./settingsCatalogUtils";

type FormSetter<T> = Dispatch<SetStateAction<T>>;

export function SpeechConfigPanel({
  value,
  ttsProviders = fallbackSpeechProviders("tts"),
  asrProviders = fallbackSpeechProviders("asr"),
  speechEvalProviders = fallbackSpeechProviders("speech_eval"),
  onChange,
}: {
  value: SpeechForm;
  ttsProviders?: ProviderChoice[];
  asrProviders?: ProviderChoice[];
  speechEvalProviders?: ProviderChoice[];
  onChange: FormSetter<SpeechForm>;
}) {
  const activeTtsProvider = ttsProviders.find((provider) => provider.value === value.ttsProvider);
  const activeAsrProvider = asrProviders.find((provider) => provider.value === value.asrProvider);
  const activeSpeechEvalProvider = speechEvalProviders.find((provider) => provider.value === value.speechEvalProvider);

  return (
    <ConfigBlock
      title="语音学习"
      summary="用于语音讲解、聊天语音输入、口语表达训练和学习效果记录采集。服务密钥统一使用上方的科大讯飞配置。"
    >
      <div className="grid gap-4 xl:grid-cols-3">
        <section className="rounded-lg border border-line bg-canvas p-3">
          <h4 className="text-sm font-semibold text-ink">语音讲解</h4>
          <p className="mt-1 text-xs leading-5 text-steel">把学习资源和讲解稿生成自然语音。</p>
          <div className="mt-3 grid gap-3">
            <ProviderSelect
              label="服务提供方"
              value={value.ttsProvider}
              providers={ttsProviders}
              testId="settings-tts-provider"
              onChange={(providerValue, provider) =>
                onChange((current) => ({
                  ...current,
                  ttsProvider: providerValue,
                  ttsBaseUrl: provider?.base_url ?? current.ttsBaseUrl,
                }))
              }
            />
            <ProviderQuickNote provider={activeTtsProvider} />
            <FieldShell label="服务地址">
              <TextInput
                value={value.ttsBaseUrl}
                onChange={(event) => onChange((current) => ({ ...current, ttsBaseUrl: event.target.value }))}
                disabled={value.ttsProvider === "disabled"}
                data-testid="settings-tts-base-url"
              />
            </FieldShell>
            <FieldShell label="默认音色">
              <SelectInput
                value={value.ttsVoice}
                onChange={(event) => onChange((current) => ({ ...current, ttsVoice: event.target.value }))}
                disabled={value.ttsProvider === "disabled"}
                data-testid="settings-tts-voice"
              >
                <option value="x5_lingxiaoxuan_flow">聆小璇</option>
                <option value="x5_lingxiaoyan_flow">聆小燕</option>
                <option value="x5_lingxiaofeng_flow">聆小峰</option>
                <option value="x5_lingxiaojing_flow">聆小静</option>
              </SelectInput>
            </FieldShell>
          </div>
        </section>

        <section className="rounded-lg border border-line bg-canvas p-3">
          <h4 className="text-sm font-semibold text-ink">语音输入</h4>
          <p className="mt-1 text-xs leading-5 text-steel">把录音转成文字，用在聊天提问和学习记录中。</p>
          <div className="mt-3 grid gap-3">
            <ProviderSelect
              label="服务提供方"
              value={value.asrProvider}
              providers={asrProviders}
              testId="settings-asr-provider"
              onChange={(providerValue, provider) =>
                onChange((current) => ({
                  ...current,
                  asrProvider: providerValue,
                  asrBaseUrl: provider?.base_url ?? current.asrBaseUrl,
                }))
              }
            />
            <ProviderQuickNote provider={activeAsrProvider} />
            <FieldShell label="服务地址">
              <TextInput
                value={value.asrBaseUrl}
                onChange={(event) => onChange((current) => ({ ...current, asrBaseUrl: event.target.value }))}
                disabled={value.asrProvider === "disabled"}
                data-testid="settings-asr-base-url"
              />
            </FieldShell>
          </div>
        </section>

        <section className="rounded-lg border border-line bg-canvas p-3">
          <h4 className="text-sm font-semibold text-ink">口语评测</h4>
          <p className="mt-1 text-xs leading-5 text-steel">评估跟读、表达和任务复述，写入学习效果闭环。</p>
          <div className="mt-3 grid gap-3">
            <ProviderSelect
              label="服务提供方"
              value={value.speechEvalProvider}
              providers={speechEvalProviders}
              testId="settings-speech-eval-provider"
              onChange={(providerValue, provider) =>
                onChange((current) => ({
                  ...current,
                  speechEvalProvider: providerValue,
                  speechEvalBaseUrl: provider?.base_url ?? current.speechEvalBaseUrl,
                }))
              }
            />
            <ProviderQuickNote provider={activeSpeechEvalProvider} />
            <FieldShell label="服务地址">
              <TextInput
                value={value.speechEvalBaseUrl}
                onChange={(event) =>
                  onChange((current) => ({ ...current, speechEvalBaseUrl: event.target.value }))
                }
                disabled={value.speechEvalProvider === "disabled"}
                data-testid="settings-speech-eval-base-url"
              />
            </FieldShell>
          </div>
        </section>
      </div>

      <details className="rounded-lg border border-line bg-canvas p-3">
        <summary className="cursor-pointer select-none text-sm font-semibold text-ink">
          少用设置，通常不用改
        </summary>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          默认适配普通话学习场景。语音服务会优先使用上方共享讯飞密钥；如果某个产品开在单独应用下，可在这里覆盖。
        </p>
        <div className="mt-3 rounded-lg border border-line bg-white/70 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h5 className="text-xs font-semibold text-ink">独立语音密钥</h5>
            <span className="text-xs text-slate-500">留空即使用共享讯飞密钥</span>
          </div>
          <div className="mt-3 grid gap-3 lg:grid-cols-3">
            <SpeechCredentialFields
              title="语音讲解"
              disabled={value.ttsProvider === "disabled"}
              appId={value.ttsAppId}
              apiKey={value.ttsApiKey}
              apiSecret={value.ttsApiSecret}
              testIdPrefix="settings-tts"
              onChange={(patch) => onChange((current) => ({ ...current, ...patch }))}
              appIdKey="ttsAppId"
              apiKeyKey="ttsApiKey"
              apiSecretKey="ttsApiSecret"
            />
            <SpeechCredentialFields
              title="语音输入"
              disabled={value.asrProvider === "disabled"}
              appId={value.asrAppId}
              apiKey={value.asrApiKey}
              apiSecret={value.asrApiSecret}
              testIdPrefix="settings-asr"
              onChange={(patch) => onChange((current) => ({ ...current, ...patch }))}
              appIdKey="asrAppId"
              apiKeyKey="asrApiKey"
              apiSecretKey="asrApiSecret"
            />
            <SpeechCredentialFields
              title="口语评测"
              disabled={value.speechEvalProvider === "disabled"}
              appId={value.speechEvalAppId}
              apiKey={value.speechEvalApiKey}
              apiSecret={value.speechEvalApiSecret}
              testIdPrefix="settings-speech-eval"
              onChange={(patch) => onChange((current) => ({ ...current, ...patch }))}
              appIdKey="speechEvalAppId"
              apiKeyKey="speechEvalApiKey"
              apiSecretKey="speechEvalApiSecret"
            />
          </div>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <FieldShell label="讲解音频编码">
            <SelectInput
              value={value.ttsEncoding}
              onChange={(event) => onChange((current) => ({ ...current, ttsEncoding: event.target.value }))}
              disabled={value.ttsProvider === "disabled"}
              data-testid="settings-tts-encoding"
            >
              <option value="lame">MP3</option>
              <option value="raw">PCM</option>
            </SelectInput>
          </FieldShell>
          <FieldShell label="讲解采样率">
            <SelectInput
              value={value.ttsSampleRate}
              onChange={(event) => onChange((current) => ({ ...current, ttsSampleRate: event.target.value }))}
              disabled={value.ttsProvider === "disabled"}
              data-testid="settings-tts-sample-rate"
            >
              <option value="24000">24000 Hz</option>
              <option value="16000">16000 Hz</option>
              <option value="8000">8000 Hz</option>
            </SelectInput>
          </FieldShell>
          <SpeechNumberSlider
            label="讲解语速"
            value={value.ttsSpeed}
            disabled={value.ttsProvider === "disabled"}
            testId="settings-tts-speed"
            onChange={(next) => onChange((current) => ({ ...current, ttsSpeed: next }))}
          />
          <SpeechNumberSlider
            label="讲解音量"
            value={value.ttsVolume}
            disabled={value.ttsProvider === "disabled"}
            testId="settings-tts-volume"
            onChange={(next) => onChange((current) => ({ ...current, ttsVolume: next }))}
          />
          <SpeechNumberSlider
            label="讲解音高"
            value={value.ttsPitch}
            disabled={value.ttsProvider === "disabled"}
            testId="settings-tts-pitch"
            onChange={(next) => onChange((current) => ({ ...current, ttsPitch: next }))}
          />
          <FieldShell label="语音输入语言">
            <TextInput
              value={value.asrLanguage}
              onChange={(event) => onChange((current) => ({ ...current, asrLanguage: event.target.value }))}
              disabled={value.asrProvider === "disabled"}
              data-testid="settings-asr-language"
            />
          </FieldShell>
          <FieldShell label="语音输入口音">
            <TextInput
              value={value.asrAccent}
              onChange={(event) => onChange((current) => ({ ...current, asrAccent: event.target.value }))}
              disabled={value.asrProvider === "disabled"}
              data-testid="settings-asr-accent"
            />
          </FieldShell>
          <FieldShell label="听写领域">
            <TextInput
              value={value.asrDomain}
              onChange={(event) => onChange((current) => ({ ...current, asrDomain: event.target.value }))}
              disabled={value.asrProvider === "disabled"}
              data-testid="settings-asr-domain"
            />
          </FieldShell>
          <FieldShell label="静音断句毫秒">
            <TextInput
              value={value.asrVadEos}
              onChange={(event) => onChange((current) => ({ ...current, asrVadEos: event.target.value }))}
              disabled={value.asrProvider === "disabled"}
              data-testid="settings-asr-vad-eos"
            />
          </FieldShell>
          <FieldShell label="评测题型">
            <SelectInput
              value={value.speechEvalCategory}
              onChange={(event) =>
                onChange((current) => ({ ...current, speechEvalCategory: event.target.value }))
              }
              disabled={value.speechEvalProvider === "disabled"}
              data-testid="settings-speech-eval-category"
            >
              <option value="read_sentence">句子朗读</option>
              <option value="read_chapter">篇章朗读</option>
              <option value="read_word">词语朗读</option>
            </SelectInput>
          </FieldShell>
          <FieldShell label="评测语言">
            <TextInput
              value={value.speechEvalLanguage}
              onChange={(event) =>
                onChange((current) => ({ ...current, speechEvalLanguage: event.target.value }))
              }
              disabled={value.speechEvalProvider === "disabled"}
              data-testid="settings-speech-eval-language"
            />
          </FieldShell>
        </div>
      </details>
    </ConfigBlock>
  );
}

function SpeechCredentialFields({
  title,
  disabled,
  appId,
  apiKey,
  apiSecret,
  testIdPrefix,
  appIdKey,
  apiKeyKey,
  apiSecretKey,
  onChange,
}: {
  title: string;
  disabled: boolean;
  appId: string;
  apiKey: string;
  apiSecret: string;
  testIdPrefix: string;
  appIdKey: keyof SpeechForm;
  apiKeyKey: keyof SpeechForm;
  apiSecretKey: keyof SpeechForm;
  onChange: (patch: Partial<SpeechForm>) => void;
}) {
  return (
    <div className="grid gap-2">
      <h6 className="text-xs font-medium text-charcoal">{title}</h6>
      <FieldShell label="AppID">
        <TextInput
          value={appId}
          onChange={(event) => onChange({ [appIdKey]: event.target.value })}
          disabled={disabled}
          placeholder="共享密钥"
          autoComplete="off"
          data-testid={`${testIdPrefix}-app-id`}
        />
      </FieldShell>
      <FieldShell label="APIKey">
        <TextInput
          value={apiKey}
          onChange={(event) => onChange({ [apiKeyKey]: event.target.value })}
          disabled={disabled}
          placeholder="共享密钥"
          type="password"
          autoComplete="off"
          data-testid={`${testIdPrefix}-api-key`}
        />
      </FieldShell>
      <FieldShell label="APISecret">
        <TextInput
          value={apiSecret}
          onChange={(event) => onChange({ [apiSecretKey]: event.target.value })}
          disabled={disabled}
          placeholder="共享密钥"
          type="password"
          autoComplete="off"
          data-testid={`${testIdPrefix}-api-secret`}
        />
      </FieldShell>
    </div>
  );
}

function fallbackSpeechProviders(kind: "tts" | "asr" | "speech_eval"): ProviderChoice[] {
  if (kind === "tts") {
    return [
      {
        value: "iflytek",
        label: "讯飞超拟人合成",
        base_url: "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6",
      },
      { value: "disabled", label: "停用", base_url: "" },
    ];
  }
  if (kind === "asr") {
    return [
      {
        value: "iflytek",
        label: "讯飞语音听写",
        base_url: "wss://iat-api.xfyun.cn/v2/iat",
      },
      { value: "disabled", label: "停用", base_url: "" },
    ];
  }
  return [
    {
      value: "iflytek",
      label: "讯飞语音评测",
      base_url: "wss://ise-api.xfyun.cn/v2/open-ise",
    },
    { value: "disabled", label: "停用", base_url: "" },
  ];
}

function SpeechNumberSlider({
  label,
  value,
  disabled,
  testId,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
  testId: string;
  onChange: (value: string) => void;
}) {
  const numeric = clampSpeechNumber(value);
  return (
    <FieldShell label={label} hint={`${numeric}`}>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={numeric}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full accent-brand-purple disabled:opacity-60"
        data-testid={testId}
      />
    </FieldShell>
  );
}

function clampSpeechNumber(value: string) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return 50;
  return Math.max(0, Math.min(100, parsed));
}
