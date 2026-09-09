# Test Plan

## Environment

Use:
- Windows
- NTFS
- isolated test volume or VM
- known test corpus

Never use personal data for destructive testing.

## Test stages

### Baseline
1. create known file
2. hash it
3. perform ordinary delete
4. demonstrate supported recovery

### Permanent deletion
1. analyze
2. dry-run
3. execute
4. verify state
5. run recovery test
6. scan residuals
7. calculate assurance
8. generate certificate

### Recoverable deletion
1. hash source
2. create encrypted recovery object
3. delete original
4. confirm original unavailable
5. attempt unauthorized restore
6. authorize restore
7. restore
8. compare SHA-256

### Certificate
- valid certificate verifies
- changed evidence fails verification
- changed signature fails verification

### Security
- traversal rejected
- system drive protected
- invalid policy rejected
- unauthorized restore blocked
- malformed AI response rejected
- AI timeout falls back safely
- vault key not exposed

### Failure tests
- source disappears during operation
- target changes
- permission denied
- disk full
- vault write failure
- recovery test inconclusive
- residual scan error
