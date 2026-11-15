/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API prefix; default `/api/v1`. May be absolute or relative. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
