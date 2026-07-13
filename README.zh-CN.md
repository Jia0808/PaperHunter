<div align="center">
  <h1>PaperHunter</h1>
  <p><strong>面向研究人员的本地论文检索与开放 PDF 下载工作台。</strong></p>
  <p>
    <a href="README.md">English</a> · 简体中文
  </p>
  <p>
    <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue"></a>
    <a href="https://github.com/Jia0808/PaperHunter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Jia0808/PaperHunter/actions/workflows/ci.yml/badge.svg"></a>
    <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12%2B-3776AB">
    <img alt="Local first" src="https://img.shields.io/badge/local--first-research-2F6FED">
  </p>
</div>

![PaperHunter 工作台](docs/assets/paperhunter-dashboard.png)

## 为什么做 PaperHunter

PaperHunter 用来帮助研究人员同时检索多个开放论文来源，通过更贴近科研场景的筛选条件整理结果，并把公开开放访问的 PDF 下载到本地文件夹。它的目标是做一个实用的文献发现工具，而不是绕过访问限制的爬虫。

项目采用普通 Python 后端和原生 HTML/CSS/JavaScript 前端，不依赖数据库、账号系统或云服务。

## 功能亮点

- 同时检索国际和国内开放论文来源。
- 支持研究意图、研究领域、年份范围、作者、期刊/会议、匹配范围、arXiv 分类、仅可下载结果等筛选条件。
- 支持控制每个数据源返回篇数，避免单个大源占满结果列表。
- 支持本地 PDF 下载和重复文件识别。
- 支持“本地收件箱”：收藏、忽略、阅读状态、标签、备注、最近搜索、下载状态和全文翻译任务状态会保存到 `data/library.json`。
- 支持 Alert inbox：可导入用户已经能看到的 ScienceDirect、Web of Science 等 alert 文本，检查候选题录，采纳完整摘要，锁定已确认记录，并在本地资料库保留 alert 来源轨迹。
- 支持模型设置面板，可配置 OpenAI 兼容 Responses/Chat Completions 接口、DeepSeek、Anthropic 和自定义提供商。
- 支持单篇摘要翻译和收藏摘要批量翻译；当来源摘要变化时，会标记已有译文可能过期。
- 支持 Zotero 双向联动：把检索结果保存到 Zotero，从本机 Zotero 导入条目和 PDF 附件，并可通过 PaperHunter Zotero Bridge 把摘要译文、全文译文和处理标签同步回 Zotero。
- 支持导出 BibTeX、适合 Zotero/EndNote 导入的 RIS、Markdown 阅读清单，以及中英对照摘要 Markdown。
- 支持对已下载 PDF 进行全文翻译：分片任务可续跑、可查看进度、输出中英对照 Markdown，并可打开译文所在文件夹。
- 支持刷新收藏论文元数据，用来更新旧收藏并尽量补回完整摘要；ChinaRxiv feed 摘要被截断时会尝试从详情页补全。
- 支持工作区备份与导入，可备份本地资料库、已下载 PDF、全文译文和翻译任务；备份会移除 API Key。
- 为 Google Scholar、知网、万方、X-MOL、Nature、Science 等通常需要手动浏览、登录、机构权限、付费、遵守 robots.txt 或验证码的来源提供外部入口。
- 本地优先：下载的 PDF 保存在 `downloaded_papers/`，全文译文保存在 `translated_papers/`，本地资料库和模型设置保存在 `data/`；这些运行时目录都不会提交到 Git。
- 技术栈轻量：Python 3.12、`requests`、`arxiv` 和浏览器原生前端代码。

## 支持的数据源

| 数据源 | 检索 | PDF 下载 | 说明 |
| --- | --- | --- | --- |
| arXiv | 支持 | 支持 | 使用 arXiv package/API。 |
| Semantic Scholar | 支持 | 仅公开开放 PDF | 受 Semantic Scholar 速率限制影响。 |
| CVF Open Access | 支持 | 支持 | 检索公开 CVF Open Access 页面。 |
| ACL Anthology | 支持 | 支持 | 使用 ACL Anthology 元数据/缓存。 |
| OpenReview | 支持 | 仅公开开放 PDF | 部分 PDF 可能需要来源站点校验。 |
| ChinaRxiv / ChinaXiv | 支持 | 仅公开开放 PDF | 国内开放论文来源；当 feed 摘要被截断时会尝试读取详情页摘要。 |
| SciOpen | 支持 | 仅公开开放 PDF | 国内/开放访问来源。 |
| National Science Open | 支持 | 仅公开开放 PDF | 开放期刊来源。 |
| Google Scholar、知网、万方、X-MOL、Nature、Science | 仅外部入口 | 不自动下载 | 这些来源可能需要手动浏览、登录、授权、付费、遵守 robots.txt 或人工验证。 |

