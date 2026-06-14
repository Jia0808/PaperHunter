# PaperHunter 发布检查清单

在给当前版本打 tag 或正式发布前，按这份清单做最后确认。

## 发布范围

- Alert 工作流：订阅来源登记、手动 Alert 导入、Alert 收件箱审阅、采用并锁定、冲突状态和来源健康状态追踪。
- 运行健康面板：只读诊断、安全报告复制、任务中心、模型测试记录、全文任务状态、Zotero dry-run 摘要。
- Zotero 集成：保存到 Zotero、从本机 Zotero 导入、自动/手动绑定 canonical itemKey、同步预览、审计记录和 Bridge 回写。
- PaperHunter Zotero Bridge `0.2.2`：本地配对 token、协议 `1`、PaperHunter 管理 note 的 upsert、`paperhunter:*` 标签、译文 Markdown 附件，以及保护用户原始内容的策略。
- 备份与导入加固：导入前预览、恢复点创建、API Key 移除提醒、恢复设置后重新安装 Bridge 的提醒。
- 浏览器与 UI 验证：真实 HTTP 冒烟测试，以及可选的 Playwright UI 点击冒烟测试。

## 发布前命令

以下命令在仓库根目录运行。执行 E2E 冒烟测试前，先确认 PaperHunter 已在 `http://127.0.0.1:8000` 运行。

```powershell
venv\Scripts\python.exe -m py_compile app.py tests\e2e_smoke.py tests\e2e_ui.py tests\test_frontend_static.py
venv\Scripts\python.exe -m unittest discover -s tests
node --check web\app.js
node --check zotero-bridge\bootstrap.js
venv\Scripts\python.exe tests\e2e_smoke.py --base-url http://127.0.0.1:8000
venv\Scripts\python.exe tests\e2e_ui.py --base-url http://127.0.0.1:8000
git diff --check HEAD
```

## 真实 RC 验证记录

- Chrome UI Alert 路径已通过：`PaperHunter Chrome UI Alert E2E 202606150145UI` 是通过浏览器页面导入的，进入 Alert 收件箱后又从页面采用并锁定。
- 完整链路已通过：`PaperHunter Full Chain Alert E2E 20260615013517` 走过 Alert 导入、采用、摘要翻译、保存到 Zotero、同步预览和真实 Bridge 回写。
- Zotero Bridge 写入结果：itemKey `DPLL37WM`，itemID `11`，noteID `12`，标签包括 `paperhunter`、`paperhunter:abstract-translated`、`paperhunter:imported`。
- Zotero 桌面 UI 已确认新条目和 1 个子笔记可见；只读 SQLite 快照也确认了 PaperHunter 管理 note 和标签真实落库。

## 发布注意点

- 生成后的 XPI 文件 `zotero-bridge/paperhunter-zotero-bridge.xpi` 已被忽略，不应提交。PaperHunter 会根据 `zotero-bridge/manifest.json` 和 `zotero-bridge/bootstrap.js`，用当前本地配对 token 重新构建 XPI。
- 本地运行文件应保持未跟踪，例如 `.paperhunter.*.pid`、`.paperhunter.*.log`、`data/`、`downloaded_papers/`、`translated_papers/`、`output/`、`test-results/`。
- `docs/social/` 是本地宣传文案和图片素材，已从核心代码发布中排除。
- 诊断面板显示 `attention` 时，可能只是旧收藏缺少摘要译文。这属于数据待补齐，不代表 Alert 工作流或 Zotero Bridge 失败。
