const state = {
  results: [],
  sortBy: "recent",
  isSearching: false,
  libraryView: "favorites",
  library: {
    favorites: [],
    ignored: [],
    history: [],
    favoriteKeys: [],
    ignoredKeys: [],
    downloadKeys: [],
  },
};

const fieldPresets = {
  all: {
    label: "全部学科",
    categories: ["All"],
  },
  "ai-ml": {
    label: "AI / 机器学习",
    categories: ["cs.AI", "cs.CL", "cs.CV", "cs.LG", "stat.ML"],
  },
  cs: {
    label: "计算机科学",
    categories: ["cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.RO"],
  },
  math: {
    label: "数学",
    categories: ["math.OC", "math.PR", "math.NA"],
  },
  physics: {
    label: "物理 / 天文",
    categories: ["physics.optics", "astro-ph.GA"],
  },
  stats: {
    label: "统计学",
    categories: ["stat.ML", "stat.AP"],
  },
  eess: {
    label: "电子工程 / 信号",
    categories: ["eess.SP", "eess.IV"],
  },
  bio: {
    label: "生命科学 / 医学计算",
    categories: ["q-bio.QM", "q-bio.NC", "stat.AP"],
  },
  "econ-fin": {
    label: "经济 / 金融",
    categories: ["econ.EM", "q-fin.ST", "stat.AP"],
  },
  custom: {
    label: "自定义分类",
    categories: [],
  },
};

const sourceLabels = {
  arxiv: "arXiv",
  semantic: "Semantic Scholar",
  cvf: "CVF Open Access",
  acl: "ACL Anthology",
  openreview: "OpenReview",
  chinarxiv: "ChinaRxiv / ChinaXiv",
  sciopen: "SciOpen",
  nso: "National Science Open",
};

const externalGateways = [
  {
    label: "Google Scholar",
    tag: "手动查看",
    url: (query) => query ? `https://scholar.google.com/scholar?q=${query}` : "https://scholar.google.com/",
  },
  {
    label: "CNKI 知网",
    tag: "权限/验证",
    url: (query) => query ? `https://kns.cnki.net/kns8s/defaultresult/index?kw=${query}` : "https://kns.cnki.net/",
  },
  {
    label: "万方数据",
    tag: "权限",
    url: (query) => query
      ? `https://s.wanfangdata.com.cn/paper?q=${query}`
      : "https://s.wanfangdata.com.cn/paper",
  },
  {
    label: "X-MOL",
    tag: "验证后粘贴",
    url: (query) => query ? `https://www.x-mol.com/paper/search?keyword=${query}` : "https://www.x-mol.com/paper",
    copyQuery: true,
  },
  {
    label: "National Science Open",
    tag: "站内检索",
    url: (query) => query ? `https://www.nso-journal.org/component/finder/search?q=${query}` : "https://www.nso-journal.org/component/finder/search",
  },
];

