/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_SPARKWEAVE_API_KEY?: string;
  readonly NEXT_PUBLIC_API_BASE?: string;
  readonly NEXT_PUBLIC_API_BASE_EXTERNAL?: string;
  readonly NEXT_PUBLIC_SPARKWEAVE_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  __SPARKWEAVE_RUNTIME_CONFIG__?: {
    apiBase?: string;
    apiKey?: string;
  };
}

