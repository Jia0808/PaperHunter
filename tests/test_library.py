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

    def test_model_settings_public_view_masks_api_key(self):
        settings = app.normalize_settings({
            "provider": "apixin_gpt",
            "apiType": "responses",
            "baseUrl": "https://example.test",
            "endpoint": "/v1/responses",
            "model": "gpt-test",
            "apiKey": "sk-secret-value",
        })

        public = app.public_settings(settings)

        self.assertTrue(public["hasApiKey"])
        self.assertEqual("sk-sec...alue", public["apiKeyMasked"])
        self.assertNotIn("apiKey", public)
        self.assertEqual("https://example.test/v1/responses", public["finalUrl"])

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
        self.assertEqual("Reply with exactly OK.", captured["json"]["input"])

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


if __name__ == "__main__":
    unittest.main()
