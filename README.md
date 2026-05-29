<div align="center">
  <h1>PaperHunter</h1>
  <p><strong>A local research paper discovery and PDF download workspace for researchers.</strong></p>
  <p>
    English · <a href="README.zh-CN.md">简体中文</a>
  </p>
  <p>
    <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue"></a>
    <a href="https://github.com/Jia0808/PaperHunter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Jia0808/PaperHunter/actions/workflows/ci.yml/badge.svg"></a>
    <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12%2B-3776AB">
    <img alt="Local first" src="https://img.shields.io/badge/local--first-research-2F6FED">
  </p>
</div>

![PaperHunter dashboard](docs/assets/paperhunter-dashboard.png)

## Why PaperHunter

PaperHunter helps researchers search across multiple open paper sources, filter results with research-oriented controls, and download public open-access PDFs into a local folder. It is designed as a practical literature discovery tool rather than a crawler that bypasses access controls.

The project uses a plain Python backend and a native HTML/CSS/JavaScript frontend. It does not require a database, account system, or cloud service.

## Highlights

- Multi-source search across international and domestic open sources.
- Research-friendly filters for intent, field, year range, author, venue, match scope, arXiv category, and downloadable-only results.
- Per-source result limits, so one large source does not dominate the list.
- Local PDF download with duplicate detection.
- Local paper inbox for favorites, ignored papers, reading status, tags, notes, recent searches, download status, and full-text translation state, stored in `data/library.json`.
- Model settings panel for OpenAI-compatible Responses/Chat Completions endpoints, DeepSeek, Anthropic, and custom providers.
- Abstract translation for a single paper or a batch of favorites, with stale-translation detection when source abstracts change.
- BibTeX, Markdown reading-list, and bilingual English/Chinese summary exports for saved favorites or individual papers.
- Full-text translation for downloaded PDFs, with resumable chunk tasks, progress tracking, bilingual Markdown output, and an action to open the translated file location.
- Favorite metadata refresh to update older saved records and recover full abstracts when available; ChinaRxiv results can hydrate truncated feed abstracts from detail pages.
- Workspace backup and import for local library data, downloads, translated papers, and translation tasks. API keys are stripped from backups.
- External gateway buttons for Google Scholar, CNKI, Wanfang, X-MOL, Nature, Science, and other sources that usually require login, institutional permission, payment, robots.txt restrictions, or CAPTCHA.
- Local-first workflow: downloaded PDFs stay under `downloaded_papers/`, translated Markdown stays under `translated_papers/`, and library/settings state stays under `data/`; these runtime paths are ignored by Git.
- Lightweight stack: Python 3.12, `requests`, `arxiv`, and browser-native frontend code.

## Supported Sources

| Source | Search | PDF Download | Notes |
| --- | --- | --- | --- |
| arXiv | Yes | Yes | Uses the arXiv package/API. |
| Semantic Scholar | Yes | Public open PDFs only | Subject to Semantic Scholar rate limits. |
| CVF Open Access | Yes | Yes | Searches public CVF Open Access pages. |
| ACL Anthology | Yes | Yes | Uses ACL Anthology metadata/cache. |
| OpenReview | Yes | Public open PDFs only | Some PDFs may require validation by the host. |
| ChinaRxiv / ChinaXiv | Yes | Public open PDFs only | Domestic open paper source; detail pages are used when feed abstracts are truncated. |
| SciOpen | Yes | Public open PDFs only | Domestic/open-access source. |
| National Science Open | Yes | Public open PDFs only | Open journal source. |
| Google Scholar, CNKI, Wanfang, X-MOL, Nature, Science | External gateway only | No automated download | These sources may require manual browsing, login, authorization, payment, robots.txt compliance, or human verification. |

## Quick Start

Python 3.12 or newer is recommended.

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

## Model Configuration

PaperHunter can translate abstracts and downloaded full text through a model endpoint that you configure locally in the UI.

Supported presets include:

- APIXIN GPT-compatible endpoints
- DeepSeek Chat Completions
- Anthropic Messages
- custom OpenAI-compatible Responses or Chat Completions endpoints

