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
- 支持模型设置面板，可配置 OpenAI 兼容 Responses/Chat Completions 接口、DeepSeek、Anthropic 和自定义提供商。
- 支持单篇摘要翻译和收藏摘要批量翻译；当来源摘要变化时，会标记已有译文可能过期。
- 支持把收藏或单篇论文导出为 BibTeX、Markdown 阅读清单，以及中英对照摘要 Markdown。
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

- APIXIN GPT 兼容接口
- DeepSeek Chat Completions
- Anthropic Messages
- 自定义 OpenAI 兼容 Responses 或 Chat Completions 接口

模型设置会保存到 `data/settings.json`，该文件已被 Git 忽略。状态接口只返回脱敏后的 API Key；工作区备份会在写入 `data/settings.json` 前移除 API Key。

翻译请求会把选中的摘要或全文分片发送到你配置的模型提供商。PaperHunter 不查询账户余额，也不会在你没有触发翻译操作时发送论文内容。

## 使用流程

1. 输入研究关键词或短语。
2. 选择研究意图、研究领域、年份范围、数据源和每个数据源返回篇数。
3. 执行检索，查看标题、作者、年份、期刊/会议和 PDF 可用性。
4. 把有用论文加入本地收件箱，忽略不想再看到的论文，并可补充阅读状态、标签和备注。
5. 如需摘要或全文翻译，先配置模型接口。
6. 翻译单篇摘要、批量翻译收藏摘要，或者在元数据更新后重译可能过期的摘要。
7. 将收藏论文导出为 BibTeX、Markdown 阅读清单或中英对照摘要文件。
8. 下载选中的开放访问 PDF，或批量下载可下载结果。
9. 对已下载 PDF 执行全文翻译，查看分片进度；任务完成后可打开译文所在文件夹。
10. 如果旧收藏显示摘要可能被截断，可以刷新收藏元数据来尽量补回完整摘要。
11. 在迁移机器或清理本地运行数据前，导出工作区备份。
12. 如果来源需要登录或机构权限，使用外部入口在浏览器中继续访问。

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
