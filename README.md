# PaperHunter

PaperHunter is a local research paper discovery and PDF download workspace.

It provides a browser-based UI for searching open paper sources, filtering research results, and downloading public open-access PDFs into a local folder.

## Features

- Multi-source search across arXiv, Semantic Scholar, CVF Open Access, ACL Anthology, OpenReview, ChinaRxiv / ChinaXiv, SciOpen, and National Science Open.
- Research-oriented filters: intent, field, year range, downloadable-only mode, author, venue, match scope, and arXiv categories.
- Per-source result control, so selecting more sources does not let one source dominate the result list.
- Local PDF download with duplicate detection.
- External gateway buttons for sources that usually require login, institutional permission, payment, or CAPTCHA.
- Plain Python backend plus native HTML/CSS/JavaScript frontend. No database is required.

## Supported Sources

| Source | Search | PDF Download | Notes |
| --- | --- | --- | --- |
| arXiv | Yes | Yes | Uses the arXiv package/API. |
| Semantic Scholar | Yes | Public open PDFs only | Subject to Semantic Scholar rate limits. |
| CVF Open Access | Yes | Yes | Searches public CVF Open Access pages. |
| ACL Anthology | Yes | Yes | Uses ACL Anthology metadata/cache. |
| OpenReview | Yes | Public open PDFs only | Some PDFs may require validation by the host. |
| ChinaRxiv / ChinaXiv | Yes | Public open PDFs only | Domestic open paper source. |
| SciOpen | Yes | Public open PDFs only | Domestic/open-access source. |
| National Science Open | Yes | Public open PDFs only | Open journal source. |
| CNKI, Wanfang, X-MOL | External gateway only | No automated download | These sources often require login, authorization, payment, or human verification. |

## Quick Start

Python 3.12 is recommended.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:8000
```

On Windows, you can also run:

```bat
start_paperhunter.bat
```

## Project Structure

```text
app.py                    Python HTTP server, search adapters, filters, downloads
web/index.html            Browser UI structure
web/styles.css            UI styling
web/app.js                Frontend state, filters, API calls
downloaded_papers/        Local PDF output directory, ignored by Git
.github/workflows/ci.yml  Syntax checks for Python and JavaScript
```

## Local Data

PDF files are saved to:

```text
downloaded_papers/
```

This directory is ignored by Git. Do not commit downloaded papers, cache files, cookies, credentials, or local environment paths.

## Development Checks

```bash
python -m py_compile app.py
node --check web/app.js
```

## Repository Safety

If you publish this repository on GitHub, review [docs/REPOSITORY_SAFETY.md](docs/REPOSITORY_SAFETY.md). At minimum:

- enable two-factor authentication on the owner account
- avoid granting collaborator `Admin` permissions
- protect the `main` branch
- disallow force pushes and branch deletion
- keep a local mirror backup

## Disclaimer

PaperHunter is intended for personal research workflow automation and open-access literature discovery. It does not bypass paywalls, login systems, CAPTCHA, institutional authorization, or publisher access controls.

See [DISCLAIMER.md](DISCLAIMER.md) for details.

## License

Apache License 2.0. See [LICENSE](LICENSE).
