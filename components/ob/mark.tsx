'use client'

// OBLIVION mark: a "vanishing trace" — a solid ring on the left dissolving
// into fading dots on the right. Evidence disappears, proof remains.
export function OblivionMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden fill="none">
      <circle cx="9" cy="12" r="6" stroke="var(--accent)" strokeWidth="1.75" />
      <circle cx="9" cy="12" r="2" fill="var(--accent)" />
      <circle cx="16.5" cy="12" r="1.15" fill="var(--accent)" opacity="0.75" />
      <circle cx="20" cy="12" r="0.85" fill="var(--accent)" opacity="0.45" />
      <circle cx="22.6" cy="12" r="0.6" fill="var(--accent)" opacity="0.2" />
    </svg>
  )
}
