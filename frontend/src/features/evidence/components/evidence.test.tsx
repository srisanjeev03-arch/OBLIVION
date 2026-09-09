import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvidenceId } from './EvidenceId'
import { HashComparison } from './HashComparison'
import { EvidenceChainViewer } from './EvidenceChainViewer'
import type { EvidenceEvent } from '@/lib/api/types'

describe('Evidence Components', () => {
  it('renders EvidenceId placeholder when value is undefined', () => {
    render(<EvidenceId value={undefined} label="Operation ID" />)
    expect(screen.getByLabelText('Operation ID: not provided')).toBeInTheDocument()
  })

  it('renders EvidenceId with truncated middle hash', () => {
    render(
      <EvidenceId
        value="4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
        label="SHA-256"
      />,
    )
    expect(screen.getByText('4f53cda18c…02b945')).toBeInTheDocument()
  })

  it('renders HashComparison with non-matching verification status', () => {
    render(
      <HashComparison
        baselineHash="4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
        verificationHash="0000000000000000000000000000000000000000000000000000000000000000"
        expectedMatch={false}
      />,
    )
    expect(screen.getByText('Hash Inverted / Non-Matching (Erased)')).toBeInTheDocument()
  })

  it('renders EvidenceChainViewer and verifies consecutive event sequence', () => {
    const events: EvidenceEvent[] = [
      {
        sequence: 1,
        event_type: 'TARGET_PROFILED',
        timestamp: '2026-09-07T12:00:00Z',
        payload_hash: 'hash-001',
      },
      {
        sequence: 2,
        event_type: 'ERASURE_COMPLETED',
        timestamp: '2026-09-07T12:01:00Z',
        payload_hash: 'hash-002',
        previous_event_hash: 'hash-001',
      },
    ]

    render(<EvidenceChainViewer events={events} />)
    expect(screen.getByText('Chain Integrity Verified')).toBeInTheDocument()
    expect(screen.getByText('TARGET_PROFILED')).toBeInTheDocument()
    expect(screen.getByText('ERASURE_COMPLETED')).toBeInTheDocument()
  })
})
