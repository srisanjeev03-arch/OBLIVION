import { create } from 'zustand'
import type { ConnectionState } from '@/lib/status'
import type { ApiErrorKind } from './errors'

/**
 * Passive backend connection tracker. The API contract has no health endpoint, so the state is
 * derived from real request outcomes (and an optional health probe when VITE_API_HEALTH_PATH is
 * set). Nothing here is persisted.
 */

export interface ConnectionError {
  kind: ApiErrorKind
  code: string
  status?: number
}

interface ConnectionStore {
  state: ConnectionState
  lastCheckedAt: string | null
  lastError: ConnectionError | null
  source: 'request' | 'probe' | null
  reportSuccess: (source: 'request' | 'probe') => void
  reportFailure: (source: 'request' | 'probe', error: ConnectionError) => void
  reset: () => void
}

export const useConnection = create<ConnectionStore>()((set) => ({
  state: 'UNKNOWN',
  lastCheckedAt: null,
  lastError: null,
  source: null,
  reportSuccess: (source) =>
    set({ state: 'CONNECTED', lastCheckedAt: new Date().toISOString(), lastError: null, source }),
  reportFailure: (source, error) =>
    set({
      state: error.kind === 'network' || error.kind === 'timeout' ? 'UNREACHABLE' : 'ERROR',
      lastCheckedAt: new Date().toISOString(),
      lastError: error,
      source,
    }),
  reset: () => set({ state: 'UNKNOWN', lastCheckedAt: null, lastError: null, source: null }),
}))
