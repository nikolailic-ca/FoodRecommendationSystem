/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the FoodRec FastAPI backend, e.g. http://127.0.0.1:8001 */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
