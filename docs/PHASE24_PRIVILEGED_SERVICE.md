# Phase 24 — Privileged Execution Boundary

Status of this document: it describes what is **implemented and tested** in this
tree. Anything not yet built is named as such under "Not implemented".

## Why this exists

The FastAPI process runs unprivileged. Operations needing more authority are
*described* to a separate service, which decides for itself whether to perform
them. The API can therefore be compromised without the attacker inheriting
unrestricted filesystem authority: they inherit only the ability to ask, and
every ask is re-checked against the privileged process's own configuration.

```
Frontend
   → FastAPI  (unprivileged)
   → Authentication / RBAC
   → Policy
   → Safety validation
   → Operation authorization
   → Authenticated IPC          ← the boundary
   → Oblivion privileged service
   → Windows filesystem primitives
```

## The operation allowlist

Six operations, and nothing else (`privileged/protocol.py`):

| Operation | Kind | Effect |
|---|---|---|
| `inspect_target` | read | Analyses one validated target |
| `scan_scope` | read | Storage profile for a validated scope |
| `delete_file` | destructive | Unlinks one validated file |
| `delete_tree` | destructive | Removes one validated directory tree |
| `prepare_recovery_object` | destructive | Vaults an encrypted copy, then unlinks |
| `restore_recovery_object` | write | Restores a vault object to a new path |

There is no `execute_command`, no `powershell`, no `cmd`, no arbitrary
executable and no arbitrary script. A request naming anything outside this set
does not reach a handler — it fails at parse.

`tests/test_privileged_ipc.py` pins this two ways: the enum is asserted by
equality (a new privileged operation must be a deliberate change), and every
module in the package is scanned for execution constructs — `subprocess`,
`os.system`, `os.popen`, `os.exec`, `os.spawn`, `shell=True`, `eval(`, `exec(`,
`__import__(`. None are present.

## Wire protocol — `OBLIVION-PRIV-1`

Framing is a 4-byte big-endian length followed by UTF-8 JSON, capped at 1 MiB.
The pipe runs in **byte mode**: message mode would fail a prefix-sized read with
`ERROR_MORE_DATA`, and the length framing is what protects against a
desynchronised peer, so the framing stays and the mode gives way.

Envelope: `{"request": {...}, "mac": "<hmac-sha256 hex>"}`

### Request fields

| Field | Notes |
|---|---|
| `protocol_version` | Must equal `OBLIVION-PRIV-1` |
| `request_id`, `nonce` | Identifiers; the nonce is single-use |
| `operation` | Must be one of the six, exactly — no case folding, no trimming |
| `operation_id` | Ties the privileged act to a persisted operation |
| `policy_id`, `mode` | Re-validated against the allowlisted policy registry |
| `target_path`, `target_type` | `target_type` is `file` or `directory` |
| `expected_volume_serial`, `expected_file_id` | Target identity; required for destructive work |
| `actor_id` | **Attribution only** — see below |
| `issued_at` | ISO-8601, **timezone required**; a naive stamp is refused |
| `params` | Only what the named operation declares |

Parsing is total and fail-closed. Unknown fields are **refused, not ignored** —
a field the privileged side silently drops is a field the unprivileged side may
believe is being enforced.

Parameter names matching secret-material patterns (`vault_key`, `password`,
`api_key`, `private_key`, …) are refused by name before the value is read. The
service holds its own secrets; none cross the boundary.

### Response

`COMPLETED` / `REFUSED` / `FAILED`, plus `result`, `refusals` and `message`.

`REFUSED` and `FAILED` are deliberately distinct: refused means the boundary
declined and **nothing was touched**; failed means the operation was permitted,
attempted, and did not complete. An evidence record needs that distinction.

No traceback ever crosses the boundary — it would leak privileged-side paths to
a less-trusted process. Unexpected exceptions become `FAILED` with a message the
service chose and `reconciliation_required: true`.

## What authentication proves — and what it does not

Requests carry an HMAC-SHA256 over the **canonical request bytes** (the Phase 23
canonicalizer, so integrity is defined over exactly the bytes the service acts
on — a field cannot change between verification and use).

That proves the request came from a process holding the service key and was not
altered in transit.

**It does not prove which human is behind it.** A privileged service cannot
authenticate an end user. `actor_id` is carried for attribution and audit; it
grants nothing. The API derives it from the authenticated session and must never
take it from a request body or query parameter.

If the API process is compromised, the attacker inherits its authority — which
is exactly why the service still enforces containment, policy, target identity
and the operation allowlist itself, so that inherited authority is *bounded*
rather than total.

**There is no fallback key.** A service with no `OBLIVION_IPC_KEY` reports
`UNAVAILABLE_NO_KEY` and refuses everything. A default secret would be
indistinguishable from no authentication at all.

## What the service decides for itself

Per `docs/PRIVILEGE_BOUNDARY.md`, on every request:

1. Operation is in the allowlist
2. Request is fresh (default 5-minute window; future-dated is also refused)
3. An actor is named
4. Policy is allowlisted and compatible with the mode and target type
5. The operation maps to a permission in this deployment
6. Target normalization, containment in **the service's own allowed roots**,
   reparse/junction rejection, system-volume protection
7. Target identity matches for destructive work (the engine re-checks
   immediately before acting — that second check is what closes the TOCTOU
   window; this one refuses early and cheaply)
8. Restore destinations are validated and **must not already exist**

The service's allowed roots are the service's own. Nothing in a request can
contribute to, extend or override them. This is the single control that keeps a
compromised API from turning the service into a general-purpose file deleter.

