import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AIAnalysisDrawer, type AIAnalysisData } from './AIAnalysisDrawer'

describe('AIAnalysisDrawer', () => {
  it('renders nothing when closed', () => {
    render(
      <AIAnalysisDrawer
        isOpen={false}
        onClose={() => {}}
        title="Test"
        aiData={null}
        showAdvisoryLabel
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows AI ADVISORY label by default', () => {
    render(
      <AIAnalysisDrawer
        isOpen
        onClose={() => {}}
        title="Sensitivity Classification"
        aiData={{ classification: 'Test' }}
        showAdvisoryLabel
      />,
    )
    expect(screen.getByText('AI ADVISORY')).toBeInTheDocument()
  })

  it('hides AI ADVISORY label when showAdvisoryLabel is false', () => {
    render(
      <AIAnalysisDrawer
        isOpen
        onClose={() => {}}
        title="Test"
        aiData={{ classification: 'Test' }}
        showAdvisoryLabel={false}
      />,
    )
    expect(screen.queryByText('AI ADVISORY')).not.toBeInTheDocument()
  })

  it('invokes onClose when close button is clicked', () => {
    const onClose = vi.fn()
    render(
      <AIAnalysisDrawer isOpen onClose={onClose} title="Test" aiData={null} showAdvisoryLabel />,
    )
    const closeButton = screen.getAllByRole('button', { name: /close/i })[0]
    expect(closeButton).toBeDefined()
    fireEvent.click(closeButton!)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('invokes onClose on Escape key press', () => {
    const onClose = vi.fn()
    render(
      <AIAnalysisDrawer isOpen onClose={onClose} title="Test" aiData={null} showAdvisoryLabel />,
    )
    // Use window.dispatchEvent
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders confidence with HIGH interpretation for 80+', () => {
    const data: AIAnalysisData = { confidence: 87 }
    render(
      <AIAnalysisDrawer isOpen onClose={() => {}} title="Test" aiData={data} showAdvisoryLabel />,
    )
    expect(screen.getByText('87%')).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('renders confidence with MEDIUM interpretation for 50-79', () => {
    const data: AIAnalysisData = { confidence: 65 }
    render(
      <AIAnalysisDrawer isOpen onClose={() => {}} title="Test" aiData={data} showAdvisoryLabel />,
    )
    expect(screen.getByText('MEDIUM')).toBeInTheDocument()
  })

  it('renders confidence with LOW interpretation for <50', () => {
    const data: AIAnalysisData = { confidence: 30 }
    render(
      <AIAnalysisDrawer isOpen onClose={() => {}} title="Test" aiData={data} showAdvisoryLabel />,
    )
    expect(screen.getByText('LOW')).toBeInTheDocument()
  })

  it('renders reasoning factors and evidence used when provided', () => {
    const data: AIAnalysisData = {
      reasoningFactors: ['Factor A', 'Factor B'],
      evidenceUsed: ['Evidence 1'],
      limitations: 'Limitation text',
    }
    render(
      <AIAnalysisDrawer isOpen onClose={() => {}} title="Test" aiData={data} showAdvisoryLabel />,
    )
    expect(screen.getByText('Factor A')).toBeInTheDocument()
    expect(screen.getByText('Factor B')).toBeInTheDocument()
    expect(screen.getByText('Evidence 1')).toBeInTheDocument()
    expect(screen.getByText('Limitation text')).toBeInTheDocument()
  })
})
