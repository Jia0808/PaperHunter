import tempfile
import unittest
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
    def test_export_bibtex_contains_core_fields(self):
        content = app.export_bibtex([SAMPLE_PAPER])

        self.assertIn("@misc{", content)
        self.assertIn("title = {Vision Language Models for Scientific Discovery}", content)
        self.assertIn("author = {Ada Lovelace and Alan Turing}", content)
        self.assertIn("year = {2026}", content)
        self.assertIn("url = {https://arxiv.org/abs/2605.00001}", content)
        self.assertIn("archivePrefix = {arXiv}", content)
        self.assertIn("primaryClass = {cs.AI}", content)
        self.assertNotIn("journal = {cs.AI}", content)

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

    def test_refresh_favorites_updates_snapshot(self):
        key = app.paper_key(SAMPLE_PAPER)
        stale_paper = {**SAMPLE_PAPER, "abstract": "Short abstract...", "fullAbstract": ""}
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
        self.assertEqual(key, stored["favorites"][key]["paper"]["paperKey"])


if __name__ == "__main__":
    unittest.main()
