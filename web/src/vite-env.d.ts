/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly NEXT_PUBLIC_API_BASE?: string;
  readonly NEXT_PUBLIC_API_BASE_EXTERNAL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  __SPARKWEAVE_RUNTIME_CONFIG__?: {
    apiBase?: string;
  };
}

