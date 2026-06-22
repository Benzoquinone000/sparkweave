import { LayoutList, Loader2, RotateCcw, Save, SlidersHorizontal } from "lucide-react";
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

  const primaryPageCount = parseRouteList(startOrder).length;
  const toolPageCount = parseRouteList(learnOrder).length;
  const pageCount = primaryPageCount + toolPageCount;

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
          <p className="mt-1 text-sm leading-6 text-slate-600">先改主题、语言和工作台名称；导航顺序放在高级配置里。</p>
        </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone="neutral">{primaryPageCount} 个主入口</Badge>
            <Badge tone="neutral">{toolPageCount} 个工具</Badge>
          </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
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
            <FieldShell label="工作台名称">
              <TextArea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="min-h-20"
                placeholder="例如：AI 学习工作台"
              />
            </FieldShell>
          </div>
        </section>

        <section className="rounded-lg border border-line bg-white p-3">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={18} className="text-brand-purple" />
            <h3 className="font-semibold text-ink">保存当前偏好</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            保存后会立即应用到工作台；不确定时可以恢复默认界面。
          </p>
          <div className="mt-4 grid gap-2">
            <Button tone="primary" type="submit" disabled={pending} className="w-full">
              {pending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              保存偏好
            </Button>
            <Button tone="secondary" type="button" onClick={() => void onReset()} disabled={pending} className="w-full">
              {pending ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />}
              重置界面
            </Button>
          </div>
        </section>
      </div>

      <details className="mt-4 rounded-lg border border-line bg-canvas p-3 [&>summary::-webkit-details-marker]:hidden">
        <summary className="dt-interactive flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-1 py-1">
          <span>
            <span className="block text-sm font-semibold text-ink">高级导航配置</span>
            <span className="mt-1 block text-xs leading-5 text-slate-500">
              只在需要自定义入口顺序时打开；普通学习体验保持默认即可。
            </span>
          </span>
          <Badge tone="neutral">{pageCount} 个入口</Badge>
        </summary>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <FieldShell label="主入口">
            <TextArea
              value={startOrder}
              onChange={(event) => setStartOrder(event.target.value)}
              aria-label="主入口路径"
              className="min-h-40 font-mono text-xs"
            />
          </FieldShell>
          <FieldShell label="更多工具">
            <TextArea
              value={learnOrder}
              onChange={(event) => setLearnOrder(event.target.value)}
              aria-label="更多工具路径"
              className="min-h-40 font-mono text-xs"
            />
          </FieldShell>
        </div>
      </details>
    </form>
  );
}
