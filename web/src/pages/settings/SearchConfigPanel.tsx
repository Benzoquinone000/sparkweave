import type { Dispatch, SetStateAction } from "react";

import { FieldShell, TextInput } from "@/components/ui/Field";
import type { ProviderChoice } from "@/lib/types";
import { ConfigBlock, ProviderSelect } from "./SettingsConfigControls";
import type { SearchForm } from "./settingsCatalogUtils";

type FormSetter<T> = Dispatch<SetStateAction<T>>;

export function SearchConfigPanel({
  value,
  providers,
  onChange,
}: {
  value: SearchForm;
  providers: ProviderChoice[];
  onChange: FormSetter<SearchForm>;
}) {
  return (
    <ConfigBlock title="联网搜索" summary="用于补充外部资料、精选视频和实时信息。">
      <ProviderSelect
        label="服务提供方"
        value={value.provider}
        providers={providers}
        testId="settings-search-provider"
        onChange={(providerValue, provider) =>
          onChange((current) => ({ ...current, provider: providerValue, baseUrl: provider?.base_url ?? "" }))
        }
      />
      <FieldShell label="服务地址">
        <TextInput
          value={value.baseUrl}
          onChange={(event) => onChange((current) => ({ ...current, baseUrl: event.target.value }))}
          data-testid="settings-search-base-url"
        />
      </FieldShell>
      <FieldShell label="密钥" hint="当前生效的搜索服务密钥">
        <TextInput
          type="password"
          autoComplete="off"
          value={value.apiKey}
          onChange={(event) => onChange((current) => ({ ...current, apiKey: event.target.value }))}
          data-testid="settings-search-api-key"
        />
      </FieldShell>
    </ConfigBlock>
  );
}
