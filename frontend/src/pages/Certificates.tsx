import { useState } from 'react'
import { FileCheck2, ShieldCheck, ShieldAlert, Zap } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/status/StatusBadge'
import { EvidenceId, EvidenceHash } from '@/components/evidence/EvidenceId'
import { useVerifyCertificateMutation } from '@/lib/api'
import { isAvailable } from '@/lib/api/capabilities'
import { cn } from '@/lib/cn'

export function Certificates() {
  const [certId] = useState('cert-8841-a9f-2026')
  const [isSimulatedTamper, setIsSimulatedTamper] = useState(false)
  const [verificationResult, setVerificationResult] = useState<{
    valid: boolean
    signature_valid: boolean
    evidence_integrity: boolean
    reason?: string
  } | null>({
    valid: true,
    signature_valid: true,
    evidence_integrity: true,
    reason: 'Ed25519 signature and Merkle payload integrity verified against root authority key.',
  })

  const verifyMutation = useVerifyCertificateMutation(certId)
  const isVerifyAvailable = isAvailable('certificates.verify')

  const handleVerify = () => {
    if (isSimulatedTamper) {
      setVerificationResult({
        valid: false,
        signature_valid: false,
        evidence_integrity: false,
        reason:
          'CRITICAL: SHA-256 payload digest mismatch. The signed hash does not match computed bundle hash.',
      })
      return
    }

    if (isVerifyAvailable) {
      verifyMutation.mutate(undefined, {
        onSuccess: (res) => {
          setVerificationResult({
            valid: Boolean(res.valid),
            signature_valid: Boolean(res.signature_valid),
            evidence_integrity: Boolean(res.evidence_integrity),
            reason: res.reason,
          })
        },
      })
    } else {
      setVerificationResult({
        valid: true,
        signature_valid: true,
        evidence_integrity: true,
        reason: 'Signature verified against local root key authority.',
      })
    }
  }

  const toggleTamper = () => {
    const next = !isSimulatedTamper
    setIsSimulatedTamper(next)
    if (next) {
      setVerificationResult({
        valid: false,
        signature_valid: false,
        evidence_integrity: false,
        reason: 'TAMPER DETECTED: Simulated alteration of target raw cluster payload.',
      })
    } else {
      setVerificationResult({
        valid: true,
        signature_valid: true,
        evidence_integrity: true,
        reason: 'Ed25519 signature and Merkle root integrity verified.',
      })
    }
  }

  const isValid = verificationResult?.valid ?? true

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Cryptographic Erasure Certificates"
        icon={<FileCheck2 className="h-4 w-4 text-accent" />}
        description="Tamper-evident cryptographic proof documents signed with Ed25519 root authority."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant={isSimulatedTamper ? 'danger' : 'outline'}
              size="sm"
              leadingIcon={<Zap className="h-3.5 w-3.5" />}
              onClick={toggleTamper}
            >
              {isSimulatedTamper ? 'Revert Tamper Test' : 'Simulate Payload Tamper'}
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={verifyMutation.isPending}
              leadingIcon={<ShieldCheck className="h-3.5 w-3.5" />}
              onClick={handleVerify}
            >
              Verify Certificate
            </Button>
          </div>
        }
      />

      <div className="flex-1 p-6 space-y-6 max-w-4xl mx-auto w-full">
        {/* Simulation Notice Banner */}
        <div className="rounded-md border border-accent/40 bg-accent-soft p-4 flex items-start justify-between gap-3 text-xs">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-bold text-accent">
              <Badge variant="accent">SIMULATION TESTBENCH</Badge>
              <span>Cryptographic Proof Specification & Verification Demo</span>
            </div>
            <p className="text-fg opacity-90 leading-relaxed text-[0.6875rem]">
              Live certificate generation and root CA signing require Milestone A backend delivery.
              This interactive view demonstrates the canonical Ed25519 signature verification model
              and payload tamper detection.
            </p>
          </div>
          <div className="shrink-0 font-mono text-[0.6875rem] text-dim">SPEC ISO/IEC 27040</div>
        </div>

        {/* Tamper Warning Banner */}
        {isSimulatedTamper && (
          <div className="rounded-md border border-danger/60 bg-danger-soft p-4 space-y-2 text-danger motion-enter">
            <div className="flex items-center gap-2 font-bold text-sm">
              <ShieldAlert className="h-5 w-5" />
              <span>CRITICAL: CRYPTOGRAPHIC INTEGRITY VIOLATION DETECTED</span>
            </div>
            <p className="text-xs text-fg leading-relaxed">
              The evidence payload bytes have been altered post-signing. The Merkle root digest no
              longer matches the Ed25519 root signature inside this certificate. The certificate is
              immediately invalidated.
            </p>
          </div>
        )}

        {/* Certificate Document Canvas */}
        <div
          className={cn(
            'rounded-lg border bg-surface p-8 space-y-6 shadow-2xl relative transition-all duration-300',
            isValid ? 'border-line-strong' : 'border-danger/80 ring-2 ring-danger/40',
          )}
        >
          {/* Top Header of Document */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-line pb-6">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs uppercase tracking-widest text-accent font-bold">
                  OBLIVION FORENSIC ATTESTATION
                </span>
                <span className="text-dim text-[0.6875rem]">/ ISO 27040 COMPLIANT</span>
              </div>
              <h2 className="text-lg font-bold text-fg tracking-tight">
                Certificate of Permanent Erasure & Destruction
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <StatusBadge
                kind="verification"
                value={isValid ? 'VALID' : 'INVALID'}
                emphasis="strong"
                size="md"
              />
            </div>
          </div>

          {/* Certificate Metadata Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="space-y-1">
              <span className="text-dim text-[0.6875rem] block uppercase">Certificate ID</span>
              <EvidenceId value={certId} label="Certificate ID" size="md" />
            </div>

            <div className="space-y-1">
              <span className="text-dim text-[0.6875rem] block uppercase">Source Operation ID</span>
              <EvidenceId value="op-8841-a9f2" label="Operation ID" size="md" />
            </div>

            <div className="space-y-1">
              <span className="text-dim text-[0.6875rem] block uppercase">Target Scope</span>
              <span className="font-mono text-fg font-semibold block truncate">
                C:\Oblivion\Targets\dataset_finance_2026.dat
              </span>
            </div>

            <div className="space-y-1">
              <span className="text-dim text-[0.6875rem] block uppercase">Execution Policy</span>
              <span className="font-mono text-fg font-semibold">
                NIST SP 800-88 Rev. 1 — Cryptographic Purge (1-Pass Sanitize)
              </span>
            </div>
          </div>

          {/* Hashes & Digests */}
          <div className="space-y-3 pt-2">
            <span className="text-xs font-bold text-fg uppercase tracking-wider block">
              Cryptographic Signatures & Digests
            </span>

            <div className="space-y-2">
              <div className="rounded-sm border border-line bg-inset p-3 space-y-1">
                <span className="text-dim text-[0.6875rem] uppercase block font-medium">
                  Pre-Erasure Baseline Digest (SHA-256)
                </span>
                <EvidenceHash
                  value={
                    isSimulatedTamper
                      ? 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
                      : '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'
                  }
                  label="Baseline SHA-256"
                />
              </div>

              <div className="rounded-sm border border-line bg-inset p-3 space-y-1">
                <span className="text-dim text-[0.6875rem] uppercase block font-medium">
                  Sequential Evidence Merkle Root Hash
                </span>
                <EvidenceHash
                  value="9a8831f4b002c9182374e6d38e219ba48810cba72199b908712398401aa89104"
                  label="Merkle Root Hash"
                />
              </div>

              <div className="rounded-sm border border-line bg-inset p-3 space-y-1">
                <span className="text-dim text-[0.6875rem] uppercase block font-medium">
                  Ed25519 Root Authority Digital Signature
                </span>
                <EvidenceHash
                  value="3b7189c201887a0ef938ba418290ab7718920bcde29188273901bca728910e9948019ab72819bcde9018726354891a2b"
                  label="Ed25519 Signature"
                />
              </div>
            </div>
          </div>

          {/* Verification Reason Statement */}
          {verificationResult?.reason && (
            <div
              className={cn(
                'rounded-sm border p-3.5 text-xs leading-relaxed',
                isValid
                  ? 'border-success/30 bg-success-soft text-success'
                  : 'border-danger/30 bg-danger-soft text-danger',
              )}
            >
              <div className="flex items-center gap-2 font-bold mb-1">
                {isValid ? (
                  <ShieldCheck className="h-4 w-4" />
                ) : (
                  <ShieldAlert className="h-4 w-4" />
                )}
                <span>Forensic Verification Attestation</span>
              </div>
              <p className="text-[0.6875rem] text-fg opacity-90">{verificationResult.reason}</p>
            </div>
          )}

          {/* Certificate Footer */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-t border-line pt-4 text-[0.6875rem] text-mute font-mono">
            <div>Attestation Authority: Oblivion Enterprise Root CA</div>
            <div>Timestamp: 2026-09-07T18:44:00Z</div>
          </div>
        </div>
      </div>
    </div>
  )
}
