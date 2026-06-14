# PaperHunter validation

Use this checklist before testing with a real Zotero desktop profile or a real model API key.

## Browser smoke test

Run PaperHunter locally, then verify these flows in a browser:

1. Open `/` and confirm the page title is `PaperHunter`.
2. Check the console for JavaScript errors. The initial Alert inbox, Zotero, and Runtime Health panels should load without errors.
3. Import an Alert with review enabled:
   - Keep `先加入 Alert 收件箱审阅，再由我确认采用` checked.
   - Leave open metadata lookup unchecked unless you are specifically testing metadata enrichment.
   - Submit a record with `Title`, `DOI`, and `Abstract`.
   - After the status request finishes, Alert inbox should show one pending/adoptable item and the batch adopt button should be enabled.
4. Import an Alert with review disabled through the API or UI:
   - The paper should be added to favorites directly.
   - No new pending Alert inbox event should be created.
5. Download `/api/zotero/bridge-xpi`:
   - HTTP status should be `200`.
   - Content type should be `application/x-xpinstall`.
   - The first bytes should be ZIP magic `PK`.
6. Confirm API shadow routes return `404`:
   - `/api/status-extra`
   - `/api/zotero/bridge-xpi-extra`
   - POST `/api/search-extra`
7. Check a mobile viewport around `390x844`:
   - No horizontal overflow.
   - Alert inbox, Zotero, and search controls remain reachable.

You can also run the real HTTP smoke script against the running app:

```powershell
venv\Scripts\python.exe tests\e2e_smoke.py --base-url http://127.0.0.1:8000
```

The default smoke run is read-only except for downloading the Bridge XPI from
the local server. To exercise a real subscription-source write in the current
workspace, add `--mutate`:

```powershell
venv\Scripts\python.exe tests\e2e_smoke.py --base-url http://127.0.0.1:8000 --mutate
```

The script checks `/api/status`, `/api/diagnostics`, the Bridge XPI package,
and API shadow-route 404 behavior. It also verifies the diagnostics safe report
is present and marked as not containing raw secrets.

When Python Playwright is installed, run the real UI click smoke:

```powershell
venv\Scripts\python.exe tests\e2e_ui.py --base-url http://127.0.0.1:8000
```

This opens a real Chromium page, clicks Runtime Health diagnostics copy, Task
Center, and the Bridge installer wizard.

Install the optional UI smoke dependency only when you need this browser check:

```powershell
venv\Scripts\python.exe -m pip install playwright
venv\Scripts\python.exe -m playwright install chromium
```

## Backup import validation

Before importing a backup into an important workspace:

1. Choose the backup ZIP from the UI.
2. Confirm the in-app preview dialog lists:
   - library/settings presence
   - full-text task, downloaded PDF, and translated Markdown counts
   - the API Key removal warning
   - the Bridge reinstall warning when settings are present
3. Click `创建恢复点并导入`.
4. Confirm the success message includes a restore-point id.
5. If settings were imported, refresh Zotero/Bridge status and reinstall the
   current Bridge XPI before attempting a write-back.

Backend import creates a private local restore point under `.cache` before
writing workspace files. If import raises after writing begins, the backend
attempts to restore library, settings, task files, downloaded PDFs, and
translated Markdown from that restore point.

## Zotero Bridge dry run

Before installing the XPI into a real Zotero profile:

1. Download the XPI from the current PaperHunter instance.
2. Confirm PaperHunter reports a valid Bridge package and a configured pairing token.
3. Install the XPI in Zotero, restart Zotero, then refresh PaperHunter.
4. The Zotero panel should report Bridge compatibility and pairing support.
5. Run a sync preview/dry-run before any real write-back.

The Bridge should only write PaperHunter-managed sync notes, `paperhunter:*` tags, and translated Markdown attachments under PaperHunter output paths.

## Real release-candidate run

For the June 2026 release-candidate pass, the following real data was kept in
the local workspace and Zotero profile for inspection:

- `PaperHunter Chrome UI Alert E2E 202606150145UI`: imported through the Chrome UI, entered the Alert inbox, then was adopted and locked from the browser.
- `PaperHunter Full Chain Alert E2E 20260615013517`: imported as a user-visible Alert, adopted, translated through the configured model endpoint, saved to Zotero, and synced back through Bridge `0.2.2`.
- Zotero item `DPLL37WM` / itemID `11` received PaperHunter noteID `12` and tags `paperhunter`, `paperhunter:abstract-translated`, and `paperhunter:imported`.
- A read-only Zotero SQLite snapshot confirmed the managed note contains the English abstract, Chinese abstract, and PaperHunter sync marker.

The diagnostics status may remain `attention` when older favorites are missing
abstract translations. This is expected data debt and does not indicate a
Zotero Bridge or Alert workflow failure.

## Final checks

Run:

```powershell
venv\Scripts\python.exe -m py_compile app.py tests\e2e_smoke.py tests\e2e_ui.py tests\test_frontend_static.py
venv\Scripts\python.exe -m unittest discover -s tests
node --check web\app.js
node --check zotero-bridge\bootstrap.js
venv\Scripts\python.exe tests\e2e_smoke.py --base-url http://127.0.0.1:8000
venv\Scripts\python.exe tests\e2e_ui.py --base-url http://127.0.0.1:8000
git diff --check HEAD
```
