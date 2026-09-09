import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AIPanel } from './AIPanel'
import type { AIResultState } from './AIAnalysisDrawer'

describe('AIPanel', () => {
  it('renders AI ADVISORY label', () => {
    render(
      <AIPanel title="Sensitivity Classification" state="UNAVAILABLE" summary="Test summary" />,
    )
    expect(screen.getByText(/AI Advisory: Sensitivity Classification/i)).toBeInTheDocument()
    expect(screen.getByText(/AI output is advisory/)).toBeInTheDocument()
  })

  it('renders UNAVAILABLE state with honest explanation', () => {
    render(
      <AIPanel
        title="Test"
        state="UNAVAILABLE"
        summary="The AI advisory layer is not yet integrated."
      />,
    )
    expect(screen.getByText('UNAVAILABLE')).toBeInTheDocument()
    expect(screen.getByText('AI Advisory Unavailable')).toBeInTheDocument()
    expect(screen.getByText(/has not yet been integrated/)).toBeInTheDocument()
  })

  it('renders ERROR state with error explanation', () => {
    render(<AIPanel title="Test" state="ERROR" summary="Something failed" />)
    expect(screen.getByText('ERROR')).toBeInTheDocument()
    expect(screen.getByText('AI Analysis Error')).toBeInTheDocument()
  })

  it('renders ANALYZING state with loading spinner', () => {
    render(<AIPanel title="Test" state="ANALYZING" summary="Analyzing..." />)
    expect(screen.getByText('ANALYZING')).toBeInTheDocument()
    expect(screen.getByText(/AI model is reasoning/)).toBeInTheDocument()
  })

  it('renders INCONCLUSIVE state with explanation', () => {
    render(<AIPanel title="Test" state="INCONCLUSIVE" summary="No conclusion" />)
    expect(screen.getByText('INCONCLUSIVE')).toBeInTheDocument()
    expect(
      screen.getByText(/AI advisory could not reach a reliable conclusion/),
    ).toBeInTheDocument()
  })

  it('expands technical explanation on toggle', () => {
    const aiData = {
      reasoningFactors: ['Factor 1', 'Factor 2'],
      evidenceUsed: ['Evidence 1'],
      limitations: 'Test limitation',
    }
    render(
      <AIPanel title="Test" state="COMPLETED" summary="Summary" aiData={aiData} confidence={85} />,
    )
    const toggle = screen.getByText(/show technical explanation/i)
    expect(toggle).toBeInTheDocument()

    // Hidden by default
    expect(screen.queryByText('Factor 1')).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(toggle)
    expect(screen.getByText('Factor 1')).toBeInTheDocument()
    expect(screen.getByText('Factor 2')).toBeInTheDocument()
    expect(screen.getByText('Evidence 1')).toBeInTheDocument()
    expect(screen.getByText('Test limitation')).toBeInTheDocument()
  })

  it('displays confidence as HIGH for 80+', () => {
    render(<AIPanel title="Test" state="COMPLETED" summary="Summary" confidence={90} />)
    expect(screen.getByText('90%')).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('displays confidence as MEDIUM for 50-79', () => {
    render(<AIPanel title="Test" state="COMPLETED" summary="Summary" confidence={60} />)
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('MEDIUM')).toBeInTheDocument()
  })

  it('displays confidence as LOW for <50', () => {
    render(<AIPanel title="Test" state="COMPLETED" summary="Summary" confidence={25} />)
    expect(screen.getByText('25%')).toBeInTheDocument()
    expect(screen.getByText('LOW')).toBeInTheDocument()
  })
})

describe('AIPanel state badges', () => {
  const states: AIResultState[] = [
    'AVAILABLE',
    'ANALYZING',
    'COMPLETED',
    'LOW_CONFIDENCE',
    'INCONCLUSIVE',
    'UNAVAILABLE',
    'ERROR',
  ]

  states.forEach((state) => {
    it(`renders the ${state} state badge`, () => {
      const { unmount } = render(<AIPanel title="Test" state={state} />)
      const badge = state === 'LOW_CONFIDENCE' ? 'LOW CONFIDENCE' : state
      expect(screen.getByText(badge)).toBeInTheDocument()
      unmount()
    })
  })
})
