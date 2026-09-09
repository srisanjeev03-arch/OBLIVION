import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

/**
 * AI advisory preferences and inference configuration.
 * These are local UI/UX preferences only and NEVER serve as a security boundary.
 */

export type AIProvider = 'local-llama' | 'remote-fallback' | 'experimental'
export type AIInferenceMode = 'strict' | 'balanced' | 'aggressive'
export type AIProcessingLocation = 'local' | 'remote' | 'hybrid'

interface AIPreferencesState {
  enabled: boolean
  provider: AIProvider
  inferenceMode: AIInferenceMode
  processingLocation: AIProcessingLocation
  showTechnicalDetails: boolean
  setEnabled: (enabled: boolean) => void
  setProvider: (provider: AIProvider) => void
  setInferenceMode: (mode: AIInferenceMode) => void
  setProcessingLocation: (location: AIProcessingLocation) => void
  setShowTechnicalDetails: (show: boolean) => void
}

export const AI_STORAGE_KEY = 'oblivion.ai.preferences.v1'

export const useAIPreferences = create<AIPreferencesState>()(
  persist(
    (set) => ({
      enabled: true,
      provider: 'local-llama',
      inferenceMode: 'balanced',
      processingLocation: 'local',
      showTechnicalDetails: false,
      setEnabled: (enabled) => set({ enabled }),
      setProvider: (provider) => set({ provider }),
      setInferenceMode: (inferenceMode) => set({ inferenceMode }),
      setProcessingLocation: (processingLocation) => set({ processingLocation }),
      setShowTechnicalDetails: (showTechnicalDetails) => set({ showTechnicalDetails }),
    }),
    {
      name: AI_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        enabled: s.enabled,
        provider: s.provider,
        inferenceMode: s.inferenceMode,
        processingLocation: s.processingLocation,
        showTechnicalDetails: s.showTechnicalDetails,
      }),
    },
  ),
)
