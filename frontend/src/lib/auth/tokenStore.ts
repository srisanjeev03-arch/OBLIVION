/**
 * In-memory bearer-token holder.
 *
 * This is the only seam between the auth layer and the HTTP transport. It is a plain module
 * (not React, not Zustand) for two reasons:
 *   1. `@/lib/api/client` must read the token without importing the auth provider, which would
 *      create a circular dependency (provider -> api -> client -> provider).
 *   2. The token must never be persisted. There is no localStorage/sessionStorage write here,
 *      so a bearer token cannot survive a document unload or be read by injected scripts.
 *
 * A session is therefore per-tab and per-document by construction: a page reload always
 * returns to an unauthenticated state until a real token endpoint is published
 * (see `@/lib/auth/authContract`).
 */

import type { AccessTokenSource } from './types'

export type { AccessTokenSource }

export interface BearerToken {
  readonly accessToken: string
  /** ISO-8601, or null when the issuing source did not report an expiry. */
  readonly expiresAt: string | null
  readonly source: AccessTokenSource
}

let current: BearerToken | null = null

type Listener = (token: BearerToken | null) => void
const listeners = new Set<Listener>()

export function setBearerToken(token: BearerToken | null): void {
  current = token
  for (const listener of listeners) listener(token)
}

export function getBearerToken(): BearerToken | null {
  return current
}

/** True when a non-expired bearer token is available for protected requests. */
export function hasBearerToken(now: number = Date.now()): boolean {
  return current !== null && !isBearerTokenExpired(now)
}

export function isBearerTokenExpired(now: number = Date.now()): boolean {
  if (!current?.expiresAt) return false
  const expiry = Date.parse(current.expiresAt)
  if (Number.isNaN(expiry)) return false
  return expiry <= now
}

/**
 * The `Authorization` header value, or null when there is no usable token.
 * An expired token is treated as absent: we never send a credential we already know is dead,
 * because a stale 401 is a worse diagnostic than an honest "no session".
 */
export function authorizationHeaderValue(now: number = Date.now()): string | null {
  if (!hasBearerToken(now)) return null
  return `Bearer ${current?.accessToken}`
}

export function subscribeToBearerToken(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function clearBearerToken(): void {
  setBearerToken(null)
}

/** Test-only: guarantees no token leaks between specs. Not referenced by application code. */
export function __resetTokenStoreForTests(): void {
  current = null
  listeners.clear()
}