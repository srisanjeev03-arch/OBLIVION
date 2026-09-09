function readString(key: keyof ImportMetaEnv): string | undefined {
  const value: unknown = (import.meta.env as Record<string, unknown>)[key]
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : undefined
}

function normaliseBaseUrl(url: string): string {
  return url.replace(/\/+$/, '')
}

const rawBase = readString('VITE_API_BASE_URL')

export const env = {
  apiBaseUrl: normaliseBaseUrl(rawBase ?? 'http://127.0.0.1:8000'),
  apiBaseUrlConfigured: rawBase !== undefined,
  apiHealthPath: readString('VITE_API_HEALTH_PATH'),
  mode: import.meta.env.MODE,
} as const
