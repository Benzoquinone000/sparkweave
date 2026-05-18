import type { Dispatch, SetStateAction } from "react";

import { Badge } from "@/components/ui/Badge";
import { FieldShell, TextInput } from "@/components/ui/Field";
import { effectiveSharedIflytekApiPassword, type SharedCredentialsForm } from "./settingsCatalogUtils";

export function SharedCredentialsBlock({
  value,
  onChange,
}: {
  value: SharedCredentialsForm;
  onChange: Dispatch<SetStateAction<SharedCredentialsForm>>;
}) {
  return (
    <section className="mt-5 rounded-lg border border-line bg-canvas p-3" data-testid="settings-shared-credentials">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">供应商共享凭据</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            同一家供应商只维护一套密钥。讯飞服务共用 APPID / APIKey / APISecret，硅基流动共用 APIKey。
          </p>
        </div>
        <Badge tone="neutral">全站共用</Badge>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-line bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-ink">科大讯飞</h4>
            <span className="text-xs text-slate-500">问答、搜索、OCR、TTS、Embedding</span>
          </div>
          <div className="mt-3 grid gap-3">
            <FieldShell label="APPID">
              <TextInput
                value={value.iflytekAppId}
                onChange={(event) => onChange((current) => ({ ...current, iflytekAppId: event.target.value }))}
                data-testid="settings-shared-iflytek-appid"
              />
            </FieldShell>
            <FieldShell label="APIKey">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.iflytekApiKey}
                onChange={(event) => onChange((current) => ({ ...current, iflytekApiKey: event.target.value }))}
                data-testid="settings-shared-iflytek-api-key"
              />
            </FieldShell>
            <FieldShell label="APISecret">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.iflytekApiSecret}
                onChange={(event) => onChange((current) => ({ ...current, iflytekApiSecret: event.target.value }))}
                data-testid="settings-shared-iflytek-api-secret"
              />
            </FieldShell>
            <FieldShell label="APIPassword" hint="当前生效值；未单独填写时显示 APIKey:APISecret。">
              <TextInput
                type="password"
                autoComplete="off"
                value={effectiveSharedIflytekApiPassword(value)}
                onChange={(event) => onChange((current) => ({ ...current, iflytekApiPassword: event.target.value }))}
                data-testid="settings-shared-iflytek-api-password"
              />
            </FieldShell>
          </div>
        </div>
        <div className="rounded-lg border border-line bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-ink">硅基流动</h4>
            <span className="text-xs text-slate-500">LLM、Embedding、DeepSeek-OCR</span>
          </div>
          <div className="mt-3 grid gap-3">
            <FieldShell label="APIKey">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.siliconflowApiKey}
                onChange={(event) => onChange((current) => ({ ...current, siliconflowApiKey: event.target.value }))}
                data-testid="settings-shared-siliconflow-api-key"
              />
            </FieldShell>
            <p className="rounded-lg bg-tint-sky px-3 py-2 text-xs leading-5 text-slate-600">
              如果模型、向量或 OCR 的服务地址包含 siliconflow，会自动使用这里的 APIKey。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