const elements = {
  form: document.querySelector("#searchForm"),
  query: document.querySelector("#queryInput"),
  intent: document.querySelector("#intentSelect"),
  perSourceLimit: document.querySelector("#perSourceLimitInput"),
  perSourceLimitValue: document.querySelector("#perSourceLimitValue"),
  sourceLimitNote: document.querySelector("#sourceLimitNote"),
  sortButtons: document.querySelectorAll("[data-sort]"),
  sourceInputs: document.querySelectorAll(".source-grid input"),
  externalGateways: document.querySelector("#externalGateways"),
  fieldPreset: document.querySelector("#fieldPreset"),
  yearFrom: document.querySelector("#yearFromInput"),
  yearTo: document.querySelector("#yearToInput"),
  downloadableOnly: document.querySelector("#downloadableOnlyInput"),
  author: document.querySelector("#authorInput"),
  venue: document.querySelector("#venueInput"),
  matchScope: document.querySelector("#matchScopeSelect"),
  categoryHint: document.querySelector("#categoryHint"),
  categoryInputs: document.querySelectorAll(".category-grid input"),
  results: document.querySelector("#results"),
  message: document.querySelector("#message"),
  resultCount: document.querySelector("#resultCount"),
  currentQuery: document.querySelector("#currentQuery"),
  currentCategories: document.querySelector("#currentCategories"),
  currentSources: document.querySelector("#currentSources"),
  sourceSummary: document.querySelector("#sourceSummary"),
  savedCount: document.querySelector("#savedCount"),
  downloadAll: document.querySelector("#downloadAllButton"),
  exportResults: document.querySelector("#exportResultsButton"),
  favoriteCount: document.querySelector("#favoriteCount"),
  ignoredCount: document.querySelector("#ignoredCount"),
  exportFavoritesBib: document.querySelector("#exportFavoritesBibButton"),
  exportFavoritesMarkdown: document.querySelector("#exportFavoritesMarkdownButton"),
  refreshFavorites: document.querySelector("#refreshFavoritesButton"),
  libraryRefreshNote: document.querySelector("#libraryRefreshNote"),
  clearHistory: document.querySelector("#clearHistoryButton"),
  libraryTabs: document.querySelectorAll("[data-library-view]"),
  libraryItems: document.querySelector("#libraryItems"),
  searchHistory: document.querySelector("#searchHistory"),
  progress: document.querySelector("#progressBar"),
};

function setMessage(text, type = "") {
  elements.message.textContent = text;
  elements.message.className = `message${type ? ` is-${type}` : ""}`;
}

function setProgress(percent) {
  elements.progress.style.width = `${Math.max(0, Math.min(100, percent))}%`;
}

function summarizeErrors(errors) {
  const messages = Object.values(errors || {}).filter(Boolean);
  if (!messages.length) {
    return "";
  }
  return messages.slice(0, 2).join(" ");
}

function getSelectedCategories() {
  return Array.from(elements.categoryInputs)
    .filter((input) => input.checked)
    .map((input) => input.value);
}

function getSelectedSources() {
  return Array.from(elements.sourceInputs)
    .filter((input) => input.checked)
    .map((input) => input.value);
}

function getNumberValue(input) {
  if (!input.value.trim()) {
    return null;
  }
  const value = Number(input.value);
  return Number.isFinite(value) ? value : null;
}

function updateSourceSummary() {
  const sources = getSelectedSources();
  const labels = sources.map((source) => sourceLabels[source] || source);
  const text = labels.length ? labels.join(", ") : "未选择";
  elements.currentSources.textContent = text;
  elements.sourceSummary.textContent = text;
  updateSourceLimitSummary();
}

function getPerSourceLimit() {
  const value = Number(elements.perSourceLimit.value);
  return Number.isFinite(value) ? value : 5;
}

function updateSourceLimitSummary() {
  const sourceCount = getSelectedSources().length;
  const perSourceLimit = getPerSourceLimit();
  elements.perSourceLimitValue.textContent = String(perSourceLimit);
  elements.sourceLimitNote.textContent = sourceCount
    ? `已选 ${sourceCount} 个源，最多返回 ${sourceCount * perSourceLimit} 篇`
    : "请至少选择一个数据源";
}

