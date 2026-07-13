import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendStaticRegressionTests(unittest.TestCase):
    def read_asset(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_frontend_uses_in_app_dialogs_instead_of_native_blocking_prompts(self):
        app_js = self.read_asset("web/app.js")
        for native_dialog in ("window.prompt", "window.confirm", "window.alert"):
            self.assertNotIn(native_dialog, app_js)
        self.assertIn("subscription-source-backdrop", app_js)
        self.assertIn("app-confirm-backdrop", app_js)

    def test_long_task_messages_do_not_report_failed_smart_brief_as_updated(self):
        app_js = self.read_asset("web/app.js")
        self.assertIn("研究雷达已刷新，但智能简报生成失败", app_js)
        self.assertIn("全文翻译任务创建超时", app_js)

    def test_runtime_health_exposes_safe_report_and_task_center_controls(self):
        index_html = self.read_asset("web/index.html")
        app_js = self.read_asset("web/app.js")
        self.assertIn('id="copyDiagnosticsButton"', index_html)
        self.assertIn('id="showTaskCenterButton"', index_html)
        self.assertIn("copyDiagnosticsSummary", app_js)
        self.assertIn("diagnosticsSafeReportText", app_js)
        self.assertIn('requestJson("/api/diagnostics", { limit: 40 }', app_js)
        self.assertIn("startBridgeInstallPolling", app_js)
        self.assertIn("bridgeReinstallRequired", app_js)

    def test_backup_preview_and_bridge_wizard_are_in_app_flows(self):
        app_js = self.read_asset("web/app.js")
        styles = self.read_asset("web/styles.css")
        self.assertIn('requestJson("/api/backup/preview"', app_js)
        self.assertIn("renderBackupPreviewDialog", app_js)
        self.assertIn("创建恢复点并导入", app_js)
        self.assertIn("renderBridgeWizard", app_js)
        self.assertIn("复制 XPI 路径", app_js)
        self.assertIn(".backup-preview-dialog", styles)
        self.assertIn(".bridge-wizard-step", styles)

    def test_gpt_model_presets_and_qq_contact_are_visible_and_interactive(self):
        index_html = self.read_asset("web/index.html")
        app_js = self.read_asset("web/app.js")
        styles = self.read_asset("web/styles.css")

        self.assertIn('id="modelPresetOptions"', index_html)
        self.assertIn('id="contactQqGroup">1060433705', index_html)
        self.assertIn('id="copyContactQqButton"', index_html)
        self.assertIn("renderModelPresetOptions", app_js)
        self.assertIn("copyContactQqGroup", app_js)
        self.assertIn(".model-preset-option.is-active", styles)
        self.assertIn(".contact-panel", styles)


if __name__ == "__main__":
    unittest.main()
