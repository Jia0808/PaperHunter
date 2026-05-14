# Security Policy

## Reporting a Vulnerability

Please do not open a public issue for security-sensitive reports.

Send a private report to the repository owner, or use GitHub's private vulnerability reporting if it is enabled for the repository.

## Scope

Security issues include:

- unsafe file writes outside `downloaded_papers/`
- path traversal in downloaded filenames
- accidental credential exposure
- unsafe execution of remote content
- behavior that bypasses access controls on third-party services

## Data Handling

PaperHunter is a local tool. It does not require API keys by default and stores downloaded PDFs locally in `downloaded_papers/`.

Never commit local runtime data, credentials, cookies, browser profiles, or downloaded papers.
