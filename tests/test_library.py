import base64
import tempfile
import unittest
import io
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import app


SAMPLE_PAPER = {
    "title": "Vision Language Models for Scientific Discovery",
    "authors": "Ada Lovelace, Alan Turing",
    "published": "2026-05-01",
    "year": 2026,
    "pdfUrl": "https://arxiv.org/pdf/2605.00001",
    "pageUrl": "https://arxiv.org/abs/2605.00001",
    "paperId": "2605.00001",
    "source": "arxiv",
    "sourceLabel": "arXiv",
    "venue": "arXiv",
    "category": "cs.AI",
    "abstract": "A concise test abstract.",
}


class LibraryTests(unittest.TestCase):
    def assertSamePath(self, expected: Path | str, actual: Path | str) -> None:
        self.assertEqual(Path(expected).resolve(), Path(actual).resolve())

    @contextmanager
    def temporary_settings_path(self, root: Path):
        settings_path = root / "state" / "settings.json"
        with patch.object(app, "SETTINGS_PATH", settings_path):
            yield settings_path

    def write_bridge_fixture_xpi(self, xpi_path: Path, *, version: str | None = None, bootstrap: str | None = None) -> None:
        manifest = json.loads(app.ZOTERO_BRIDGE_MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["version"] = version or app.ZOTERO_BRIDGE_VERSION
        source_bootstrap = app.ZOTERO_BRIDGE_BOOTSTRAP_PATH.read_text(encoding="utf-8")
        token = app.zotero_bridge_token()
        packaged_bootstrap = bootstrap if bootstrap is not None else source_bootstrap.replace(app.ZOTERO_BRIDGE_TOKEN_PLACEHOLDER, token)
        with zipfile.ZipFile(xpi_path, "w") as zip_file:
            zip_file.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
            zip_file.writestr("bootstrap.js", packaged_bootstrap)

    class HandlerStub(app.PaperHunterHandler):
        def __init__(self, path: str):
            self.path = path
            self.responses = []
            self.bytes_responses = []

        def read_json(self) -> dict:
            return {}

        def send_json(self, payload: dict, status: int = 200) -> None:
            self.responses.append((status, payload))

        def send_bytes(self, content: bytes, content_type: str, filename: str) -> None:
            self.bytes_responses.append((content, content_type, filename))

    class HeaderStub(app.PaperHunterHandler):
        def __init__(self, path: str):
            self.path = path
            self.headers_sent = []

        def send_header(self, key: str, value: str) -> None:
            self.headers_sent.append((key, value))

    def test_static_assets_send_no_store_headers(self):
        handler = self.HeaderStub("/app.js?v=test")
        with patch.object(app.SimpleHTTPRequestHandler, "end_headers"):
            handler.end_headers()

        self.assertIn(("Cache-Control", "no-store, max-age=0"), handler.headers_sent)
        self.assertIn(("Pragma", "no-cache"), handler.headers_sent)

    def test_normalized_request_path_strips_query_and_keeps_exact_path(self):
        self.assertEqual("/api/status", app.normalized_request_path("/api/status?refresh=1"))
        self.assertEqual("/api/status-extra", app.normalized_request_path("/api/status-extra?refresh=1"))
        self.assertEqual("/api/search", app.normalized_request_path("api/search"))
        self.assertEqual("/", app.normalized_request_path(""))

    def test_runtime_paths_can_be_overridden_from_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env = os.environ.copy()
            env.update({
                "LIBRARY_PATH": str(root / "state" / "library.json"),
                "SETTINGS_PATH": str(root / "state" / "settings.json"),
                "FULLTEXT_TASK_DIR": str(root / "tasks" / "fulltext"),
                "DOWNLOAD_DIR": str(root / "papers"),
                "TRANSLATED_DIR": str(root / "translated"),
                "ZOTERO_DB_PATH": str(root / "zotero" / "zotero.sqlite"),
                "ZOTERO_STORAGE_DIR": str(root / "zotero" / "storage"),
                "PORT": "8123",
            })
            script = (
                "import json, app; "
                "print(json.dumps({"
                "'library': str(app.LIBRARY_PATH), "
                "'settings': str(app.SETTINGS_PATH), "
                "'tasks': str(app.FULLTEXT_TASK_DIR), "
                "'download': str(app.DOWNLOAD_DIR), "
                "'translated': str(app.TRANSLATED_DIR), "
                "'zoteroDb': str(app.ZOTERO_DB_PATH), "
                "'zoteroStorage': str(app.ZOTERO_STORAGE_DIR), "
                "'port': app.PORT"
                "}))"
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            paths = json.loads(result.stdout)

        self.assertSamePath(root / "state" / "library.json", paths["library"])
        self.assertSamePath(root / "state" / "settings.json", paths["settings"])
        self.assertSamePath(root / "tasks" / "fulltext", paths["tasks"])
        self.assertSamePath(root / "papers", paths["download"])
        self.assertSamePath(root / "translated", paths["translated"])
        self.assertSamePath(root / "zotero" / "zotero.sqlite", paths["zoteroDb"])
        self.assertSamePath(root / "zotero" / "storage", paths["zoteroStorage"])
        self.assertEqual(8123, paths["port"])

    def test_http_get_rejects_api_prefix_shadow_route(self):
        handler = self.HandlerStub("/api/status-extra?refresh=1")
        with patch.object(app, "load_library", side_effect=AssertionError("status route should not run")):
            handler.do_GET()

        self.assertEqual(404, handler.responses[-1][0])
        self.assertFalse(handler.bytes_responses)

    def test_http_post_rejects_api_prefix_shadow_route(self):
        handler = self.HandlerStub("/api/search-extra")
        with patch.object(app, "search_papers", side_effect=AssertionError("search route should not run")):
            handler.do_POST()

        self.assertEqual(404, handler.responses[-1][0])

    def create_zotero_test_db(self, db_path: Path, storage_dir: Path) -> Path:
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(
                """
                create table itemTypes (itemTypeID integer primary key, typeName text);
                create table items (
                    itemID integer primary key,
                    itemTypeID integer,
                    dateAdded text,
                    dateModified text,
                    clientDateModified text,
                    libraryID integer,
                    key text,
                    version integer,
                    synced integer
                );
                create table fields (fieldID integer primary key, fieldName text);
                create table itemData (itemID integer, fieldID integer, valueID integer);
                create table itemDataValues (valueID integer primary key, value text);
                create table creators (creatorID integer primary key, firstName text, lastName text, fieldMode integer);
                create table itemCreators (itemID integer, creatorID integer, creatorTypeID integer, orderIndex integer);
                create table creatorTypes (creatorTypeID integer primary key, creatorType text);
                create table itemAttachments (itemID integer, parentItemID integer, linkMode integer, contentType text, charsetID integer, path text);
                create table collections (collectionID integer primary key, key text, collectionName text);
                create table collectionItems (collectionID integer, itemID integer);
                create table tags (tagID integer primary key, name text);
                create table itemTags (itemID integer, tagID integer);
                create table itemNotes (itemID integer primary key, parentItemID integer, note text, title text);
                create table deletedItems (itemID integer);
                """
            )
            conn.executemany("insert into itemTypes values (?, ?)", [(1, "journalArticle"), (2, "attachment")])
            conn.executemany(
                "insert into items values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (10, 1, "2026-05-01 00:00:00", "2026-05-02 00:00:00", "", 1, "ITEMKEY", 1, 1),
                    (11, 2, "2026-05-01 00:00:00", "2026-05-02 00:00:00", "", 1, "ATTKEY", 1, 1),
                    (12, 1, "2026-05-01 00:00:00", "2026-05-02 00:00:00", "", 1, "NOTEKEY", 1, 1),
                ],
            )
            fields = {
                "title": "Imported Zotero Paper",
                "abstractNote": "Complete Zotero abstract.",
                "date": "2026-05-01",
                "publicationTitle": "Journal of Tests",
                "DOI": "10.1234/zotero.paper",
                "url": "https://example.test/paper",
            }
            for index, (name, value) in enumerate(fields.items(), start=1):
                conn.execute("insert into fields values (?, ?)", (index, name))
                conn.execute("insert into itemDataValues values (?, ?)", (index, value))
                conn.execute("insert into itemData values (?, ?, ?)", (10, index, index))
            conn.execute("insert into creators values (?, ?, ?, ?)", (1, "Grace", "Hopper", 0))
            conn.execute("insert into creatorTypes values (?, ?)", (1, "author"))
            conn.execute("insert into itemCreators values (?, ?, ?, ?)", (10, 1, 1, 0))
            conn.execute("insert into itemAttachments values (?, ?, ?, ?, ?, ?)", (11, 10, 1, "application/pdf", None, "storage:test.pdf"))
            conn.execute("insert into collections values (?, ?, ?)", (1, "COLLKEY", "Imported Collection"))
            conn.execute("insert into collectionItems values (?, ?)", (1, 10))
            conn.execute("insert into tags values (?, ?)", (1, "important"))
            conn.execute("insert into itemTags values (?, ?)", (10, 1))
            conn.execute("insert into itemNotes values (?, ?, ?, ?)", (12, 10, "<p>User Zotero note</p>", "User Zotero note"))
            conn.commit()
        finally:
            conn.close()
        pdf_dir = storage_dir / "ATTKEY"
        pdf_dir.mkdir(parents=True)
        pdf_path = pdf_dir / "test.pdf"
        pdf_path.write_bytes(b"%PDF test")
        return pdf_path

    def zotero_candidate(self, item_key: str, **overrides) -> dict:
        item_id = sum(ord(char) for char in item_key)
        candidate = {
            **SAMPLE_PAPER,
            "source": "zotero",
            "sourceLabel": "Zotero",
            "paperId": f"zotero-{item_key}",
            "pdfUrl": "",
            "localPdfPath": "",
            "access": "user_library",
            "zotero": {
                "itemKey": item_key,
                "libraryID": 1,
                "itemID": item_id,
                "attachments": [],
                "notes": [],
                "collections": [],
            },
        }
        candidate.update(overrides)
        return app.paper_snapshot(candidate)

    def test_export_bibtex_contains_core_fields(self):
        content = app.export_bibtex([{**SAMPLE_PAPER, "doi": "10.1234/example.paper"}])

        self.assertIn("@misc{", content)
        self.assertIn("title = {Vision Language Models for Scientific Discovery}", content)
        self.assertIn("author = {Ada Lovelace and Alan Turing}", content)
        self.assertIn("year = {2026}", content)
        self.assertIn("url = {https://arxiv.org/abs/2605.00001}", content)
        self.assertIn("doi = {10.1234/example.paper}", content)
        self.assertIn("archivePrefix = {arXiv}", content)
        self.assertIn("primaryClass = {cs.AI}", content)
        self.assertNotIn("journal = {cs.AI}", content)

    def test_export_ris_contains_zotero_endnote_fields(self):
        paper = {
            **SAMPLE_PAPER,
            "paperId": "10.1234/example.paper",
            "tags": ["reading", "ai"],
            "note": "Keep for review.",
        }

        content = app.export_ris([paper])

        self.assertIn("TY  - ELEC", content)
        self.assertIn("TI  - Vision Language Models for Scientific Discovery", content)
        self.assertIn("AU  - Ada Lovelace", content)
        self.assertIn("AU  - Alan Turing", content)
        self.assertIn("PY  - 2026", content)
        self.assertIn("Y1  - 2026/05/01", content)
        self.assertIn("T2  - arXiv", content)
        self.assertIn("AB  - A concise test abstract.", content)
        self.assertIn("DO  - 10.1234/example.paper", content)
        self.assertIn("UR  - https://arxiv.org/abs/2605.00001", content)
        self.assertIn("L1  - https://arxiv.org/pdf/2605.00001", content)
        self.assertIn("KW  - cs.AI", content)
        self.assertIn("KW  - reading", content)
        self.assertIn("N1  - Source: arXiv | Keep for review.", content)
        self.assertTrue(content.rstrip().endswith("ER  -"))

    def test_export_papers_supports_ris_format(self):
        response = app.export_papers({"format": "ris", "papers": [SAMPLE_PAPER]})

        self.assertTrue(response["ok"])
        self.assertEqual("ris", response["format"])
        self.assertEqual("paperhunter-library.ris", response["filename"])
        self.assertEqual("application/x-research-info-systems; charset=utf-8", response["mimeType"])
        self.assertEqual(1, response["count"])
        self.assertIn("TY  - ELEC", response["content"])

    def test_zotero_item_from_paper_contains_reference_metadata(self):
        paper = {
            **SAMPLE_PAPER,
            "paperId": "10.1234/example.paper",
            "tags": ["reading"],
            "note": "Keep for review.",
        }

        item = app.zotero_item_from_paper(paper)

        self.assertEqual("preprint", item["itemType"])
        self.assertEqual("Vision Language Models for Scientific Discovery", item["title"])
        self.assertEqual("Ada", item["creators"][0]["firstName"])
        self.assertEqual("Lovelace", item["creators"][0]["lastName"])
        self.assertEqual("A concise test abstract.", item["abstractNote"])
        self.assertEqual("2026-05-01", item["date"])
        self.assertEqual("https://arxiv.org/abs/2605.00001", item["url"])
        self.assertEqual("10.1234/example.paper", item["DOI"])
        self.assertEqual("arXiv", item["archive"])
        self.assertEqual("arXiv", item["repository"])
        self.assertIn({"tag": "reading"}, item["tags"])
        self.assertIn({"tag": "cs.AI"}, item["tags"])
        self.assertIn("Public PDF: https://arxiv.org/pdf/2605.00001", item["notes"][0]["note"])

    def test_save_papers_to_zotero_posts_to_connector(self):
        captured = {}

        class Response:
            status_code = 201
            text = ""

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return Response()

        with patch.object(app.requests, "post", side_effect=fake_post):
            response = app.save_papers_to_zotero({"papers": [SAMPLE_PAPER]})

        self.assertTrue(response["ok"])
        self.assertEqual(1, response["saved"])
        self.assertEqual(app.ZOTERO_CONNECTOR_SAVE_ITEMS_URL, captured["url"])
        self.assertEqual("application/json", captured["headers"]["Content-Type"])
        self.assertEqual("https://arxiv.org/abs/2605.00001", captured["json"]["uri"])
        self.assertEqual("preprint", captured["json"]["items"][0]["itemType"])

    def test_zotero_connector_status_reports_unavailable(self):
        with patch.object(app.requests, "get", side_effect=app.requests.RequestException("offline")):
            status = app.zotero_connector_status()

        self.assertFalse(status["available"])
        self.assertIn("未检测到本机 Zotero", status["message"])

    def test_zotero_connector_status_reports_available(self):
        class Response:
            status_code = 200

        with patch.object(app.requests, "get", return_value=Response()):
            status = app.zotero_connector_status()

        self.assertTrue(status["available"])
        self.assertIn("已检测到本机 Zotero", status["message"])

    def test_zotero_status_reports_import_and_bridge_availability(self):
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(app, "ZOTERO_DB_PATH", Path(tmpdir) / "zotero.sqlite"),
            patch.object(app, "ZOTERO_STORAGE_DIR", Path(tmpdir) / "storage"),
            patch.object(app, "zotero_connector_status", return_value={"available": True, "message": "connector ok"}),
            patch.object(
                app,
                "zotero_bridge_status",
                return_value={
                    "available": False,
                    "message": "bridge missing",
                    "package": {"valid": True, "version": app.ZOTERO_BRIDGE_VERSION},
                    "installSteps": app.ZOTERO_BRIDGE_INSTALL_STEPS,
                },
            ),
        ):
            app.ZOTERO_DB_PATH.write_text("", encoding="utf-8")
            app.ZOTERO_STORAGE_DIR.mkdir()
            status = app.zotero_status()

        self.assertTrue(status["available"])
        self.assertTrue(status["importAvailable"])
        self.assertFalse(status["syncAvailable"])
        self.assertIn("database", status)
        self.assertIn("bridge", status)
        self.assertTrue(status["bridge"]["package"]["valid"])
        self.assertEqual(app.ZOTERO_BRIDGE_INSTALL_STEPS, status["bridge"]["installSteps"])

    def test_zotero_bridge_status_requires_compatible_protocol(self):
        class Response:
            status_code = 200

            def json(self):
                return {"ok": True, "version": "0.1.0"}

        with patch.object(app.requests, "get", return_value=Response()):
            status = app.zotero_bridge_status()

        self.assertTrue(status["available"])
        self.assertFalse(status["compatible"])
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, status["expectedVersion"])
        self.assertEqual(app.ZOTERO_BRIDGE_DOWNLOAD_URL, status["downloadUrl"])
        self.assertIn("package", status)
        self.assertIn("版本、协议或配对能力不兼容", status["message"])

    def test_zotero_bridge_status_accepts_expected_protocol(self):
        class PingResponse:
            status_code = 200

            def json(self):
                return {
                    "ok": True,
                    "version": app.ZOTERO_BRIDGE_VERSION,
                    "protocolVersion": app.ZOTERO_BRIDGE_PROTOCOL_VERSION,
                    "capabilities": app.ZOTERO_BRIDGE_CAPABILITIES,
                }

        class PairingResponse:
            status_code = 200
            text = "{}"

            def json(self):
                return {"ok": True, "tokenAccepted": True}

        captured = {}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return PairingResponse()

        with (
            patch.object(app.requests, "get", return_value=PingResponse()),
            patch.object(app.requests, "post", side_effect=fake_post),
        ):
            status = app.zotero_bridge_status()

        self.assertTrue(status["available"])
        self.assertTrue(status["compatible"])
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, status["version"])
        self.assertEqual(app.ZOTERO_BRIDGE_INSTALL_STEPS, status["installSteps"])
        self.assertEqual(app.ZOTERO_BRIDGE_CAPABILITIES, status["capabilities"])
        self.assertTrue(status["pairing"]["configured"])
        self.assertTrue(status["pairing"]["verified"])
        self.assertEqual(app.ZOTERO_BRIDGE_PAIRING_CHECK_URL, captured["url"])
        self.assertEqual("PaperHunter", captured["json"]["client"])
        self.assertTrue(captured["json"]["pairingToken"])

    def test_zotero_bridge_status_blocks_token_mismatch_even_when_version_matches(self):
        class PingResponse:
            status_code = 200

            def json(self):
                return {
                    "ok": True,
                    "version": app.ZOTERO_BRIDGE_VERSION,
                    "protocolVersion": app.ZOTERO_BRIDGE_PROTOCOL_VERSION,
                    "capabilities": app.ZOTERO_BRIDGE_CAPABILITIES,
                }

        class PairingResponse:
            status_code = 401
            text = "PaperHunter Bridge pairing token is invalid"

            def json(self):
                return {"ok": False, "error": self.text}

        with (
            patch.object(app.requests, "get", return_value=PingResponse()),
            patch.object(app.requests, "post", return_value=PairingResponse()),
        ):
            status = app.zotero_bridge_status()

        self.assertTrue(status["available"])
        self.assertFalse(status["compatible"])
        self.assertEqual("pairing_check_failed", status["reason"])
        self.assertFalse(status["pairing"]["verified"])
        self.assertIn("配对 token", status["message"])

    def test_read_zotero_papers_imports_metadata_and_pdf_attachment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "zotero.sqlite"
            storage_dir = root / "storage"
            cache_dir = root / "cache"
            storage_dir.mkdir()
            pdf_path = self.create_zotero_test_db(db_path, storage_dir)
            with (
                patch.object(app, "ZOTERO_DB_PATH", db_path),
                patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir),
                patch.object(app, "CACHE_DIR", cache_dir),
            ):
                papers = app.read_zotero_papers(limit=10)

        self.assertEqual(1, len(papers))
        paper = papers[0]
        self.assertEqual("Imported Zotero Paper", paper["title"])
        self.assertEqual("Grace Hopper", paper["authors"])
        self.assertEqual("10.1234/zotero.paper", paper["doi"])
        self.assertSamePath(pdf_path, paper["localPdfPath"])
        self.assertTrue(paper["downloadable"])
        self.assertTrue(paper["isDownloaded"])
        self.assertEqual("ITEMKEY", paper["zotero"]["itemKey"])
        self.assertEqual("User Zotero note", paper["zotero"]["notes"][0]["preview"])
        self.assertFalse(paper["zotero"]["notes"][0]["managedByPaperHunter"])
        self.assertEqual("", paper.get("note", ""))
        self.assertEqual("important", paper["tags"][0])

    def test_read_zotero_papers_accepts_linked_pdf_in_download_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "zotero.sqlite"
            storage_dir = root / "storage"
            cache_dir = root / "cache"
            download_dir = root / "downloaded_papers"
            storage_dir.mkdir()
            download_dir.mkdir()
            linked_pdf = download_dir / "linked.pdf"
            linked_pdf.write_bytes(b"%PDF linked")
            self.create_zotero_test_db(db_path, storage_dir)
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("update itemAttachments set linkMode = ?, path = ? where itemID = ?", (2, str(linked_pdf), 11))
                conn.commit()
            finally:
                conn.close()
            with (
                patch.object(app, "ZOTERO_DB_PATH", db_path),
                patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir),
                patch.object(app, "DOWNLOAD_DIR", download_dir),
                patch.object(app, "CACHE_DIR", cache_dir),
            ):
                papers = app.read_zotero_papers(limit=10)

        self.assertEqual(1, len(papers))
        paper = papers[0]
        self.assertSamePath(linked_pdf, paper["localPdfPath"])
        self.assertTrue(paper["downloadable"])
        self.assertTrue(paper["zotero"]["attachments"][0]["isPdf"])

    def test_read_zotero_papers_reports_paperhunter_markdown_attachment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "zotero.sqlite"
            storage_dir = root / "storage"
            cache_dir = root / "cache"
            translated_dir = root / "translated_papers"
            storage_dir.mkdir()
            translated_dir.mkdir()
            pdf_path = self.create_zotero_test_db(db_path, storage_dir)
            markdown_path = translated_dir / "paper.bilingual.md"
            markdown_path.write_text("# translated", encoding="utf-8")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "insert into items values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (13, 2, "2026-05-01 00:00:00", "2026-05-02 00:00:00", "", 1, "MDKEY", 1, 1),
                )
                conn.execute(
                    "insert into itemAttachments values (?, ?, ?, ?, ?, ?)",
                    (13, 10, 2, "text/markdown", None, str(markdown_path)),
                )
                conn.execute("insert into itemDataValues values (?, ?)", (99, "PaperHunter full-text translation"))
                conn.execute("insert into itemData values (?, ?, ?)", (13, 1, 99))
                conn.commit()
            finally:
                conn.close()
            with (
                patch.object(app, "ZOTERO_DB_PATH", db_path),
                patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir),
                patch.object(app, "TRANSLATED_DIR", translated_dir),
                patch.object(app, "CACHE_DIR", cache_dir),
            ):
                papers = app.read_zotero_papers(limit=10)

        paper = papers[0]
        self.assertSamePath(pdf_path, paper["localPdfPath"])
        attachments = paper["zotero"]["attachments"]
        self.assertEqual(2, len(attachments))
        markdown = next(attachment for attachment in attachments if attachment["contentType"] == "text/markdown")
        self.assertSamePath(markdown_path, markdown["path"])
        self.assertTrue(markdown["managedByPaperHunter"])
        self.assertFalse(markdown["isPdf"])
        self.assertEqual("PaperHunter full-text translation", markdown["title"])

    def test_import_zotero_library_persists_favorites_and_download_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "zotero.sqlite"
            storage_dir = root / "storage"
            cache_dir = root / "cache"
            library_path = root / "library.json"
            storage_dir.mkdir()
            pdf_path = self.create_zotero_test_db(db_path, storage_dir)
            with (
                patch.object(app, "ZOTERO_DB_PATH", db_path),
                patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir),
                patch.object(app, "CACHE_DIR", cache_dir),
                patch.object(app, "LIBRARY_PATH", library_path),
            ):
                response = app.import_zotero_library({"limit": 10, "requirePdf": True})
                library = app.load_library()

        self.assertTrue(response["ok"])
        self.assertEqual(1, response["imported"])
        self.assertEqual(1, response["withPdf"])
        key = next(iter(library["favorites"]))
        self.assertEqual("user_library", library["favorites"][key]["paper"]["access"])
        self.assertSamePath(pdf_path, library["downloads"][key]["path"])
        self.assertEqual("zotero", library["downloads"][key]["source"])

    def test_import_zotero_library_links_existing_paper_by_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "zotero.sqlite"
            storage_dir = root / "storage"
            cache_dir = root / "cache"
            library_path = root / "library.json"
            storage_dir.mkdir()
            self.create_zotero_test_db(db_path, storage_dir)
            existing = app.paper_snapshot({
                **SAMPLE_PAPER,
                "title": "Imported Zotero Paper",
                "paperId": "local-existing",
                "source": "semantic",
                "translations": {
                    "zh": {
                        "text": "已有中文摘要。",
                        "language": "zh",
                        "sourceHash": app.stable_text_hash("Complete Zotero abstract."),
                    }
                },
            })
            existing_key = app.paper_key(existing)
            with (
                patch.object(app, "ZOTERO_DB_PATH", db_path),
                patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir),
                patch.object(app, "CACHE_DIR", cache_dir),
                patch.object(app, "LIBRARY_PATH", library_path),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {existing_key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": existing}},
                    "favorites": {existing_key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": existing}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                response = app.import_zotero_library({"limit": 10})
                library = app.load_library()

        self.assertTrue(response["ok"])
        self.assertEqual(1, response["linked"])
        self.assertIn(existing_key, library["favorites"])
        self.assertEqual("ITEMKEY", library["favorites"][existing_key]["paper"]["zotero"]["itemKey"])
        self.assertEqual("已有中文摘要。", library["favorites"][existing_key]["paper"]["translations"]["zh"]["text"])
        self.assertNotIn("zotero-10-1234-zotero-paper", library["favorites"])

    def test_find_download_record_accepts_zotero_storage_pdf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            storage_dir = root / "storage"
            pdf_dir = storage_dir / "ATTKEY"
            pdf_dir.mkdir(parents=True)
            pdf_path = pdf_dir / "paper.pdf"
            pdf_path.write_bytes(b"%PDF test")
            with patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir):
                filename, resolved = app.find_download_record({}, "paper", {"localPdfPath": str(pdf_path)})

        self.assertEqual("paper.pdf", filename)
        self.assertEqual(pdf_path.resolve(), resolved)

    def test_download_existing_pdf_records_library_download(self):
        paper = {**SAMPLE_PAPER, "paperId": "download-existing"}
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_path = root / "library.json"
            download_dir = root / "downloaded_papers"
            download_dir.mkdir()
            filename = app.sanitize_filename(paper["title"], paper["paperId"])
            (download_dir / filename).write_bytes(b"%PDF existing")
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "DOWNLOAD_DIR", download_dir),
                patch.object(app.requests, "get") as http_get,
            ):
                app.save_library(app.empty_library())
                response = app.download_pdf(paper)
                stored = app.load_library()

        http_get.assert_not_called()
        self.assertTrue(response["ok"])
        self.assertIn(key, stored["downloads"])
        self.assertIn(key, stored["papers"])
        self.assertTrue(stored["papers"][key]["paper"]["isDownloaded"])

    def test_zotero_sync_payload_includes_note_tags_and_translated_attachment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            translated_dir = root / "translated_papers"
            translated_dir.mkdir()
            output = translated_dir / "paper.bilingual.md"
            output.write_text("# 译文", encoding="utf-8")
            paper = app.paper_snapshot({
                **SAMPLE_PAPER,
                "zotero": {"itemKey": "ITEMKEY"},
                "translations": {
                    "zh": {
                        "text": "中文摘要。",
                        "language": "zh",
                        "sourceHash": app.stable_text_hash(SAMPLE_PAPER["abstract"]),
                    }
                },
                "fulltextTranslations": [{
                    "type": "fulltext",
                    "language": "zh",
                    "format": "markdown",
                    "file": "translated_papers/paper.bilingual.md",
                    "createdAt": "2026-05-31T00:00:00+00:00",
                }],
            })
            with (
                patch.object(app, "ROOT_DIR", root),
                patch.object(app, "TRANSLATED_DIR", translated_dir),
            ):
                payload = app.zotero_sync_payload(paper)

        self.assertEqual("ITEMKEY", payload["itemKey"])
        self.assertEqual(app.ZOTERO_BRIDGE_PROTOCOL_VERSION, payload["protocolVersion"])
        self.assertEqual("PaperHunter", payload["client"])
        self.assertTrue(payload["pairingToken"])
        self.assertTrue(payload["policy"]["preserveUserContent"])
        self.assertEqual([str(translated_dir.resolve())], payload["allowedAttachmentRoots"])
        self.assertIn("PaperHunter 同步结果", payload["noteHtml"])
        self.assertIn("中文摘要。", payload["noteHtml"])
        self.assertIn("paperhunter:abstract-translated", payload["tags"])
        self.assertIn("paperhunter:fulltext-translated", payload["tags"])
        self.assertEqual([output.resolve()], [Path(path).resolve() for path in payload["attachments"]])

    def test_zotero_sync_payload_deduplicates_translated_attachment_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            translated_dir = root / "translated_papers"
            translated_dir.mkdir()
            output = translated_dir / "paper.bilingual.md"
            output.write_text("# Translation", encoding="utf-8")
            paper = app.paper_snapshot({
                **SAMPLE_PAPER,
                "zotero": {"itemKey": "ITEMKEY"},
                "fulltextTranslations": [
                    {
                        "type": "fulltext",
                        "language": "zh",
                        "format": "markdown",
                        "file": "translated_papers/paper.bilingual.md",
                        "createdAt": "2026-05-31T00:00:00+00:00",
                    },
                    {
                        "type": "fulltext",
                        "language": "zh",
                        "format": "markdown",
                        "file": "translated_papers/paper.bilingual.md",
                        "createdAt": "2026-05-31T00:01:00+00:00",
                    },
                ],
            })
            with (
                patch.object(app, "ROOT_DIR", root),
                patch.object(app, "TRANSLATED_DIR", translated_dir),
            ):
                payload = app.zotero_sync_payload(paper)

        self.assertEqual([output.resolve()], [Path(path).resolve() for path in payload["attachments"]])

    def test_zotero_sync_payload_rejects_conflicting_item_keys(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "zotero": {"itemKey": "OLDKEY"},
            "zoteroSync": {"status": "synced", "itemKey": "SYNCEDKEY"},
        })

        self.assertEqual("conflict", paper["zoteroLink"]["status"])

        with self.assertRaises(ValueError):
            app.zotero_sync_payload(paper, include_fulltext=False)

    def test_zotero_safe_sync_tags_rejects_user_tags(self):
        tags = app.zotero_safe_sync_tags(["paperhunter", "paperhunter:fulltext-translated", "important", "zotero"])

        self.assertEqual(["paperhunter", "paperhunter:fulltext-translated"], tags)

    def test_sync_paper_to_zotero_posts_to_bridge(self):
        captured = {}

        class Response:
            status_code = 200
            text = "{}"

            def json(self):
                return {"ok": True, "noteID": 12}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return Response()

        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "zotero": {"itemKey": "ITEMKEY"},
            "translations": {
                "zh": {
                    "text": "中文摘要。",
                    "language": "zh",
                    "sourceHash": app.stable_text_hash(SAMPLE_PAPER["abstract"]),
                }
            },
        })

        with patch.object(app.requests, "post", side_effect=fake_post):
            response = app.sync_paper_to_zotero({"paper": paper, "includeFulltext": False})

        self.assertTrue(response["ok"])
        self.assertEqual("ITEMKEY", captured["json"]["itemKey"])
        self.assertEqual(app.ZOTERO_BRIDGE_SYNC_URL, captured["url"])
        self.assertIn("paperhunter:abstract-translated", captured["json"]["tags"])

    def test_sync_paper_to_zotero_auto_links_before_bridge_post(self):
        captured = {}

        class Response:
            status_code = 200
            text = "{}"

            def json(self):
                return {"ok": True, "noteID": 12}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return Response()

        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "title": "Imported Zotero Paper",
            "paperId": "local-existing",
            "source": "semantic",
            "translations": {
                "zh": {
                    "text": "已有中文摘要。",
                    "language": "zh",
                    "sourceHash": app.stable_text_hash(SAMPLE_PAPER["abstract"]),
                }
            },
        })
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "zotero.sqlite"
            storage_dir = root / "storage"
            cache_dir = root / "cache"
            library_path = root / "library.json"
            storage_dir.mkdir()
            self.create_zotero_test_db(db_path, storage_dir)
            with (
                patch.object(app, "ZOTERO_DB_PATH", db_path),
                patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir),
                patch.object(app, "CACHE_DIR", cache_dir),
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app.requests, "post", side_effect=fake_post),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "favorites": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                response = app.sync_paper_to_zotero({"paperKey": key, "paper": paper, "includeFulltext": False})
                library = app.load_library()

        self.assertTrue(response["ok"])
        self.assertTrue(response["linked"])
        self.assertEqual("ITEMKEY", captured["json"]["itemKey"])
        self.assertEqual("ITEMKEY", library["favorites"][key]["paper"]["zotero"]["itemKey"])
        self.assertEqual("synced", library["favorites"][key]["paper"]["zoteroSync"]["status"])
        self.assertEqual("ITEMKEY", library["favorites"][key]["paper"]["zoteroSync"]["itemKey"])
        self.assertEqual(12, library["favorites"][key]["paper"]["zoteroSync"]["noteID"])

    def test_sync_paper_to_zotero_records_failed_state(self):
        class Response:
            status_code = 400
            text = "Bridge failed"

        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "zotero": {"itemKey": "ITEMKEY"},
            "translations": {
                "zh": {
                    "text": "中文摘要。",
                    "language": "zh",
                    "sourceHash": app.stable_text_hash(SAMPLE_PAPER["abstract"]),
                }
            },
        })
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_path = root / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app.requests, "post", return_value=Response()),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "favorites": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                with self.assertRaises(RuntimeError):
                    app.sync_paper_to_zotero({"paperKey": key, "includeFulltext": False})
                library = app.load_library()

        self.assertEqual("failed", library["favorites"][key]["paper"]["zoteroSync"]["status"])
        self.assertIn("Bridge failed", library["favorites"][key]["paper"]["zoteroSync"]["error"])

    def test_link_zotero_items_resolves_paper_key_from_library(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "title": "Imported Zotero Paper",
            "paperId": "local-existing",
            "source": "semantic",
        })
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "zotero.sqlite"
            storage_dir = root / "storage"
            cache_dir = root / "cache"
            library_path = root / "library.json"
            storage_dir.mkdir()
            self.create_zotero_test_db(db_path, storage_dir)
            with (
                patch.object(app, "ZOTERO_DB_PATH", db_path),
                patch.object(app, "ZOTERO_STORAGE_DIR", storage_dir),
                patch.object(app, "CACHE_DIR", cache_dir),
                patch.object(app, "LIBRARY_PATH", library_path),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "favorites": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                response = app.link_zotero_items({"paperKey": key})
                library = app.load_library()

        self.assertTrue(response["ok"])
        self.assertEqual(1, response["linked"])
        self.assertEqual("ITEMKEY", library["favorites"][key]["paper"]["zotero"]["itemKey"])

    def test_resolve_zotero_match_marks_duplicate_item_keys_ambiguous(self):
        candidates = [
            self.zotero_candidate("ITEMKEYA"),
            self.zotero_candidate("ITEMKEYB"),
        ]

        result = app.resolve_zotero_match(SAMPLE_PAPER, candidates)

        self.assertEqual("ambiguous", result["status"])
        self.assertEqual(2, len(result["candidates"]))
        self.assertEqual({"ITEMKEYA", "ITEMKEYB"}, {item["itemKey"] for item in result["candidates"]})

    def test_save_papers_to_zotero_does_not_create_duplicate_when_ambiguous(self):
        paper = app.paper_snapshot(SAMPLE_PAPER)
        candidates = [
            self.zotero_candidate("ITEMKEYA"),
            self.zotero_candidate("ITEMKEYB"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(app, "LIBRARY_PATH", Path(tmpdir) / "library.json"),
                patch.object(app, "read_zotero_candidates", return_value=candidates),
                patch.object(app.requests, "post") as connector_post,
            ):
                response = app.save_papers_to_zotero({"papers": [paper]})
                library = app.load_library()

        connector_post.assert_not_called()
        self.assertTrue(response["ok"])
        self.assertEqual(0, response["saved"])
        self.assertEqual(1, response["ambiguous"])
        key = app.paper_key(paper)
        self.assertEqual("ambiguous", library["papers"][key]["paper"]["zoteroLink"]["status"])

    def test_zotero_sync_preview_blocks_ambiguous_match(self):
        paper = app.paper_snapshot(SAMPLE_PAPER)
        key = app.paper_key(paper)
        candidates = [
            self.zotero_candidate("ITEMKEYA"),
            self.zotero_candidate("ITEMKEYB"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(app, "LIBRARY_PATH", Path(tmpdir) / "library.json"),
                patch.object(app, "read_zotero_candidates", return_value=candidates),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "favorites": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                preview = app.zotero_sync_preview({"paperKey": key, "includeFulltext": False})

        self.assertTrue(preview["ok"])
        self.assertFalse(preview["ready"])
        self.assertEqual("ambiguous", preview["status"])
        self.assertEqual(2, len(preview["candidates"]))

    def test_zotero_sync_preview_can_skip_persisting_review_state(self):
        paper = app.paper_snapshot(SAMPLE_PAPER)
        key = app.paper_key(paper)
        candidates = [
            self.zotero_candidate("ITEMKEYA"),
            self.zotero_candidate("ITEMKEYB"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(app, "LIBRARY_PATH", Path(tmpdir) / "library.json"),
                patch.object(app, "read_zotero_candidates", return_value=candidates),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "favorites": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                preview = app.zotero_sync_preview({
                    "paperKey": key,
                    "includeFulltext": False,
                    "persistReview": False,
                })
                stored = app.load_library()

        self.assertTrue(preview["ok"])
        self.assertFalse(preview["ready"])
        self.assertEqual("ambiguous", preview["status"])
        self.assertNotIn("library", preview)
        stored_link = stored["favorites"][key]["paper"].get("zoteroLink", {})
        self.assertNotEqual("ambiguous", stored_link.get("status"))
        self.assertEqual([], stored["zoteroAudit"])

    def test_zotero_sync_preview_conflict_returns_review_candidates(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "conflict-preview",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYB"},
        })
        key = app.paper_key(paper)
        candidates = [
            self.zotero_candidate("ITEMKEYA"),
            self.zotero_candidate("ITEMKEYB"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(app, "LIBRARY_PATH", Path(tmpdir) / "library.json"),
                patch.object(app, "read_zotero_candidates", return_value=candidates),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "favorites": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                preview = app.zotero_sync_preview({"paperKey": key, "includeFulltext": False})

        self.assertTrue(preview["ok"])
        self.assertFalse(preview["ready"])
        self.assertEqual("conflict", preview["status"])
        self.assertEqual({"ITEMKEYA", "ITEMKEYB"}, {item["itemKey"] for item in preview["candidates"]})

    def test_zotero_favorites_sync_preview_does_not_post_to_bridge(self):
        ready_paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "ready-preview",
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
        })
        blocked_paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "blocked-preview",
            "title": "Blocked Preview Paper",
            "zoteroLink": {
                "status": "ambiguous",
                "candidates": [
                    app.zotero_link_candidate(self.zotero_candidate("ITEMKEYB"), 98),
                    app.zotero_link_candidate(self.zotero_candidate("ITEMKEYC"), 96),
                ],
            },
        })
        ready_key = app.paper_key(ready_paper)
        blocked_key = app.paper_key(blocked_paper)
        candidates = [
            self.zotero_candidate("ITEMKEYA"),
            self.zotero_candidate("ITEMKEYB"),
            self.zotero_candidate("ITEMKEYC"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(app, "LIBRARY_PATH", Path(tmpdir) / "library.json"),
                patch.object(app, "read_zotero_candidates", return_value=candidates),
                patch.object(app.requests, "post") as bridge_post,
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {
                        ready_key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": ready_paper},
                        blocked_key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": blocked_paper},
                    },
                    "favorites": {
                        ready_key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": ready_paper},
                        blocked_key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": blocked_paper},
                    },
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                preview = app.zotero_favorites_sync_preview({"includeFulltext": False})
                stored = app.load_library()

        bridge_post.assert_not_called()
        self.assertTrue(preview["ok"])
        self.assertEqual(2, preview["checked"])
        self.assertEqual(1, preview["ready"])
        self.assertEqual(1, preview["blocked"])
        self.assertEqual("batch-preview", stored["zoteroAudit"][0]["action"])

    def test_confirm_zotero_link_writes_audit_event(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "confirm-audit",
            "zoteroLink": {
                "status": "ambiguous",
                "candidates": [app.zotero_link_candidate(self.zotero_candidate("ITEMKEYA"), 97)],
            },
        })
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(app, "LIBRARY_PATH", Path(tmpdir) / "library.json"),
                patch.object(app, "read_zotero_candidates", return_value=[self.zotero_candidate("ITEMKEYA")]),
            ):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "favorites": {key: {"createdAt": "2026-05-01T00:00:00+00:00", "paper": paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                response = app.confirm_zotero_link({"paperKey": key, "itemKey": "ITEMKEYA"})
                stored = app.load_library()

        self.assertTrue(response["ok"])
        self.assertEqual("ITEMKEYA", response["itemKey"])
        self.assertEqual("confirm-link", stored["zoteroAudit"][0]["action"])
        self.assertEqual("ITEMKEYA", stored["zoteroAudit"][0]["itemKey"])

    def test_zotero_audit_status_returns_full_read_only_history(self):
        audit = [
            {
                "createdAt": f"2026-05-0{index}T00:00:00+00:00",
                "action": f"event-{index}",
                "paperKey": f"paper-{index}",
                "title": f"Paper {index}",
                "itemKey": f"ITEMKEY{index}",
                "status": "ok",
                "message": "Audit event",
                "details": {"index": index},
            }
            for index in range(1, 4)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(app, "LIBRARY_PATH", Path(tmpdir) / "library.json"):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {},
                    "favorites": {},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                    "zoteroAudit": audit,
                })
                response = app.zotero_audit_status({"limit": 2})
                stored = app.load_library()

        self.assertTrue(response["ok"])
        self.assertEqual(3, response["total"])
        self.assertEqual(2, len(response["items"]))
        self.assertEqual("event-1", response["items"][0]["action"])
        self.assertEqual(audit, stored["zoteroAudit"])

    def test_ignored_paper_is_hidden_and_counted(self):
        key = app.paper_key(SAMPLE_PAPER)
        library = {
            "favorites": {},
            "ignored": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": SAMPLE_PAPER}},
            "downloads": {},
            "history": [],
        }

        visible, hidden_count = app.apply_library_state([dict(SAMPLE_PAPER)], library)

        self.assertEqual([], visible)
        self.assertEqual(1, hidden_count)

    def test_search_result_inherits_download_and_fulltext_state(self):
        key = app.paper_key(SAMPLE_PAPER)
        stored_paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "isDownloaded": True,
            "fulltextTranslations": [{
                "type": "fulltext",
                "language": "zh",
                "format": "markdown",
                "file": "translated_papers/sample.bilingual.md",
                "model": "gpt-test",
                "createdAt": "2026-05-29T00:00:00+00:00",
            }],
        })
        library = {
            "papers": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored_paper}},
            "favorites": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored_paper}},
            "ignored": {},
            "downloads": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "filename": "sample.pdf", "paper": stored_paper}},
            "history": [],
        }

        visible, hidden_count = app.apply_library_state([dict(SAMPLE_PAPER)], library)

        self.assertEqual(0, hidden_count)
        self.assertTrue(visible[0]["isFavorite"])
        self.assertTrue(visible[0]["isDownloaded"])
        self.assertEqual("translated_papers/sample.bilingual.md", visible[0]["fulltextTranslations"][0]["file"])

    def test_search_result_inherits_full_abstract_from_library(self):
        key = app.paper_key(SAMPLE_PAPER)
        stored_paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "abstract": "Short abstract...",
            "fullAbstract": "Complete abstract sentence one. Complete abstract sentence two.",
        })
        library = {
            "papers": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored_paper}},
            "favorites": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored_paper}},
            "ignored": {},
            "downloads": {},
            "history": [],
        }

        visible, hidden_count = app.apply_library_state([{**SAMPLE_PAPER, "abstract": "Short abstract..."}], library)

        self.assertEqual(0, hidden_count)
        self.assertEqual("Complete abstract sentence one. Complete abstract sentence two.", visible[0]["fullAbstract"])
        self.assertIn("Complete abstract sentence one.", visible[0]["abstract"])

    def test_search_result_keeps_more_complete_abstract_than_library(self):
        key = app.paper_key(SAMPLE_PAPER)
        stored_paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "abstract": "Short abstract...",
            "fullAbstract": "Short abstract th...",
            "translations": {
                "zh": {
                    "text": "短译文 th...",
                    "language": "zh",
                    "sourceHash": app.stable_text_hash("Short abstract th..."),
                }
            },
        })
        library = {
            "papers": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored_paper}},
            "favorites": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored_paper}},
            "ignored": {},
            "downloads": {},
            "history": [],
        }
        fresh = {
            **SAMPLE_PAPER,
            "abstract": "Short abstract...",
            "fullAbstract": "Complete abstract sentence one. Complete abstract sentence two.",
        }

        visible, hidden_count = app.apply_library_state([fresh], library)

        self.assertEqual(0, hidden_count)
        self.assertEqual("Complete abstract sentence one. Complete abstract sentence two.", visible[0]["fullAbstract"])
        self.assertTrue(visible[0]["translations"]["zh"]["stale"])

    def test_resolve_translated_file_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            translated_dir = Path(tmpdir) / "translated_papers"
            translated_dir.mkdir()
            outside = Path(tmpdir) / "outside.md"
            outside.write_text("nope", encoding="utf-8")
            with patch.object(app, "TRANSLATED_DIR", translated_dir):
                with self.assertRaises(ValueError):
                    app.resolve_translated_file("../outside.md")

    def test_open_fulltext_folder_selects_translated_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            translated_dir = Path(tmpdir) / "translated_papers"
            translated_dir.mkdir()
            output = translated_dir / "sample.bilingual.md"
            output.write_text("ok", encoding="utf-8")
            with (
                patch.object(app, "TRANSLATED_DIR", translated_dir),
                patch.object(app.sys, "platform", "win32"),
                patch.object(app.subprocess, "Popen") as popen,
            ):
                response = app.open_fulltext_folder({"file": "sample.bilingual.md"})

        self.assertTrue(response["ok"])
        self.assertEqual("translated_papers/sample.bilingual.md", response["file"])
        popen.assert_called_once()
        self.assertEqual("explorer", popen.call_args.args[0][0])

    def test_translated_relative_path_falls_back_to_translated_dir_segment(self):
        path = Path("C:/Users/runneradmin/AppData/Local/Temp/tmp123/translated_papers/sample.bilingual.md")

        with patch.object(app, "TRANSLATED_DIR", Path("C:/Users/RUNNER~1/AppData/Local/Temp/tmp123/translated_papers")):
            relative = app.translated_relative_path(path)

        self.assertEqual("translated_papers/sample.bilingual.md", relative)

    def test_translated_relative_path_prefers_active_translated_dir_inside_repo(self):
        translated_dir = app.ROOT_DIR / "downloaded_papers" / "validation" / "translated"
        path = translated_dir / "sample.bilingual.md"

        with patch.object(app, "TRANSLATED_DIR", translated_dir):
            relative = app.translated_relative_path(path)

        self.assertEqual("translated_papers/sample.bilingual.md", relative)

    def test_resolve_translated_file_uses_active_translated_dir_for_standard_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            translated_dir = Path(tmpdir) / "custom-translated"
            translated_dir.mkdir()
            output = translated_dir / "sample.bilingual.md"
            output.write_text("ok", encoding="utf-8")
            with patch.object(app, "TRANSLATED_DIR", translated_dir):
                resolved = app.resolve_translated_file("translated_papers/sample.bilingual.md")

        self.assertEqual(output.resolve(), resolved)

    def test_update_library_persists_favorite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                response = app.update_library({"action": "favorite", "paper": SAMPLE_PAPER})
                stored = app.load_library()

        key = app.paper_key(SAMPLE_PAPER)
        self.assertTrue(response["ok"])
        self.assertIn(key, stored["favorites"])
        self.assertEqual("Vision Language Models for Scientific Discovery", stored["favorites"][key]["paper"]["title"])
        self.assertEqual(app.LIBRARY_SCHEMA_VERSION, stored["version"])
        self.assertIn("translations", stored["favorites"][key]["paper"])

    def test_migrates_legacy_library_entries(self):
        key = app.paper_key(SAMPLE_PAPER)
        legacy = {
            "version": 1,
            "favorites": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": SAMPLE_PAPER}},
            "ignored": {},
            "downloads": {},
            "history": [{"query": "vision language", "resultCount": 3, "sources": ["arxiv"]}],
        }

        migrated = app.migrate_library(legacy)

        self.assertEqual(app.LIBRARY_SCHEMA_VERSION, migrated["version"])
        self.assertIn(key, migrated["favorites"])
        paper = migrated["favorites"][key]["paper"]
        self.assertEqual(key, paper["paperKey"])
        self.assertEqual("", paper["readingStatus"])
        self.assertEqual([], paper["tags"])
        self.assertEqual({}, paper["translations"])
        self.assertEqual(1, len(migrated["history"]))

    def test_unignore_removes_ignored_entry(self):
        key = app.paper_key(SAMPLE_PAPER)
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "favorites": {},
                    "ignored": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": SAMPLE_PAPER}},
                    "downloads": {},
                    "history": [],
                })
                response = app.update_library({"action": "unignore", "paperKey": key})
                stored = app.load_library()

        self.assertTrue(response["ok"])
        self.assertNotIn(key, stored["ignored"])

    def test_markdown_export_prefers_full_abstract(self):
        paper = {
            **SAMPLE_PAPER,
            "abstract": "Short abstract.",
            "fullAbstract": "Full abstract sentence one. Full abstract sentence two.",
        }

        content = app.export_markdown([paper])

        self.assertIn("Full abstract sentence one. Full abstract sentence two.", content)
        self.assertNotIn("Short abstract.", content)

    def test_markdown_export_marks_truncated_fallback(self):
        paper = {
            **SAMPLE_PAPER,
            "abstract": "Short abstract...",
            "fullAbstract": "",
        }

        content = app.export_markdown([paper])

        self.assertIn("Short abstract... (可能已截断)", content)

    def test_markdown_export_marks_truncated_full_abstract(self):
        paper = {
            **SAMPLE_PAPER,
            "abstract": "Short abstract...",
            "fullAbstract": "Full abstract begins but ends with th...",
        }

        content = app.export_markdown([paper])

        self.assertIn("Full abstract begins but ends with th... (可能已截断)", content)

    def test_bilingual_export_marks_truncated_translation(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "fullAbstract": "Full abstract begins but ends with th...",
            "translations": {
                "zh": {
                    "text": "中文摘要也被截断 th...",
                    "language": "zh",
                    "sourceHash": app.stable_text_hash("Full abstract begins but ends with th..."),
                }
            },
        })

        content = app.export_bilingual_markdown([paper])

        self.assertIn("### English Abstract（可能已截断）", content)
        self.assertIn("### 中文摘要（可能已截断）", content)

    def test_refresh_favorites_updates_snapshot(self):
        key = app.paper_key(SAMPLE_PAPER)
        stale_paper = {
            **SAMPLE_PAPER,
            "abstract": "Short abstract...",
            "fullAbstract": "",
            "note": "Keep my note",
            "tags": ["agent"],
        }
        refreshed_paper = {
            **SAMPLE_PAPER,
            "abstract": "Short abstract.",
            "fullAbstract": "Full abstract after refresh.",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                app.save_library({
                    "version": 1,
                    "favorites": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stale_paper}},
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                with patch.object(app, "find_refreshed_paper", return_value=refreshed_paper):
                    response = app.refresh_favorites_metadata()
                stored = app.load_library()

        self.assertEqual(1, response["refreshed"])
        self.assertIn(key, stored["favorites"])
        self.assertEqual("Full abstract after refresh.", stored["favorites"][key]["paper"]["fullAbstract"])
        self.assertEqual("Full abstract after refresh.", stored["papers"][key]["paper"]["fullAbstract"])
        self.assertEqual("Keep my note", stored["favorites"][key]["paper"]["note"])
        self.assertEqual(["agent"], stored["favorites"][key]["paper"]["tags"])
        self.assertEqual(key, stored["favorites"][key]["paper"]["paperKey"])

    def test_paper_snapshot_normalizes_abstract_metadata(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "fullAbstract": "Complete alert abstract with enough detail to keep as a full record.",
            "abstractSource": "alert",
            "abstractSourceLabel": "ScienceDirect Alert",
            "abstractFetchedAt": "2026-06-01T00:00:00+00:00",
            "abstractAccessMode": "user-visible",
            "abstractDiagnostics": [{
                "source": "OpenAlex",
                "sourceLabel": "OpenAlex",
                "status": "available",
                "message": "Open metadata returned an abstract.",
                "completeness": "complete",
                "textLength": "64",
                "selected": True,
            }],
            "abstractConflict": {
                "hasConflict": True,
                "sources": ["OpenAlex", "Crossref"],
                "message": "多个来源返回了不完全相同的完整摘要。",
            },
        })

        self.assertEqual("alert", paper["abstractSource"])
        self.assertEqual("ScienceDirect Alert", paper["abstractSourceLabel"])
        self.assertEqual("complete", paper["abstractCompleteness"])
        self.assertEqual("user-visible", paper["abstractAccessMode"])
        self.assertEqual("2026-06-01T00:00:00+00:00", paper["abstractFetchedAt"])
        self.assertEqual("openalex", paper["abstractDiagnostics"][0]["source"])
        self.assertTrue(paper["abstractDiagnostics"][0]["selected"])
        self.assertEqual(64, paper["abstractDiagnostics"][0]["textLength"])
        self.assertTrue(paper["abstractConflict"]["hasConflict"])

    def test_merge_paper_abstract_keeps_long_complete_over_short_candidate(self):
        long_abstract = " ".join(["This is a complete local abstract with more detail."] * 12)
        current = app.paper_snapshot({
            **SAMPLE_PAPER,
            "fullAbstract": long_abstract,
            "abstractSource": "zotero",
            "abstractSourceLabel": "Zotero",
            "abstractCompleteness": "complete",
        })
        candidate = {
            "text": "Short complete abstract.",
            "source": "crossref",
            "sourceLabel": "Crossref",
            "accessMode": "open-metadata",
            "completeness": "complete",
        }

        merged = app.merge_paper_abstract(current, candidate)

        self.assertEqual(long_abstract, merged["fullAbstract"])
        self.assertEqual("zotero", merged["abstractSource"])

    def test_locked_abstract_is_not_replaced_by_auto_candidate(self):
        locked = app.paper_snapshot({
            **SAMPLE_PAPER,
            "fullAbstract": "Locked abstract chosen by the user.",
            "abstractSource": "alert",
            "abstractSourceLabel": "ScienceDirect Alert",
            "abstractLocked": True,
            "abstractConfirmedAt": "2026-06-01T00:00:00+00:00",
            "abstractConfirmedBy": "user",
        })
        candidate = {
            "text": "Longer complete abstract from an automatic open metadata refresh.",
            "source": "openalex",
            "sourceLabel": "OpenAlex",
            "accessMode": "open-metadata",
            "completeness": "complete",
        }

        merged = app.merge_paper_abstract(locked, candidate)

        self.assertEqual("Locked abstract chosen by the user.", merged["fullAbstract"])
        self.assertEqual("alert", merged["abstractSource"])
        self.assertTrue(merged["abstractLocked"])

    def test_confirm_abstract_candidate_preserves_zotero_binding(self):
        existing = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "confirm-abstract-preserve",
            "abstract": "Short abstract...",
            "fullAbstract": "",
            "note": "Keep note",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(existing)
        candidate = {
            "text": "Confirmed abstract from a user-visible subscription alert.",
            "source": "alert",
            "sourceLabel": "ScienceDirect Alert",
            "accessMode": "user-visible",
            "fetchedAt": "2026-06-01T00:00:00+00:00",
            "completeness": "complete",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": existing}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.abstract_confirm_payload({
                    "paperKey": key,
                    "candidate": candidate,
                    "lock": True,
                })
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertTrue(response["locked"])
        self.assertEqual("Confirmed abstract from a user-visible subscription alert.", paper["fullAbstract"])
        self.assertEqual("alert", paper["abstractSource"])
        self.assertTrue(paper["abstractLocked"])
        self.assertEqual("user", paper["abstractConfirmedBy"])
        self.assertEqual("confirm", paper["abstractAudit"][0]["action"])
        self.assertEqual("ITEMKEYA", paper["zotero"]["itemKey"])
        self.assertEqual("confirmed", paper["zoteroLink"]["status"])
        self.assertEqual("ITEMKEYA", paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])
        self.assertEqual(12, paper["zoteroSync"]["noteID"])
        self.assertEqual("Keep note", paper["note"])

    def test_enrich_favorites_respects_locked_abstract_and_keeps_candidates(self):
        locked = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "locked-enrich",
            "doi": "10.1234/locked.enrich",
            "fullAbstract": "Locked abstract selected by the user.",
            "abstractSource": "alert",
            "abstractSourceLabel": "WoS Alert",
            "abstractLocked": True,
            "abstractConfirmedAt": "2026-06-01T00:00:00+00:00",
            "abstractConfirmedBy": "user",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(locked)
        candidate = {
            "text": "Automatic OpenAlex abstract should stay only as a candidate.",
            "source": "openalex",
            "sourceLabel": "OpenAlex",
            "accessMode": "open-metadata",
            "fetchedAt": "2026-06-01T00:00:00+00:00",
            "completeness": "complete",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "read_zotero_candidates", return_value=[]),
                patch.object(
                    app,
                    "open_metadata_abstract_candidates_with_diagnostics",
                    return_value=([candidate], [app.abstract_diagnostic_from_candidate(candidate)]),
                ),
                patch.object(app, "find_refreshed_paper", return_value=None),
            ):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": locked}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.enrich_favorites_abstracts({"onlyIncomplete": False})
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertEqual(1, response["checked"])
        self.assertEqual(0, response["enriched"])
        self.assertEqual("Locked abstract selected by the user.", paper["fullAbstract"])
        self.assertEqual("alert", paper["abstractSource"])
        self.assertTrue(paper["abstractLocked"])
        self.assertTrue(any(item["source"] == "openalex" for item in paper["abstractCandidates"]))
        self.assertEqual("ITEMKEYA", paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])

    def test_search_result_inherits_locked_abstract_from_library(self):
        key = app.paper_key(SAMPLE_PAPER)
        stored = app.paper_snapshot({
            **SAMPLE_PAPER,
            "fullAbstract": "Locked library abstract.",
            "abstractSource": "alert",
            "abstractSourceLabel": "ScienceDirect Alert",
            "abstractLocked": True,
            "abstractConfirmedAt": "2026-06-01T00:00:00+00:00",
            "abstractConfirmedBy": "user",
        })
        library = {
            "version": 3,
            "papers": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored}},
            "favorites": {key: {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stored}},
            "ignored": {},
            "downloads": {},
            "history": [],
        }

        visible, hidden_count = app.apply_library_state(
            [{**SAMPLE_PAPER, "fullAbstract": "Longer search result abstract that should not override the lock."}],
            library,
        )

        self.assertEqual(0, hidden_count)
        self.assertEqual("Locked library abstract.", visible[0]["fullAbstract"])
        self.assertEqual("alert", visible[0]["abstractSource"])
        self.assertTrue(visible[0]["abstractLocked"])

    def test_parse_alert_text_extracts_chinese_abstract_and_doi(self):
        papers = app.parse_alert_text(
            """
            标题: Subscription Alert Paper
            作者: Ada Lovelace
            期刊: Journal of Alerts
            DOI: 10.1234/alert.paper
            摘要: This alert abstract is visible to the user and contains the complete summary.
            链接: https://example.test/alert.paper
            """,
            "ScienceDirect Alert",
        )

        self.assertEqual(1, len(papers))
        paper = papers[0]
        self.assertEqual("Subscription Alert Paper", paper["title"])
        self.assertEqual("10.1234/alert.paper", paper["doi"])
        self.assertEqual("alert", paper["source"])
        self.assertEqual("ScienceDirect Alert", paper["abstractSourceLabel"])
        self.assertIn("complete summary", paper["abstract"])
        self.assertEqual("complete", paper["abstractCompleteness"])

    def test_parse_alert_text_extracts_multiple_ris_items(self):
        papers = app.parse_alert_text(
            """
            TY  - JOUR
            TI  - First Alert Paper
            AU  - Ada Lovelace
            PY  - 2026
            DO  - 10.1234/alert.first
            AB  - First visible alert abstract.
            ER  -
            TY  - JOUR
            TI  - Second Alert Paper
            AU  - Alan Turing
            PY  - 2025
            DO  - 10.1234/alert.second
            AB  - Second visible alert abstract.
            ER  -
            """,
            "WoS Alert",
        )

        self.assertEqual(2, len(papers))
        self.assertEqual("First Alert Paper", papers[0]["title"])
        self.assertEqual("10.1234/alert.first", papers[0]["doi"])
        self.assertIn("First visible", papers[0]["fullAbstract"])
        self.assertEqual("Second Alert Paper", papers[1]["title"])
        self.assertEqual("10.1234/alert.second", papers[1]["doi"])
        self.assertIn("Second visible", papers[1]["fullAbstract"])

    def test_import_alert_merges_existing_and_preserves_zotero_binding(self):
        existing = app.paper_snapshot({
            **SAMPLE_PAPER,
            "doi": "10.1234/alert.paper",
            "abstract": "Short abstract...",
            "fullAbstract": "",
            "note": "Keep my note",
            "tags": ["agent"],
            "zotero": {"itemKey": "ITEMKEY", "libraryID": 1, "itemID": 10},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEY"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEY", "noteID": 12},
        })
        key = app.paper_key(existing)
        alert_text = """
        标题: Vision Language Models for Scientific Discovery
        DOI: 10.1234/alert.paper
        摘要: Full abstract from a user-visible subscription alert.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "read_zotero_candidates", return_value=[]),
                patch.object(app, "open_metadata_abstract_candidates_with_diagnostics", return_value=([], [])),
            ):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": existing}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": True,
                })
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertEqual(1, response["updated"])
        self.assertEqual(1, len(stored["favorites"]))
        self.assertEqual("Full abstract from a user-visible subscription alert.", paper["fullAbstract"])
        self.assertEqual("alert", paper["abstractSource"])
        self.assertEqual("ITEMKEY", paper["zotero"]["itemKey"])
        self.assertEqual("ITEMKEY", paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])
        self.assertEqual("Keep my note", paper["note"])
        self.assertEqual(["agent"], paper["tags"])

    def test_import_alert_records_subscription_source_history(self):
        alert_text = """
        ScienceDirect Topic Alert
        Title: Source History Paper
        DOI: 10.1234/source.history
        Abstract: Complete ScienceDirect alert abstract visible to the user.
        URL: https://www.sciencedirect.com/science/article/pii/S123456
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                app.save_library(app.empty_library())
                response = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "Alert",
                    "enrich": False,
                })
                stored = app.load_library()
                subscription = app.public_subscription_status(stored)

        self.assertEqual(1, response["imported"])
        self.assertEqual("sciencedirect-alert", response["source"]["id"])
        self.assertTrue(response["historyEvent"]["detected"])
        self.assertEqual("sciencedirect-alert", stored["alertImportHistory"][0]["sourceId"])
        self.assertEqual(1, stored["alertImportHistory"][0]["count"])
        source = next(item for item in subscription["sources"] if item["id"] == "sciencedirect-alert")
        self.assertEqual(1, source["importCount"])
        self.assertEqual("ScienceDirect Alert", source["sourceLabel"])
        self.assertIn("alertInbox", subscription)
        self.assertEqual(0, subscription["alertInbox"]["pendingCount"])

    def test_import_alert_can_skip_open_metadata_checks_when_enriching(self):
        alert_text = """
        ScienceDirect Topic Alert
        Title: No Open Metadata Check Paper
        DOI: 10.1234/no.open.check
        Abstract: Complete alert abstract visible to the user.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "read_zotero_candidates", return_value=[]),
                patch.object(app, "open_metadata_abstract_candidates_with_diagnostics") as open_metadata,
            ):
                app.save_library(app.empty_library())
                response = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": True,
                    "checkOpenMetadata": False,
                })

        open_metadata.assert_not_called()
        self.assertEqual(1, response["imported"])
        self.assertFalse(response["checkOpenMetadata"])
        self.assertEqual(1, response["sourceHealth"]["alertComplete"])
        self.assertEqual(0, response["sourceHealth"]["openLagging"])

    def test_subscription_sources_payload_allows_custom_authorized_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                app.save_library(app.empty_library())
                response = app.subscription_sources_payload({
                    "action": "upsert",
                    "source": {
                        "id": "institution-alert",
                        "name": "Institution Alert",
                        "provider": "custom",
                        "sourceLabel": "Institution Alert",
                        "sourceType": "custom",
                        "authorizationMode": "manual-alert",
                        "enabled": True,
                    },
                })
                toggled = app.subscription_sources_payload({
                    "action": "toggle",
                    "source": {"id": "institution-alert"},
                })

        custom = next(item for item in response["sources"] if item["id"] == "institution-alert")
        self.assertTrue(custom["enabled"])
        self.assertEqual("manual-alert", custom["authorizationMode"])
        toggled_custom = next(item for item in toggled["sources"] if item["id"] == "institution-alert")
        self.assertFalse(toggled_custom["enabled"])

    def test_import_alert_respects_locked_abstract_and_preserves_zotero_binding(self):
        locked = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "locked-alert-import",
            "doi": "10.1234/locked.alert",
            "abstract": "Locked alert abstract.",
            "fullAbstract": "Locked alert abstract selected by the user.",
            "abstractSource": "alert",
            "abstractSourceLabel": "WoS Alert",
            "abstractLocked": True,
            "abstractConfirmedAt": "2026-06-01T00:00:00+00:00",
            "abstractConfirmedBy": "user",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(locked)
        alert_text = """
        Web of Science Alert
        Title: Vision Language Models for Scientific Discovery
        DOI: 10.1234/locked.alert
        Abstract: New user-visible alert abstract should remain only a source record.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": locked}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "WoS Alert",
                    "enrich": False,
                })
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertEqual(1, response["updated"])
        self.assertEqual("wos-alert", response["source"]["id"])
        self.assertEqual("Locked alert abstract selected by the user.", paper["fullAbstract"])
        self.assertEqual("alert", paper["abstractSource"])
        self.assertTrue(paper["abstractLocked"])
        self.assertEqual("ITEMKEYA", paper["zotero"]["itemKey"])
        self.assertEqual("ITEMKEYA", paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])

    def test_import_alert_review_only_adds_inbox_without_overwriting_existing_abstract(self):
        existing = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "review-only-alert",
            "doi": "10.1234/review.alert",
            "abstract": "Short existing abstract...",
            "fullAbstract": "",
            "abstractSource": "source",
            "abstractSourceLabel": "Open metadata",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(existing)
        alert_text = """
        ScienceDirect Alert
        Title: Vision Language Models for Scientific Discovery
        DOI: 10.1234/review.alert
        Abstract: Full alert abstract that should wait for explicit user adoption.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": existing}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": False,
                    "reviewOnly": True,
                })
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertTrue(response["reviewOnly"])
        self.assertEqual("Short existing abstract...", paper["abstract"])
        self.assertEqual("", paper["fullAbstract"])
        self.assertEqual("source", paper["abstractSource"])
        self.assertEqual("ITEMKEYA", paper["zoteroLink"]["itemKey"])
        self.assertEqual(1, len(stored["alertInbox"]))
        inbox_item = app.public_alert_inbox_status(stored)["items"][0]
        self.assertEqual("pending", inbox_item["status"])
        self.assertTrue(inbox_item["canAdopt"])
        self.assertEqual(key, inbox_item["paperKey"])
        self.assertEqual("alert", paper["abstractCandidates"][0]["source"])

    def test_import_alert_review_only_new_paper_stages_candidate_before_adoption(self):
        alert_text = """
        ScienceDirect Alert
        Title: New Alert Review Paper
        DOI: 10.1234/new.review.alert
        Abstract: Full alert abstract should be staged until the user adopts it.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                imported = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": False,
                    "reviewOnly": True,
                })
                stored_after_import = app.load_library()
                event_id = imported["alertInboxEvents"][0]["id"]
                adopted = app.alert_inbox_payload({
                    "action": "batch-adopt",
                    "eventIds": [event_id],
                    "lock": True,
                })
                stored_after_adopt = app.load_library()

        key = imported["keys"][0]
        staged = stored_after_import["favorites"][key]["paper"]
        self.assertEqual("", staged["fullAbstract"])
        self.assertNotEqual("Full alert abstract should be staged until the user adopts it.", staged["abstract"])
        self.assertEqual("source", staged["abstractSource"])
        self.assertEqual("alert", staged["abstractCandidates"][0]["source"])
        self.assertEqual("Full alert abstract should be staged until the user adopts it.", staged["abstractCandidates"][0]["text"])
        inbox_item = app.public_alert_inbox_status(stored_after_import)["items"][0]
        self.assertEqual("pending", inbox_item["status"])
        self.assertTrue(inbox_item["canAdopt"])

        paper = stored_after_adopt["favorites"][key]["paper"]
        self.assertEqual(1, adopted["adopted"])
        self.assertEqual("Full alert abstract should be staged until the user adopts it.", paper["fullAbstract"])
        self.assertEqual("alert", paper["abstractSource"])
        self.assertTrue(paper["abstractLocked"])
        self.assertEqual("user", paper["abstractConfirmedBy"])

    def test_alert_inbox_batch_adopt_confirms_and_preserves_zotero_binding(self):
        existing = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "adopt-alert",
            "doi": "10.1234/adopt.alert",
            "abstract": "Short existing abstract...",
            "fullAbstract": "",
            "abstractSource": "source",
            "abstractSourceLabel": "Open metadata",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(existing)
        alert_text = """
        Web of Science Alert
        Title: Vision Language Models for Scientific Discovery
        DOI: 10.1234/adopt.alert
        Abstract: Full alert abstract adopted from the review inbox.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": existing}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                imported = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "WoS Alert",
                    "enrich": False,
                    "reviewOnly": True,
                })
                event_id = imported["alertInboxEvents"][0]["id"]
                adopted = app.alert_inbox_payload({
                    "action": "batch-adopt",
                    "eventIds": [event_id],
                    "lock": True,
                })
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertEqual(1, adopted["adopted"])
        self.assertEqual("Full alert abstract adopted from the review inbox.", paper["fullAbstract"])
        self.assertEqual("alert", paper["abstractSource"])
        self.assertEqual("WoS Alert", paper["abstractSourceLabel"])
        self.assertTrue(paper["abstractLocked"])
        self.assertEqual("user", paper["abstractConfirmedBy"])
        self.assertEqual("ITEMKEYA", paper["zotero"]["itemKey"])
        self.assertEqual("ITEMKEYA", paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])
        self.assertEqual("alert-inbox-adopt", paper["abstractAudit"][0]["action"])
        inbox_item = app.public_alert_inbox_status(stored)["items"][0]
        self.assertEqual("adopted", inbox_item["status"])
        self.assertFalse(inbox_item["canAdopt"])

    def test_alert_inbox_batch_adopt_skips_locked_abstract_and_preserves_zotero_binding(self):
        locked = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "locked-inbox-alert",
            "doi": "10.1234/locked.inbox",
            "abstract": "Locked abstract.",
            "fullAbstract": "Locked abstract selected by the user.",
            "abstractSource": "alert",
            "abstractSourceLabel": "WoS Alert",
            "abstractLocked": True,
            "abstractConfirmedAt": "2026-06-01T00:00:00+00:00",
            "abstractConfirmedBy": "user",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(locked)
        alert_text = """
        ScienceDirect Alert
        Title: Vision Language Models for Scientific Discovery
        DOI: 10.1234/locked.inbox
        Abstract: New alert abstract should not replace a locked user choice.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": locked}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                imported = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": False,
                    "reviewOnly": True,
                })
                event_id = imported["alertInboxEvents"][0]["id"]
                adopted = app.alert_inbox_payload({
                    "action": "batch-adopt",
                    "eventIds": [event_id],
                    "lock": True,
                })
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertEqual(0, adopted["adopted"])
        self.assertEqual(1, adopted["skipped"]["locked"])
        self.assertEqual("Locked abstract selected by the user.", paper["fullAbstract"])
        self.assertEqual("alert", paper["abstractSource"])
        self.assertTrue(paper["abstractLocked"])
        self.assertEqual("ITEMKEYA", paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])
        inbox_item = app.public_alert_inbox_status(stored)["items"][0]
        self.assertEqual("locked", inbox_item["status"])
        self.assertFalse(inbox_item["canAdopt"])

    def test_import_alert_files_reports_open_lagging_and_preserves_zotero_binding(self):
        existing = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "existing-alert-file",
            "doi": "10.1234/file.csv",
            "abstract": "Short existing abstract...",
            "fullAbstract": "",
            "zotero": {"itemKey": "ITEMFILE", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMFILE"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMFILE", "noteID": 12},
        })
        key = app.paper_key(existing)
        csv_alert = (
            "Title,Authors,Journal,Year,DOI,Abstract,URL\n"
            "\"Vision Language Models for Scientific Discovery\",\"Ada Lovelace\","
            "\"ScienceDirect Journal\",2026,10.1234/file.csv,"
            "\"Complete subscription alert abstract from a CSV export.\","
            "\"https://example.test/file.csv\"\n"
        )
        ris_alert = """
        TY  - JOUR
        TI  - RIS Alert File Paper
        AU  - Alan Turing
        PY  - 2026
        DO  - 10.1234/file.ris
        AB  - Complete subscription alert abstract from a RIS export.
        UR  - https://example.test/file.ris
        ER  -
        """
        open_empty = [
            app.abstract_diagnostic_empty("semantic", "Semantic Scholar", "No abstract found.", "empty"),
            app.abstract_diagnostic_empty("crossref", "Crossref", "No abstract found.", "empty"),
            app.abstract_diagnostic_empty("openalex", "OpenAlex", "No abstract found.", "empty"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "open_metadata_abstract_candidates_with_diagnostics", return_value=([], open_empty)),
            ):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": existing}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.import_alert_payload({
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": False,
                    "checkOpenMetadata": True,
                    "files": [
                        {
                            "name": "sciencedirect-alert.csv",
                            "mimeType": "text/csv",
                            "contentBase64": base64.b64encode(csv_alert.encode("utf-8")).decode("ascii"),
                        },
                        {
                            "name": "wos-alert.ris",
                            "mimeType": "application/x-research-info-systems",
                            "contentBase64": base64.b64encode(ris_alert.encode("utf-8")).decode("ascii"),
                        },
                    ],
                })
                stored = app.load_library()

        self.assertEqual(2, response["documents"])
        self.assertEqual(2, response["parseReport"]["documents"])
        self.assertEqual(2, response["parseReport"]["parsed"])
        self.assertEqual(2, response["parseReport"]["doiCount"])
        self.assertEqual(2, response["parseReport"]["completeAbstracts"])
        self.assertEqual(2, response["sourceHealth"]["openLagging"])
        self.assertEqual(1, response["updated"])
        self.assertEqual(1, response["imported"])
        paper = stored["favorites"][key]["paper"]
        self.assertEqual("Complete subscription alert abstract from a CSV export.", paper["fullAbstract"])
        self.assertEqual("ITEMFILE", paper["zotero"]["itemKey"])
        self.assertEqual("ITEMFILE", paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])
        self.assertEqual("open_lagging", paper["alertSourceHealth"]["status"])
        self.assertEqual([], stored["alertInbox"])

    def test_import_alert_review_only_keeps_alert_candidate_when_enriched_metadata_exists(self):
        alert_text = """
        ScienceDirect Alert
        Title: Review Only Alert Paper
        DOI: 10.1234/review.enriched
        Abstract: Subscription alert abstract that the user can already view.
        """
        open_candidate = {
            "text": "Open metadata abstract returned by Crossref and should not be staged as the review-only candidate.",
            "source": "crossref",
            "sourceLabel": "Crossref",
            "accessMode": "open-metadata",
            "fetchedAt": "2026-06-01T00:00:00+00:00",
            "completeness": "complete",
        }

        def fake_enrich(paper, **_kwargs):
            return {
                "paper": app.paper_snapshot({
                    **paper,
                    "fullAbstract": open_candidate["text"],
                    "abstract": open_candidate["text"],
                    "abstractSource": "crossref",
                    "abstractSourceLabel": "Crossref",
                    "abstractCompleteness": "complete",
                    "abstractDiagnostics": [app.abstract_diagnostic_from_candidate(open_candidate)],
                    "abstractCandidates": [open_candidate],
                })
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "read_zotero_candidates", return_value=[]),
                patch.object(app, "enrich_paper_abstract", side_effect=fake_enrich),
            ):
                response = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": True,
                    "reviewOnly": True,
                })
                stored = app.load_library()

        key = response["keys"][0]
        paper = stored["favorites"][key]["paper"]
        self.assertTrue(response["reviewOnly"])
        self.assertEqual("", paper["fullAbstract"])
        self.assertEqual("source", paper["abstractSource"])
        self.assertEqual("missing", paper["abstractCompleteness"])
        self.assertEqual("open_has_abstract", paper["alertSourceHealth"]["status"])
        self.assertEqual("alert", paper["abstractCandidates"][0]["source"])
        self.assertEqual(
            "Subscription alert abstract that the user can already view.",
            paper["abstractCandidates"][0]["text"],
        )
        self.assertNotEqual(open_candidate["text"], paper["abstractCandidates"][0]["text"])
        inbox_item = app.public_alert_inbox_status(stored)["items"][0]
        self.assertEqual("pending", inbox_item["status"])
        self.assertTrue(inbox_item["canAdopt"])
        self.assertEqual(paper["abstractCandidates"][0]["text"], inbox_item["candidate"]["text"])

    def test_research_radar_reports_actions_and_uses_smart_brief_model(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "radar-action-paper",
            "doi": "10.1234/radar.paper",
            "abstract": "Complete alert abstract for radar triage.",
            "fullAbstract": "Complete alert abstract for radar triage.",
            "abstractSource": "alert",
            "abstractSourceLabel": "ScienceDirect Alert",
            "abstractCompleteness": "complete",
            "alertSourceHealth": {
                "status": "open_lagging",
                "alertComplete": True,
                "alertCompleteness": "complete",
                "openHasAbstract": False,
                "openLagging": True,
                "openMissing": True,
                "doi": "10.1234/radar.paper",
                "sourceLabel": "ScienceDirect Alert",
            },
            "translations": {
                "zh": {
                    "text": "Old translation.",
                    "language": "zh",
                    "sourceHash": app.stable_text_hash("Old abstract."),
                }
            },
            "zotero": {"itemKey": "RADARKEY", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "ambiguous", "itemKey": "RADARKEY"},
            "zoteroSync": {"status": "pending", "itemKey": "RADARKEY"},
        })
        key = app.paper_key(paper)
        alert_candidate = app.normalize_abstract_candidate({
            "text": "A newer complete alert abstract waiting in the inbox.",
            "source": "alert",
            "sourceLabel": "ScienceDirect Alert",
            "accessMode": "user-visible",
            "fetchedAt": "2026-06-01T00:00:00+00:00",
            "completeness": "complete",
        })
        alert_event = app.normalize_alert_inbox_event({
            "createdAt": "2026-06-01T00:00:00+00:00",
            "sourceId": "sciencedirect-alert",
            "sourceLabel": "ScienceDirect Alert",
            "provider": "sciencedirect",
            "authorizationMode": "manual-alert",
            "paperKey": key,
            "title": paper["title"],
            "doi": paper["doi"],
            "status": "pending",
            "candidate": alert_candidate,
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            settings_path = Path(tmpdir) / "settings.json"
            with patch.object(app, "LIBRARY_PATH", library_path), patch.object(app, "SETTINGS_PATH", settings_path):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": paper}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                library["alertInbox"] = [alert_event]
                app.save_library(library)
                app.save_settings(app.normalize_settings({
                    "provider": "apixin_gpt",
                    "apiType": "responses",
                    "baseUrl": "https://example.test",
                    "endpoint": "/v1/responses",
                    "model": "gpt-test",
                    "apiKey": "sk-test",
                }))

                deterministic = app.research_radar_payload({"smart": False, "limit": 8})
                with patch.object(app, "invoke_model_text", return_value=("Smart radar brief.", {"total_tokens": 9})) as invoke:
                    smart = app.research_radar_payload({"smart": True, "limit": 8})

        action_types = {item["type"] for item in deterministic["actions"]}
        self.assertEqual(1, deterministic["stats"]["favorites"])
        self.assertEqual(1, deterministic["stats"]["alertPending"])
        self.assertEqual(1, deterministic["stats"]["alertAdoptable"])
        self.assertEqual(1, deterministic["stats"]["translationStale"])
        self.assertEqual(1, deterministic["stats"]["zoteroReview"])
        self.assertEqual(1, deterministic["stats"]["openLagging"])
        self.assertIn("alert-adopt", action_types)
        self.assertIn("review-source-health", action_types)
        self.assertIn("translate", action_types)
        self.assertIn("zotero-confirm", action_types)
        self.assertIn("read-later", action_types)
        self.assertEqual("skipped", deterministic["smartBrief"]["status"])
        self.assertEqual("done", smart["smartBrief"]["status"])
        self.assertEqual("Smart radar brief.", smart["smartBrief"]["text"])
        self.assertEqual({"total_tokens": 9}, smart["smartBrief"]["usage"])
        invoke.assert_called_once()

    def test_enrich_favorites_preserves_zotero_binding(self):
        stale = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "enrich-preserve",
            "doi": "10.1234/enrich.paper",
            "abstract": "Short abstract...",
            "fullAbstract": "",
            "note": "Do not overwrite",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(stale)
        candidate = {
            "text": "Complete abstract from OpenAlex metadata.",
            "source": "openalex",
            "sourceLabel": "OpenAlex",
            "accessMode": "open-metadata",
            "fetchedAt": "2026-06-01T00:00:00+00:00",
            "completeness": "complete",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "read_zotero_candidates", return_value=[]),
                patch.object(
                    app,
                    "open_metadata_abstract_candidates_with_diagnostics",
                    return_value=([candidate], [app.abstract_diagnostic_from_candidate(candidate)]),
                ),
                patch.object(app, "find_refreshed_paper", return_value=None),
            ):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stale}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.enrich_favorites_abstracts({"onlyIncomplete": True})
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertEqual(1, response["checked"])
        self.assertEqual(1, response["enriched"])
        self.assertEqual("Complete abstract from OpenAlex metadata.", paper["fullAbstract"])
        self.assertEqual("openalex", paper["abstractSource"])
        self.assertEqual("ITEMKEYA", paper["zotero"]["itemKey"])
        self.assertEqual("confirmed", paper["zoteroLink"]["status"])
        self.assertEqual("synced", paper["zoteroSync"]["status"])
        self.assertEqual("Do not overwrite", paper["note"])
        self.assertTrue(any(item["source"] == "openalex" for item in paper["abstractDiagnostics"]))

    def test_enrich_paper_records_open_metadata_diagnostics_and_conflict(self):
        crossref = {
            "text": "Complete abstract from Crossref metadata.",
            "source": "crossref",
            "sourceLabel": "Crossref",
            "accessMode": "open-metadata",
            "fetchedAt": "2026-06-01T00:00:00+00:00",
            "completeness": "complete",
        }
        openalex = {
            "text": "Different complete abstract from OpenAlex metadata.",
            "source": "openalex",
            "sourceLabel": "OpenAlex",
            "accessMode": "open-metadata",
            "fetchedAt": "2026-06-01T00:00:00+00:00",
            "completeness": "complete",
        }

        with (
            patch.object(app, "open_metadata_abstract_candidates_with_diagnostics", return_value=(
                [crossref, openalex],
                [
                    app.abstract_diagnostic_from_candidate(crossref),
                    app.abstract_diagnostic_from_candidate(openalex),
                ],
            )),
            patch.object(app, "find_refreshed_paper", return_value=None),
        ):
            response = app.enrich_paper_abstract(
                {**SAMPLE_PAPER, "doi": "10.1234/conflict.paper", "abstract": "Short abstract..."},
                zotero_candidates=[],
            )

        paper = response["paper"]
        self.assertTrue(response["changed"])
        self.assertEqual("crossref", paper["abstractSource"])
        self.assertTrue(paper["abstractConflict"]["hasConflict"])
        self.assertIn("Crossref", paper["abstractConflict"]["sources"])
        selected = [item for item in paper["abstractDiagnostics"] if item["selected"]]
        self.assertEqual("crossref", selected[0]["source"])
        self.assertTrue(any(item["source"] == "openalex" and item["status"] == "available" for item in paper["abstractDiagnostics"]))

    def test_enrich_favorites_persists_diagnostics_without_abstract_change(self):
        stale = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "diagnostics-only",
            "abstract": "Short abstract...",
            "fullAbstract": "",
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {"status": "confirmed", "itemKey": "ITEMKEYA"},
            "zoteroSync": {"status": "synced", "itemKey": "ITEMKEYA", "noteID": 12},
        })
        key = app.paper_key(stale)
        openalex_empty = app.abstract_diagnostic_empty(
            "openalex",
            "OpenAlex",
            "未返回摘要，可能尚未收录、尚未更新或该来源不公开摘要。",
            "empty",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "read_zotero_candidates", return_value=[]),
                patch.object(app, "open_metadata_abstract_candidates_with_diagnostics", return_value=([], [openalex_empty])),
                patch.object(app, "find_refreshed_paper", return_value=None),
            ):
                library = app.empty_library()
                entry = {"createdAt": "2026-05-23T00:00:00+00:00", "paper": stale}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                app.save_library(library)

                response = app.enrich_favorites_abstracts({"onlyIncomplete": True})
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertEqual(1, response["checked"])
        self.assertEqual(0, response["enriched"])
        self.assertEqual(1, response["diagnosticsUpdated"])
        self.assertEqual("", paper["fullAbstract"])
        self.assertEqual("Short abstract...", paper["abstract"])
        self.assertTrue(any(item["source"] == "openalex" and item["status"] == "empty" for item in paper["abstractDiagnostics"]))
        self.assertEqual("ITEMKEYA", paper["zoteroLink"]["itemKey"])

    def test_model_settings_public_view_masks_api_key(self):
        settings = app.normalize_settings({
            "provider": "apixin_gpt",
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-secret-value",
            "privatePdfMode": "local_only",
            "selfHostedModel": False,
        })

        public = app.public_settings(settings)

        self.assertTrue(public["hasApiKey"])
        self.assertEqual("sk-sec...alue", public["apiKeyMasked"])
        self.assertTrue(public["hasZoteroBridgeToken"])
        self.assertIn("...", public["zoteroBridgeTokenMasked"])
        self.assertNotIn("apiKey", public)
        self.assertNotIn("zoteroBridgeToken", public)
        self.assertEqual("https://example.test/v1/responses", public["finalUrl"])
        self.assertEqual("local_only", public["privatePdfMode"])
        self.assertFalse(public["selfHostedModel"])
        self.assertFalse(public["modelEndpointIsLocal"])

    def test_model_settings_preserve_existing_key_when_blank(self):
        existing = app.normalize_settings({
            "provider": "apixin_gpt",
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-existing",
        })

        updated = app.normalize_settings({"model": "gpt-new"}, existing)

        self.assertEqual("sk-existing", updated["apiKey"])
        self.assertEqual("gpt-new", updated["model"])

    def test_responses_connection_uses_responses_payload(self):
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})

            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    return {"output_text": "OK", "usage": {"input_tokens": 1, "output_tokens": 1}}

            return Response()

        settings = app.normalize_settings({
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-test",
        })

        with patch.object(app.requests, "post", side_effect=fake_post):
            text, usage = app.test_responses_connection(settings)

        self.assertEqual("OK", text)
        self.assertEqual({"input_tokens": 1, "output_tokens": 1}, usage)
        self.assertEqual("https://example.test/v1/responses", captured["url"])
        self.assertEqual("Bearer sk-test", captured["headers"]["Authorization"])
        self.assertEqual("gpt-test", captured["json"]["model"])
        self.assertEqual([{"role": "user", "content": "Reply with exactly OK."}], captured["json"]["input"])
        self.assertEqual(64, captured["json"]["max_output_tokens"])

    def test_model_connection_rejects_empty_text_response(self):
        def fake_post(url, headers, json, timeout):
            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "status": "completed",
                        "output": [],
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    }

            return Response()

        settings = {
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-test",
        }

        with patch.object(app.requests, "post", side_effect=fake_post):
            with self.assertRaises(RuntimeError) as error:
                app.test_model_connection({"settings": settings})

        self.assertIn("没有返回文本", str(error.exception))

    def test_responses_connection_falls_back_to_chat_when_output_is_empty(self):
        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})

            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    if url.endswith("/v1/responses"):
                        return {
                            "status": "completed",
                            "output": [],
                            "usage": {"input_tokens": 1, "output_tokens": 1},
                        }
                    return {"choices": [{"message": {"content": "OK"}}], "usage": {"total_tokens": 2}}

            return Response()

        settings = app.normalize_settings({
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-test",
        })

        with patch.object(app.requests, "post", side_effect=fake_post):
            text, usage = app.test_responses_connection(settings)

        self.assertEqual("OK", text)
        self.assertEqual("chat_completions", usage["fallbackApiType"])
        self.assertEqual("https://example.test/v1/responses", calls[0]["url"])
        self.assertEqual("https://example.test/v1/chat/completions", calls[1]["url"])
        self.assertEqual([{"role": "user", "content": "Reply with exactly OK."}], calls[0]["json"]["input"])
        self.assertEqual("Reply with exactly OK.", calls[1]["json"]["messages"][0]["content"])

    def test_invoke_model_text_uses_responses_message_input(self):
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})

            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "output": [{
                            "type": "message",
                            "content": [{"type": "output_text", "text": "中文译文。"}],
                        }],
                        "usage": {"total_tokens": 8},
                    }

            return Response()

        settings = app.normalize_settings({
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-test",
        })

        with patch.object(app.requests, "post", side_effect=fake_post):
            text, usage = app.invoke_model_text(settings, "Translate this abstract.", max_tokens=120)

        self.assertEqual("中文译文。", text)
        self.assertEqual({"total_tokens": 8}, usage)
        self.assertEqual("https://example.test/v1/responses", captured["url"])
        self.assertEqual([{"role": "user", "content": "Translate this abstract."}], captured["json"]["input"])
        self.assertEqual(120, captured["json"]["max_output_tokens"])

    def test_invoke_model_text_falls_back_to_chat_when_responses_output_is_empty(self):
        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})

            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    if url.endswith("/v1/responses"):
                        return {
                            "status": "completed",
                            "output": [],
                            "usage": {"input_tokens": 3, "output_tokens": 1},
                        }
                    return {
                        "choices": [{"message": {"content": "Fallback translation."}}],
                        "usage": {"total_tokens": 11},
                    }

            return Response()

        settings = app.normalize_settings({
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-test",
        })

        with patch.object(app.requests, "post", side_effect=fake_post):
            text, usage = app.invoke_model_text(settings, "Translate this abstract.", max_tokens=120)

        self.assertEqual("Fallback translation.", text)
        self.assertEqual("chat_completions", usage["fallbackApiType"])
        self.assertEqual("https://example.test/v1/responses", calls[0]["url"])
        self.assertEqual("https://example.test/v1/chat/completions", calls[1]["url"])
        self.assertEqual([{"role": "user", "content": "Translate this abstract."}], calls[0]["json"]["input"])
        self.assertEqual("Translate this abstract.", calls[1]["json"]["messages"][0]["content"])
        self.assertEqual(120, calls[1]["json"]["max_tokens"])

    def test_chat_connection_uses_chat_payload(self):
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})

            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    return {"choices": [{"message": {"content": "OK"}}], "usage": {"total_tokens": 2}}

            return Response()

        settings = app.normalize_settings({
            "apiType": "chat_completions",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/chat/completions",
            "model": "qwen-plus",
            "apiKey": "sk-test",
        })

        with patch.object(app.requests, "post", side_effect=fake_post):
            text, usage = app.test_chat_completions_connection(settings)

        self.assertEqual("OK", text)
        self.assertEqual({"total_tokens": 2}, usage)
        self.assertEqual("https://example.test/v1/chat/completions", captured["url"])
        self.assertEqual("qwen-plus", captured["json"]["model"])
        self.assertEqual("Reply with exactly OK.", captured["json"]["messages"][0]["content"])

    def test_model_connection_persists_last_test_record(self):
        def fake_post(url, headers, json, timeout):
            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    return {"choices": [{"message": {"content": "OK"}}], "usage": {"total_tokens": 2}}

            return Response()

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            with (
                patch.object(app, "SETTINGS_PATH", settings_path),
                patch.object(app.requests, "post", side_effect=fake_post),
            ):
                response = app.test_model_connection({
                    "settings": {
                        "provider": "custom",
                        "apiType": "chat_completions",
                        "baseUrl": "https://example.test",
                        "endpoint": "/v1/chat/completions",
                        "model": "qwen-plus",
                        "apiKey": "sk-test",
                    }
                })
                saved = app.load_settings()
                diagnostic = app.model_diagnostics(saved)

        self.assertTrue(response["ok"])
        self.assertEqual("success", saved["lastTest"]["status"])
        self.assertEqual("qwen-plus", saved["lastTest"]["model"])
        self.assertEqual("https://example.test/v1/chat/completions", saved["lastTest"]["finalUrl"])
        self.assertEqual(2, saved["lastTest"]["usage"]["total_tokens"])
        self.assertEqual("success", diagnostic["lastTest"]["status"])

    def test_model_connection_persists_failed_last_test_record(self):
        def fake_post(url, headers, json, timeout):
            raise app.requests.RequestException("gateway timeout")

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            with (
                patch.object(app, "SETTINGS_PATH", settings_path),
                patch.object(app.requests, "post", side_effect=fake_post),
            ):
                with self.assertRaises(RuntimeError):
                    app.test_model_connection({
                        "settings": {
                            "provider": "custom",
                            "apiType": "chat_completions",
                            "baseUrl": "https://example.test",
                            "endpoint": "/v1/chat/completions",
                            "model": "qwen-plus",
                            "apiKey": "sk-test",
                        }
                    })
                saved = app.load_settings()

        self.assertEqual("failed", saved["lastTest"]["status"])
        self.assertIn("gateway timeout", saved["lastTest"]["error"])
        self.assertEqual("https://example.test/v1/chat/completions", saved["lastTest"]["finalUrl"])

    def test_anthropic_connection_uses_messages_payload(self):
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})

            class Response:
                status_code = 200
                text = "{}"

                def raise_for_status(self):
                    return None

                def json(self):
                    return {"content": [{"type": "text", "text": "OK"}], "usage": {"input_tokens": 1}}

            return Response()

        settings = app.normalize_settings({
            "apiType": "anthropic_messages",
            "baseUrl": "https://api.anthropic.com",
            "endpoint": "/v1/messages",
            "model": "claude-test",
            "apiKey": "sk-ant-test",
        })

        with patch.object(app.requests, "post", side_effect=fake_post):
            text, usage = app.test_anthropic_connection(settings)

        self.assertEqual("OK", text)
        self.assertEqual({"input_tokens": 1}, usage)
        self.assertEqual("https://api.anthropic.com/v1/messages", captured["url"])
        self.assertEqual("sk-ant-test", captured["headers"]["x-api-key"])
        self.assertEqual("2023-06-01", captured["headers"]["anthropic-version"])

    def test_translate_abstract_saves_translation_to_library(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            settings_path = Path(tmpdir) / "settings.json"
            with patch.object(app, "LIBRARY_PATH", library_path), patch.object(app, "SETTINGS_PATH", settings_path):
                app.save_settings(app.normalize_settings({
                    "provider": "apixin_gpt",
                    "apiType": "responses",
                    "baseUrl": "https://example.test",
                    "endpoint": "/v1/responses",
                    "model": "gpt-test",
                    "apiKey": "sk-test",
                }))
                with patch.object(app, "invoke_model_text", return_value=("这是一段中文摘要。", {"total_tokens": 12})):
                    response = app.translate_abstract({"paper": SAMPLE_PAPER})
                stored = app.load_library()

        key = app.paper_key(SAMPLE_PAPER)
        self.assertTrue(response["ok"])
        self.assertEqual("这是一段中文摘要。", response["translation"]["text"])
        self.assertIn(key, stored["papers"])
        saved_translation = stored["papers"][key]["paper"]["translations"]["zh"]
        self.assertEqual("gpt-test", saved_translation["model"])
        self.assertEqual(app.TRANSLATION_PROMPT_VERSION, saved_translation["promptVersion"])
        self.assertEqual(app.stable_text_hash(app.translation_source_text(SAMPLE_PAPER)), saved_translation["sourceHash"])

    def test_translation_marks_stale_when_abstract_changes(self):
        source_hash = app.stable_text_hash("Old abstract.")
        paper = {
            **SAMPLE_PAPER,
            "abstract": "New abstract.",
            "translations": {
                "zh": {
                    "text": "旧译文。",
                    "language": "zh",
                    "provider": "apixin_gpt",
                    "model": "gpt-test",
                    "translatedAt": "2026-05-27T00:00:00+00:00",
                    "promptVersion": app.TRANSLATION_PROMPT_VERSION,
                    "sourceHash": source_hash,
                }
            },
        }

        snapshot = app.paper_snapshot(paper)

        self.assertTrue(snapshot["translations"]["zh"]["stale"])

    def test_bilingual_markdown_includes_english_and_chinese_abstracts(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "fullAbstract": "This is the complete English abstract.",
            "translations": {
                "zh": {
                    "text": "这是完整的中文摘要。",
                    "language": "zh",
                    "provider": "apixin_gpt",
                    "model": "gpt-test",
                    "translatedAt": "2026-05-27T00:00:00+00:00",
                    "promptVersion": app.TRANSLATION_PROMPT_VERSION,
                    "sourceHash": app.stable_text_hash("This is the complete English abstract."),
                }
            },
        })

        content = app.export_bilingual_markdown([paper])

        self.assertIn("# PaperHunter 中英文摘要阅读清单", content)
        self.assertIn("### English Abstract", content)
        self.assertIn("This is the complete English abstract.", content)
        self.assertIn("### 中文摘要", content)
        self.assertIn("这是完整的中文摘要。", content)

    def test_extract_chinarxiv_page_abstract(self):
        html = """
        <h2>Abstract</h2>
        <div class="abstract-blockquote">
          <p>[Objective] Complete detail-page abstract sentence.</p>
        </div>
        """

        abstract = app.extract_chinarxiv_page_abstract(html)

        self.assertEqual("[Objective] Complete detail-page abstract sentence.", abstract)

    def test_parse_chinarxiv_feed_hydrates_truncated_abstract(self):
        feed = """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Hydrated ChinaRxiv Paper</title>
            <summary>Short abstract th...</summary>
            <link href="http://chinarxiv.org/items/chinaxiv-202504.00184" rel="alternate" />
            <updated>2026-05-29T00:00:00Z</updated>
          </entry>
        </feed>
        """

        with patch.object(app, "chinarxiv_page_abstract", return_value="Complete abstract from detail page."):
            results = app.parse_chinarxiv_feed(feed, 1, "Hydrated")

        self.assertEqual(1, len(results))
        self.assertEqual("Complete abstract from detail page.", results[0]["fullAbstract"])

    def test_batch_translate_only_missing_favorite_translations(self):
        translated_paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "2605.00001",
            "translations": {
                "zh": {
                    "text": "已有译文。",
                    "language": "zh",
                    "provider": "apixin_gpt",
                    "model": "gpt-test",
                    "translatedAt": "2026-05-27T00:00:00+00:00",
                    "promptVersion": app.TRANSLATION_PROMPT_VERSION,
                    "sourceHash": app.stable_text_hash(SAMPLE_PAPER["abstract"]),
                }
            },
        })
        missing_paper = app.paper_snapshot({**SAMPLE_PAPER, "paperId": "2605.00002", "title": "Second Paper"})
        translated_key = app.paper_key(translated_paper)
        missing_key = app.paper_key(missing_paper)

        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            settings_path = Path(tmpdir) / "settings.json"
            with patch.object(app, "LIBRARY_PATH", library_path), patch.object(app, "SETTINGS_PATH", settings_path):
                app.save_settings(app.normalize_settings({
                    "provider": "apixin_gpt",
                    "apiType": "responses",
                    "baseUrl": "https://example.test",
                    "endpoint": "/v1/responses",
                    "model": "gpt-test",
                    "apiKey": "sk-test",
                }))
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {},
                    "favorites": {
                        translated_key: {"createdAt": "2026-05-27T00:00:00+00:00", "paper": translated_paper},
                        missing_key: {"createdAt": "2026-05-27T00:00:00+00:00", "paper": missing_paper},
                    },
                    "ignored": {},
                    "downloads": {},
                    "history": [],
                })
                with patch.object(app, "invoke_model_text", return_value=("新译文。", {"total_tokens": 10})) as invoke:
                    response = app.batch_translate_abstracts({})
                stored = app.load_library()

        self.assertEqual(1, response["translated"])
        self.assertEqual(1, response["skipped"])
        self.assertEqual(1, invoke.call_count)
        self.assertEqual("已有译文。", stored["favorites"][translated_key]["paper"]["translations"]["zh"]["text"])
        self.assertEqual("新译文。", stored["favorites"][missing_key]["paper"]["translations"]["zh"]["text"])

    def test_update_paper_metadata_persists_status_note_and_tags(self):
        key = app.paper_key(SAMPLE_PAPER)
        with tempfile.TemporaryDirectory() as tmpdir:
            library_path = Path(tmpdir) / "library.json"
            with patch.object(app, "LIBRARY_PATH", library_path):
                app.update_library({"action": "favorite", "paper": SAMPLE_PAPER})
                response = app.update_library({
                    "action": "update-paper",
                    "paperKey": key,
                    "updates": {
                        "readingStatus": "reading",
                        "note": "Important for translation workflow.",
                        "tags": "llm, education",
                    },
                })
                stored = app.load_library()

        paper = stored["favorites"][key]["paper"]
        self.assertTrue(response["ok"])
        self.assertEqual("reading", paper["readingStatus"])
        self.assertEqual("Important for translation workflow.", paper["note"])
        self.assertEqual(["llm", "education"], paper["tags"])
        self.assertEqual(["llm", "education"], stored["papers"][key]["paper"]["tags"])

    def test_workspace_backup_removes_api_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_path = root / "library.json"
            settings_path = root / "settings.json"
            download_dir = root / "downloaded_papers"
            translated_dir = root / "translated_papers"
            download_dir.mkdir()
            translated_dir.mkdir()
            (download_dir / "paper.pdf").write_bytes(b"%PDF test")
            (translated_dir / "paper.zh.md").write_text("中文译文", encoding="utf-8")
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "SETTINGS_PATH", settings_path),
                patch.object(app, "DOWNLOAD_DIR", download_dir),
                patch.object(app, "TRANSLATED_DIR", translated_dir),
            ):
                app.save_library(app.empty_library())
                app.save_settings(app.normalize_settings({"apiKey": "sk-secret", "model": "gpt-test"}))
                content, filename = app.export_workspace_backup()

        self.assertTrue(filename.endswith(".zip"))
        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            settings = json.loads(zip_file.read("data/settings.json").decode("utf-8"))
            names = zip_file.namelist()
        self.assertEqual("", settings["apiKey"])
        self.assertEqual("", settings["zoteroBridgeToken"])
        self.assertTrue(settings["apiKeyRemoved"])
        self.assertTrue(settings["zoteroBridgeTokenRemoved"])
        self.assertIn("downloaded_papers/paper.pdf", names)
        self.assertIn("translated_papers/paper.zh.md", names)

    def test_http_backup_export_stream_has_zip_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_path = root / "library.json"
            settings_path = root / "settings.json"
            download_dir = root / "downloaded_papers"
            translated_dir = root / "translated_papers"
            download_dir.mkdir()
            translated_dir.mkdir()
            (download_dir / "paper.pdf").write_bytes(b"%PDF test")
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "SETTINGS_PATH", settings_path),
                patch.object(app, "DOWNLOAD_DIR", download_dir),
                patch.object(app, "TRANSLATED_DIR", translated_dir),
            ):
                app.save_library(app.empty_library())
                app.save_settings(app.normalize_settings({"apiKey": "sk-secret", "model": "gpt-test"}))
                content, filename = app.export_workspace_backup()

        self.assertTrue(filename.endswith(".zip"))
        self.assertTrue(content.startswith(b"PK\x03\x04"))

    def test_read_zotero_bridge_xpi_returns_package_bytes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xpi_path = root / "paperhunter-zotero-bridge.xpi"
            with self.temporary_settings_path(root):
                self.write_bridge_fixture_xpi(xpi_path)
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", xpi_path):
                    content, filename = app.read_zotero_bridge_xpi()

        self.assertTrue(content.startswith(b"PK\x03\x04"))
        self.assertEqual("paperhunter-zotero-bridge.xpi", filename)

    def test_zotero_bridge_package_status_reports_valid_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xpi_path = root / "paperhunter-zotero-bridge.xpi"
            with self.temporary_settings_path(root):
                self.write_bridge_fixture_xpi(xpi_path)
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", xpi_path):
                    status = app.zotero_bridge_package_status()

        self.assertTrue(status["available"])
        self.assertTrue(status["valid"])
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, status["version"])
        self.assertEqual(app.ZOTERO_BRIDGE_PROTOCOL_VERSION, status["protocolVersion"])
        self.assertEqual(app.ZOTERO_BRIDGE_DOWNLOAD_URL, status["downloadUrl"])
        self.assertGreater(status["size"], 0)

    def test_zotero_bridge_package_status_builds_missing_package_from_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.temporary_settings_path(root):
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", root / "missing.xpi"):
                    status = app.zotero_bridge_package_status()

        self.assertTrue(status["available"])
        self.assertTrue(status["valid"])
        self.assertTrue(status["builtFromSource"])
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, status["version"])
        self.assertGreater(status["size"], 0)

    def test_zotero_bridge_package_status_rebuilds_invalid_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xpi_path = root / "paperhunter-zotero-bridge.xpi"
            with self.temporary_settings_path(root):
                with zipfile.ZipFile(xpi_path, "w") as zip_file:
                    zip_file.writestr("manifest.json", json.dumps({"version": "0.1.0"}))
                    zip_file.writestr("bootstrap.js", 'var PaperHunterBridge = { version: "0.1.0", protocolVersion: 1 };')
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", xpi_path):
                    status = app.zotero_bridge_package_status()

        self.assertTrue(status["available"])
        self.assertTrue(status["valid"])
        self.assertTrue(status["builtFromSource"])
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, status["version"])

    def test_read_zotero_bridge_xpi_builds_missing_package_from_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xpi_path = root / "missing.xpi"
            with self.temporary_settings_path(root):
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", xpi_path):
                    content, filename = app.read_zotero_bridge_xpi()

        self.assertEqual("missing.xpi", filename)
        self.assertTrue(content.startswith(b"PK\x03\x04"))

    def test_read_zotero_bridge_xpi_rebuilds_incomplete_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xpi_path = root / "paperhunter-zotero-bridge.xpi"
            with self.temporary_settings_path(root):
                with zipfile.ZipFile(xpi_path, "w") as zip_file:
                    zip_file.writestr("manifest.json", "{}")
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", xpi_path):
                    content, _ = app.read_zotero_bridge_xpi()

        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, manifest["version"])

    def test_read_zotero_bridge_xpi_rebuilds_stale_package_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xpi_path = root / "paperhunter-zotero-bridge.xpi"
            with self.temporary_settings_path(root):
                with zipfile.ZipFile(xpi_path, "w") as zip_file:
                    zip_file.writestr("manifest.json", json.dumps({"version": "0.1.0"}))
                    zip_file.writestr("bootstrap.js", 'var PaperHunterBridge = { version: "0.1.0", protocolVersion: 1 };')
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", xpi_path):
                    content, _ = app.read_zotero_bridge_xpi()

        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, manifest["version"])

    def test_read_zotero_bridge_xpi_rebuilds_package_that_differs_from_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xpi_path = root / "paperhunter-zotero-bridge.xpi"
            with self.temporary_settings_path(root):
                source_bootstrap = app.ZOTERO_BRIDGE_BOOTSTRAP_PATH.read_text(encoding="utf-8")
                expected_bootstrap = source_bootstrap.replace(app.ZOTERO_BRIDGE_TOKEN_PLACEHOLDER, app.zotero_bridge_token())
                stale_bootstrap = expected_bootstrap.replace(
                    "PaperHunter Zotero Bridge started",
                    "PaperHunter Zotero Bridge stale",
                )
                self.write_bridge_fixture_xpi(xpi_path, bootstrap=stale_bootstrap)
                with patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", xpi_path):
                    content, _ = app.read_zotero_bridge_xpi()

        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            bootstrap = zip_file.read("bootstrap.js").decode("utf-8")
        self.assertEqual(
            json.loads(app.ZOTERO_BRIDGE_MANIFEST_PATH.read_text(encoding="utf-8")),
            manifest,
        )
        source_bootstrap = app.ZOTERO_BRIDGE_BOOTSTRAP_PATH.read_text(encoding="utf-8")
        self.assertNotIn(app.ZOTERO_BRIDGE_TOKEN_PLACEHOLDER, bootstrap)
        self.assertEqual(expected_bootstrap, bootstrap)

    def test_read_zotero_bridge_xpi_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            missing_manifest = root / "manifest.json"
            missing_bootstrap = root / "bootstrap.js"
            with (
                self.temporary_settings_path(root),
                patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", root / "missing.xpi"),
                patch.object(app, "ZOTERO_BRIDGE_MANIFEST_PATH", missing_manifest),
                patch.object(app, "ZOTERO_BRIDGE_BOOTSTRAP_PATH", missing_bootstrap),
            ):
                with self.assertRaises(ValueError):
                    app.read_zotero_bridge_xpi()

    def test_repository_zotero_bridge_package_matches_current_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                self.temporary_settings_path(root),
                patch.object(app, "ZOTERO_BRIDGE_XPI_PATH", root / "paperhunter-zotero-bridge.xpi"),
            ):
                content, filename = app.read_zotero_bridge_xpi()

        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            bootstrap = zip_file.read("bootstrap.js").decode("utf-8")

        self.assertEqual("paperhunter-zotero-bridge.xpi", filename)
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, manifest["version"])
        self.assertIn("protocolVersion: 1", bootstrap)
        self.assertIn("preserveUserContent", bootstrap)
        self.assertIn("managedNoteAttribute", bootstrap)
        self.assertIn("isManagedNote", bootstrap)
        self.assertIn("PaperHunter Bridge only links translated Markdown attachments", bootstrap)
        self.assertIn("assertLocalRequest", bootstrap)
        self.assertIn("allowedAttachmentRoots", bootstrap)
        self.assertIn("only links attachments inside PaperHunter translated output", bootstrap)
        self.assertIn("/paperhunter/pairing-check", bootstrap)
        self.assertIn("canVerifyPairingToken", bootstrap)
        self.assertIn("assertPaired", bootstrap)
        self.assertNotIn(app.ZOTERO_BRIDGE_TOKEN_PLACEHOLDER, bootstrap)

    def test_backup_import_rejects_path_traversal(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zip_file:
            zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1}))
            zip_file.writestr("../evil.txt", "bad")

        with self.assertRaises(ValueError):
            app.extract_backup_zip(buffer.getvalue())

    def test_backup_import_restores_workspace_files_without_api_key(self):
        buffer = io.BytesIO()
        library = app.empty_library()
        settings = app.normalize_settings({"apiKey": "sk-should-not-restore", "model": "gpt-test"})
        settings["apiKey"] = ""
        with zipfile.ZipFile(buffer, "w") as zip_file:
            zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1}))
            zip_file.writestr("data/library.json", json.dumps(library))
            zip_file.writestr("data/settings.json", json.dumps(settings))
            zip_file.writestr("downloaded_papers/a.pdf", b"%PDF test")
            zip_file.writestr("translated_papers/a.zh.md", "译文")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(app, "LIBRARY_PATH", root / "library.json"),
                patch.object(app, "SETTINGS_PATH", root / "settings.json"),
                patch.object(app, "DOWNLOAD_DIR", root / "downloaded_papers"),
                patch.object(app, "TRANSLATED_DIR", root / "translated_papers"),
            ):
                imported = app.extract_backup_zip(buffer.getvalue())
                restored_settings = app.load_settings()
                restored_pdf = (root / "downloaded_papers" / "a.pdf").exists()
                restored_md = (root / "translated_papers" / "a.zh.md").exists()

        self.assertTrue(imported["library"])
        self.assertTrue(imported["settings"])
        self.assertEqual("", restored_settings["apiKey"])
        self.assertTrue(restored_pdf)
        self.assertTrue(restored_md)

    def test_backup_import_generates_new_zotero_bridge_token(self):
        buffer = io.BytesIO()
        library = app.empty_library()
        backup_token = "A" * 32
        settings = app.normalize_settings({
            "apiKey": "sk-should-not-restore",
            "zoteroBridgeToken": backup_token,
            "model": "gpt-test",
        })
        with zipfile.ZipFile(buffer, "w") as zip_file:
            zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1}))
            zip_file.writestr("data/library.json", json.dumps(library))
            zip_file.writestr("data/settings.json", json.dumps(settings))

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(app, "LIBRARY_PATH", root / "library.json"),
                patch.object(app, "SETTINGS_PATH", root / "settings.json"),
            ):
                app.extract_backup_zip(buffer.getvalue())
                restored_settings = app.load_settings()

        self.assertEqual("", restored_settings["apiKey"])
        self.assertNotEqual(backup_token, restored_settings["zoteroBridgeToken"])
        self.assertRegex(restored_settings["zoteroBridgeToken"], r"^[A-Za-z0-9_\-]{24,96}$")

    def test_backup_preview_reports_impact_without_importing(self):
        buffer = io.BytesIO()
        library = app.empty_library()
        settings = app.normalize_settings({"apiKey": "sk-should-not-restore", "model": "gpt-test"})
        with zipfile.ZipFile(buffer, "w") as zip_file:
            zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1, "createdAt": "2026-06-08T00:00:00+00:00"}))
            zip_file.writestr("data/library.json", json.dumps(library))
            zip_file.writestr("data/settings.json", json.dumps(settings))
            zip_file.writestr("data/fulltext_tasks/task.json", "{}")
            zip_file.writestr("downloaded_papers/a.pdf", b"%PDF test")

        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(app, "LIBRARY_PATH", root / "library.json"),
                patch.object(app, "SETTINGS_PATH", root / "settings.json"),
            ):
                app.save_settings(app.normalize_settings({"apiKey": "current-key", "model": "current-model"}))
                before = app.load_settings()
                preview = app.backup_preview_payload({"contentBase64": encoded})
                after = app.load_settings()

        self.assertTrue(preview["library"]["present"])
        self.assertTrue(preview["settings"]["present"])
        self.assertEqual(1, preview["files"]["counts"]["tasks"])
        self.assertEqual(1, preview["files"]["counts"]["downloaded"])
        self.assertTrue(preview["impact"]["bridgeReinstallRequired"])
        self.assertEqual(before["apiKey"], after["apiKey"])
        self.assertEqual(before["model"], after["model"])

    def test_backup_import_payload_warns_bridge_reinstall_after_settings_restore(self):
        buffer = io.BytesIO()
        settings = app.normalize_settings({
            "apiKey": "sk-should-not-restore",
            "zoteroBridgeToken": "A" * 32,
            "model": "gpt-test",
        })
        with zipfile.ZipFile(buffer, "w") as zip_file:
            zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1}))
            zip_file.writestr("data/settings.json", json.dumps(settings))

        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(app, "LIBRARY_PATH", root / "library.json"),
                patch.object(app, "SETTINGS_PATH", root / "settings.json"),
            ):
                response = app.import_backup_payload({"contentBase64": encoded, "strategy": "merge"})
                restored_settings = app.load_settings()

        self.assertTrue(response["bridgeReinstallRequired"])
        self.assertTrue(response["bridgeReminder"]["required"])
        self.assertEqual(app.ZOTERO_BRIDGE_VERSION, response["bridgeReminder"]["expectedVersion"])
        self.assertEqual(app.ZOTERO_BRIDGE_DOWNLOAD_URL, response["bridgeReminder"]["downloadUrl"])
        self.assertIn(app.ZOTERO_BRIDGE_VERSION, response["bridgeReminder"]["message"])
        self.assertEqual(app.mask_secret(restored_settings["zoteroBridgeToken"]), response["bridgeReminder"]["tokenMasked"])
        self.assertNotIn(restored_settings["zoteroBridgeToken"], json.dumps(response, ensure_ascii=False))
        self.assertEqual("", restored_settings["apiKey"])
        self.assertTrue(response["rollbackAvailable"])
        self.assertTrue(Path(response["restorePoint"]["path"]).exists())

    def test_backup_import_rolls_back_when_file_restore_fails(self):
        buffer = io.BytesIO()
        settings = app.normalize_settings({"model": "backup-model"})
        with zipfile.ZipFile(buffer, "w") as zip_file:
            zip_file.writestr("paperhunter-backup.json", json.dumps({"app": "PaperHunter", "version": 1}))
            zip_file.writestr("data/settings.json", json.dumps(settings))
            zip_file.writestr("downloaded_papers/a.pdf", b"%PDF test")

        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_path = root / "library.json"
            settings_path = root / "settings.json"
            download_dir = root / "downloaded_papers"
            translated_dir = root / "translated_papers"
            task_dir = root / "fulltext_tasks"
            restore_dir = root / "restore-points"
            for path in (download_dir, translated_dir, task_dir):
                path.mkdir(parents=True)
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "SETTINGS_PATH", settings_path),
                patch.object(app, "DOWNLOAD_DIR", download_dir),
                patch.object(app, "TRANSLATED_DIR", translated_dir),
                patch.object(app, "FULLTEXT_TASK_DIR", task_dir),
                patch.object(app, "BACKUP_RESTORE_POINT_DIR", restore_dir),
            ):
                app.save_library(app.empty_library())
                app.save_settings(app.normalize_settings({"apiKey": "current-key", "model": "current-model"}))
                before = app.load_settings()
                with patch.object(app, "extract_backup_zip", side_effect=RuntimeError("forced import failure")):
                    with self.assertRaises(RuntimeError):
                        app.import_backup_payload({"contentBase64": encoded, "strategy": "merge"})
                after = app.load_settings()

        self.assertEqual(before["apiKey"], after["apiKey"])
        self.assertEqual(before["model"], after["model"])

    @contextmanager
    def fulltext_test_context(self, root: Path, paper: dict, key: str, filename: str):
        library_path = root / "library.json"
        settings_path = root / "settings.json"
        download_dir = root / "downloaded_papers"
        translated_dir = root / "translated_papers"
        task_dir = root / "data" / "fulltext_tasks"
        download_dir.mkdir()
        translated_dir.mkdir()
        task_dir.mkdir(parents=True)
        (download_dir / filename).write_bytes(b"%PDF test")
        with (
            patch.object(app, "LIBRARY_PATH", library_path),
            patch.object(app, "SETTINGS_PATH", settings_path),
            patch.object(app, "DOWNLOAD_DIR", download_dir),
            patch.object(app, "TRANSLATED_DIR", translated_dir),
            patch.object(app, "FULLTEXT_TASK_DIR", task_dir),
        ):
            yield

    def save_fulltext_test_state(self, paper: dict, key: str, filename: str) -> None:
        app.save_settings(app.normalize_settings({
            "provider": "apixin_gpt",
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-test",
        }))
        app.save_library({
            "version": app.LIBRARY_SCHEMA_VERSION,
            "papers": {key: {"createdAt": "2026-05-27T00:00:00+00:00", "paper": paper}},
            "favorites": {key: {"createdAt": "2026-05-27T00:00:00+00:00", "paper": paper}},
            "ignored": {},
            "downloads": {key: {"createdAt": "2026-05-27T00:00:00+00:00", "filename": filename, "paper": paper}},
            "history": [],
        })

    def test_stage8_acceptance_flow_preserves_zotero_state(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "stage8-real-pdf",
            "doi": "10.1234/stage8.acceptance",
            "abstract": "Short open metadata abstract...",
            "fullAbstract": "",
            "abstractSource": "source",
            "abstractSourceLabel": "Open metadata",
            "isDownloaded": True,
            "zotero": {"itemKey": "STAGE8ZO", "libraryID": 1, "itemID": 88},
            "zoteroLink": {
                "status": "confirmed",
                "itemKey": "STAGE8ZO",
                "libraryID": 1,
                "itemID": 88,
                "confidence": 100,
                "source": "manual-confirmation",
            },
            "zoteroSync": {
                "status": "synced",
                "itemKey": "STAGE8ZO",
                "syncedAt": "2026-06-05T00:00:00+00:00",
                "noteID": 88,
                "attachments": 1,
                "tags": ["paperhunter"],
            },
        })
        key = app.paper_key(paper)
        filename = app.sanitize_filename(paper["title"], paper["paperId"])
        alert_text = """
        ScienceDirect Alert
        Title: Vision Language Models for Scientific Discovery
        DOI: 10.1234/stage8.acceptance
        Abstract: Full subscription alert abstract visible through the user's authorized alert, longer than the open metadata summary and suitable for translation.
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_path = root / "library.json"
            settings_path = root / "settings.json"
            download_dir = root / "downloaded_papers"
            translated_dir = root / "translated_papers"
            task_dir = root / "data" / "fulltext_tasks"
            download_dir.mkdir()
            translated_dir.mkdir()
            task_dir.mkdir(parents=True)
            (download_dir / filename).write_bytes(b"%PDF stage8 acceptance fixture")
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "SETTINGS_PATH", settings_path),
                patch.object(app, "DOWNLOAD_DIR", download_dir),
                patch.object(app, "TRANSLATED_DIR", translated_dir),
                patch.object(app, "FULLTEXT_TASK_DIR", task_dir),
            ):
                self.save_fulltext_test_state(paper, key, filename)

                imported = app.import_alert_payload({
                    "text": alert_text,
                    "sourceLabel": "ScienceDirect Alert",
                    "enrich": False,
                    "reviewOnly": True,
                })
                after_import = app.load_library()["favorites"][key]["paper"]
                event_id = imported["alertInboxEvents"][0]["id"]
                adopted = app.alert_inbox_payload({
                    "action": "batch-adopt",
                    "eventIds": [event_id],
                    "lock": True,
                })
                after_adopt = app.load_library()["favorites"][key]["paper"]

                with patch.object(app, "invoke_model_text", return_value=("Stage 8 abstract translation.", {"total_tokens": 11})) as abstract_model:
                    abstract_translation = app.translate_abstract({"paper": after_adopt, "paperKey": key})
                after_abstract_translation = app.load_library()["favorites"][key]["paper"]

                with (
                    patch.object(
                        app,
                        "extract_pdf_text",
                        return_value="This first-page PDF text comes from a downloaded paper fixture and is long enough for one translation chunk.",
                    ),
                    patch.object(app, "invoke_model_text", return_value=("Stage 8 full-text translation.", {"total_tokens": 22})) as fulltext_model,
                ):
                    task = app.new_fulltext_task({
                        "paper": after_abstract_translation,
                        "paperKey": key,
                        "chunkSize": 500,
                        "maxChunks": 1,
                        "maxPages": 1,
                    })
                    app.run_fulltext_task(task["taskId"])
                finished_task = app.load_fulltext_task(task["taskId"])
                finished_task_view = app.public_fulltext_task(finished_task)

                with patch.object(app, "invoke_model_text", return_value=("Stage 8 smart brief.", {"total_tokens": 7})) as radar_model:
                    radar = app.research_radar_payload({"smart": True, "limit": 8})

                final_paper = app.load_library()["favorites"][key]["paper"]
                output_path = root / Path(finished_task["file"])
                output_exists = output_path.exists()

        self.assertTrue(imported["reviewOnly"])
        self.assertEqual("Short open metadata abstract...", after_import["abstract"])
        self.assertEqual("", after_import["fullAbstract"])
        self.assertEqual(1, adopted["adopted"])
        self.assertEqual("alert", after_adopt["abstractSource"])
        self.assertTrue(after_adopt["abstractLocked"])
        self.assertTrue(abstract_translation["ok"])
        self.assertEqual("done", finished_task["status"])
        self.assertEqual("done", finished_task_view["status"])
        self.assertEqual(1, finished_task_view["completedChunks"])
        self.assertTrue(output_exists)
        self.assertIn("fulltextTranslations", final_paper)
        self.assertEqual(1, len(final_paper["fulltextTranslations"]))
        self.assertEqual("STAGE8ZO", final_paper["zotero"]["itemKey"])
        self.assertEqual("confirmed", final_paper["zoteroLink"]["status"])
        self.assertEqual("STAGE8ZO", final_paper["zoteroLink"]["itemKey"])
        self.assertEqual("synced", final_paper["zoteroSync"]["status"])
        self.assertEqual("STAGE8ZO", final_paper["zoteroSync"]["itemKey"])
        self.assertEqual(88, final_paper["zoteroSync"]["noteID"])
        self.assertEqual("Stage 8 abstract translation.", final_paper["translations"]["zh"]["text"])
        self.assertEqual(1, radar["stats"]["favorites"])
        self.assertEqual(1, radar["stats"]["downloaded"])
        self.assertEqual(1, radar["stats"]["alertAdopted"])
        self.assertEqual(0, radar["stats"]["translationMissing"])
        self.assertEqual(1, radar["stats"]["zoteroLinked"])
        self.assertEqual(1, radar["stats"]["zoteroSynced"])
        self.assertEqual("done", radar["smartBrief"]["status"])
        self.assertEqual("Stage 8 smart brief.", radar["smartBrief"]["text"])
        abstract_model.assert_called_once()
        fulltext_model.assert_called_once()
        radar_model.assert_called_once()

    def test_diagnostics_payload_reports_runtime_health_without_side_effects(self):
        full_abstract = "Complete alert abstract visible through the user's authorized alert."
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "stage9-diagnostics",
            "doi": "10.1234/stage9.diagnostics",
            "abstract": full_abstract,
            "fullAbstract": full_abstract,
            "abstractSource": "alert",
            "abstractSourceLabel": "ScienceDirect Alert",
            "abstractLocked": True,
            "abstractConfirmedAt": "2026-06-05T00:00:00+00:00",
            "abstractConfirmedBy": "user",
            "isDownloaded": True,
            "translations": {
                "zh": {
                    "text": "阶段九摘要译文。",
                    "language": "zh",
                    "provider": "apixin_gpt",
                    "model": "gpt-test",
                    "translatedAt": "2026-06-05T00:01:00+00:00",
                    "promptVersion": app.TRANSLATION_PROMPT_VERSION,
                    "sourceHash": app.stable_text_hash(full_abstract),
                }
            },
            "fulltextTranslations": [{
                "type": "fulltext",
                "language": "zh",
                "format": "markdown",
                "file": "translated_papers/stage9.bilingual.md",
                "model": "gpt-test",
                "createdAt": "2026-06-05T00:02:00+00:00",
            }],
            "zotero": {"itemKey": "STAGE9ZO", "libraryID": 1, "itemID": 99},
            "zoteroLink": {"status": "confirmed", "itemKey": "STAGE9ZO"},
            "zoteroSync": {"status": "synced", "itemKey": "STAGE9ZO", "noteID": 99},
        })
        key = app.paper_key(paper)
        alert_candidate = app.normalize_abstract_candidate({
            "text": full_abstract,
            "source": "alert",
            "sourceLabel": "ScienceDirect Alert",
            "accessMode": "user-visible",
            "fetchedAt": "2026-06-05T00:00:00+00:00",
            "completeness": "complete",
        })
        alert_event = app.normalize_alert_inbox_event({
            "createdAt": "2026-06-05T00:00:00+00:00",
            "sourceId": "sciencedirect-alert",
            "sourceLabel": "ScienceDirect Alert",
            "provider": "sciencedirect",
            "authorizationMode": "manual-alert",
            "paperKey": key,
            "title": paper["title"],
            "doi": paper["doi"],
            "status": "adopted",
            "candidate": alert_candidate,
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            library_path = root / "library.json"
            settings_path = root / "settings.json"
            task_dir = root / "data" / "fulltext_tasks"
            task_dir.mkdir(parents=True)
            with (
                patch.object(app, "LIBRARY_PATH", library_path),
                patch.object(app, "SETTINGS_PATH", settings_path),
                patch.object(app, "FULLTEXT_TASK_DIR", task_dir),
                patch.object(app, "invoke_model_text") as invoke_model,
                patch.object(app.requests, "get") as request_get,
                patch.object(app.requests, "post") as request_post,
                patch.object(app, "read_zotero_candidates") as zotero_candidates,
            ):
                app.save_settings(app.normalize_settings({
                    "provider": "apixin_gpt",
                    "apiType": "responses",
                    "baseUrl": "https://example.test",
                    "endpoint": "/v1/responses",
                    "model": "gpt-test",
                    "apiKey": "sk-test",
                }))
                library = app.empty_library()
                entry = {"createdAt": "2026-06-05T00:00:00+00:00", "paper": paper}
                library["papers"][key] = entry
                library["favorites"][key] = entry
                library["downloads"][key] = {
                    "createdAt": "2026-06-05T00:00:00+00:00",
                    "filename": app.sanitize_filename(paper["title"], paper["paperId"]),
                    "paper": paper,
                }
                library["alertInbox"] = [alert_event]
                app.save_library(library)
                app.save_fulltext_task({
                    "version": app.FULLTEXT_TASK_SCHEMA_VERSION,
                    "taskId": app.fulltext_task_id(key),
                    "paperKey": key,
                    "paper": paper,
                    "title": paper["title"],
                    "status": "done",
                    "createdAt": "2026-06-05T00:02:00+00:00",
                    "updatedAt": "2026-06-05T00:03:00+00:00",
                    "finishedAt": "2026-06-05T00:03:00+00:00",
                    "file": "translated_papers/stage9.bilingual.md",
                    "filename": "stage9.bilingual.md",
                    "usage": {"total_tokens": 22},
                    "chunks": [{
                        "index": 1,
                        "status": "done",
                        "source": "First page text.",
                        "translation": "第一页译文。",
                        "usage": {"total_tokens": 22},
                    }],
                })

                response = app.diagnostics_payload({"limit": 8})
                stored = app.load_library()

        self.assertTrue(response["ok"])
        self.assertEqual("ready", response["status"])
        self.assertTrue(response["model"]["configured"])
        self.assertTrue(response["model"]["fallback"]["available"])
        self.assertEqual("chat_completions", response["model"]["fallback"]["apiType"])
        self.assertEqual(1, response["fulltext"]["counts"]["done"])
        self.assertEqual(1, response["radar"]["stats"]["alertAdopted"])
        self.assertEqual(0, response["radar"]["stats"]["translationMissing"])
        self.assertEqual(1, response["zotero"]["counts"]["syncReady"])
        self.assertEqual(1, response["zotero"]["counts"]["synced"])
        self.assertEqual(1, len(response["zotero"]["items"]))
        self.assertTrue(response["zotero"]["items"][0]["syncPlan"]["ready"])
        self.assertIn("paperhunter:abstract-translated", response["zotero"]["items"][0]["syncPlan"]["tags"])
        self.assertEqual("ready", response["acceptance"]["status"])
        self.assertTrue(response["policy"]["readOnly"])
        self.assertIn("safeReport", response)
        self.assertFalse(response["safeReport"]["privacy"]["containsRawSecrets"])
        safe_report_text = json.dumps(response["safeReport"], ensure_ascii=False)
        self.assertNotIn("sk-test", safe_report_text)
        self.assertIn("sk...st", safe_report_text)
        self.assertEqual([], stored["zoteroAudit"])
        invoke_model.assert_not_called()
        request_get.assert_not_called()
        request_post.assert_not_called()
        zotero_candidates.assert_not_called()

    def test_diagnostics_safe_report_redacts_api_key_and_bridge_token(self):
        raw_token = "TOKEN1234567890TOKEN1234567890"
        raw_key = "sk-live-should-never-leak"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with (
                patch.object(app, "LIBRARY_PATH", root / "library.json"),
                patch.object(app, "SETTINGS_PATH", root / "settings.json"),
                patch.object(app, "FULLTEXT_TASK_DIR", root / "fulltext_tasks"),
            ):
                app.save_settings(app.normalize_settings({
                    "provider": "custom",
                    "apiType": "chat_completions",
                    "baseUrl": "https://example.test",
                    "endpoint": "/v1/chat/completions",
                    "model": "gpt-test",
                    "apiKey": raw_key,
                    "zoteroBridgeToken": raw_token,
                }))
                response = app.diagnostics_payload({"limit": 4})

        serialized = json.dumps(response["safeReport"], ensure_ascii=False)
        self.assertNotIn(raw_key, serialized)
        self.assertNotIn(raw_token, serialized)
        self.assertIn(app.mask_secret(raw_key), serialized)
        self.assertIn(app.mask_secret(raw_token), serialized)
        self.assertEqual(["apiKey", "zoteroBridgeToken"], response["safeReport"]["privacy"]["redacted"])

    def test_fulltext_task_writes_markdown_and_index(self):
        paper = app.paper_snapshot({**SAMPLE_PAPER, "paperId": "fulltext-1", "isDownloaded": True})
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            filename = app.sanitize_filename(paper["title"], paper["paperId"])
            with self.fulltext_test_context(root, paper, key, filename):
                self.save_fulltext_test_state(paper, key, filename)
                with (
                    patch.object(app, "extract_pdf_text", return_value="First paragraph. Second paragraph. Third paragraph."),
                    patch.object(app, "invoke_model_text", return_value=("译文片段。", {"total_tokens": 20})),
                ):
                    response = app.new_fulltext_task({"paper": paper, "paperKey": key, "chunkSize": 20})
                    app.run_fulltext_task(response["taskId"])
                task = app.load_fulltext_task(response["taskId"])
                stored = app.load_library()
                output_path = root / (task["file"].replace("/", "\\"))
                output_exists = output_path.exists()
                content = output_path.read_text(encoding="utf-8")

        self.assertEqual("done", task["status"])
        self.assertTrue(output_exists)
        self.assertIn("### English", content)
        self.assertIn("### 中文", content)
        self.assertIn("译文片段。", content)
        index = stored["favorites"][key]["paper"]["fulltextTranslations"][0]
        self.assertEqual("fulltext", index["type"])
        self.assertTrue(index["file"].endswith(".bilingual.md"))

    def test_fulltext_task_preserves_current_zotero_state_when_task_snapshot_is_stale(self):
        stale_paper = app.paper_snapshot({**SAMPLE_PAPER, "paperId": "fulltext-preserve-zotero", "isDownloaded": True})
        current_paper = app.paper_snapshot({
            **stale_paper,
            "zotero": {"itemKey": "ITEMKEYA", "libraryID": 1, "itemID": 101},
            "zoteroLink": {
                "status": "confirmed",
                "itemKey": "ITEMKEYA",
                "libraryID": 1,
                "itemID": 101,
                "confidence": 100,
                "source": "manual-confirmation",
                "confirmedAt": "2026-05-28T00:00:00+00:00",
            },
            "zoteroSync": {
                "status": "synced",
                "itemKey": "ITEMKEYA",
                "syncedAt": "2026-05-28T00:10:00+00:00",
                "noteID": 12,
                "attachments": 1,
                "tags": ["paperhunter", "paperhunter:abstract-translated"],
            },
            "translations": {
                "zh": {
                    "text": "Existing zh abstract.",
                    "language": "zh",
                    "sourceHash": app.stable_text_hash(stale_paper["abstract"]),
                }
            },
        })
        key = app.paper_key(stale_paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            filename = app.sanitize_filename(stale_paper["title"], stale_paper["paperId"])
            with self.fulltext_test_context(root, stale_paper, key, filename):
                self.save_fulltext_test_state(stale_paper, key, filename)
                with patch.object(app, "extract_pdf_text", return_value="First paragraph. Second paragraph."):
                    task = app.new_fulltext_task({"paper": stale_paper, "paperKey": key, "chunkSize": 20})
                app.save_library({
                    "version": app.LIBRARY_SCHEMA_VERSION,
                    "papers": {key: {"createdAt": "2026-05-27T00:00:00+00:00", "paper": current_paper}},
                    "favorites": {key: {"createdAt": "2026-05-27T00:00:00+00:00", "paper": current_paper}},
                    "ignored": {},
                    "downloads": {key: {"createdAt": "2026-05-27T00:00:00+00:00", "filename": filename, "paper": current_paper}},
                    "history": [],
                })
                with patch.object(app, "invoke_model_text", return_value=("Translated result", {"total_tokens": 2})):
                    app.run_fulltext_task(task["taskId"])
                stored = app.load_library()["favorites"][key]["paper"]

        self.assertEqual("confirmed", stored["zoteroLink"]["status"])
        self.assertEqual("ITEMKEYA", stored["zoteroLink"]["itemKey"])
        self.assertEqual("synced", stored["zoteroSync"]["status"])
        self.assertEqual("ITEMKEYA", stored["zoteroSync"]["itemKey"])
        self.assertEqual(12, stored["zoteroSync"]["noteID"])
        self.assertEqual("ITEMKEYA", stored["zotero"]["itemKey"])
        self.assertIn("zh", stored["translations"])
        self.assertEqual(1, len(stored["fulltextTranslations"]))

    def test_fulltext_task_replaces_existing_index_for_same_markdown_file(self):
        paper = app.paper_snapshot({**SAMPLE_PAPER, "paperId": "fulltext-dedupe", "isDownloaded": True})
        key = app.paper_key(paper)
        existing_index = {
            "type": "fulltext",
            "language": "zh",
            "format": "markdown",
            "file": f"translated_papers/{key}.bilingual.md",
            "model": "old-model",
            "createdAt": "2026-05-27T00:00:00+00:00",
        }
        paper["fulltextTranslations"] = [existing_index, dict(existing_index)]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            filename = app.sanitize_filename(paper["title"], paper["paperId"])
            with self.fulltext_test_context(root, paper, key, filename):
                self.save_fulltext_test_state(paper, key, filename)
                with (
                    patch.object(app, "extract_pdf_text", return_value="First paragraph. Second paragraph."),
                    patch.object(app, "invoke_model_text", return_value=("Translated result", {"total_tokens": 2})),
                ):
                    task = app.new_fulltext_task({"paper": paper, "paperKey": key, "force": True, "chunkSize": 20})
                    app.run_fulltext_task(task["taskId"])
                stored = app.load_library()["favorites"][key]["paper"]

        self.assertEqual(1, len(stored["fulltextTranslations"]))
        self.assertEqual(f"translated_papers/{key}.bilingual.md", stored["fulltextTranslations"][0]["file"])
        self.assertEqual("gpt-test", stored["fulltextTranslations"][0]["model"])

    def test_fulltext_task_requires_consent_for_zotero_library_pdf(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "fulltext-zotero-private",
            "isDownloaded": True,
            "access": "user_library",
        })
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            filename = app.sanitize_filename(paper["title"], paper["paperId"])
            with self.fulltext_test_context(root, paper, key, filename):
                self.save_fulltext_test_state(paper, key, filename)
                with patch.object(app, "extract_pdf_text", return_value="Private PDF text.") as extractor:
                    with self.assertRaises(ValueError) as error:
                        app.new_fulltext_task({"paper": paper, "paperKey": key, "chunkSize": 20})

                extractor.assert_not_called()
                self.assertIn("needs confirmation", str(error.exception))

    def test_fulltext_local_only_blocks_remote_private_pdf(self):
        paper = app.paper_snapshot({
            **SAMPLE_PAPER,
            "paperId": "fulltext-zotero-local-only",
            "isDownloaded": True,
            "access": "user_library",
        })
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            filename = app.sanitize_filename(paper["title"], paper["paperId"])
            with self.fulltext_test_context(root, paper, key, filename):
                self.save_fulltext_test_state(paper, key, filename)
                app.save_settings(app.normalize_settings({
                    "provider": "apixin_gpt",
                    "apiType": "responses",
                    "baseUrl": "https://example.test",
                    "endpoint": "/v1/responses",
                    "model": "gpt-test",
                    "apiKey": "sk-test",
                    "privatePdfMode": "local_only",
                }, app.load_settings()))
                with patch.object(app, "extract_pdf_text", return_value="Private PDF text.") as extractor:
                    with self.assertRaises(ValueError) as error:
                        app.new_fulltext_task({
                            "paper": paper,
                            "paperKey": key,
                            "chunkSize": 20,
                            "userLibraryConsent": True,
                        })

                extractor.assert_not_called()
                self.assertIn("local/self-hosted only", str(error.exception))

    def test_fulltext_task_can_resume_failed_chunk(self):
        paper = app.paper_snapshot({**SAMPLE_PAPER, "paperId": "fulltext-resume", "isDownloaded": True})
        key = app.paper_key(paper)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            filename = app.sanitize_filename(paper["title"], paper["paperId"])
            with self.fulltext_test_context(root, paper, key, filename):
                self.save_fulltext_test_state(paper, key, filename)
                source_text = " ".join(f"Sentence {index}." for index in range(160))
                with patch.object(app, "extract_pdf_text", return_value=source_text):
                    task = app.new_fulltext_task({"paper": paper, "paperKey": key, "chunkSize": 500})
                calls = {"count": 0}

                def flaky_translate(*args, **kwargs):
                    calls["count"] += 1
                    if calls["count"] == 2:
                        raise TimeoutError("temporary timeout")
                    return (f"译文 {calls['count']}", {"total_tokens": 1})

                with patch.object(app, "invoke_model_text", side_effect=flaky_translate):
                    app.run_fulltext_task(task["taskId"])
                failed = app.load_fulltext_task(task["taskId"])
                self.assertEqual("failed", failed["status"])
                self.assertEqual("done", failed["chunks"][0]["status"])
                self.assertEqual("failed", failed["chunks"][1]["status"])

                with patch.object(app, "invoke_model_text", return_value=("续跑译文", {"total_tokens": 2})):
                    app.run_fulltext_task(task["taskId"])
                resumed = app.load_fulltext_task(task["taskId"])

        self.assertEqual("done", resumed["status"])
        self.assertTrue(resumed["file"].endswith(".bilingual.md"))
        self.assertTrue(all(chunk["status"] == "done" for chunk in resumed["chunks"]))

    def test_fulltext_export_rejects_missing_chunk(self):
        task = {
            "chunks": [
                {"index": 1, "status": "done", "source": "A", "translation": "甲"},
                {"index": 3, "status": "done", "source": "C", "translation": "丙"},
            ]
        }

        with self.assertRaises(RuntimeError):
            app.completed_fulltext_chunks(task)


if __name__ == "__main__":
    unittest.main()