function renderExternalGateways() {
  const rawQuery = elements.query.value.trim();
  const query = encodeURIComponent(rawQuery);
  elements.externalGateways.replaceChildren();
  externalGateways.forEach((gateway) => {
    const link = document.createElement("a");
    link.className = "gateway-link";
    link.href = gateway.url(query);
    link.target = "_blank";
    link.rel = "noreferrer";
    if (gateway.copyQuery) {
      link.title = "该站点会先做人机验证，已尽量带关键词，并会在点击时复制关键词。";
      link.addEventListener("click", async (event) => {
        if (!rawQuery) {
          return;
        }
        event.preventDefault();
        const opened = window.open("", "_blank");
        if (opened) {
          opened.opener = null;
          opened.location.href = link.href;
        }
        try {
          await navigator.clipboard.writeText(rawQuery);
          setMessage(`已复制关键词“${rawQuery}”，X-MOL 验证后可直接粘贴搜索。`, "success");
        } catch (error) {
          setMessage("X-MOL 可能会在验证后清空关键词，请手动粘贴当前检索词。");
        }
        if (!opened) {
          setMessage("浏览器拦截了 X-MOL 新窗口；关键词已尽量复制，请允许弹窗后再点一次。", "error");
        }
      });
    }

    const label = document.createElement("span");
    label.textContent = gateway.label;
    const tag = document.createElement("small");
    tag.textContent = gateway.tag;
    link.append(label, tag);
    elements.externalGateways.append(link);
  });
}

function getActiveFieldLabel() {
  const preset = fieldPresets[elements.fieldPreset.value];
  if (!preset || elements.fieldPreset.value === "custom") {
    return "自定义分类";
  }
  return preset.label;
}

function updateCategorySummary() {
  const categories = getSelectedCategories();
  if (!categories.length) {
    elements.currentCategories.textContent = "未选择";
    return;
  }
  elements.currentCategories.textContent = `${getActiveFieldLabel()} / ${categories.join(", ")}`;
}

function setCheckedCategories(categories) {
  elements.categoryInputs.forEach((input) => {
    input.checked = categories.includes(input.value);
  });
  updateCategorySummary();
}

function applyFieldPreset() {
  const preset = fieldPresets[elements.fieldPreset.value] || fieldPresets.custom;
  if (elements.fieldPreset.value !== "custom") {
    setCheckedCategories(preset.categories);
  }
  elements.categoryHint.textContent = elements.fieldPreset.value === "custom" ? "当前为自定义" : "可手动微调";
  updateCategorySummary();
}

function updateSortButtons() {
  elements.sortButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.sort === state.sortBy);
  });
}

function renderSkeleton() {
  elements.results.replaceChildren();
  for (let index = 0; index < 4; index += 1) {
    const skeleton = document.createElement("div");
    skeleton.className = "skeleton";
    elements.results.append(skeleton);
  }
}

function createMetaChip(text) {
  const chip = document.createElement("span");
  chip.textContent = text || "-";
  return chip;
}

function formatSourceCounts(counts = {}) {
  return Object.entries(counts)
    .filter(([, count]) => Number(count) > 0)
    .map(([source, count]) => `${sourceLabels[source] || source} ${count}`)
    .join("，");
}

function paperUrl(paper) {
  return paper.pageUrl || paper.entryUrl || paper.pdfUrl || "#";
}

function paperDisplayMeta(paper) {
  return [
    paper.sourceLabel || sourceLabels[paper.source] || "Source",
    paper.year || paper.published || "",
    paper.venue || paper.category || "",
  ].filter(Boolean).join(" · ");
}

function normalizeLibrary(library = {}) {
  return {
    favorites: Array.isArray(library.favorites) ? library.favorites : [],
    ignored: Array.isArray(library.ignored) ? library.ignored : [],
    history: Array.isArray(library.history) ? library.history : [],
    favoriteKeys: Array.isArray(library.favoriteKeys) ? library.favoriteKeys : [],
    ignoredKeys: Array.isArray(library.ignoredKeys) ? library.ignoredKeys : [],
    downloadKeys: Array.isArray(library.downloadKeys) ? library.downloadKeys : [],
  };
}

function isFavorite(paper) {
  return state.library.favoriteKeys.includes(paper.paperKey);
}

function annotatePaper(paper) {
  paper.isFavorite = isFavorite(paper);
  paper.isIgnored = state.library.ignoredKeys.includes(paper.paperKey);
  return paper;
}

function syncResultsWithLibrary() {
  state.results = state.results.map(annotatePaper).filter((paper) => !paper.isIgnored);
}

