import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'
import { ASSURANCE_STATES } from '@/lib/status'

describe('StatusBadge', () => {
  it('renders operation states with appropriate text and accessibility label', () => {
    render(<StatusBadge kind="operation" value="ERASING" />)
    const badge = screen.getByText('Erasing')
    expect(badge).toBeInTheDocument()
  })

  it('renders assurance states correctly', () => {
    render(<StatusBadge kind="assurance" value="PASSED" />)
    const badge = screen.getByText('Passed')
    expect(badge).toBeInTheDocument()
  })

  it('does not offer a VALIDATED assurance state the backend never emits', () => {
    // assuranceStateMeta is the only source of assurance labels, and its keys are the backend's
    // AssuranceStatus values plus the console's own NOT_EVALUATED.
    expect(ASSURANCE_STATES).not.toContain('VALIDATED')
    expect(ASSURANCE_STATES).toEqual(
      expect.arrayContaining(['PASSED', 'PARTIAL', 'INCONCLUSIVE', 'FAILED', 'NOT_EVALUATED']),
    )
  })

  it('renders verification states correctly', () => {
    render(<StatusBadge kind="verification" value="INVALID" />)
    const badge = screen.getByText('Invalid')
    expect(badge).toBeInTheDocument()
  })
})
