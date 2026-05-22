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
          <h3 className="font-semibold text-ink">服务密钥</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            同一家服务只维护一套密钥，问答、资料理解、搜索和图片文字识别会按需共用。
          </p>
        </div>
        <Badge tone="neutral">全站共用</Badge>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-line bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-ink">科大讯飞</h4>
            <span className="text-xs text-slate-500">问答、搜索、语音、资料理解、图片识别</span>
          </div>
          <div className="mt-3 grid gap-3">
            <FieldShell label="应用 ID">
              <TextInput
                value={value.iflytekAppId}
                onChange={(event) => onChange((current) => ({ ...current, iflytekAppId: event.target.value }))}
                data-testid="settings-shared-iflytek-appid"
              />
            </FieldShell>
            <FieldShell label="访问密钥">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.iflytekApiKey}
                onChange={(event) => onChange((current) => ({ ...current, iflytekApiKey: event.target.value }))}
                data-testid="settings-shared-iflytek-api-key"
              />
            </FieldShell>
            <FieldShell label="密钥 Secret">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.iflytekApiSecret}
                onChange={(event) => onChange((current) => ({ ...current, iflytekApiSecret: event.target.value }))}
                data-testid="settings-shared-iflytek-api-secret"
              />
            </FieldShell>
            <FieldShell label="连接密码" hint="当前生效值；未单独填写时显示访问密钥:Secret。">
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
            <span className="text-xs text-slate-500">问答模型、资料理解、DeepSeek 图片识别</span>
          </div>
          <div className="mt-3 grid gap-3">
            <FieldShell label="访问密钥">
              <TextInput
                type="password"
                autoComplete="off"
                value={value.siliconflowApiKey}
                onChange={(event) => onChange((current) => ({ ...current, siliconflowApiKey: event.target.value }))}
                data-testid="settings-shared-siliconflow-api-key"
              />
            </FieldShell>
            <p className="rounded-lg bg-tint-sky px-3 py-2 text-xs leading-5 text-slate-600">
              如果问答、资料理解或图片识别的服务地址包含 siliconflow，会自动使用这里的访问密钥。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