function createLibraryAction(label, handler, disabled = false) {
  const button = document.createElement("button");
  button.className = "library-item-action";
  button.type = "button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", handler);
  return button;
}

function createLibraryItem(paper, view) {
  const item = document.createElement("article");
  item.className = "library-item";

  const header = document.createElement("div");
  header.className = "library-item-header";

  const title = document.createElement("strong");
  title.textContent = paper.title || "Untitled";
  title.title = paper.title || "";

  const meta = document.createElement("span");
  meta.textContent = paperDisplayMeta(paper);
  header.append(title, meta);

  const actions = document.createElement("div");
  actions.className = "library-item-actions";

  const openLink = document.createElement("a");
  openLink.className = "library-item-action";
  openLink.href = paperUrl(paper);
  openLink.target = "_blank";
  openLink.rel = "noreferrer";
  openLink.textContent = "来源";
  openLink.title = "打开来源页面";

  actions.append(openLink);

  if (view === "favorites") {
    actions.append(
      createLibraryAction("下载", () => downloadLibraryPaper(paper), !paper.downloadable || paper.isDownloaded),
      createLibraryAction("BibTeX", () => copyLibraryPaperExport(paper, "bibtex")),
      createLibraryAction("Markdown", () => copyLibraryPaperExport(paper, "markdown")),
      createLibraryAction("取消收藏", () => updateLibraryPaperFromPanel("unfavorite", paper)),
    );
  } else {
    actions.append(createLibraryAction("恢复", () => updateLibraryPaperFromPanel("unignore", paper)));
  }

  item.append(header, actions);
  return item;
}

