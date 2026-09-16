/**
 * Objective Selection may preselect the erasure mode through route state. Only a real operation
 * mode is accepted; anything else falls back to the page default rather than being trusted.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { ErasureWorkflow } from './ErasureWorkflow'

function renderWithState(state: unknown) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: '/erasure', state }]}>
        <ErasureWorkflow />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ErasureWorkflow mode preselection', () => {
  it('opens in controlled-recoverable mode when the objective asks for it', () => {
    renderWithState({ objective: 'RECOVERABLE', mode: 'CONTROLLED_RECOVERABLE' })
    expect(screen.getByText('RECOVERABLE VIA RETENTION')).toBeInTheDocument()
  })

  it('ignores a mode that is not a real operation mode', () => {
    renderWithState({ mode: 'DRIVE_WIPE' })
    expect(screen.getByText('IRREVERSIBLE')).toBeInTheDocument()
    expect(screen.queryByText('RECOVERABLE VIA RETENTION')).not.toBeInTheDocument()
  })

  it('keeps the default when opened without any objective', () => {
    renderWithState(null)
    expect(screen.getByText('IRREVERSIBLE')).toBeInTheDocument()
  })
})
