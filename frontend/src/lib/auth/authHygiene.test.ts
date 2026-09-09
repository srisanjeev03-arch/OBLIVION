import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { AUTH_TOKEN_ISSUANCE_PUBLISHED } from './authContract'

/**
 * Structural guarantees, enforced by scanning the real source tree.
 *
 * Every rule here corresponds to an acceptance criterion that is otherwise only visible by
 * reading carefully. A regression - someone re-adds a cookie credential, or reintroduces a
 * build-time flag that turns dev personas on in production - fails `npm test` instead of shipping.
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

const FILES = sourceFiles()
const textOf = (file: string) => readFileSync(file, 'utf8')
const rel = (file: string) => relative(SRC, file).replace(/\\/g, '/')
const matching = (pattern: RegExp) =>
  FILES.filter((f) => pattern.test(textOf(f))).map(rel)

describe('auth hygiene: no cookie-based authentication', () => {
  it('never sends ambient credentials with fetch', () => {
    expect(matching(/credentials:\s*['"](?:same-origin|include)['"]/)).toEqual([])
  })

  it('never reads or writes document.cookie', () => {
    expect(matching(/document\.cookie/)).toEqual([])
  })

  it('declares credentials: "omit" on the shared transport', () => {
    expect(textOf(join(SRC, 'lib', 'api', 'client.ts'))).toContain("credentials: 'omit'")
  })
})

describe('auth hygiene: auth calls go through exactly one door', () => {
  it('the auth API module uses the shared client and never hand-rolls a request', () => {
    const source = textOf(join(SRC, 'lib', 'api', 'auth.ts'))
    expect(source).toMatch(/from '\.\/client'/)
    // No second transport: auth must not bypass base-URL, bearer-attachment and error handling.
    expect(source).not.toMatch(/\bfetch\(/)
    expect(source).not.toMatch(/new XMLHttpRequest/)
    expect(source).not.toMatch(/Authorization['"]?\s*[:=]/)
  })

  it('only the auth API module addresses /api/auth paths', () => {
    // Widening this list means a second component started minting credentials.
    expect(matching(/request[<(][^\n]*['"`]\/api\/auth/)).toEqual(['lib/api/auth.ts'])
  })

  it('no module outside the transport assigns an Authorization header', () => {
    // The transport owns the credential. Anything else risks a second, unreviewed auth path.
    expect(matching(/Authorization['"]?\s*[:=]/)).toEqual(['lib/api/client.ts'])
  })
})

describe('auth hygiene: production cannot use dev authentication', () => {
  it('VITE_MOCK_AUTH is unread - a build-time flag can no longer enable dev auth', () => {
    // The identifier may appear in prose explaining why it is gone; what must not exist is a read.
    expect(matching(/import\.meta\.env\.VITE_MOCK_AUTH/)).toEqual([])
    expect(matching(/env\.VITE_MOCK_AUTH/)).toEqual([])
  })

  it('the dev gate depends on import.meta.env.DEV and nothing configurable', () => {
    const source = textOf(join(SRC, 'lib', 'auth', 'devAuth.ts'))
    const start = source.indexOf('export function isDevAuthEnabled')
    const end = source.indexOf('/** Throws a stable error')
    expect(start).toBeGreaterThan(-1)
    expect(end).toBeGreaterThan(start)

    const gate = source.slice(start, end)
    // The two permitted inputs...
    expect(gate).toMatch(/import\.meta\.env\.DEV/)
    expect(gate).toMatch(/import\.meta\.env\.MODE\s*===\s*'test'/)
    // ...and no environment variable or runtime flag may participate.
    expect(gate).not.toMatch(/VITE_/)
    expect(gate).not.toMatch(/process\.env/)
    expect(gate).not.toMatch(/localStorage|sessionStorage|cookie/)
  })

  it('dev personas are reachable only through the explicitly-named action', () => {
    // devLogin lives in the dev module and the provider's persona action; nothing else.
    expect(matching(/\bdevLogin\s*\(/)).toEqual(['lib/auth/devAuth.ts', 'lib/auth/provider.tsx'])
  })

  it('no bearer token is ever persisted to browser storage', () => {
    expect(matching(/localStorage\.setItem\([^)]*token/i)).toEqual([])
    expect(matching(/sessionStorage\.setItem\([^)]*token/i)).toEqual([])
  })
})

describe('auth hygiene: no fake security-success states', () => {
  it('only the auth layer can declare a session authenticated', () => {
    expect(matching(/setAuthState\(\s*['"]AUTHENTICATED['"]/)).toEqual([
      'lib/auth/devAuth.ts',
      'lib/auth/provider.tsx',
    ])
  })

  it('no component asserts authentication from a frontend-only boolean', () => {
    expect(matching(/\bisAuthenticated\b/)).toEqual([])
  })
})

describe('OpenAPI stays the source of truth', () => {
  // The frontend no longer vendors a copy of the contract: a second file is a second source of
  // truth, and it was exactly that copy which went stale and made the console refuse a backend
  // that had supported login all along. It reads the repository's generated document instead.
  const contract = readFileSync(join(process.cwd(), '..', 'docs', 'OPENAPI.yaml'), 'utf8')

  it('declares the bearer scheme the transport implements', () => {
    expect(contract).toMatch(/bearerAuth:\s*\n\s*type:\s*http\s*\n\s*scheme:\s*bearer/)
    expect(contract).toMatch(/security:\s*\n\s*-\s*bearerAuth:/)
  })

  it('does not mislabel the opaque session token as a JWT', () => {
    // The backend mints secrets.token_urlsafe(32). Claiming JWT would invite a client to parse
    // claims that are not there.
    expect(contract).not.toMatch(/bearerFormat:\s*JWT/)
    expect(contract).toMatch(/bearerFormat:\s*OpaqueSessionToken/)
  })

  it('publishes the auth paths, and the frontend agrees', () => {
    const hasAuthPath = /^\s{2}\/api\/auth/m.test(contract)
    expect(hasAuthPath).toBe(AUTH_TOKEN_ISSUANCE_PUBLISHED)
    expect(contract).toMatch(/^\s{2}\/api\/auth\/login:/m)
    expect(contract).toMatch(/^\s{2}\/api\/auth\/me:/m)
    expect(contract).toMatch(/^\s{2}\/api\/auth\/logout:/m)
  })

  it('generates its types from that same document, not a hand-written twin', () => {
    const pkg = JSON.parse(
      readFileSync(join(process.cwd(), 'package.json'), 'utf8'),
    ) as { scripts: Record<string, string> }
    expect(pkg.scripts['gen:api']).toMatch(/\.\.\/docs\/OPENAPI\.yaml/)
    // A vendored copy under contract/ would silently diverge from the backend.
    expect(() => statSync(join(process.cwd(), 'contract'))).toThrow()
  })
})