## 快速开始

推荐使用 Python 3.12 或更新版本。

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

然后打开：

```text
http://127.0.0.1:8000
```

Windows 也可以直接运行：

```bat
start_paperhunter.bat
```

## 模型配置

PaperHunter 可以通过你在界面中配置的模型接口翻译摘要和已下载 PDF 的全文内容。

当前支持的预设包括：

- APIXIN GPT 兼容接口，内置 `gpt-5.6-sol`、`gpt-5.6-luna`、`gpt-5.6-terra` 快捷选择
- DeepSeek Chat Completions
- Anthropic Messages
- 自定义 OpenAI 兼容 Responses 或 Chat Completions 接口

模型设置会保存到 `data/settings.json`，该文件已被 Git 忽略。状态接口只返回脱敏后的 API Key；工作区备份会在写入 `data/settings.json` 前移除 API Key。

翻译请求会把选中的摘要或全文分片发送到你配置的模型提供商。PaperHunter 不查询账户余额，也不会在你没有触发翻译操作时发送论文内容。

## 联系与反馈

QQ 群：`1060433705`

如果 OpenAI 兼容的 Responses 端点返回 `completed` 但没有可见文本，PaperHunter 会在可以推断出对应路径时自动改用同一网关的 Chat Completions 路由重试。这样可以兼容同时支持两种 API、但只在 Chat Completions 响应中暴露文本的中转服务。

## 阶段 8 验收说明

阶段 8 的端到端验收路径是：导入用户可见的 ScienceDirect 或 Web of Science alert，从 Alert inbox 采纳完整摘要，翻译摘要，把已下载 PDF 翻译成中英对照 Markdown，生成 Research Radar 智能摘要，并确认 Zotero 绑定状态仍然保留。

验收时应使用临时的 `LIBRARY_PATH`、`SETTINGS_PATH`、`FULLTEXT_TASK_DIR`、`DOWNLOAD_DIR` 和 `TRANSLATED_DIR`。可以从 `downloaded_papers/` 选取真实 PDF 做验证，但测试不得清空或覆盖真实 PaperHunter 资料库、已下载论文、译文目录或 Zotero 数据。

这里的权限边界是有意设计的：PaperHunter 不绕过付费墙，也不自动化受限出版方访问；但如果用户已经通过合法路径拥有入口，也不能因为开放元数据缺失、滞后或新期刊更新不及时，就剥夺用户把 alert 文本、本地 Zotero 条目和本地 PDF 纳入工作流的能力。

## 阶段 9 运行健康

“运行健康”面板是阶段 8 流程的只读排障中心。它会汇总模型配置、最近一次用户显式触发的模型连接测试、可续跑的全文翻译任务、Zotero 绑定状态和验收检查。

模型卡片会把最近一次连接测试记录保存到 `data/settings.json`：测试状态、测试时间、接口类型、Responses 空输出时实际 fallback 到的接口类型、最终 URL、返回文本长度、usage 和规范化错误信息。这个记录只会在你点击模型测试或执行本来就会调用模型的翻译路径时更新。

全文卡片会列出最近的分片翻译任务。失败或部分完成的任务如果仍能在本地库中找到对应论文，可以从面板继续；已完成任务可以直接打开译文 Markdown 所在位置。

Zotero 卡片会展示收藏论文的 dry-run 计划：canonical `itemKey`、是否已有摘要/全文译文、将管理多少个 `paperhunter:*` 标签，以及将链接多少个译文 Markdown 附件。从这个面板打开的单篇 dry-run 会传入 `persistReview: false`，因此不会写 Zotero、不会创建 audit 事件，也不会把重复候选或需确认状态持久化到资料库。真正回写 Zotero 仍然需要用户在正式同步入口明确触发。

刷新诊断不会调用模型、不会读取 Zotero 候选记录、不会写 Zotero audit，也不会清空 PA/ZO、已下载论文、全文译文或 Zotero 数据。

## 引用管理工具

PaperHunter 可以把当前检索结果、收藏列表或单篇论文通过 Zotero 本机 Connector 接口直接保存到已经打开的 Zotero 桌面端，也可以导出为 RIS，用于导入 Zotero、EndNote 和其他引用管理工具。保存或导出的题录会尽量包含标题、作者、年份/日期、期刊或会议、摘要、可获取的 DOI、来源页面、公开 PDF 链接、关键词和备注。

