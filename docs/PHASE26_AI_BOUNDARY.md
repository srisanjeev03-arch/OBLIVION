# Phase 26 — The AI Boundary

This document describes what is **implemented and tested** in this tree.

## The boundary

```
AI → Recommendation → Policy Engine → Safety Validator → Authorization
   → Human Confirmation → Deterministic Execution
```

`oblivion.ai` implements the first two arrows and hands off. It cannot reach any
of the rest, and that is enforced structurally rather than promised in prose.

## How "advisory" is enforced

**By import graph.** A test walks every module in `oblivion/ai/` with `ast` and
fails if any of them imports `oblivion.core.erasure`, `oblivion.privileged`,
`oblivion.core.pipeline`, `oblivion.core.auth`, `oblivion.certificate.issuer`,
`oblivion.persistence`, `subprocess` or `os.system`. None do. The package may
import `PolicyEngine` — it must, to check a recommendation — and nothing else
that acts.

**By type.** `Advisory` has no field that can carry a decision. `advisory` is a
read-only property returning `True`, not a settable flag, so no construction
path — deserialization included — can make an advisory binding.

**By validation.** Output containing `authorized`, `approve`, `execute`,
`command`, `action`, `verdict`, `decision`, `certificate_result`,
`assurance_status`, `verification_status`, `target_path` or `actor_id` is
**refused**, not stripped.

**By absence, made discoverable.** `apply_is_not_supported()` exists as a raising
stub so that someone searching for a way to execute a recommendation finds the
explanation rather than concluding they have not found the right method yet.

## The output contract

A single JSON object. These fields, and no others:

| Field | Notes |
|---|---|
| `kind` | One of the four advisory kinds |
| `assessment` | Free text, ≤2000 chars, scanned for unsupported claims |
| `confidence` | 0..1. **Refused if outside** — never clamped |
| `factors` | Structured reasons, ≤20 items, also scanned |
| `evidence_ids` | Required for interpretations |
| `limitations` | Also scanned — a "limitation" asserting perfection is the most confusing possible place for such a claim |
| `recommended_policy_id` | A *suggestion*, checked by `PolicyEngine` |
| `sensitivity` | One of the nine classes |

Unknown fields are refused: a model inventing a field misunderstood the
contract, and dropping it silently would hide that.

Confidence outside 0..1 is refused rather than clamped, because clamping records
a confidence the model never expressed.

### No hidden reasoning

`reasoning`, `rationale`, `chain_of_thought`, `thoughts`, `thinking`,
`scratchpad`, `internal_monologue`, `deliberation` and `analysis_steps` are all
refused. Structured `factors` are what a reviewer needs; hidden reasoning is not
something this system stores.

## Claims that are refused outright

Thirteen patterns, matched case-insensitively against `assessment`, `factors`
and `limitations`:

guaranteed unrecoverable · 100% secure/deleted/erased · impossible to recover ·
cannot be recovered · unrecoverable by any · physically erased/destroyed/
sanitized · NAND erased/wiped · military-grade · DoD 5220 · permanently
destroyed · forensically clean · no trace remains · zero risk of recovery

These are refused because **this system cannot support them**: the privileged
service performs no overwrite, opens no raw volume handle and examines no
physical medium. A caveat placed next to a confident false claim does not undo
it, so the output is rejected instead.

Accurate scoped language remains sayable, and a test pins that — otherwise the
validator would push authors toward vagueness:

> "Filesystem enumeration did not reach the content. This describes that method
> only; carving and journal analysis were not attempted."

## Availability

| Situation | Result |
|---|---|
| No provider configured | `NullProvider`, status `UNAVAILABLE` with a reason |
| Unknown provider name | `NullProvider` — never silently substitutes another model |
| Local weights or runtime missing | `UNAVAILABLE` with the reason |
| Provider raises | `UNAVAILABLE`; an advisory failing must never fail an erasure |
| Model answered badly | `REJECTED` with reasons |

`UNAVAILABLE` and `REJECTED` stay distinct: one says no model answered, the
other says one answered badly. Only the second is a signal about model quality,
and Phase 27 measures it.

**The pipeline runs without AI.** Deterministic policy, safety validation and
evidence are the authoritative path; the model only ever explains and suggests.

## Provider configuration

| Variable | Meaning |
|---|---|
| `OBLIVION_AI_PROVIDER` | `none` (default), or `qwen`/`local-qwen`/`local` |
| `OBLIVION_AI_MODEL` | Model id recorded on every advisory |
| `OBLIVION_AI_MODEL_PATH` | Path to local weights |

`LocalQwenProvider` checks for weights on disk and an importable runtime before
claiming availability, and imports nothing at module scope — so the package
imports cleanly on a machine with no ML stack, which is every machine currently
running this test suite. The stated development target is 8 GB of VRAM, so a
quantized local build is the expected deployment; the provider reports what it
found and leaves the choice to the operator.

## What the advisor sends

Metadata only — name, size, type. **File contents are never sent to a model.**
Handing the data the system was asked to erase to a third component is the
opposite of the job, and `classify_sensitivity` has no parameter through which
contents could be passed.

## Recommendations

`SecurityAdvisor.recommend_policy` runs the model's suggestion past
`PolicyEngine.validate_operation_policy`. A policy that is not allowlisted, or
not compatible with the mode and target type, makes the whole result `REJECTED`
— so an unusable suggestion never reaches a human looking actionable.

AI recommendation ≠ authorization ≠ execution ≠ certificate result.

## Not implemented in this phase

- **The AI is not wired into the Phase 25 pipeline.** Deliberate: the pipeline's
  correctness must not depend on a component that may be unavailable, and
  nothing in the erasure path currently needs advice. Wiring it in means adding
  an advisory *field* to the result, never a decision input.
- **No hosted-provider adapter.** Only null, static (tests) and local Qwen.
- **No streaming or batching.** One prompt, one response.
- **No advisory persistence.** Advisories are returned, not stored; putting them
  in evidence needs a decision about whether model output belongs in a record
  that is meant to contain observations.