function renderLibraryItems() {
  elements.libraryTabs.forEach((button) => {
    const isActive = button.dataset.libraryView === state.libraryView;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  elements.libraryItems.replaceChildren();
  const items = state.libraryView === "ignored" ? state.library.ignored : state.library.favorites;
  if (!items.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = state.libraryView === "ignored" ? "暂无忽略论文" : "暂无收藏论文";
    elements.libraryItems.append(empty);
    return;
  }

  items.forEach((paper) => {
    elements.libraryItems.append(createLibraryItem(paper, state.libraryView));
  });
}

function renderLibrary() {
  const favoriteCount = state.library.favorites.length;
  const ignoredCount = state.library.ignored.length;
  elements.favoriteCount.textContent = String(favoriteCount);
  elements.ignoredCount.textContent = String(ignoredCount);
  elements.exportFavoritesBib.disabled = favoriteCount === 0;
  elements.exportFavoritesMarkdown.disabled = favoriteCount === 0;
  elements.refreshFavorites.disabled = favoriteCount === 0;
  elements.clearHistory.disabled = state.library.history.length === 0;
  const staleCount = state.library.favorites.filter((paper) => !paper.fullAbstract).length;
  elements.libraryRefreshNote.textContent = staleCount
    ? `${staleCount} 篇收藏可能只有截断摘要，可刷新补全可获取的元数据。`
    : "收藏元数据已包含完整摘要或来源未提供更多内容。";
  renderLibraryItems();

  elements.searchHistory.replaceChildren();
  if (!state.library.history.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = "暂无历史";
    elements.searchHistory.append(empty);
    return;
  }

  state.library.history.slice(0, 6).forEach((item) => {
    const button = document.createElement("button");
    button.className = "history-item";
    button.type = "button";
    button.title = item.query || "";
    button.addEventListener("click", () => {
      elements.query.value = item.query || "";
      elements.intent.value = item.intent || "general";
      elements.fieldPreset.value = item.fieldPreset || "all";
      state.sortBy = item.sortBy || "recent";
      updateSortButtons();
      applyFieldPreset();
      renderExternalGateways();
      elements.query.focus();
    });

    const title = document.createElement("strong");
    title.textContent = item.query || "未命名检索";
    const meta = document.createElement("span");
    const sourceText = Array.isArray(item.sources) ? item.sources.map((source) => sourceLabels[source] || source).join(", ") : "";
    meta.textContent = `${item.resultCount || 0} 篇 · ${sourceText || "默认来源"}`;
    button.append(title, meta);
    elements.searchHistory.append(button);
  });
}

function updateLibrary(library) {
  state.library = normalizeLibrary(library);
  syncResultsWithLibrary();
  renderLibrary();
}

function downloadTextFile(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType || "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function createPaperCard(paper, index) {
  const card = document.createElement("article");
  card.className = "paper-card";
  card.classList.toggle("is-favorite", Boolean(paper.isFavorite));

  const content = document.createElement("div");
  const meta = document.createElement("div");
  meta.className = "paper-meta";
  meta.append(
    createMetaChip(paper.sourceLabel || "Source"),
    createMetaChip(paper.category || paper.venue || "Paper"),
    createMetaChip(paper.published || String(paper.year || "")),
    createMetaChip(paper.paperId || paper.arxivId || "")
  );

  const title = document.createElement("h3");
  title.textContent = paper.title || "Untitled";

  const authors = document.createElement("p");
  authors.className = "authors";
  authors.textContent = paper.authors || "Unknown authors";

  const abstract = document.createElement("p");
  abstract.className = "abstract";
  abstract.textContent = paper.abstract || "No abstract available.";

  content.append(meta, title, authors, abstract);

  const actions = document.createElement("div");
  actions.className = "paper-actions";

  const downloadButton = document.createElement("button");
  downloadButton.className = "paper-action";
  downloadButton.type = "button";
  downloadButton.dataset.index = String(index);
  downloadButton.textContent = !paper.downloadable ? "无 PDF" : paper.isDownloaded ? "已保存" : "下载 PDF";
  downloadButton.disabled = Boolean(paper.isDownloaded) || !paper.downloadable;
  downloadButton.addEventListener("click", () => downloadPaper(index, downloadButton));

  const link = document.createElement("a");
  link.className = "paper-link";
  link.href = paper.pageUrl || paper.entryUrl || paper.pdfUrl || "#";
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "打开来源";
  link.title = `打开 ${paper.sourceLabel || "来源"} 页面`;
  link.setAttribute("aria-label", `打开 ${paper.sourceLabel || "来源"} 页面`);

  const favoriteButton = document.createElement("button");
  favoriteButton.className = "paper-action";
  favoriteButton.type = "button";
  favoriteButton.textContent = paper.isFavorite ? "取消收藏" : "收藏";
  favoriteButton.addEventListener("click", () => toggleFavorite(index, favoriteButton));

  const ignoreButton = document.createElement("button");
  ignoreButton.className = "paper-action";
  ignoreButton.type = "button";
  ignoreButton.textContent = "忽略";
  ignoreButton.addEventListener("click", () => ignorePaper(index, ignoreButton));

  const copyBibButton = document.createElement("button");
  copyBibButton.className = "paper-action";
  copyBibButton.type = "button";
  copyBibButton.textContent = "复制 BibTeX";
  copyBibButton.addEventListener("click", () => copyPaperExport(index, "bibtex"));

  const copyMarkdownButton = document.createElement("button");
  copyMarkdownButton.className = "paper-action";
  copyMarkdownButton.type = "button";
  copyMarkdownButton.textContent = "复制 Markdown";
  copyMarkdownButton.addEventListener("click", () => copyPaperExport(index, "markdown"));

  const secondaryActions = document.createElement("div");
  secondaryActions.className = "paper-secondary-actions";
  secondaryActions.append(favoriteButton, ignoreButton, copyBibButton, copyMarkdownButton);

  actions.append(downloadButton, link, secondaryActions);
  card.append(content, actions);
  return card;
}

function renderResults() {
  elements.results.replaceChildren();
  elements.resultCount.textContent = String(state.results.length);
  elements.downloadAll.disabled = state.results.filter((paper) => paper.downloadable && !paper.isDownloaded).length === 0;
  elements.exportResults.disabled = state.results.length === 0;

  if (state.results.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <p class="empty-kicker">No Results</p>
      <h3>没有找到匹配论文</h3>
      <p>可以减少年份、作者、会议或可下载限制，也可以换成更具体的模型名、方法名或会议名。</p>
    `;
    elements.results.append(empty);
    return;
  }

  state.results.forEach((paper, index) => {
    elements.results.append(createPaperCard(paper, index));
  });
}

async function requestJson(url, payload, timeoutMs = 22000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || "请求失败。");
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("检索超时。可以减少数据源，或先只选 arXiv / CVF 试一次。");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

async function refreshStatus() {
  const response = await fetch("/api/status");
  const data = await response.json();
  elements.savedCount.textContent = String(data.downloadedCount || 0);
  updateLibrary(data.library || {});
}

async function updatePaperLibrary(action, paper) {
  const data = await requestJson("/api/library", { action, paper, paperKey: paper.paperKey });
  updateLibrary(data.library || {});
  return data;
}

async function updateLibraryPaperFromPanel(action, paper) {
  try {
    await updatePaperLibrary(action, paper);
    const messages = {
      unfavorite: "已从收藏列表移除。",
      unignore: "已恢复该论文，后续检索会重新显示。",
    };
    setMessage(messages[action] || "本地收件箱已更新。", "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function downloadLibraryPaper(paper) {
  if (!paper || !paper.downloadable || paper.isDownloaded) {
    return;
  }
  setMessage(`正在下载：${paper.title}`);
  try {
    const data = await requestJson("/api/download", paper, 60000);
    elements.savedCount.textContent = String(data.downloadedCount || 0);
    await refreshStatus();
    setMessage(`${data.message} ${data.filename}`, "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function copyLibraryPaperExport(paper, format) {
  try {
    const data = await exportPapers({ scope: "results", format, papers: [paper], download: false });
    await copyText(data.content);
    setMessage(format === "bibtex" ? "收藏 BibTeX 已复制。" : "收藏 Markdown 已复制。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function toggleFavorite(index, button) {
  const paper = state.results[index];
  if (!paper || button.disabled) {
    return;
  }

  const action = paper.isFavorite ? "unfavorite" : "favorite";
  button.disabled = true;
  try {
    await updatePaperLibrary(action, paper);
    setMessage(action === "favorite" ? "已加入收藏。" : "已取消收藏。", "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function ignorePaper(index, button) {
  const paper = state.results[index];
  if (!paper || button.disabled) {
    return;
  }

  button.disabled = true;
  try {
    await updatePaperLibrary("ignore", paper);
    setMessage("已忽略该论文，后续检索会默认隐藏。", "success");
    renderResults();
  } catch (error) {
    button.disabled = false;
    setMessage(error.message, "error");
  }
}

async function clearHistory() {
  try {
    const data = await requestJson("/api/library", { action: "clear-history", paperKey: "history" });
    updateLibrary(data.library || {});
    setMessage("搜索历史已清空。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function refreshFavoritesMetadata() {
  if (elements.refreshFavorites.disabled) {
    return;
  }

  const originalText = elements.refreshFavorites.textContent;
  elements.refreshFavorites.disabled = true;
  elements.refreshFavorites.textContent = "刷新中";
  setMessage("正在刷新收藏元数据，部分来源可能需要等待...");

  try {
    const data = await requestJson("/api/library", { action: "refresh-favorites", paperKey: "favorites" }, 60000);
    updateLibrary(data.library || {});
    const errorCount = data.errors ? Object.keys(data.errors).length : 0;
    const suffix = errorCount ? `，${errorCount} 篇未匹配或来源暂时失败` : "";
    setMessage(`已刷新 ${data.refreshed || 0}/${data.checked || 0} 篇收藏${suffix}。`, errorCount ? "" : "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.refreshFavorites.textContent = originalText;
    elements.refreshFavorites.disabled = state.library.favorites.length === 0;
  }
}

async function exportPapers({ scope = "results", format = "bibtex", papers = state.results, download = true } = {}) {
  const data = await requestJson("/api/export", { scope, format, papers });
  if (download) {
    downloadTextFile(data.filename, data.content, data.mimeType);
  }
  return data;
}

async function exportCurrentResults() {
  try {
    const data = await exportPapers({ scope: "results", format: "bibtex", papers: state.results });
    setMessage(`已导出 ${data.count} 篇当前结果。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function exportFavorites(format) {
  try {
    const data = await exportPapers({ scope: "favorites", format });
    setMessage(`已导出 ${data.count} 篇收藏论文。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function copyPaperExport(index, format) {
  const paper = state.results[index];
  if (!paper) {
    return;
  }
  try {
    const data = await exportPapers({ scope: "results", format, papers: [paper], download: false });
    await copyText(data.content);
    setMessage(format === "bibtex" ? "BibTeX 已复制。" : "Markdown 已复制。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function performSearch(event) {
  event.preventDefault();
  if (state.isSearching) {
    return;
  }

  const query = elements.query.value.trim();
  if (!query) {
    setMessage("请输入检索关键词。", "error");
    elements.query.focus();
    return;
  }

  state.isSearching = true;
  setProgress(0);
  setMessage("正在检索多个来源，请稍等...");
  renderSkeleton();

  try {
    const categories = getSelectedCategories();
    const sources = getSelectedSources();
    if (!sources.length) {
      throw new Error("请至少选择一个数据源。");
    }
    const perSourceLimit = getPerSourceLimit();
    const data = await requestJson("/api/search", {
      query,
      maxResults: perSourceLimit * sources.length,
      perSourceLimit,
      sortBy: state.sortBy,
      categories,
      sources,
      fieldPreset: elements.fieldPreset.value,
      intent: elements.intent.value,
      yearFrom: getNumberValue(elements.yearFrom),
      yearTo: getNumberValue(elements.yearTo),
      downloadableOnly: elements.downloadableOnly.checked,
      author: elements.author.value.trim(),
      venue: elements.venue.value.trim(),
      matchScope: elements.matchScope.value,
    });
    state.results = (data.results || []).map(annotatePaper);
    elements.savedCount.textContent = String(data.downloadedCount || 0);
    updateLibrary(data.library || state.library);
    elements.currentQuery.textContent = query;
    updateCategorySummary();
    updateSourceSummary();
    renderResults();

    const errorCount = data.errors ? Object.keys(data.errors).length : 0;
    const successSourceCount = Object.keys(data.sourceCounts || {}).length;
    const theoreticalMax = sources.length * perSourceLimit;
    const countText = data.perSourceLimit
      ? `（${successSourceCount}/${sources.length} 个来源有结果，每源最多 ${data.perSourceLimit} 篇，理论最多 ${theoreticalMax} 篇）`
      : "";
    const sourceBreakdown = formatSourceCounts(data.sourceCounts);
    const issueText = summarizeErrors(data.errors);
    const hiddenText = data.hiddenIgnoredCount ? `已隐藏 ${data.hiddenIgnoredCount} 篇忽略论文。` : "";
    const suffix = errorCount ? `，有 ${errorCount} 个来源暂时失败。${issueText}` : "。";
    const breakdownText = sourceBreakdown ? `来源分布：${sourceBreakdown}。` : "";
    setMessage(`找到 ${state.results.length} 篇论文${countText}。${breakdownText}${hiddenText}${suffix}`, state.results.length ? "success" : "");
    setProgress(100);
    window.setTimeout(() => setProgress(0), 650);
  } catch (error) {
    state.results = [];
    renderResults();
    setMessage(error.message, "error");
    setProgress(0);
  } finally {
    state.isSearching = false;
  }
}

async function downloadPaper(index, button) {
  const paper = state.results[index];
  if (!paper || button.disabled) {
    return;
  }

  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "下载中";
  setMessage(`正在下载：${paper.title}`);

  try {
    const data = await requestJson("/api/download", paper, 60000);
    paper.isDownloaded = true;
    button.textContent = "已保存";
    elements.savedCount.textContent = String(data.downloadedCount || 0);
    refreshStatus().catch(() => {});
    setMessage(`${data.message} ${data.filename}`, "success");
    renderResults();
  } catch (error) {
    button.disabled = false;
    button.textContent = originalText;
    setMessage(error.message, "error");
  }
}

async function downloadAll() {
  const pending = state.results
    .map((paper, index) => ({ paper, index }))
    .filter(({ paper }) => paper.downloadable && !paper.isDownloaded);

  if (pending.length === 0) {
    setMessage("当前结果中可下载的 PDF 都已经保存。", "success");
    return;
  }

  elements.downloadAll.disabled = true;
  let completed = 0;
  let failed = 0;

  for (const item of pending) {
    const { paper, index } = item;
    setMessage(`正在下载 ${completed + 1}/${pending.length}：${paper.title}`);
    try {
      const data = await requestJson("/api/download", paper, 60000);
      paper.isDownloaded = true;
      elements.savedCount.textContent = String(data.downloadedCount || 0);
      const button = document.querySelector(`[data-index="${index}"]`);
      if (button) {
        button.disabled = true;
        button.textContent = "已保存";
      }
    } catch (error) {
      failed += 1;
    }
    completed += 1;
    setProgress((completed / pending.length) * 100);
  }

  renderResults();
  refreshStatus().catch(() => {});
  window.setTimeout(() => setProgress(0), 800);

  if (failed) {
    setMessage(`批量下载完成，但有 ${failed} 篇失败。`, "error");
  } else {
    setMessage("批量下载完成。", "success");
  }
}

elements.perSourceLimit.addEventListener("input", updateSourceLimitSummary);

elements.sortButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.sortBy = button.dataset.sort;
    updateSortButtons();
  });
});

elements.sourceInputs.forEach((input) => {
  input.addEventListener("change", updateSourceSummary);
});

elements.query.addEventListener("input", renderExternalGateways);

elements.categoryInputs.forEach((input) => {
  input.addEventListener("change", () => {
    if (input.value === "All" && input.checked) {
      elements.categoryInputs.forEach((item) => {
        if (item !== input) {
          item.checked = false;
        }
      });
    }
    if (input.value !== "All" && input.checked) {
      const allInput = Array.from(elements.categoryInputs).find((item) => item.value === "All");
      if (allInput) {
        allInput.checked = false;
      }
    }
    elements.fieldPreset.value = "custom";
    elements.categoryHint.textContent = "当前为自定义";
    updateCategorySummary();
  });
});

elements.fieldPreset.addEventListener("change", applyFieldPreset);
elements.form.addEventListener("submit", performSearch);
elements.downloadAll.addEventListener("click", downloadAll);
elements.exportResults.addEventListener("click", exportCurrentResults);
elements.exportFavoritesBib.addEventListener("click", () => exportFavorites("bibtex"));
elements.exportFavoritesMarkdown.addEventListener("click", () => exportFavorites("markdown"));
elements.refreshFavorites.addEventListener("click", refreshFavoritesMetadata);
elements.clearHistory.addEventListener("click", clearHistory);
elements.libraryTabs.forEach((button) => {
  button.addEventListener("click", () => {
    state.libraryView = button.dataset.libraryView || "favorites";
    renderLibraryItems();
  });
});

updateSortButtons();
updateSourceSummary();
applyFieldPreset();
renderExternalGateways();
refreshStatus().catch(() => {
  setMessage("后端状态读取失败，请确认 Python 服务正在运行。", "error");
});
