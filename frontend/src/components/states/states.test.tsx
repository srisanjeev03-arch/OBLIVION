import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LoadingState, EmptyState, ErrorState, UnavailableState } from './index'
import { ApiError } from '@/lib/api/errors'

describe('Global Screen States', () => {
  it('renders LoadingState with status role and custom description', () => {
    render(<LoadingState title="Analyzing Cluster Facts" description="Reading sector 0x40" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Analyzing Cluster Facts')).toBeInTheDocument()
    expect(screen.getByText('Reading sector 0x40')).toBeInTheDocument()
  })

  it('renders EmptyState with honest default explanation', () => {
    render(<EmptyState title="No Operations Recorded" />)
    expect(screen.getByText('No Operations Recorded')).toBeInTheDocument()
    expect(screen.getByText('The backend returned no records for this view.')).toBeInTheDocument()
  })

  it('renders UnavailableState with explicit phase reason', () => {
    render(
      <UnavailableState
        title="Detector Unavailable"
        reason="Awaiting backend: Phase 6 — Evidence Chain."
      />,
    )
    expect(screen.getByText('Detector Unavailable')).toBeInTheDocument()
    expect(screen.getByText('Awaiting backend: Phase 6 — Evidence Chain.')).toBeInTheDocument()
  })

  it('renders ErrorState with retry trigger for retryable network errors', () => {
    const onRetry = vi.fn()
    const error = new ApiError({
      kind: 'network',
      message: 'Connection refused',
      code: 'ERR_REFUSED',
      retryable: true,
    })

    render(<ErrorState error={error} onRetry={onRetry} />)
    const retryBtn = screen.getByRole('button', { name: 'Retry' })
    expect(retryBtn).toBeInTheDocument()
    fireEvent.click(retryBtn)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
