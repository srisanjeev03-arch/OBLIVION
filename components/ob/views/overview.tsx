'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Plus,
  Pencil,
  Check,
  X,
  GripVertical,
  Maximize2,
  Trash2,
  RotateCcw,
  Search,
  Info,
  Copy,
} from 'lucide-react'
import { Page, PageHeader } from '../page'
import { Button, EmptyState } from '../primitives'
import { useShell } from '../shell-context'
import { cn } from '@/lib/utils'
import type { WidgetInstance, WidgetSize, Workspace } from '@/lib/types'
import {
  WIDGETS,
  WIDGET_LIST,
  DEFAULT_WORKSPACES,
  SIZE_COLS,
  SIZE_ORDER,
} from '@/lib/widgets'

const WS_KEY = 'oblivion.workspaces'
const WS_ACTIVE = 'oblivion.workspace.active'
const FIRST_RUN = 'oblivion.firstrun'

let uid = 0
const genId = () => `w${Date.now()}${uid++}`

function loadWorkspaces(): Workspace[] {
  try {
    const raw = localStorage.getItem(WS_KEY)
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return structuredClone(DEFAULT_WORKSPACES)
}

const PRESETS: { id: string; name: string; description: string; widgets: string[] }[] = [
  {
    id: 'guided',
    name: 'Guided',
    description: 'A simple, calm overview of what matters right now.',
    widgets: ['erasure-overview', 'active-operations', 'verification-status', 'recent-erasures'],
  },
  {
    id: 'operations',
    name: 'Operations',
    description: 'Active work, queue depth and worker health.',
    widgets: ['active-operations', 'queue-status', 'backend-health', 'failure-analysis', 'recent-erasures'],
  },
  {
    id: 'forensics',
    name: 'Forensics',
    description: 'Residuals, recovery, evidence and audit trail.',
    widgets: ['residual-classifications', 'recovery-operations', 'recent-certificates', 'sensitivity-overview', 'audit-activity'],
  },
  {
    id: 'advanced',
    name: 'Advanced',
    description: 'Maximum information density for expert operators.',
    widgets: [
      'erasure-overview', 'active-operations', 'verification-status', 'queue-status',
      'assurance-distribution', 'erasure-activity', 'backend-health', 'failure-analysis',
      'recent-certificates', 'audit-activity',
    ],
  },
]

export function OverviewView() {
  const { navigate, toast } = useShell()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activeId, setActiveId] = useState('overview')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<WidgetInstance[] | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [firstRun, setFirstRun] = useState(false)
  const dragIndex = useRef<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)

  useEffect(() => {
    setWorkspaces(loadWorkspaces())
    try {
      setActiveId(localStorage.getItem(WS_ACTIVE) || 'overview')
      if (!localStorage.getItem(FIRST_RUN)) setFirstRun(true)
    } catch {
      /* ignore */
    }
  }, [])

  const persist = (next: Workspace[]) => {
    setWorkspaces(next)
    try {
      localStorage.setItem(WS_KEY, JSON.stringify(next))
    } catch {
      /* ignore */
    }
  }

  const active = useMemo(
    () => workspaces.find((w) => w.id === activeId) ?? workspaces[0],
    [workspaces, activeId],
  )

  const widgets = editing && draft ? draft : (active?.widgets ?? [])

  const startEdit = () => {
    setDraft(structuredClone(active?.widgets ?? []))
    setEditing(true)
  }
  const cancelEdit = () => {
    setEditing(false)
    setDraft(null)
    setAddOpen(false)
  }
  const saveEdit = () => {
    if (!active || !draft) return
    persist(workspaces.map((w) => (w.id === active.id ? { ...w, widgets: draft } : w)))
    setEditing(false)
    setDraft(null)
    setAddOpen(false)
    toast({ title: 'Workspace saved', description: `“${active.name}” layout updated.`, tone: 'success' })
  }
  const resetWorkspace = () => {
    const def = DEFAULT_WORKSPACES.find((w) => w.id === active?.id)
    setDraft(structuredClone(def?.widgets ?? []))
  }

  const updateDraft = (fn: (d: WidgetInstance[]) => WidgetInstance[]) =>
    setDraft((d) => (d ? fn(d) : d))

  const addWidget = (type: string) => {
    const def = WIDGETS[type]
    updateDraft((d) => [...d, { id: genId(), type, size: def.defaultSize }])
    toast({ title: 'Widget added', description: def.title })
  }

  const switchWorkspace = (id: string) => {
    if (editing) return
    setActiveId(id)
    try {
      localStorage.setItem(WS_ACTIVE, id)
    } catch {
      /* ignore */
    }
  }

  const createWorkspace = () => {
    const id = `ws-${Date.now()}`
    const name = `Workspace ${workspaces.length + 1}`
    persist([...workspaces, { id, name, widgets: [] }])
    switchWorkspace(id)
    toast({ title: 'Workspace created', description: name })
  }

  const duplicateWorkspace = () => {
    if (!active) return
    const id = `ws-${Date.now()}`
    persist([...workspaces, { id, name: `${active.name} copy`, widgets: structuredClone(active.widgets) }])
    switchWorkspace(id)
  }

  const applyPreset = (widgetTypes: string[]) => {
    const ws: WidgetInstance[] = widgetTypes.map((t) => ({
      id: genId(),
      type: t,
      size: WIDGETS[t].defaultSize,
    }))
    persist(workspaces.map((w) => (w.id === 'overview' ? { ...w, widgets: ws } : w)))
    setActiveId('overview')
    dismissFirstRun()
  }
  const dismissFirstRun = () => {
    setFirstRun(false)
    try {
      localStorage.setItem(FIRST_RUN, '1')
    } catch {
      /* ignore */
    }
  }

  // drag reorder
  const onDrop = (index: number) => {
    const from = dragIndex.current
    if (from == null || from === index) {
      setOverIndex(null)
      return
    }
    updateDraft((d) => {
      const next = [...d]
      const [moved] = next.splice(from, 1)
      next.splice(index, 0, moved)
      return next
    })
    dragIndex.current = null
    setOverIndex(null)
  }

  if (!active) return null

  return (
    <Page className="max-w-none">
      <PageHeader
        title={active.name}
        description="Your configurable control room. Every widget is data-backed and reflects the current backend state."
        actions={
          editing ? (
            <>
              <Button variant="ghost" size="sm" onClick={resetWorkspace}>
                <RotateCcw className="h-3.5 w-3.5" /> Reset
              </Button>
              <Button variant="subtle" size="sm" onClick={() => setAddOpen(true)}>
                <Plus className="h-3.5 w-3.5" /> Add widget
              </Button>
              <Button variant="ghost" size="sm" onClick={cancelEdit}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={saveEdit}>
                <Check className="h-3.5 w-3.5" /> Save changes
              </Button>
            </>
          ) : (
            <>
              <Button variant="subtle" size="sm" onClick={() => navigate('workflow')}>
                <Plus className="h-3.5 w-3.5" /> New operation
              </Button>
              <Button variant="outline" size="sm" onClick={startEdit}>
                <Pencil className="h-3.5 w-3.5" /> Edit dashboard
              </Button>
            </>
          )
        }
      />

      {/* Workspace tabs */}
      <div className="mb-5 flex items-center gap-1 border-b border-line">
        {workspaces.map((w) => (
          <button
            key={w.id}
            onClick={() => switchWorkspace(w.id)}
            disabled={editing && w.id !== active.id}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-[0.8125rem] transition-colors disabled:opacity-40',
              w.id === active.id
                ? 'border-current text-fg'
                : 'border-transparent text-mute hover:text-dim',
            )}
            style={w.id === active.id ? { borderColor: 'var(--accent)' } : undefined}
          >
            {w.name}
          </button>
        ))}
        {!editing && (
          <div className="ml-1 flex items-center gap-0.5">
            <button
              onClick={createWorkspace}
              className="flex h-7 w-7 items-center justify-center rounded-md text-mute hover:bg-inset hover:text-fg"
              title="Create workspace"
            >
              <Plus className="h-4 w-4" />
            </button>
            <button
              onClick={duplicateWorkspace}
              className="flex h-7 w-7 items-center justify-center rounded-md text-mute hover:bg-inset hover:text-fg"
              title="Duplicate workspace"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {widgets.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line-strong">
          <EmptyState
            icon={Search}
            title="This workspace is empty"
            description="Add widgets to build a view tailored to how you work."
            action={
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  if (!editing) startEdit()
                  setAddOpen(true)
                }}
              >
                <Plus className="h-3.5 w-3.5" /> Add widget
              </Button>
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-12">
          {widgets.map((w, i) => {
            const def = WIDGETS[w.type]
            if (!def) return null
            return (
              <div
                key={w.id}
                className={cn(
                  'col-span-1 transition-all',
                  SIZE_COLS[w.size],
                  overIndex === i && editing && 'ring-2 ring-offset-0',
                )}
                style={overIndex === i && editing ? { boxShadow: '0 0 0 2px var(--accent)' } : undefined}
                draggable={editing}
                onDragStart={() => (dragIndex.current = i)}
                onDragOver={(e) => {
                  if (!editing) return
                  e.preventDefault()
                  setOverIndex(i)
                }}
                onDragLeave={() => setOverIndex((o) => (o === i ? null : o))}
                onDrop={() => onDrop(i)}
              >
                <WidgetFrame
                  def={def}
                  editing={editing}
                  size={w.size}
                  onResize={(s) =>
                    updateDraft((d) =>
                      d.map((x) => (x.id === w.id ? { ...x, size: s } : x)),
                    )
                  }
                  onRemove={() =>
                    updateDraft((d) => d.filter((x) => x.id !== w.id))
                  }
                />
              </div>
            )
          })}
        </div>
      )}

      {addOpen && (
        <AddWidgetSheet
          onClose={() => setAddOpen(false)}
          onAdd={addWidget}
          existing={widgets.map((w) => w.type)}
        />
      )}

      {firstRun && (
        <FirstRunDialog
          onPick={applyPreset}
          onSkip={dismissFirstRun}
        />
      )}
    </Page>
  )
}

