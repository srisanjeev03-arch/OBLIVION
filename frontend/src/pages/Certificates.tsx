import { useState, type FormEvent } from 'react'
import { FileCheck2, Search } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { EvidenceHash } from '@/components/evidence/EvidenceId'
import { CertificateVerificationPanel } from '@/components/certificate/CertificateVerificationPanel'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import {
  useCertificateQuery,
  useVerifyCertificateMutation,
  type CertificateVerificationOut,
} from '@/lib/api'
import { unavailableReason } from '@/lib/api/capabilities'

/**
 * Certificate lookup and verification.
 *
 * Everything shown here is a backend response. The screen starts with no certificate and no
 * verification result, and it never fills either in itself:
 *
 *   - there is no seeded `valid: true` on load, because nothing has been verified yet;
 *   - there is no "simulate tamper" control, because a frontend toggle cannot alter evidence and
 *     showing one would teach operators that verification results are a UI setting;
 *   - there are no compliance badges, because compliance is an assertion about a process, not a
 *     field the API returns.
 *
 * The contract publishes no certificate collection route, so an operator arrives with an ID â€” from
 * an operation's evidence trail â€” rather than browsing a list. That limitation is stated on screen.
 */
export function Certificates() {
  const [enteredId, setEnteredId] = useState('')
  const [lookupId, setLookupId] = useState<string | null>(null)
  const [verification, setVerification] = useState<CertificateVerificationOut | null>(null)

  const certificateQuery = useCertificateQuery(lookupId ?? undefined)
  const verifyMutation = useVerifyCertificateMutation(lookupId ?? '')

  const handleLookup = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = enteredId.trim()
    if (!trimmed) return
    setVerification(null)
    setLookupId(trimmed)
  }

  const handleVerify = () => {
    if (!lookupId) return
    verifyMutation.mutate(undefined, { onSuccess: (result) => setVerification(result) })
  }

  const listGap = unavailableReason('certificates.list')
  const cert = certificateQuery.data

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Certificates"
        icon={<FileCheck2 className="h-4 w-4 text-accent" />}
        description="Retrieve an issued erasure certificate and run the backend's cryptographic verification."
      />

      <div className="space-y-4 p-4 sm:p-5">
        <form
          onSubmit={handleLookup}
          className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4 sm:flex-row sm:items-end"
        >
          <div className="min-w-0 flex-1">
            <Input
              label="Certificate ID"
              placeholder="e.g. cert_1a2b3c4d5e6f"
              value={enteredId}
              onChange={(e) => setEnteredId(e.target.value)}
              mono
              className="font-mono text-xs"
              hint={listGap ?? undefined}
            />
          </div>
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={!enteredId.trim()}
            leadingIcon={<Search className="h-3.5 w-3.5" />}
          >
            Retrieve
          </Button>
        </form>

        {!lookupId && (
          <EmptyState
            title="No certificate selected"
            description="Enter a certificate ID issued by a completed operation. Verification results are produced by the backend, never by this console."
          />
        )}

        {lookupId && certificateQuery.isPending && <LoadingState title="Fetching certificate" />}

        {lookupId && certificateQuery.isError && (
          <ErrorState
            error={certificateQuery.error}
            title="Certificate could not be retrieved"
          />
        )}

        {lookupId && cert && (
          <>
            <Panel>
              <PanelHeader title="Issued certificate" />
              <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                <Field label="Certificate ID" value={cert.id} mono />
                <Field label="Operation ID" value={cert.operation_id} mono />
                <Field label="Signing algorithm" value={cert.signing_algorithm} mono />
                <Field label="Key ID" value={cert.key_id ?? 'not recorded'} mono />
                <Field label="Issued at" value={formatIssued(cert.issued_at)} mono />
                <Field label="Claim" value={cert.claim ?? 'not recorded'} />
              </dl>

              <div className="mt-3 space-y-2">
                <span className="block text-[0.625rem] font-bold uppercase tracking-wider text-dim">
                  Evidence digest (SHA-256, as recorded by the backend)
                </span>
                <EvidenceHash value={cert.evidence_digest} label="Evidence digest" />
              </div>

              <div className="mt-3 space-y-2">
                <span className="block text-[0.625rem] font-bold uppercase tracking-wider text-dim">
                  Signature and public key (hex, as stored)
                </span>
                <EvidenceHash value={cert.signature} label="Signature" />
                <EvidenceHash value={cert.public_key} label="Public key" />
              </div>
            </Panel>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="primary"
                size="md"
                onClick={handleVerify}
                loading={verifyMutation.isPending}
              >
                Verify at backend
              </Button>
              <span className="text-[0.6875rem] text-dim">
                Runs POST /api/certificates/&#123;id&#125;/verify. The backend decides validity; this
                console only renders its answer.
              </span>
            </div>

            {verifyMutation.isError && (
              <ErrorState
                error={verifyMutation.error}
                title="Verification request failed"
              />
            )}

            {verification ? (
              <CertificateVerificationPanel verification={verification} />
            ) : (
              !verifyMutation.isPending && (
                <div className="rounded-md border border-line bg-inset p-3 text-[0.6875rem] leading-relaxed text-dim">
                  NOT VERIFIED â€” no verification has been run against this certificate in this
                  session. An unverified certificate has no status; it is not provisionally valid.
                </div>
              )
            )}
          </>
        )}
      </div>
    </div>
  )
}

/** Render the backend timestamp without inventing one when it is absent or unreadable. */
function formatIssued(issuedAt: string): string {
  const parsed = Date.parse(issuedAt)
  if (Number.isNaN(parsed)) return issuedAt || 'not recorded'
  return `${new Date(parsed).toISOString().replace('T', ' ').slice(0, 19)} UTC`
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[0.625rem] font-bold uppercase tracking-wider text-dim">{label}</dt>
      <dd
        className={
          mono
            ? 'mt-0.5 font-mono text-xs break-all text-fg'
            : 'mt-0.5 text-xs leading-relaxed text-fg'
        }
      >
        {value}
      </dd>
    </div>
  )
}


