# AI Specification

## Principle

AI improves analysis and explanation. Deterministic security code remains authoritative.

## 1. Sensitive Data Discovery

Hybrid pipeline:
- regex
- structured parsers
- NER where useful
- lightweight classification
- deterministic rules

Possible categories:
- names
- phone numbers
- emails
- addresses
- financial information
- customer records
- employee records
- confidential/legal content
- credential-like data

Example:
```text
customer_database.csv
Names: 14,820
Phones: 14,617
Emails: 13,982
Sensitivity: CRITICAL
```

## 2. Residual Classification

Input:
- residual filename
- metadata
- fragment information
- hashes/similarity where supported
- timestamps
- directory relationships

Output:
- artifact type
- relationship hypothesis
- sensitivity
- qualitative risk
- explanation

## 3. Recovery Risk

Factors:
- filesystem
- storage type
- encryption state
- deletion method
- TRIM-related observations where measurable
- allocation characteristics
- residual findings
- actual recovery result

Risk levels:
LOW, MEDIUM, HIGH, INCONCLUSIVE

Do not fabricate recovery percentages.

## 4. Policy Recommendation

AI recommends from an allowlist.

Example:
```text
Target: employee_records.db
Sensitivity: CRITICAL
Storage: SSD
Recommended:
1. application-level cleanup
2. cryptographic key handling
3. logical erasure
4. residual verification
5. recovery test
```

The deterministic policy engine decides what can actually execute.

## 5. Omniroute integration

Implement an AI provider adapter:
- timeout
- retry policy
- schema validation
- model/provider metadata
- redaction/minimization
- no destructive tool access

Never send plaintext sensitive file contents unless explicitly required and approved. Prefer metadata/features/local inference.

## Evaluation

Track:
- precision
- recall
- false-positive rate
- false-negative rate
- calibration/consistency
- latency

AI failure must degrade safely to deterministic analysis.
