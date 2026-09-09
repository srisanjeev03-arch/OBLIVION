# Requirements Traceability

| Requirement | Component | Evidence | Test |
|---|---|---|---|
| Target discovery | Discovery | TargetProfile | discovery tests |
| Storage awareness | StorageProfiler | StorageProfile | profile tests |
| Permanent deletion | ErasureEngine | operation events | erasure tests |
| Recoverable deletion | Vault + Erasure | RecoveryObject | vault tests |
| Authorized restore | RBAC + Recovery | security events | auth tests |
| Recovery verification | RecoveryEngine | recovery result | recovery tests |
| Residual analysis | ResidualScanner | residual events | residual tests |
| AI sensitivity | AI service | AI result | AI evaluation |
| Policy recommendation | AI + Policy | recommendation | policy tests |
| Assurance | AssuranceEngine | Assurance | assurance tests |
| Evidence integrity | EvidenceEngine | event chain | tamper tests |
| Certificate | Signer | Certificate | signature tests |
| Frontend compatibility | API | OpenAPI | contract tests |
