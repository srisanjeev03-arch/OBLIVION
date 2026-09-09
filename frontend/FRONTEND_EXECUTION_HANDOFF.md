# OBLIVION FRONTEND — EXECUTION HANDOFF

Use FRONTEND_MASTER_BUILD_PROMPT.md as the master prompt.

Run the frontend agent from the actual frontend repository.

FIRST RUN:
Only perform reconnaissance + shell/API foundation.

Do not ask the agent to build every page in one generation.

RESPONSIBILITY SPLIT

Frontend:
- UI
- routing
- workflow presentation
- API calls
- evidence visualization
- loading/error/empty states
- UI preferences

Backend:
- target validation
- deletion
- recovery
- residual analysis
- cryptography
- authorization
- evidence generation
- certificate signing/verification
- security decisions

SECURITY:
Never move backend responsibilities into browser code.

Do not fabricate API endpoints or production data.

If backend capability is missing, render UNAVAILABLE and keep the UI integration-ready.

Recommended build order:
1. Shell
2. Design system
3. API boundary
4. Overview
5. Targets
6. Operations
7. Erasure
8. Recovery Vault
9. Recovery
10. Residual Analysis
11. Assurance
12. Certificates
13. Audit
14. Accessibility/responsive
15. Visual polish
16. Production audit