Model settings are saved to `data/settings.json`, which is ignored by Git. The public status API returns only a masked key, and workspace backups intentionally remove the API key before writing `data/settings.json` into the backup ZIP.

Translation requests send the selected abstract or full-text chunk to the configured model provider. PaperHunter does not query your account balance and does not send papers for translation unless you trigger a translation action.

## Typical Workflow

1. Enter a research keyword or phrase.
2. Select research intent, field, year range, source group, and per-source limit.
3. Run the search and review metadata, venues, years, and PDF availability.
4. Save useful papers to the local inbox, ignore papers you do not want to see again, and optionally add reading status, tags, or notes.
5. Configure a model endpoint if you want abstract or full-text translation.
6. Translate one abstract, batch-translate favorite abstracts, or retranslate stale summaries after metadata changes.
7. Export saved favorites as BibTeX, a Markdown reading list, or a bilingual English/Chinese summary file.
8. Download selected open-access PDFs or batch-download downloadable results.
9. Translate downloaded full text into bilingual Markdown, monitor chunk progress, and open the output folder when the task is complete.
10. Refresh favorite metadata when older saved items show truncated abstracts.
11. Export a workspace backup before moving machines or cleaning local runtime data.
12. Use external gateway buttons when a source needs browser-side login or institution access.

## Project Structure

```text
app.py                    Python HTTP server, source adapters, filters, downloads
web/index.html            Browser UI structure
web/styles.css            UI styling
web/app.js                Frontend state, filters, API calls
data/                     Local library, model settings, and task state, ignored by Git
data/fulltext_tasks/      Resumable full-text translation task state, ignored by Git
downloaded_papers/        Local PDF output directory, ignored by Git
translated_papers/        Bilingual Markdown full-text translation output, ignored by Git
docs/assets/              README and documentation images
tests/                    Backend regression tests
.github/workflows/ci.yml  Syntax checks for Python and JavaScript
```

## Development Checks

```bash
python -m py_compile app.py
python -m unittest discover -s tests
node --check web/app.js
```

## Local Data and Backups

PaperHunter is local-first, but some actions intentionally call external services:

- search requests call the selected public paper sources
- abstract and full-text translation requests call the model endpoint you configured
- external gateway buttons open third-party websites in your browser

Local runtime data is ignored by Git:

- `data/library.json` stores favorites, ignored papers, metadata, tags, notes, translations, and recent searches
- `data/settings.json` stores local model settings and may contain an API key
- `data/fulltext_tasks/` stores resumable translation task progress
- `downloaded_papers/` stores downloaded PDFs
- `translated_papers/` stores bilingual Markdown full-text translations

The workspace backup feature exports local library data, downloaded PDFs, translated papers, and full-text task state. It includes model settings without the API key, so API credentials must be re-entered after restoring a backup.

## Compliance

PaperHunter only attempts automated downloads from open PDF URLs or public open-access endpoints. It does not bypass paywalls, authentication, CAPTCHA, institutional access controls, or publisher restrictions.

Sources such as Google Scholar, CNKI, Wanfang, X-MOL, Nature, Science, and similar websites may require manual browsing, login, institutional authorization, payment, robots.txt compliance, or human verification. PaperHunter exposes them only as external browser entry points where appropriate.

See [DISCLAIMER.md](DISCLAIMER.md) for details.

## Repository Safety

If you publish this repository on GitHub, review [docs/REPOSITORY_SAFETY.md](docs/REPOSITORY_SAFETY.md). At minimum:

- enable two-factor authentication on the owner account
- protect the `main` branch
- disallow force pushes and branch deletion
- avoid granting collaborator `Admin` permissions unless necessary
- keep a local mirror backup

## Contributing

Issues and pull requests are welcome. Please keep source integrations compliant with each website's terms of service and avoid adding logic that bypasses access restrictions.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution guide and [SECURITY.md](SECURITY.md) for security reporting.

## License

Apache License 2.0. See [LICENSE](LICENSE).
