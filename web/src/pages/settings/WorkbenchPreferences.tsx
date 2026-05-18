import { LayoutList, Loader2, RotateCcw, Save } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FieldShell, SelectInput, TextArea } from "@/components/ui/Field";
import type { SettingsResponse, SidebarSettings, ThemeOption } from "@/lib/types";
import { fallbackThemes, formatRouteList, normalizeNavOrder, parseRouteList } from "./settingsPreferenceUtils";

type WorkbenchPreferenceInput = {
  theme: SettingsResponse["ui"]["theme"];
  language: SettingsResponse["ui"]["language"];
  description: string;
  navOrder: SidebarSettings["nav_order"];
};

export function WorkbenchPreferences({
  settings,
  themes,
  sidebar,
  pending,
  onSave,
  onReset,
}: {
  settings: SettingsResponse;
  themes: ThemeOption[];
  sidebar?: SidebarSettings;
  pending: boolean;
  onSave: (input: WorkbenchPreferenceInput) => Promise<void>;
  onReset: () => Promise<void>;
}) {
  const currentNavOrder = useMemo(
    () => sidebar?.nav_order || normalizeNavOrder(settings.ui.sidebar_nav_order),
    [settings.ui.sidebar_nav_order, sidebar?.nav_order],
  );
  const [theme, setTheme] = useState(settings.ui.theme);
  const [language, setLanguage] = useState(settings.ui.language);
  const [description, setDescription] = useState(sidebar?.description || settings.ui.sidebar_description || "");
  const [startOrder, setStartOrder] = useState(formatRouteList(currentNavOrder.start));
  const [learnOrder, setLearnOrder] = useState(formatRouteList(currentNavOrder.learnResearch));

  const pageCount = parseRouteList(startOrder).length + parseRouteList(learnOrder).length;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSave({
      theme,
      language,
      description,
      navOrder: {
        start: parseRouteList(startOrder),
        learnResearch: parseRouteList(learnOrder),
      },
    });
  };

  return (
    <form className="rounded-lg border border-line bg-white p-3" onSubmit={submit}>
      <div
        className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-tint-sky px-3 py-3"
        data-testid="settings-preferences-toggle"
      >
        <div>
          <div className="flex items-center gap-2">
            <LayoutList size={18} className="text-brand-blue" />
            <h2 className="text-base font-semibold text-ink">工作台偏好</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-600">语言、主题和侧栏顺序，演示前再调整。</p>
        </div>
        <Badge tone="neutral">{pageCount} 个页面</Badge>
      </div>

      <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-line pt-4">
        <Button tone="secondary" type="button" onClick={() => void onReset()} disabled={pending}>
          {pending ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />}
          重置界面
        </Button>
        <Button tone="primary" type="submit" disabled={pending}>
          {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          保存偏好
        </Button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <section className="rounded-lg border border-line bg-canvas p-3">
          <h3 className="font-semibold text-ink">界面基调</h3>
          <div className="mt-4 grid gap-4">
            <FieldShell label="主题">
              <SelectInput value={theme} onChange={(event) => setTheme(event.target.value as SettingsResponse["ui"]["theme"])}>
                {(themes.length ? themes : fallbackThemes()).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </SelectInput>
            </FieldShell>
            <FieldShell label="语言">
              <SelectInput value={language} onChange={(event) => setLanguage(event.target.value as SettingsResponse["ui"]["language"])}>
                <option value="zh">中文</option>
                <option value="en">English</option>
              </SelectInput>
            </FieldShell>
            <FieldShell label="侧栏宣言">
              <TextArea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="min-h-24"
                placeholder="例如：AI 学习工作台"
              />
            </FieldShell>
          </div>
        </section>

        <section className="rounded-lg border border-line bg-canvas p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold text-ink">侧栏导航顺序</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">每行一个页面路径，保存后立即生效。</p>
            </div>
            <Badge tone="neutral">{pageCount} 个页面</Badge>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <FieldShell label="顶部常用区">
              <TextArea
                value={startOrder}
                onChange={(event) => setStartOrder(event.target.value)}
                aria-label="Start 区域"
                className="min-h-48 font-mono text-xs"
              />
            </FieldShell>
            <FieldShell label="学习研究区">
              <TextArea
                value={learnOrder}
                onChange={(event) => setLearnOrder(event.target.value)}
                aria-label="Learn / Research 区域"
                className="min-h-48 font-mono text-xs"
              />
            </FieldShell>
          </div>
        </section>
      </div>
    </form>
  );
}
