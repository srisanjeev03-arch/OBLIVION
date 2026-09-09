import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders operation states with appropriate text and accessibility label', () => {
    render(<StatusBadge kind="operation" value="ERASING" />)
    const badge = screen.getByText('Erasing')
    expect(badge).toBeInTheDocument()
  })

  it('renders assurance states correctly', () => {
    render(<StatusBadge kind="assurance" value="VALIDATED" />)
    const badge = screen.getByText('Validated')
    expect(badge).toBeInTheDocument()
  })

  it('renders verification states correctly', () => {
    render(<StatusBadge kind="verification" value="INVALID" />)
    const badge = screen.getByText('Invalid')
    expect(badge).toBeInTheDocument()
  })
})