如果本机已安装 Zotero，PaperHunter 还可以从 `~/Zotero/zotero.sqlite` 的只读快照导入 Zotero 条目、标签、分组信息和 PDF 附件路径。导入的 Zotero PDF 会作为用户已有合法馆藏处理，不要求它是开放访问 PDF，也不会尝试绕过访问控制去下载受限全文。

保存到 Zotero 或从 Zotero 导入后，PaperHunter 会按 DOI、来源 URL、来源 ID 和标题/年份自动寻找同一篇文献，并把 Zotero `itemKey` 回绑到本地论文记录。这样一篇论文不会因为先在 PaperHunter 收藏、再保存到 Zotero 而断开后续同步链路。

要把 PaperHunter 中的摘要译文、全文翻译结果和 `paperhunter:*` 状态标签同步回 Zotero，需要从 PaperHunter 的 Zotero 联动面板点击“下载 Bridge 插件”取得本地 XPI 并安装。这个 XPI 会在需要时从仓库跟踪的 `zotero-bridge/manifest.json` 和 `zotero-bridge/bootstrap.js` 源码重新构建，并且会用本地 token 绑定到当前 PaperHunter 实例。安装后 Zotero 会提供本机 `/paperhunter/ping` 和 `/paperhunter/sync` 端点，PaperHunter 会在对应 Zotero 条目下创建或更新唯一一条由 PaperHunter 管理的 “PaperHunter 同步结果” note，只写入 `paperhunter:*` 状态标签，并且只把 PaperHunter `translated_papers/` 输出目录下的全文译文 Markdown 作为本地链接附件挂回 Zotero。Bridge 不会删除、覆盖或移动 Zotero 原始条目、PDF、用户笔记、用户标签或分组。

推荐用户流程是：先安装并打开 Zotero，再启动 PaperHunter；需要时把 Zotero 中已有的条目和 PDF 附件路径导入 PaperHunter；在 PaperHunter 中做摘要翻译、全文翻译或总结；如果希望这些处理结果回到 Zotero，再安装/启用可选的 PaperHunter Zotero Bridge。Zotero 仍然是原始文献库的管理中心。

对于非开放访问论文，PaperHunter 会把题录和 PDF 分开处理：可以保存元数据、DOI 和外部访问入口，但不会绕过付费墙、登录、验证码、机构访问控制或出版方限制。如果你通过自己的合法访问路径获得 PDF，仍然可以把本地文件纳入 PaperHunter 的管理和翻译工作流。

完整的 Alert 到 Zotero 操作流程，包括 Alert 导入、认领/锁定、摘要翻译、Zotero 保存/导入、Bridge 安装、dry-run 预览和真实回写，见中文说明：[Zotero 与 Alert 工作流指南](docs/ZOTERO_ALERT_WORKFLOW.zh-CN.md)。

### 安装 PaperHunter Zotero Bridge

Bridge 是 Zotero 的本地插件，不修改 Zotero 源码。用户正常安装 Zotero，启动 PaperHunter，需要回写译文时再安装这个可选插件即可。

1. 在 PaperHunter 的 Zotero 联动面板点击“下载 Bridge 插件”。如果本地 XPI 缺失或版本过期，PaperHunter 会从已跟踪的 Bridge 源码重新构建。
2. 在 Zotero 中打开插件管理器。
3. 选择“从文件安装插件”，选中刚下载的 `paperhunter-zotero-bridge.xpi`。
4. 重启 Zotero。
5. 回到 PaperHunter 刷新页面或重新启动 PaperHunter，面板应显示 `Bridge 0.2.2 已可用`、配对 token 已验证，并显示“回写可用”。

如果面板仍显示“回写需 Bridge”，先确认 Zotero 正在运行，再重新安装当前页面下载的 XPI 并重启 Zotero。如果显示版本、协议或配对 token 不兼容，请从当前 PaperHunter 页面重新下载 XPI 覆盖安装，确保 XPI 内嵌的配对 token 与这个工作区一致。换机器或恢复设置后会生成新的本地配对 token，因此需要把新下载的 XPI 重新安装到 Zotero。Bridge 只接受带匹配配对 token 的 PaperHunter 本机请求，只更新 PaperHunter 管理的同步 note、`paperhunter:*` 标签和译文 Markdown 附件；用户原来的 Zotero 条目、PDF、标签、笔记和分组会保留。

## 使用流程