function WidgetFrame({
  def,
  editing,
  size,
  onResize,
  onRemove,
}: {
  def: (typeof WIDGETS)[string]
  editing: boolean
  size: WidgetSize
  onResize: (s: WidgetSize) => void
  onRemove: () => void
}) {
  const [sizeMenu, setSizeMenu] = useState(false)
  return (
    <section
      className={cn(
        'flex h-full flex-col rounded-lg border bg-surface transition-colors',
        editing ? 'border-line-strong' : 'border-line',
      )}
    >
      <header className="flex items-center gap-2 px-3.5 pt-3 pb-2">
        {editing && (
          <GripVertical className="h-3.5 w-3.5 shrink-0 cursor-grab text-mute active:cursor-grabbing" />
        )}
        <h3 className="flex-1 truncate text-[0.8125rem] font-semibold text-fg">
          {def.title}
        </h3>
        {!editing && (
          <span className="group relative">
            <Info className="h-3.5 w-3.5 text-mute" />
            <span className="pointer-events-none absolute right-0 top-5 z-20 w-48 rounded-md border border-line-strong bg-elevated p-2 text-[0.6875rem] text-dim opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
              {def.description}
            </span>
          </span>
        )}
        {editing && (
          <div className="flex items-center gap-0.5">
            <div className="relative">
              <button
                onClick={() => setSizeMenu((s) => !s)}
                className="flex h-6 items-center gap-1 rounded border border-line px-1.5 text-[0.6875rem] text-dim hover:bg-inset"
                title="Resize widget"
              >
                <Maximize2 className="h-3 w-3" /> {size}
              </button>
              {sizeMenu && (
                <div className="animate-scale-in absolute right-0 top-7 z-30 flex flex-col rounded-md border border-line-strong bg-elevated p-1 shadow-lg">
                  {SIZE_ORDER.map((s) => (
                    <button
                      key={s}
                      onClick={() => {
                        onResize(s)
                        setSizeMenu(false)
                      }}
                      className={cn(
                        'rounded px-3 py-1 text-left text-[0.75rem] hover:bg-inset',
                        s === size ? 'text-fg' : 'text-dim',
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={onRemove}
              className="flex h-6 w-6 items-center justify-center rounded text-mute hover:bg-danger-soft hover:text-[color:var(--danger)]"
              title="Remove widget"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </header>
      <div className={cn('flex-1 px-3.5 pb-3.5', editing && 'pointer-events-none opacity-90')}>
        {def.render()}
      </div>
    </section>
  )
}

function AddWidgetSheet({
  onClose,
  onAdd,
  existing,
}: {
  onClose: () => void
  onAdd: (type: string) => void
  existing: string[]
}) {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState<string>('ALL')
  const cats = ['ALL', 'CORE', 'DATA', 'RECOVERY', 'EVIDENCE', 'SYSTEM', 'ANALYTICS', 'AI']
  const filtered = WIDGET_LIST.filter(
    (w) =>
      (cat === 'ALL' || w.category === cat) &&
      (w.title.toLowerCase().includes(q.toLowerCase()) ||
        w.description.toLowerCase().includes(q.toLowerCase())),
  )
  return (
    <div className="fixed inset-0 z-90 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="animate-fade-up relative flex h-full w-full max-w-md flex-col border-l border-line-strong bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-fg">Add widget</h2>
            <p className="text-[0.6875rem] text-mute">
              {WIDGET_LIST.length} widgets across 7 categories
            </p>
          </div>
          <button onClick={onClose} className="text-mute hover:text-fg" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="border-b border-line px-4 py-3">
          <div className="flex h-9 items-center gap-2 rounded-md border border-line bg-inset px-2.5">
            <Search className="h-3.5 w-3.5 text-mute" />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search widgets…"
              className="h-full flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-mute"
            />
          </div>
          <div className="mt-2.5 flex flex-wrap gap-1">
            {cats.map((c) => (
              <button
                key={c}
                onClick={() => setCat(c)}
                className={cn(
                  'rounded-full border px-2.5 py-0.5 text-[0.6875rem] transition-colors',
                  cat === c
                    ? 'border-transparent bg-inset text-fg'
                    : 'border-line text-mute hover:text-dim',
                )}
                style={cat === c ? { color: 'var(--accent)' } : undefined}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 space-y-2 overflow-y-auto p-4">
          {filtered.map((w) => {
            const added = existing.includes(w.type)
            return (
              <div
                key={w.type}
                className="flex items-start justify-between gap-3 rounded-lg border border-line bg-inset p-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-[0.8125rem] font-medium text-fg">{w.title}</p>
                    <span className="rounded border border-line px-1 py-0.5 text-[0.625rem] text-mute">
                      {w.category}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[0.75rem] text-dim">{w.description}</p>
                </div>
                <Button
                  variant={added ? 'ghost' : 'subtle'}
                  size="sm"
                  onClick={() => onAdd(w.type)}
                >
                  {added ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                  {added ? 'Added' : 'Add'}
                </Button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function FirstRunDialog({
  onPick,
  onSkip,
}: {
  onPick: (widgets: string[]) => void
  onSkip: () => void
}) {
  return (
    <div className="fixed inset-0 z-100 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/55 backdrop-blur-[2px]" />
      <div className="animate-scale-in relative w-full max-w-lg rounded-xl border border-line-strong bg-surface p-6 shadow-2xl">
        <h2 className="text-base font-semibold text-fg">Choose a starting layout</h2>
        <p className="mt-1 text-[0.8125rem] text-dim">
          Pick a preset to begin. You can customize everything — or start from scratch — at any time.
        </p>
        <div className="mt-4 grid grid-cols-2 gap-2.5">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => onPick(p.widgets)}
              className="rounded-lg border border-line bg-inset p-3.5 text-left transition-colors hover:border-line-strong"
            >
              <p className="text-[0.8125rem] font-medium text-fg">{p.name}</p>
              <p className="mt-1 text-[0.75rem] text-dim">{p.description}</p>
              <p className="mt-2 font-mono text-[0.625rem] text-mute">
                {p.widgets.length} widgets
              </p>
            </button>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onSkip}>
            Start from the default layout
          </Button>
        </div>
      </div>
    </div>
  )
}
