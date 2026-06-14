"""Real browser UI smoke checks for PaperHunter.

Requires the optional Python Playwright package and browser runtime:
  pip install playwright
  python -m playwright install chromium

Run against a live server:
  python tests/e2e_ui.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Python Playwright is not installed. Install it with: "
            "pip install playwright && python -m playwright install chromium"
        ) from exc
    return sync_playwright


def run(base_url: str, headless: bool = True) -> dict:
    sync_playwright = require_playwright()
    checks: list[dict] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector("#copyDiagnosticsButton", timeout=15000)
        title = page.title()
        assert title == "PaperHunter", f"unexpected title: {title}"
        checks.append({"name": "page-load", "title": title})

        page.locator("#copyDiagnosticsButton").click()
        page.wait_for_function(
            "() => document.querySelector('#message')?.textContent.includes('安全诊断摘要')",
            timeout=15000,
        )
        message = page.locator("#message").inner_text(timeout=5000)
        assert "安全诊断摘要" in message, message
        checks.append({"name": "copy-diagnostics", "message": message})

        page.locator("#showTaskCenterButton").click()
        page.wait_for_selector(".task-center-dialog", timeout=10000)
        task_title = page.locator(".task-center-dialog h3").inner_text(timeout=5000)
        task_count = page.locator(".task-center-dialog .diagnostics-detail-item").count()
        assert task_title == "任务中心", task_title
        checks.append({"name": "task-center", "tasks": task_count})
        page.locator(".task-center-dialog").get_by_role("button", name="关闭").click()

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / "paperhunter-ui-smoke.zip"
            settings = {
                "provider": "custom",
                "apiType": "chat_completions",
                "baseUrl": "https://example.test",
                "endpoint": "/v1/chat/completions",
                "model": "ui-smoke-model",
                "apiKey": "sk-ui-smoke",
            }
            with zipfile.ZipFile(backup_path, "w") as zip_file:
                zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1}))
                zip_file.writestr("data/settings.json", json.dumps(settings))
                zip_file.writestr("downloaded_papers/ui-smoke.pdf", b"%PDF ui smoke")
            page.locator("#importBackupInput").set_input_files(str(backup_path))
            page.wait_for_selector(".backup-preview-dialog", timeout=15000)
            backup_text = page.locator(".backup-preview-dialog").inner_text(timeout=5000)
            assert "导入备份预览" in backup_text
            assert "创建恢复点并导入" in backup_text
            assert "API Key" in backup_text
            checks.append({"name": "backup-preview", "dialog": True})
            page.locator(".backup-preview-dialog").get_by_role("button", name="取消").click()

        page.locator("#showZoteroBridgeHelpButton").click()
        page.wait_for_selector(".zotero-bridge-help-dialog", timeout=10000)
        bridge_text = page.locator(".zotero-bridge-help-dialog").inner_text(timeout=5000)
        assert "Bridge 安装与排障" in bridge_text
        assert "复制 XPI 路径" in bridge_text
        assert "下载 XPI" in bridge_text
        steps = page.locator(".zotero-bridge-help-dialog .bridge-wizard-step").count()
        assert steps == 4, f"expected 4 bridge wizard steps, got {steps}"
        checks.append({"name": "bridge-wizard", "steps": steps})
        browser.close()
    return {"baseUrl": base_url, "checks": checks}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(args.base_url, headless=not args.headed)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
