import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * Forbidden security literals.
 *
 * Section 9 of the finalisation brief is mandatory: a console must never present a simulated
 * security result as though the backend produced it. The individual inventions this repo had —
 * a certificate that reported `valid: true` on load, a "Simulate Payload Tamper" button, a
 * "NIST SP 800-88 Purge" policy, an "ISO 27040 COMPLIANT" badge, an assurance snapshot of
 * hardcoded zeros — are each gone now, but deleting them once does not stop them coming back.
 *
 * So the vocabulary is pinned. These are not style preferences: every phrase below asserts a
 * security property that no API response in this project can support.
 *
 * Comments are stripped before scanning, because explaining a removed fabrication ("this screen
 * used to claim ISO compliance") is exactly the kind of record worth keeping.
 */

const SRC = join(process.cwd(), 'src')

function sourceFiles(dir: string = SRC): string[] {
  const found: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      found.push(...sourceFiles(full))
    } else if (/\.tsx?$/.test(entry) && !/\.(test|spec)\.tsx?$/.test(entry)) {
      found.push(full)
    }
  }
  return found
}

/**
 * Drop comments so historical notes about removed fakes do not trip the scanner, while JSX text
 * and string literals — what an operator actually reads — still do.
 */
function stripComments(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '') // block comments
    .replace(/^\s*\/\/.*$/gm, '') // whole-line comments
    .replace(/^\s*\*.*$/gm, '') // block-comment continuation lines
}

const rel = (file: string) => relative(SRC, file).replace(/\\/g, '/')
const codeOnly = (file: string) => stripComments(readFileSync(file, 'utf8'))

const FILES = sourceFiles()

function hitsFor(pattern: RegExp): string[] {
  const hits: string[] = []
  for (const file of FILES) {
    const lines = codeOnly(file).split('\n')
    lines.forEach((line, index) => {
      if (pattern.test(line)) hits.push(`${rel(file)}:${index + 1}: ${line.trim().slice(0, 90)}`)
    })
  }
  return hits
}

describe('no fabricated standards or compliance claims', () => {
  // Compliance is a statement about a process and an auditor's judgement. No endpoint in this
  // contract returns it, so no screen may assert it.
  const BANNED_COMPLIANCE = [/NIST/, /ISO[ /]?(IEC)?\s*27\d{3}/, /DoD\s*5220/, /FIPS\s*180/, /BSI-GS/]

  for (const pattern of BANNED_COMPLIANCE) {
    it(`renders nothing matching ${pattern}`, () => {
      expect(hitsFor(pattern)).toEqual([])
    })
  }

  it('never claims COMPLIANT anywhere in shipped code', () => {
    expect(hitsFor(/COMPLIANT/i)).toEqual([])
  })
})

describe('no fabricated security outcomes', () => {
  it('has no tamper simulation', () => {
    // A frontend toggle cannot alter evidence; offering one implies verification is a UI setting.
    expect(hitsFor(/simulat/i)).toEqual([])
  })

  it('has no invented tamper verdict', () => {
    expect(hitsFor(/TAMPER DETECTED/i)).toEqual([])
  })

  it('uses no VALIDATED assurance state the backend cannot emit', () => {
    // AssuranceStatus is PASSED | FAILED | PARTIAL | INCONCLUSIVE.
    expect(hitsFor(/\bVALIDATED\b/)).toEqual([])
  })

  it('makes no absolute irrecoverability claim', () => {
    // CLAUDE.md forbids asserting 100% irrecoverability or guaranteed removal. The pattern targets
    // affirmative claims only: this console's central axiom is the *denial* of such a claim
    // ("NOT DETECTED is not the same as PROVABLY UNRECOVERABLE"), and a scanner that flagged the
    // denial would either be loosened later or delete the most important sentence on the page.
    const affirmative =
      /guarantee[d]?|proven\s+(to\s+be\s+)?(ir|un)?recoverable|(100\s*%|entirely|absolutely|totally)\s+(irrecoverable|unrecoverable|destroyed|erased|non-?recoverable)/i
    // Tailwind arbitrary values and CSS math are layout, not claims.
    const cssArbitrary = /calc\(|\b[wh]-\[|min-w-\[|max-w-\[/
    expect(hitsFor(affirmative).filter((hit) => !cssArbitrary.test(hit))).toEqual([])
  })

  it('invents no Merkle or root-CA authority', () => {
    expect(hitsFor(/Merkle|Root CA|root authority key/i)).toEqual([])
  })
})

describe('no invented identifiers', () => {
  it('contains no fabricated policy id', () => {
    // Real ids come from contract-policies.ts, generated from the backend registry.
    expect(hitsFor(/pol-nist|pol-dod|pol-bld|POLICIES\s*=\s*\[/)).toEqual([])
  })

  it('contains no hardcoded 64-hex digest or long signature literal', () => {
    // A pasted hash is indistinguishable from a real one, which is what makes it dangerous.
    expect(hitsFor(/['"`][0-9a-f]{40,}['"`]/)).toEqual([])
  })

  it('contains no fabricated operation or certificate identifier', () => {
    expect(hitsFor(/OP-[0-9A-F]{6,}|cert-\d{4}-/)).toEqual([])
  })

  it('uses no Math.random to synthesise security or progress data', () => {
    expect(hitsFor(/Math\.random/)).toEqual([])
  })
})

describe('no fabricated aggregate metrics', () => {
  it('never renders a bare zero count next to a security label', () => {
    // The old dashboard showed three assurance rows all reading 0 with no endpoint to count from.
    expect(hitsFor(/font-mono tabular text-fg">0</)).toEqual([])
  })

  it('asserts no all-clear without a query', () => {
    expect(hitsFor(/all recorded states are nominal|all systems? (are )?nominal|no unhandled/i)).toEqual(
      [],
    )
  })
})

describe('scanner sanity', () => {
  it('detects a known-bad line, so a clean result means something', () => {
    // Without this, a bug in stripComments or the file walk could make every check vacuously pass.
    const sample = stripComments(
      '// NIST SP 800-88 in a comment is ignored\n' +
        'const label = "ISO 27040 COMPLIANT"\n' +
        'const hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"\n',
    )
    expect(sample).not.toMatch(/NIST/)
    expect(sample).toMatch(/ISO\s*27040/)
    expect(sample).toMatch(/COMPLIANT/)
    expect(sample).toMatch(/['"`][0-9a-f]{40,}['"`]/)
  })

  it('walks a non-trivial number of source files', () => {
    expect(FILES.length).toBeGreaterThan(60)
  })
})

describe('no mock or fixture data in shipped code', () => {
  it('imports nothing from a mock module', () => {
    expect(hitsFor(/from ['"][^'"]*mock/i)).toEqual([])
  })

  it('declares no mock-data module anywhere in the tree', () => {
    expect(FILES.filter((f) => /mock/i.test(rel(f))).map(rel)).toEqual([])
  })
})
