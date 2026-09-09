import { useState } from 'react'
import {
  Settings as SettingsIcon,
  Palette,
  Shield,
  Wifi,
  RefreshCw,
  Check,
  Moon,
  Sun,
  Monitor,
  Sparkles,
} from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Switch } from '@/components/ui/Switch'
import { StatusBadge } from '@/components/status/StatusBadge'
import { usePrefs, type ThemeMode, type Density, type Corner, type Motion } from '@/lib/prefs'
import { CURATED_PRESETS, SINGLE_ACCENTS, type PresetId, type SingleAccentId } from '@/lib/themes'
import { useConnection } from '@/lib/api/connection'
import { useAIPreferences } from '@/stores/ai.store'
import { env } from '@/lib/env'
import { cn } from '@/lib/cn'

export function Settings() {
  const {
    theme,
    presetId,
    singleAccent,
    accentMode,
    density,
    corner,
    motion,
    setTheme,
    setPreset,
    setSingleAccent,
    setAccentMode,
    setDensity,
    setCorner,
    setMotion,
  } = usePrefs()

  const connection = useConnection()
  const ai = useAIPreferences()

  const [requireExplicitPhrases, setRequireExplicitPhrases] = useState(true)
  const [auditClientTelemetry, setAuditClientTelemetry] = useState(true)
  const [apiUrl, setApiUrl] = useState(env.apiBaseUrl)
  const [savedFeedback, setSavedFeedback] = useState(false)

  const handleSaveSettings = () => {
    setSavedFeedback(true)
    setTimeout(() => setSavedFeedback(false), 2000)
  }

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Settings & Governance Controls"
        icon={<SettingsIcon className="h-4 w-4" />}
        description="Configure operator interface ergonomics, curated forensic color presets, and backend connectivity."
        actions={
          <Button
            variant="primary"
            size="sm"
            leadingIcon={savedFeedback ? <Check className="h-3.5 w-3.5" /> : undefined}
            onClick={handleSaveSettings}
          >
            {savedFeedback ? 'Preferences Saved' : 'Save Preferences'}
          </Button>
        }
      />

      <div className="flex-1 p-6 space-y-6 max-w-5xl mx-auto w-full">
        {/* Section 1: Curated Theme & Accent Presets */}
        <div className="rounded-md border border-line bg-surface p-5 space-y-5">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <Palette className="h-4 w-4 text-accent" />
              <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
                Theme Presets & Palette Architecture
              </h3>
            </div>

            {/* Mode Switcher */}
            <div className="inline-flex items-center gap-1 rounded-sm border border-line bg-inset p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setAccentMode('preset')}
                className={cn(
                  'px-2.5 py-1 rounded-xs font-medium transition-colors',
                  accentMode === 'preset'
                    ? 'bg-elevated text-fg font-semibold shadow-xs'
                    : 'text-dim hover:text-fg',
                )}
              >
                Curated Presets (9)
              </button>
              <button
                type="button"
                onClick={() => setAccentMode('single')}
                className={cn(
                  'px-2.5 py-1 rounded-xs font-medium transition-colors',
                  accentMode === 'single'
                    ? 'bg-elevated text-fg font-semibold shadow-xs'
                    : 'text-dim hover:text-fg',
                )}
              >
                Single Accent (11)
              </button>
            </div>
          </div>

          {/* Curated Presets Grid */}
          {accentMode === 'preset' && (
            <div className="space-y-3">
              <div className="text-[0.6875rem] text-dim">
                Curated multi-color forensic presets with coordinated primary, secondary, and
                supporting accents. Background remains pure black (
                <code className="font-mono">#000000</code>).
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                {(Object.keys(CURATED_PRESETS) as PresetId[]).map((pid) => {
                  const p = CURATED_PRESETS[pid]
                  const isSelected = presetId === pid
                  const pCol = SINGLE_ACCENTS[p.primary]
                  const sCol = SINGLE_ACCENTS[p.secondary]
                  const supCol = SINGLE_ACCENTS[p.supporting]

                  return (
                    <button
                      key={pid}
                      type="button"
                      onClick={() => setPreset(pid)}
                      className={cn(
                        'flex flex-col text-left p-3 rounded-md border transition-all space-y-2',
                        isSelected
                          ? 'border-accent bg-accent-soft text-fg ring-1 ring-accent/30'
                          : 'border-line bg-elevated/40 hover:bg-elevated hover:border-line-strong text-dim',
                      )}
                    >
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-xs text-fg">{p.name}</span>
                          <span className="text-[0.625rem] text-mute font-mono">
                            / {p.subtitle}
                          </span>
                        </div>
                        {isSelected && <Check className="h-3.5 w-3.5 text-accent shrink-0" />}
                      </div>

                      <p className="text-[0.6875rem] text-dim leading-snug line-clamp-2">
                        {p.description}
                      </p>

                      {/* 3-Dot Color Swatch Preview */}
                      <div className="flex items-center gap-3 pt-1 border-t border-line/40 text-[0.625rem] font-mono">
                        <div className="flex items-center gap-1">
                          <span
                            className="h-2 w-2 rounded-full shrink-0"
                            style={{ backgroundColor: pCol.hex }}
                          />
                          <span className="text-dim">{pCol.name.split(' ')[1] || pCol.name}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span
                            className="h-2 w-2 rounded-full shrink-0"
                            style={{ backgroundColor: sCol.hex }}
                          />
                          <span className="text-dim">{sCol.name.split(' ')[1] || sCol.name}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span
                            className="h-2 w-2 rounded-full shrink-0"
                            style={{ backgroundColor: supCol.hex }}
                          />
                          <span className="text-dim">
                            {supCol.name.split(' ')[1] || supCol.name}
                          </span>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Single Accent Swatches */}
          {accentMode === 'single' && (
            <div className="space-y-3">
              <div className="text-[0.6875rem] text-dim">
                Select a single uniform accent. The system automatically computes hover, active,
                soft, and focus variants with verified accessible contrast.
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
                {(Object.keys(SINGLE_ACCENTS) as SingleAccentId[]).map((aid) => {
                  const acc = SINGLE_ACCENTS[aid]
                  const isSelected = singleAccent === aid

                  return (
                    <button
                      key={aid}
                      type="button"
                      onClick={() => setSingleAccent(aid)}
                      className={cn(
                        'flex items-center gap-2.5 p-2.5 rounded-md border text-left transition-all',
                        isSelected
                          ? 'border-accent bg-accent-soft text-fg ring-1 ring-accent/30'
                          : 'border-line bg-elevated/40 hover:bg-elevated hover:border-line-strong text-dim',
                      )}
                    >
                      <span
                        className="h-4 w-4 rounded-full border border-white/20 shrink-0"
                        style={{ backgroundColor: acc.hex }}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-xs text-fg truncate">{acc.name}</div>
                        <div className="text-[0.625rem] text-mute font-mono">{acc.hex}</div>
                      </div>
                      {isSelected && <Check className="h-3.5 w-3.5 text-accent shrink-0" />}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Color Scheme & Ergonomics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-3 border-t border-line text-xs">
            {/* Theme Mode */}
            <div className="space-y-1.5">
              <span className="text-dim text-[0.6875rem] uppercase font-medium block">
                Ground Canvas Mode
              </span>
              <div className="grid grid-cols-3 gap-1">
                {(['dark', 'light', 'system'] as ThemeMode[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setTheme(m)}
                    className={cn(
                      'flex items-center justify-center gap-1 h-7 rounded-sm border text-xs capitalize transition-colors',
                      theme === m
                        ? 'border-accent bg-accent-soft text-accent font-semibold'
                        : 'border-line bg-inset text-dim hover:text-fg',
                    )}
                  >
                    {m === 'dark' && <Moon className="h-3 w-3" />}
                    {m === 'light' && <Sun className="h-3 w-3" />}
                    {m === 'system' && <Monitor className="h-3 w-3" />}
                    <span>{m}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Layout Density */}
            <div className="space-y-1.5">
              <Select<Density>
                label="Information Density"
                value={density}
                onChange={(val) => setDensity(val)}
                options={[
                  { value: 'compact', label: 'Compact (High-Density TUI)' },
                  { value: 'standard', label: 'Standard (Balanced Console)' },
                  { value: 'comfortable', label: 'Comfortable (Spacious View)' },
                ]}
                size="sm"
              />
            </div>

            {/* Corner Radius */}
            <div className="space-y-1.5">
              <Select<Corner>
                label="Corner Radius"
                value={corner}
                onChange={(val) => setCorner(val)}
                options={[
                  { value: 'sharp', label: 'Sharp (Technical Console)' },
                  { value: 'balanced', label: 'Balanced (5px Radius)' },
                  { value: 'soft', label: 'Soft (8px Radius)' },
                ]}
                size="sm"
              />
            </div>

            {/* Motion Behavior */}
            <div className="space-y-1.5">
              <Select<Motion>
                label="Motion Behavior"
                value={motion}
                onChange={(val) => setMotion(val)}
                options={[
                  { value: 'full', label: 'Full (120ms transitions)' },
                  { value: 'minimal', label: 'Minimal (Zero motion)' },
                ]}
                size="sm"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Safety & Destruction Guardrails */}
        <div className="rounded-md border border-line bg-surface p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-line pb-3">
            <Shield className="h-4 w-4 text-warning" />
            <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
              Safety Guardrails & Governance
            </h3>
          </div>

          <div className="space-y-3">
            <Switch
              checked={requireExplicitPhrases}
              onCheckedChange={setRequireExplicitPhrases}
              label="Enforce Mandatory High-Consequence Scope Acknowledgment"
              description="Requires operators to explicitly review file count and byte size before authorizing erasure."
            />

            <Switch
              checked={auditClientTelemetry}
              onCheckedChange={setAuditClientTelemetry}
              label="Capture Local Client Audit Timestamps"
              description="Correlates operator UI interactions with backend cryptographic evidence records."
            />
          </div>
        </div>

        {/* Section 3: Daemon Connectivity & Diagnostic Probes */}
        <div className="rounded-md border border-line bg-surface p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <Wifi className="h-4 w-4 text-accent" />
              <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
                Backend Daemon Connectivity
              </h3>
            </div>
            <StatusBadge kind="connection" value={connection.state} />
          </div>

          <div className="space-y-3 text-xs">
            <div className="space-y-1">
              <span className="text-dim text-[0.6875rem] uppercase font-medium block">
                Authoritative API Endpoint (VITE_API_BASE_URL)
              </span>
              <div className="flex gap-2">
                <Input
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  className="font-mono text-xs flex-1"
                />
                <Button
                  variant="outline"
                  size="md"
                  leadingIcon={<RefreshCw className="h-3.5 w-3.5" />}
                  onClick={() => window.location.reload()}
                >
                  Test Probe
                </Button>
              </div>
            </div>

            <p className="text-[0.6875rem] text-dim leading-relaxed">
              Oblivion frontend communicates exclusively via standard HTTP/JSON contracts. Direct
              filesystem access, shell subprocess execution, and private cryptographic key handling
              are strictly forbidden in browser code.
            </p>
          </div>
        </div>

        {/* Section 4: AI Intelligence Configuration */}
        <div className="rounded-md border border-line bg-surface p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-line pb-3">
            <Sparkles className="h-4 w-4 text-accent" />
            <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
              AI Intelligence Layer
            </h3>
          </div>

          <div className="space-y-3">
            <Switch
              checked={ai.enabled}
              onCheckedChange={ai.setEnabled}
              label="Enable AI Intelligence Layer"
              description="When enabled, AI advisory panels will appear in supported views. This does not affect backend operations."
            />

            <div className="rounded-sm border border-line bg-elevated/40 p-3 space-y-3 text-xs">
              <div className="font-semibold text-fg">AI Provider</div>
              <Select
                label="AI Provider"
                hideLabel
                value={ai.provider}
                onChange={(val) => ai.setProvider(val)}
                options={[
                  { value: 'local-llama', label: 'Local LLaMA (Privacy-Preserving)' },
                  { value: 'remote-fallback', label: 'Remote Fallback' },
                  { value: 'experimental', label: 'Experimental' },
                ]}
              />
            </div>

            <div className="rounded-sm border border-line bg-elevated/40 p-3 space-y-3 text-xs">
              <div className="font-semibold text-fg">Inference Mode</div>
              <Select
                label="Inference Mode"
                hideLabel
                value={ai.inferenceMode}
                onChange={(val) => ai.setInferenceMode(val)}
                options={[
                  { value: 'strict', label: 'Strict (Conservative / Low Risk)' },
                  { value: 'balanced', label: 'Balanced (Default)' },
                  { value: 'aggressive', label: 'Aggressive (Maximum Coverage)' },
                ]}
              />
            </div>

            <div className="rounded-sm border border-line bg-elevated/40 p-3 space-y-3 text-xs">
              <div className="font-semibold text-fg">Processing Location</div>
              <Select
                label="Processing Location"
                hideLabel
                value={ai.processingLocation}
                onChange={(val) => ai.setProcessingLocation(val)}
                options={[
                  { value: 'local', label: 'Local Only (Maximum Privacy)' },
                  { value: 'remote', label: 'Remote (Higher Capability)' },
                  { value: 'hybrid', label: 'Hybrid (Best Available)' },
                ]}
              />
            </div>

            <Switch
              checked={ai.showTechnicalDetails}
              onCheckedChange={ai.setShowTechnicalDetails}
              label="Show Technical AI Explanations"
              description="Display reasoning factors, evidence used, and model information in AI panels."
            />
          </div>
        </div>
      </div>
    </div>
  )
}
