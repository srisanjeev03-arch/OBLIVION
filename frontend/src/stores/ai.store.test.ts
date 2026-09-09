import { describe, it, expect, beforeEach } from 'vitest'
import { useAIPreferences, AI_STORAGE_KEY } from './ai.store'

describe('useAIPreferences store', () => {
  beforeEach(() => {
    localStorage.clear()
    // reset store to defaults by setting to defaults
    useAIPreferences.setState({
      enabled: true,
      provider: 'local-llama',
      inferenceMode: 'balanced',
      processingLocation: 'local',
      showTechnicalDetails: false,
    })
  })

  it('has expected default state', () => {
    const state = useAIPreferences.getState()
    expect(state.enabled).toBe(true)
    expect(state.provider).toBe('local-llama')
    expect(state.inferenceMode).toBe('balanced')
    expect(state.processingLocation).toBe('local')
    expect(state.showTechnicalDetails).toBe(false)
  })

  it('updates enabled state', () => {
    useAIPreferences.getState().setEnabled(false)
    expect(useAIPreferences.getState().enabled).toBe(false)
  })

  it('updates provider', () => {
    useAIPreferences.getState().setProvider('experimental')
    expect(useAIPreferences.getState().provider).toBe('experimental')
  })

  it('updates inference mode', () => {
    useAIPreferences.getState().setInferenceMode('strict')
    expect(useAIPreferences.getState().inferenceMode).toBe('strict')
  })

  it('updates processing location', () => {
    useAIPreferences.getState().setProcessingLocation('remote')
    expect(useAIPreferences.getState().processingLocation).toBe('remote')
  })

  it('updates show technical details', () => {
    useAIPreferences.getState().setShowTechnicalDetails(true)
    expect(useAIPreferences.getState().showTechnicalDetails).toBe(true)
  })

  it('exposes a stable storage key constant', () => {
    expect(AI_STORAGE_KEY).toBe('oblivion.ai.preferences.v1')
  })
})
