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
- 为 Google Scholar、知网、万方、X-MOL、Nature、Science 等通常需要手动浏览、登录、机构权限、付费、遵守 robots.txt 或验证码的来源提供外部入口。
- 本地优先：下载的 PDF 保存在 `downloaded_papers/`，该目录不会提交到 Git。
- 技术栈轻量：Python 3.12、`requests`、`arxiv` 和浏览器原生前端代码。

## 支持的数据源

| 数据源 | 检索 | PDF 下载 | 说明 |
| --- | --- | --- | --- |
| arXiv | 支持 | 支持 | 使用 arXiv package/API。 |
| Semantic Scholar | 支持 | 仅公开开放 PDF | 受 Semantic Scholar 速率限制影响。 |
| CVF Open Access | 支持 | 支持 | 检索公开 CVF Open Access 页面。 |
| ACL Anthology | 支持 | 支持 | 使用 ACL Anthology 元数据/缓存。 |
| OpenReview | 支持 | 仅公开开放 PDF | 部分 PDF 可能需要来源站点校验。 |
| ChinaRxiv / ChinaXiv | 支持 | 仅公开开放 PDF | 国内开放论文来源。 |
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

## 使用流程

1. 输入研究关键词或短语。
2. 选择研究意图、研究领域、年份范围、数据源和每个数据源返回篇数。
3. 执行检索，查看标题、作者、年份、期刊/会议和 PDF 可用性。
4. 下载选中的开放访问 PDF，或批量下载可下载结果。
5. 如果来源需要登录或机构权限，使用外部入口在浏览器中继续访问。

## 项目结构

```text
app.py                    Python HTTP 服务、数据源适配、筛选、下载
web/index.html            浏览器界面结构
web/styles.css            界面样式
web/app.js                前端状态、筛选、API 调用
downloaded_papers/        本地 PDF 输出目录，已被 Git 忽略
docs/assets/              README 和文档图片
.github/workflows/ci.yml  Python 和 JavaScript 语法检查
```

## 开发检查

```bash
python -m py_compile app.py
node --check web/app.js
```

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
