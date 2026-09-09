import type { DimensionResultOut, VerificationDimension } from '@/lib/api/queries'
import { VERIFICATION_DIMENSIONS } from '@/lib/api/queries'

/**
 * Pure certificate-verification logic, kept apart from the component that renders it so the
 * component module exports only components (react-refresh) and so this is testable on its own.
 */

/** Human-readable labels for the backend's verification dimensions. */
export const DIMENSION_LABEL: Readonly<Record<VerificationDimension, string>> = {
  STRUCTURE: 'Structure',
  VERSION_COMPATIBILITY: 'Version compatibility',
  EVIDENCE_AVAILABILITY: 'Evidence availability',
  EVIDENCE_DIGEST: 'Evidence digest',
  SIGNATURE_VALIDITY: 'Signature validity',
  PUBLIC_KEY_CONSISTENCY: 'Public key consistency',
  SIGNER_TRUST: 'Signer trust',
  EVIDENCE_CHAIN_INTEGRITY: 'Evidence chain integrity',
  OPERATION_CONSISTENCY: 'Operation consistency',
  TARGET_CONSISTENCY: 'Target consistency',
}

/**
 * Order the backend's rows to the contract's declared dimension order and synthesise a NOT_CHECKED
 * row for any dimension the response omitted.
 *
 * The contract declares `minItems: 10`, but a missing dimension must never simply disappear: an
 * absent row reads as "nothing to report", which is exactly how an incomplete verification could be
 * made to look clean.
 */
export function alignDimensions(dimensions: readonly DimensionResultOut[]): DimensionResultOut[] {
  const byName = new Map(dimensions.map((d) => [d.dimension, d]))
  const known: DimensionResultOut[] = VERIFICATION_DIMENSIONS.map(
    (name) =>
      byName.get(name) ?? {
        dimension: name,
        result: 'NOT_CHECKED',
        detail: 'The backend returned no result for this dimension.',
        evidence_ref: null,
      },
  )
  // Anything the backend reported that this build does not model still gets shown.
  const extra = dimensions.filter((d) => !VERIFICATION_DIMENSIONS.includes(d.dimension))
  return [...known, ...extra]
}
