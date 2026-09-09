# Omniroute Integration

## Purpose

Omniroute is an AI routing/provider layer used by the Oblivion backend.

## Design

Create an internal abstraction:

```text
AIProvider
  ├── OmnirouteProvider
  └── LocalProvider (optional)
```

Application services depend on `AIProvider`, not directly on Omniroute.

## Configuration

Use environment variables such as:
- AI_PROVIDER
- OMNIROUTE_BASE_URL
- OMNIROUTE_MODEL

Do not hard-code API keys.

## Requirements

- request timeout
- bounded retries
- structured output
- schema validation
- model/provider metadata
- redaction
- no tool access for destructive operations
- safe fallback

## Important

Do not assume a particular Omniroute configuration, model name, API key or Claude Code setting.

Read the user's actual environment/configuration before changing integration settings.

## Failure

If Omniroute is unavailable:
- deterministic sensitive-data rules may continue
- AI-specific fields should become unavailable/unknown
- destructive policy execution must remain deterministic
