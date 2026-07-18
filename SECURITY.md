# Security Policy

## Supported versions

Security fixes are applied to the latest released version and the current `main` branch. Older releases may not receive backports.

## Reporting a vulnerability

Please do not disclose vulnerabilities, credentials, or exploit details in a public issue.

Use [GitHub private vulnerability reporting](https://github.com/Drlinglong/Remis/security/advisories/new) to send a private report. Include:

- the affected version or commit;
- reproduction steps or a minimal proof of concept;
- the expected and actual security boundary;
- any known impact or suggested mitigation.

This is a volunteer-maintained open-source project. Reports will be acknowledged as capacity allows, and valid findings will be prioritized by severity and exploitability.

## Scope notes

Remis processes local mod files and may connect to user-configured model providers. Reports involving path traversal, unsafe file writes, credential exposure, dependency compromise, or untrusted model output crossing a hard validation boundary are especially useful.
