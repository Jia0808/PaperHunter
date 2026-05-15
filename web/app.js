const state = {
  results: [],
  sortBy: "recent",
  isSearching: false,
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

function createPaperCard(paper, index) {
  const card = document.createElement("article");
  card.className = "paper-card";

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
  link.textContent = `打开 ${paper.sourceLabel || "来源"}`;

  actions.append(downloadButton, link);
  card.append(content, actions);
  return card;
}

function renderResults() {
  elements.results.replaceChildren();
  elements.resultCount.textContent = String(state.results.length);
  elements.downloadAll.disabled = state.results.filter((paper) => paper.downloadable && !paper.isDownloaded).length === 0;

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
    state.results = data.results || [];
    elements.savedCount.textContent = String(data.downloadedCount || 0);
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
    const suffix = errorCount ? `，有 ${errorCount} 个来源暂时失败。${issueText}` : "。";
    const breakdownText = sourceBreakdown ? `来源分布：${sourceBreakdown}。` : "";
    setMessage(`找到 ${state.results.length} 篇论文${countText}。${breakdownText}${suffix}`, state.results.length ? "success" : "");
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

updateSortButtons();
updateSourceSummary();
applyFieldPreset();
renderExternalGateways();
refreshStatus().catch(() => {
  setMessage("后端状态读取失败，请确认 Python 服务正在运行。", "error");
});
