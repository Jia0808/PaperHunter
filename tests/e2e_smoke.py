"""Real HTTP smoke checks for a running PaperHunter server.

Run with:
  python tests/e2e_smoke.py --base-url http://127.0.0.1:8000

Pass --mutate to exercise real subscription-source, Alert inbox, and Zotero
dry-run writes against the current workspace. Without --mutate the script only
reads endpoints and downloads the Bridge XPI.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from io import BytesIO


def request_json(base_url: str, path: str, payload: dict | None = None, timeout: int = 20) -> tuple[int, dict]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"ok": False, "error": body}
        return exc.code, parsed


def request_bytes(base_url: str, path: str, timeout: int = 20) -> tuple[int, str, bytes]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(base_url: str, mutate: bool = False) -> dict:
    results: dict[str, object] = {"baseUrl": base_url, "mutate": mutate, "checks": []}

    status_code, status = request_json(base_url, "/api/status", timeout=30)
    assert_true(status_code == 200 and status.get("ok"), f"/api/status failed: {status_code} {status}")
    bridge = ((status.get("zotero") or {}).get("bridge") or {})
    model_settings = status.get("modelSettings") or {}
    results["checks"].append({
        "name": "status",
        "downloadedCount": status.get("downloadedCount"),
        "bridgeCompatible": bool(bridge.get("compatible")),
        "bridgeVersion": bridge.get("version") or "",
        "expectedBridgeVersion": bridge.get("expectedVersion") or "",
        "modelApiType": model_settings.get("apiType") or "",
        "modelHasApiKey": bool(model_settings.get("hasApiKey")),
    })

    status_code, diagnostics = request_json(base_url, "/api/diagnostics", timeout=30)
    assert_true(status_code == 200 and diagnostics.get("ok"), f"/api/diagnostics failed: {status_code} {diagnostics}")
    safe_report = diagnostics.get("safeReport") or {}
    assert_true(safe_report.get("privacy", {}).get("containsRawSecrets") is False, "safeReport privacy flag is missing")
    assert_true("安全诊断摘要" in str(safe_report.get("text") or ""), "safeReport text is missing")
    results["checks"].append({
        "name": "diagnostics",
        "status": diagnostics.get("status"),
        "fulltextTasks": ((diagnostics.get("fulltext") or {}).get("counts") or {}).get("total", 0),
        "safeReportChars": len(str(safe_report.get("text") or "")),
    })

    xpi_path = "/api/zotero/bridge-xpi?version=e2e-smoke"
    status_code, content_type, content = request_bytes(base_url, xpi_path, timeout=30)
    assert_true(status_code == 200, f"Bridge XPI returned HTTP {status_code}")
    assert_true("application/x-xpinstall" in content_type.lower(), f"Unexpected XPI content type: {content_type}")
    assert_true(content.startswith(b"PK"), "Bridge XPI is not a ZIP/XPI package")
    with zipfile.ZipFile(BytesIO(content), "r") as zip_file:
        manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
        bootstrap = zip_file.read("bootstrap.js").decode("utf-8")
    assert_true("/paperhunter/pairing-check" in bootstrap, "Bridge XPI is missing pairing-check endpoint")
    assert_true("__PAPERHUNTER_BRIDGE_TOKEN__" not in bootstrap, "Bridge XPI still contains token placeholder")
    results["checks"].append({
        "name": "bridge-xpi",
        "version": manifest.get("version"),
        "bytes": len(content),
        "pairingCheck": True,
    })

    status_code, shadow = request_json(base_url, "/api/status-extra", timeout=10)
    assert_true(status_code == 404 and shadow.get("ok") is False, "shadow GET route should return 404")
    status_code, shadow = request_json(base_url, "/api/search-extra", {"query": "test"}, timeout=10)
    assert_true(status_code == 404 and shadow.get("ok") is False, "shadow POST route should return 404")
    results["checks"].append({"name": "shadow-routes", "ok": True})

    preview_buffer = BytesIO()
    with zipfile.ZipFile(preview_buffer, "w") as zip_file:
        zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1}))
        zip_file.writestr("data/settings.json", json.dumps({
            "provider": "custom",
            "apiType": "chat_completions",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/chat/completions",
            "model": "e2e-smoke-model",
            "apiKey": "sk-e2e-smoke",
        }))
        zip_file.writestr("downloaded_papers/e2e-smoke.pdf", b"%PDF e2e smoke")
    status_code, preview = request_json(base_url, "/api/backup/preview", {
        "contentBase64": base64.b64encode(preview_buffer.getvalue()).decode("ascii"),
    }, timeout=20)
    assert_true(status_code == 200 and preview.get("ok"), f"backup preview failed: {preview}")
    assert_true(preview.get("impact", {}).get("restorePointWillBeCreated") is True, "backup preview should declare restore point")
    assert_true(preview.get("impact", {}).get("bridgeReinstallRequired") is True, "settings preview should require Bridge reinstall")
    results["checks"].append({
        "name": "backup-preview",
        "downloaded": preview.get("files", {}).get("counts", {}).get("downloaded", 0),
        "bridgeReinstallRequired": True,
    })

    if mutate:
        source_id = f"e2e-smoke-{int(time.time())}"
        payload = {
            "action": "upsert",
            "source": {
                "id": source_id,
                "name": "E2E Smoke Source",
                "provider": "custom",
                "mode": "manual-alert",
                "enabled": True,
                "url": "https://example.test/alerts",
            },
        }
        status_code, source_response = request_json(base_url, "/api/subscription/sources", payload, timeout=20)
        assert_true(status_code == 200 and source_response.get("ok"), f"subscription source write failed: {source_response}")
        found = any(item.get("id") == source_id for item in source_response.get("sources") or [])
        assert_true(found, "created subscription source was not returned")
        results["checks"].append({"name": "subscription-source-write", "id": source_id})

        doi_suffix = int(time.time())
        alert_text = f"""
        Web of Science Alert
        Title: E2E Alert Workflow {doi_suffix}
        Authors: Ada Lovelace; Alan Turing
        Journal: Journal of Smoke Tests
        Year: 2026
        DOI: 10.1234/e2e.alert.{doi_suffix}
        Abstract: This complete alert abstract is visible to the user and should be staged before adoption. It is long enough to be classified as a complete candidate during the Alert inbox review flow.
        URL: https://example.test/e2e-alert-{doi_suffix}
        """
        status_code, imported = request_json(base_url, "/api/alert/import", {
            "text": alert_text,
            "sourceLabel": "Web of Science Alert",
            "enrich": False,
            "reviewOnly": True,
        }, timeout=20)
        assert_true(status_code == 200 and imported.get("ok"), f"Alert import failed: {imported}")
        paper_key = (imported.get("keys") or [""])[0]
        event = (imported.get("alertInboxEvents") or [{}])[0]
        event_id = event.get("id")
        assert_true(bool(paper_key and event_id), "Alert import did not return paper key and inbox event")

        status_code, inbox = request_json(base_url, "/api/alert/inbox", {"action": "status"}, timeout=20)
        alert_inbox = inbox.get("alertInbox") or {}
        items = alert_inbox.get("items") or []
        inbox_item = next((item for item in items if item.get("id") == event_id), None)
        assert_true(status_code == 200 and inbox.get("ok") and inbox_item, f"Alert inbox event missing: {inbox}")
        assert_true(inbox_item.get("status") == "pending", f"Alert inbox event should be pending: {inbox_item}")
        assert_true(inbox_item.get("canAdopt") is True, f"Alert inbox event should be adoptable: {inbox_item}")
        assert_true(((inbox_item.get("candidate") or {}).get("source")) == "alert", "Alert candidate source was not preserved")

        status_code, adopted = request_json(base_url, "/api/alert/inbox", {
            "action": "batch-adopt",
            "eventIds": [event_id],
            "lock": True,
        }, timeout=20)
        assert_true(status_code == 200 and adopted.get("ok"), f"Alert adoption failed: {adopted}")
        assert_true(adopted.get("adopted") == 1, f"Expected one adopted Alert item: {adopted}")
        adopted_inbox = adopted.get("alertInbox") or {}
        adopted_items = adopted_inbox.get("items") or []
        adopted_item = next((item for item in adopted_items if item.get("id") == event_id), None)
        assert_true(adopted_item and adopted_item.get("status") == "adopted", f"Alert inbox event was not adopted: {adopted}")
        assert_true((adopted_inbox.get("adoptedCount") or 0) >= 1, "Adopted Alert count was not updated")

        status_code, preview = request_json(base_url, "/api/zotero/sync-preview", {
            "paperKey": paper_key,
            "includeFulltext": False,
            "persistReview": False,
        }, timeout=20)
        assert_true(status_code == 200 and preview.get("ok"), f"Zotero sync preview failed: {preview}")
        assert_true(preview.get("ready") is False, "Unmatched smoke paper should not be ready to sync")
        assert_true(preview.get("status") == "unmatched", f"Unexpected Zotero preview status: {preview}")
        results["checks"].append({
            "name": "alert-inbox-zotero-preview",
            "paperKey": paper_key,
            "adopted": adopted.get("adopted"),
            "zoteroPreviewStatus": preview.get("status"),
        })

    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--mutate",
        action="store_true",
        help="write temporary subscription, Alert inbox, and Zotero preview data to the running workspace",
    )
    args = parser.parse_args(argv)
    try:
        results = run(args.base_url, args.mutate)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
