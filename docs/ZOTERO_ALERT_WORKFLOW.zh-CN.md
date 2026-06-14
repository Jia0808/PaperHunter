# Zotero 与 Alert 工作流使用说明

这份说明面向日常使用者，解释 PaperHunter 新增的 Alert 导入、摘要翻译、Zotero 保存/导入、Bridge 插件安装和译文回写流程。

## 你会用到的几个概念

- **Alert**：你已经能看到的订阅提醒、邮件提醒、出版社页面文本或导出的题录文本。PaperHunter 只处理你粘贴或选择的可见内容，不自动抓取受限网页。
- **Alert 收件箱**：Alert 导入后先进入这里，等你确认摘要是否可信、是否采用。这样不会把不完整或冲突摘要直接写进本地库。
- **采用并锁定**：把 Alert 里的摘要作为当前论文摘要保存下来，并标记为用户确认。之后开放元数据滞后或缺失时，也不会轻易覆盖这段已确认摘要。
- **Zotero itemKey**：Zotero 给每个条目的本地唯一标识。PaperHunter 需要知道 itemKey，才能把译文回写到正确的 Zotero 条目。
- **Bridge 插件**：一个安装在 Zotero 里的本地插件。它只接受本机 PaperHunter 的配对请求，用来把 PaperHunter 管理的 note、`paperhunter:*` 标签和译文 Markdown 附件写回 Zotero。
- **dry-run 预览**：真正回写前的只读预览。它会告诉你将写入哪个 Zotero itemKey、哪些标签、几个附件，不会修改 Zotero。

## 推荐完整流程

1. 打开 Zotero 桌面端。
2. 启动 PaperHunter，并在浏览器里打开 PaperHunter 页面。
3. 用 Alert 导入论文摘要，先进入 Alert 收件箱。
4. 在 Alert 收件箱里检查摘要，点击“采用并锁定”。
5. 对论文执行摘要翻译，必要时执行全文翻译。
6. 把论文保存到 Zotero，或从 Zotero 导入已有条目。
7. 在 Zotero 联动面板确认 PaperHunter 已找到正确的 Zotero itemKey。
8. 点击“下载 Bridge 插件”，把当前工作区专属 XPI 安装到 Zotero。
9. 回到 PaperHunter，确认 Zotero 联动状态显示“回写可用”。
10. 点击“同步译文回 Zotero”，先查看 dry-run 预览。
11. 确认预览无误后，再执行真实回写。

## 导入 Alert

在 PaperHunter 页面中点击“导入 Alert”。

建议默认保持：

- “先加入 Alert 收件箱审阅，再由我确认采用”：开启。
- “同时查询开放元数据补全摘要”：按需开启。新论文或新期刊可能还没有被开放数据库及时索引，Alert 摘要反而更完整。

Alert 文本至少建议包含：

```text
Title: 论文标题
Authors: 作者
Journal: 期刊或会议
Year: 年份
DOI: DOI
Abstract: 摘要
URL: 来源页面
```

导入后，论文会进入 Alert 收件箱。你可以逐条检查，也可以在确认无误后批量采用。

## 理解 Alert 收件箱状态

- **待审**：已识别到 Alert 摘要，但还没有被你采用。
- **可采用**：这条摘要足够完整，可以作为当前论文摘要。
- **已采用**：你已经确认并保存这条摘要。
- **锁定**：当前摘要由用户确认，后续自动补全不会随意覆盖。
- **冲突**：同一篇论文出现了不同来源或不同文本的摘要，需要人工判断。
- **不完整**：摘要看起来可能被截断或太短，建议谨慎采用。

## 摘要翻译

采用摘要后，可以在本地收件箱里对单篇论文翻译摘要，也可以批量翻译收藏摘要。

翻译会把当前摘要发送到你配置的模型接口。PaperHunter 不查询账户余额，也不会在你没有触发翻译时发送论文内容。

如果诊断面板显示 `attention`，常见原因是旧收藏里还有论文没有摘要译文。这不一定是故障。

## 保存到 Zotero 与从 Zotero 导入

Zotero 联动面板里有几个按钮：

- **从 Zotero 导入**：从本机 Zotero 资料库读取题录、标签、分组和 PDF 附件路径，加入 PaperHunter 本地库。
- **只导入有 PDF**：只导入带本地 PDF 附件的 Zotero 条目。
- **保存到 Zotero**：把 PaperHunter 里的论文题录保存到正在运行的 Zotero 桌面端。
- **管理绑定**：查看或确认 PaperHunter 论文和 Zotero itemKey 的对应关系。
- **操作历史**：查看最近的 dry-run、真实同步和绑定确认记录。

