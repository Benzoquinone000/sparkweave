import type { SettingsResponse, SidebarSettings, ThemeOption } from "@/lib/types";

export function normalizeNavOrder(
  value: SettingsResponse["ui"]["sidebar_nav_order"] | undefined,
): SidebarSettings["nav_order"] {
  return {
    start: Array.isArray(value?.start) ? value.start : ["/guide", "/knowledge", "/notebook", "/settings"],
    learnResearch: Array.isArray(value?.learnResearch)
      ? value.learnResearch
      : ["/chat", "/question", "/memory", "/agents", "/co-writer", "/vision", "/playground"],
  };
}

export function settingsPreferenceKey(settings: SettingsResponse, sidebar: SidebarSettings | undefined) {
  return JSON.stringify({
    theme: settings.ui.theme,
    language: settings.ui.language,
    description: sidebar?.description || settings.ui.sidebar_description || "",
    nav_order: sidebar?.nav_order || settings.ui.sidebar_nav_order,
  });
}

export function formatRouteList(routes: string[] | undefined) {
  return (routes ?? []).join("\n");
}

export function parseRouteList(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((route) => route.trim())
    .filter(Boolean);
}

export function fallbackThemes(): ThemeOption[] {
  return [
    { id: "snow", name: "Snow" },
    { id: "light", name: "Light" },
    { id: "dark", name: "Dark" },
    { id: "glass", name: "Glass" },
  ];
}