1. 输入研究关键词或短语。
2. 选择研究意图、研究领域、年份范围、数据源和每个数据源返回篇数。
3. 执行检索，查看标题、作者、年份、期刊/会议和 PDF 可用性。
4. 把有用论文加入本地收件箱，忽略不想再看到的论文，并可补充阅读状态、标签和备注。
5. 当出版商或数据库 alert 比开放来源更新时，把用户可见的 alert 文本导入 Alert inbox，采纳完整摘要并锁定到本地论文记录。
6. 如需摘要或全文翻译，先配置模型接口。
7. 翻译单篇摘要、批量翻译收藏摘要，或者在元数据更新后重译可能过期的摘要。
8. 将题录保存到 Zotero，或从 Zotero 导入已有馆藏和 PDF 附件。
9. 下载选中的开放访问 PDF，或批量下载可下载结果。
10. 对已下载 PDF 执行全文翻译，查看分片进度；任务完成后可打开译文所在文件夹。
11. 如需回写 Zotero，启用 PaperHunter Zotero Bridge 后同步摘要译文、全文译文附件和状态标签。
12. 把收藏论文导出为 BibTeX、适合 Zotero/EndNote 导入的 RIS、Markdown 阅读清单或中英对照摘要文件。
13. 如果旧收藏显示摘要可能被截断，可以刷新收藏元数据来尽量补回完整摘要。
14. 在迁移机器或清理本地运行数据前，导出工作区备份。
15. 如果来源需要登录或机构权限，使用外部入口在浏览器中继续访问。

## 项目结构

```text
app.py                    Python HTTP 服务、数据源适配、筛选、下载
web/index.html            浏览器界面结构
web/styles.css            界面样式
web/app.js                前端状态、筛选、API 调用
data/                     本地资料库、模型设置和任务状态目录，已被 Git 忽略
data/fulltext_tasks/      可续跑的全文翻译任务状态，已被 Git 忽略
downloaded_papers/        本地 PDF 输出目录，已被 Git 忽略
translated_papers/        全文翻译输出的中英对照 Markdown，已被 Git 忽略
zotero-bridge/            Zotero 本地插件源码；XPI 会在需要时从这些文件重新构建
docs/assets/              README 和文档图片
tests/                    后端回归测试
.github/workflows/ci.yml  Python 和 JavaScript 语法检查
```

## 开发检查

```bash
python -m py_compile app.py
python -m unittest discover -s tests
node --check web/app.js
```

## 本地数据与备份

PaperHunter 采用本地优先设计，但部分操作会按你的选择访问外部服务：

- 检索会请求所选公开论文来源
- 摘要和全文翻译会请求你配置的模型接口
- 外部入口会在浏览器中打开第三方网站

以下本地运行数据已被 Git 忽略：

- `data/library.json` 保存收藏、忽略、元数据、标签、备注、译文和最近搜索
- `data/settings.json` 保存本地模型设置，可能包含 API Key
- `data/fulltext_tasks/` 保存可续跑的全文翻译任务进度
- `downloaded_papers/` 保存下载的 PDF
- `translated_papers/` 保存全文翻译生成的中英对照 Markdown
- `output/`、`test-results/`、`tmp-*.png` 和 `zotero-bridge/*.xpi` 是本地验证或构建产物

工作区备份会导出本地资料库、已下载 PDF、全文译文和全文翻译任务状态。备份中会包含不带 API Key 的模型设置，因此恢复备份后需要重新填写 API Key。

## 合规说明

PaperHunter 只会尝试从开放 PDF 链接或公开开放访问端点自动下载论文，不会绕过付费墙、登录、验证码、机构访问控制或出版方限制。

Google Scholar、知网、万方、X-MOL、Nature、Science 等网站可能需要手动浏览、登录、机构授权、付费、遵守 robots.txt 或人工验证。PaperHunter 只在适当情况下提供外部浏览器入口。

更多说明见 [DISCLAIMER.md](DISCLAIMER.md)。

## 仓库安全

如果你要把这个项目发布到 GitHub，建议阅读 [docs/REPOSITORY_SAFETY.md](docs/REPOSITORY_SAFETY.md)。至少应当：

- 为仓库所有者账号开启双重验证
- 保护 `main` 分支
- 禁止强制推送和删除分支
- 除非必要，不给协作者 `Admin` 权限
- 保留一个本地镜像备份

## 贡献

欢迎提交 Issue 和 Pull Request。新增数据源时，请遵守对应网站的服务条款，不要加入绕过访问限制的逻辑。

贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题报告见 [SECURITY.md](SECURITY.md)。

## 许可证

本项目使用 Apache License 2.0，详见 [LICENSE](LICENSE)。