Refusals accumulate so the response explains the whole picture, but one reason
is enough to refuse, and a "permitted" outcome carrying refusals cannot be
constructed — the invariant is asserted in the dataclass.

## Replay protection

A nonce is remembered for exactly as long as a request bearing it could still
pass the freshness check, so memory is bounded without opening a gap. A
correctly formed, correctly signed request is still refused on its second
arrival.

### Cache lifetime — process/service, **not** restart-persistent

Replay protection is **scoped to the lifetime of the cache object**, and nothing
longer. Stated precisely, per deployment:

| Deployment | Cache owner | Protection lasts |
|---|---|---|
| HTTP API (in-process transport) | `app.state.privileged_replay_cache`, created in `create_app()` | The life of the FastAPI application |
| Named-pipe host | The long-lived `PrivilegedService` the host constructs | The life of that host process |

The HTTP service object itself is rebuilt per request — it is cheap, and its
validator must track configuration — but the cache is injected into it via
`ServiceConfig.replay_cache` so that it is **not**. This was audit finding M-1:
before it, each request built its own empty cache, so no nonce was ever seen
twice and the control did nothing in the default deployment.

**There is no restart persistence, and none is claimed.** A restart empties the
cache, so a captured request stays replayable for the remainder of its freshness
window (default five minutes). Bounding that window is the mitigation; a
persistent nonce store is not implemented. Anyone requiring replay resistance
across restarts must shorten `max_request_age` or add persistence — the current
protocol does not provide it.

### Concurrency

`ReplayCache.remember` performs eviction, membership check and insert under one
lock, as a single atomic operation. The two halves are only a control together:
between a bare check and a bare insert, a second thread bearing the same nonce
would also see "not seen". A test releases 32 threads simultaneously on one
nonce and asserts exactly one is admitted.

### Bounds

Retention is bounded twice. Expiry is the ordinary mechanism — a nonce is
dropped once a request carrying it would be refused as stale anyway. A hard
ceiling (`ReplayCache.DEFAULT_MAX_ENTRIES`, 100 000) bounds memory by
construction rather than by an assumption about traffic.

At the ceiling the cache **refuses rather than evicting a live nonce**, raising
`ReplayCacheFull`, which the service turns into a refusal. Forgetting an
unexpired nonce to make room would silently re-open its replay window; a refused
legitimate request is recoverable, an accepted replay is not.

## Transports

| Transport | Isolation | Use |
|---|---|---|
| `InProcessTransport` | **None**, and says so via `isolated` | Tests, and development without a privileged host |
| `NamedPipeTransport` | Real process boundary | Deployment |

The pipe ACL is a security control, not configuration:
`D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;<creator SID>)` — SYSTEM, Administrators
and the creating account only, with a protected DACL so no inherited ACE can
widen it. A world-writable pipe would let any local process submit requests the
service would then dutifully authenticate.

Remote clients are rejected (`PIPE_REJECT_REMOTE_CLIENTS`). The server handles
one client at a time: privileged filesystem operations against a shared target
are not obviously safe to run concurrently, and serialising removes that race
entirely at a cost that does not matter here.

Clients wait briefly (default 5s) for a pipe that is starting up or busy, then
give up with `ServiceUnavailableError`. **Unreachable is not a refusal** — the
caller learned nothing about the request — and the distinct exception type keeps
callers from conflating them.

### A ctypes note

Every Win32 call declares `argtypes`/`restype`. This is not tidiness: undeclared
calls marshal handles as 32-bit ints, which silently truncates them on x64 and
produces failures that look like access-denied. A security boundary reporting a
misleading cause is worse than one that fails loudly.

## Configuration

| Variable | Meaning | Absent → |
|---|---|---|
| `OBLIVION_IPC_KEY` | Hex, ≥32 bytes | Service is `UNAVAILABLE_NO_KEY` and refuses all work |
| `OBLIVION_VAULT_KEY` | Hex, exactly 32 bytes | `recovery_vault` capability is `UNAVAILABLE` |
| `OBLIVION_VAULT_ROOT` | Vault directory | `recovery_vault` capability is `UNAVAILABLE` |

A wrong-length vault key is treated as **absent**, never padded, stretched or
hashed into shape: silently deriving a key from malformed input would make a
misconfiguration look like a working vault.

## Capability reporting

The service reports what actually works here:

| Capability | State | Why |
|---|---|---|
| `logical_file_deletion` | SUPPORTED | Unlink after identity revalidation |
| `logical_tree_deletion` | SUPPORTED | Tree removal, logical only |
| `media_sanitization` | **UNAVAILABLE** | No overwrite, block-level or device sanitization is performed. This build cannot and does not claim physical irrecoverability. |
| `recovery_vault` | Follows configuration | AES-256-GCM with verified round-trip when configured |
| `raw_volume_access` | **UNAVAILABLE** | No raw physical-drive handles are opened. Recovery testing is filesystem-level, not media-level. |

`UNAVAILABLE` means the environment cannot provide it — **not** that it silently
degrades to something weaker.

## Not implemented in this phase

- **Durable operation-state reconciliation.** A timeout or unexpected exception
  returns `reconciliation_required: true`, because a filesystem call cannot be
  recalled once it has returned. Persisting and reconciling that against the
  operation record is the next piece of work, not something this phase claims.
- **A packaged Windows service host.** `NamedPipeServer.serve_forever()` is the
  loop; installing it as a service under a separate account is deployment work.
- **Cooperative cancellation of in-flight destructive work.** `CancellationToken`
  exists and is only safe to check between whole items — never mid-write. A
  half-completed destructive operation would leave the filesystem and the
  persisted state disagreeing, which is worse than finishing.