保存或导入后，PaperHunter 会尝试用 DOI、URL、来源 ID、标题和年份自动匹配同一篇论文，并把 Zotero itemKey 写回 PaperHunter 本地记录。

如果出现多个候选，PaperHunter 不会自动合并 Zotero 条目。你需要在“管理绑定”里手动确认。

## 下载 Bridge 插件

截图里的“下载 Bridge 插件”按钮会生成并下载当前工作区专属的 Zotero 插件 XPI。

它的来源是仓库里的两个源码文件：

- `zotero-bridge/manifest.json`
- `zotero-bridge/bootstrap.js`

下载时，PaperHunter 会把当前本机的配对 token 写入 XPI。所以：

- 不要把生成后的 `paperhunter-zotero-bridge.xpi` 提交到 Git。
- 不要把自己机器下载的 XPI 发给别人复用。
- 每个用户都应该从自己正在运行的 PaperHunter 页面点击“下载 Bridge 插件”。
- 换机器、恢复设置或重新生成配对 token 后，需要重新下载并覆盖安装 XPI。

Bridge 源代码会随项目一起公开。用户可以检查它到底做了什么。

## 在 Zotero 中安装 Bridge

1. 点击 PaperHunter 里的“下载 Bridge 插件”，得到 `paperhunter-zotero-bridge.xpi`。
2. 打开 Zotero。
3. 打开 Zotero 插件/附加组件管理器。
4. 选择“从文件安装插件”。
5. 选择刚下载的 XPI。
6. 重启 Zotero。
7. 回到 PaperHunter，刷新页面或重新检测 Zotero 状态。

正常情况下，Zotero 联动面板会显示：

- 保存可用
- 导入可用
- 回写可用
- Bridge 版本兼容
- 配对 token 已验证

## Bridge 会写什么

真实回写时，Bridge 只写 PaperHunter 管理的内容：

- 创建或更新一条 PaperHunter 管理的 Zotero 子笔记。
- 添加 `paperhunter` 和 `paperhunter:*` 状态标签。
- 把 PaperHunter 生成的译文 Markdown 作为本地链接附件挂到 Zotero 条目下。

Bridge 不会做这些事：

- 不删除 Zotero 条目。
- 不合并 Zotero 条目。
- 不移动或覆盖原始 PDF。
- 不覆盖用户自己写的 Zotero 笔记。
- 不删除用户已有标签。
- 不修改 Zotero collections。
- 不绕过登录、验证码、付费墙或机构访问限制。

## 先看 dry-run，再真实回写

点击“同步译文回 Zotero”后，PaperHunter 会先展示 dry-run 预览。

你需要重点看：

- 将写入的 Zotero itemKey 是否正确。
- 是否显示“可回写”。
- 将添加哪些 `paperhunter:*` 标签。
- 将链接几个译文 Markdown 附件。
- 是否有“需确认”“未匹配”“冲突”等提示。

只有确认无误后，再点击确认回写。

## 常见问题

### 为什么显示“导入可用”，但“回写不可用”？

通常说明 PaperHunter 能读到 Zotero 本地资料库，但 Zotero Bridge 没有安装、没有启用、版本不兼容，或 Zotero 没有重启。

处理方法：

1. 确认 Zotero 正在运行。
2. 从当前 PaperHunter 页面重新点击“下载 Bridge 插件”。
3. 在 Zotero 里覆盖安装 XPI。
4. 重启 Zotero。
5. 回到 PaperHunter 刷新状态。

### 为什么提示配对 token 不匹配？

XPI 里内嵌的 token 和当前 PaperHunter 工作区保存的 token 不一致。

常见原因：

- 换了机器。
- 导入了备份。
- 重新生成了设置。
- 安装的是旧 XPI。

处理方法是从当前 PaperHunter 页面重新下载 XPI，并覆盖安装到 Zotero。

### 为什么同步预览里有“未匹配”？

这说明 PaperHunter 还不知道对应的 Zotero itemKey。

你可以：

- 先把这篇论文保存到 Zotero。
- 或从 Zotero 导入已有条目。
- 或在“管理绑定”里手动确认候选条目。

### 为什么诊断是 `attention`？

`attention` 不一定代表系统失败。常见原因是部分旧收藏还没有摘要译文、开放元数据滞后、或某些条目还没有匹配到 Zotero。

如果 Zotero 联动显示“回写可用”，Bridge 版本和配对都正常，那么 `attention` 多半只是待处理事项。

### 生成的 XPI 是否安全？

XPI 是本地生成的，只包含 Bridge 源码和当前工作区的配对 token。它只接受本机请求，并且只写 PaperHunter 管理的 note、标签和译文附件。

如果你担心安全，可以直接查看 `zotero-bridge/bootstrap.js` 源码。
