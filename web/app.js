const state = {
  results: [],
  sortBy: "recent",
  isSearching: false,
  libraryView: "favorites",
  alertInboxFilter: "active",
  researchRadar: null,
  modelProviders: [],
  modelApiTypes: {},
  modelSettings: null,
  selectedProvider: "apixin_gpt",
  zotero: {
    available: false,
    importAvailable: false,
    syncAvailable: false,
    message: "未检测 Zotero 状态。",
    importMessage: "",
    syncMessage: "",
    bridgeCapabilities: {},
  },
  subscription: {
    sources: [],
    alertImportHistory: [],
    alertInbox: { items: [], counts: {}, pendingCount: 0, adoptableCount: 0, lockedCount: 0, conflictCount: 0 },
    enabledCount: 0,
    policy: "",
    freshnessNote: "",
    lastImport: {},
  },
  diagnostics: null,
  bridgeInstallPoller: null,
  bridgeInstallPollStartedAt: 0,
  pendingBackupImport: null,
  fulltextTasks: {},
  fulltextPollers: {},
  library: {
    favorites: [],
    ignored: [],
    history: [],
    favoriteKeys: [],
    ignoredKeys: [],
    downloadKeys: [],
    subscriptionSources: [],
    alertImportHistory: [],
    alertInbox: { items: [], counts: {}, pendingCount: 0, adoptableCount: 0, lockedCount: 0, conflictCount: 0 },
    zoteroAudit: [],
    zoteroLastSync: {},
  },
  expandedLibraryItems: {},
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
  alert: "Alert 导入",
  zotero: "Zotero",
};

const abstractMetadataFields = [
  "abstractSource",
  "abstractSourceLabel",
  "abstractFetchedAt",
  "abstractCompleteness",
  "abstractAccessMode",
  "abstractDiagnostics",
  "abstractConflict",
  "abstractLocked",
  "abstractConfirmedAt",
  "abstractConfirmedBy",
    "abstractCandidates",
    "abstractAudit",
    "alertSourceHealth",
    "metadataUpdatedAt",
  ];

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

const readingStatusLabels = {
  "": "未设置",
  unread: "待读",
  reading: "精读",
  read: "已读",
  to_translate: "待翻译",
};

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
  exportResultsRis: document.querySelector("#exportResultsRisButton"),
  saveResultsZotero: document.querySelector("#saveResultsZoteroButton"),
  favoriteCount: document.querySelector("#favoriteCount"),
  ignoredCount: document.querySelector("#ignoredCount"),
  exportFavoritesBib: document.querySelector("#exportFavoritesBibButton"),
  exportFavoritesRis: document.querySelector("#exportFavoritesRisButton"),
  saveFavoritesZotero: document.querySelector("#saveFavoritesZoteroButton"),
  importZotero: document.querySelector("#importZoteroButton"),
  importZoteroPdf: document.querySelector("#importZoteroPdfButton"),
  syncFavoritesZotero: document.querySelector("#syncFavoritesZoteroButton"),
  manageZoteroBindings: document.querySelector("#manageZoteroBindingsButton"),
  showZoteroAudit: document.querySelector("#showZoteroAuditButton"),
  showZoteroBridgeHelp: document.querySelector("#showZoteroBridgeHelpButton"),
  downloadZoteroBridge: document.querySelector("#downloadZoteroBridgeLink"),
  zoteroStatusNote: document.querySelector("#zoteroStatusNote"),
  zoteroLinkSummary: document.querySelector("#zoteroLinkSummary"),
  zoteroBridgeNote: document.querySelector("#zoteroBridgeNote"),
  zoteroInstallNote: document.querySelector("#zoteroInstallNote"),
  zoteroAuditSummary: document.querySelector("#zoteroAuditSummary"),
  exportFavoritesMarkdown: document.querySelector("#exportFavoritesMarkdownButton"),
  exportFavoritesBilingual: document.querySelector("#exportFavoritesBilingualButton"),
  batchTranslate: document.querySelector("#batchTranslateButton"),
  refreshFavorites: document.querySelector("#refreshFavoritesButton"),
  enrichAbstracts: document.querySelector("#enrichAbstractsButton"),
  importAlert: document.querySelector("#importAlertButton"),
  importSubscriptionAlert: document.querySelector("#importSubscriptionAlertButton"),
  addSubscriptionSource: document.querySelector("#addSubscriptionSourceButton"),
  subscriptionStatusNote: document.querySelector("#subscriptionStatusNote"),
  subscriptionSourceList: document.querySelector("#subscriptionSourceList"),
  subscriptionImportHistory: document.querySelector("#subscriptionImportHistory"),
  subscriptionFreshnessNote: document.querySelector("#subscriptionFreshnessNote"),
  alertInboxStatusNote: document.querySelector("#alertInboxStatusNote"),
  alertInboxList: document.querySelector("#alertInboxList"),
  alertInboxFilter: document.querySelector("#alertInboxFilter"),
  adoptAlertInbox: document.querySelector("#adoptAlertInboxButton"),
  refreshAlertInbox: document.querySelector("#refreshAlertInboxButton"),
  researchRadarStatus: document.querySelector("#researchRadarStatus"),
  refreshResearchRadar: document.querySelector("#refreshResearchRadarButton"),
  smartResearchBrief: document.querySelector("#smartResearchBriefButton"),
  researchRadarStats: document.querySelector("#researchRadarStats"),
  researchRadarBrief: document.querySelector("#researchRadarBrief"),
  researchRadarActions: document.querySelector("#researchRadarActions"),
  researchRadarDigest: document.querySelector("#researchRadarDigest"),
  libraryRefreshNote: document.querySelector("#libraryRefreshNote"),
  clearHistory: document.querySelector("#clearHistoryButton"),
  modelStatusBadge: document.querySelector("#modelStatusBadge"),
  modelProviders: document.querySelector("#modelProviders"),
  modelApiType: document.querySelector("#modelApiTypeSelect"),
  modelBaseUrl: document.querySelector("#modelBaseUrlInput"),
  modelEndpoint: document.querySelector("#modelEndpointInput"),
  modelName: document.querySelector("#modelNameInput"),
  modelApiKey: document.querySelector("#modelApiKeyInput"),
  modelKeyHint: document.querySelector("#modelKeyHint"),
  modelFinalUrl: document.querySelector("#modelFinalUrl"),
  privatePdfMode: document.querySelector("#privatePdfModeSelect"),
  selfHostedModel: document.querySelector("#selfHostedModelInput"),
  modelPrivacyNote: document.querySelector("#modelPrivacyNote"),
  testModel: document.querySelector("#testModelButton"),
  saveModel: document.querySelector("#saveModelButton"),
  modelTestNote: document.querySelector("#modelTestNote"),
  diagnosticsStatusNote: document.querySelector("#diagnosticsStatusNote"),
  refreshDiagnostics: document.querySelector("#refreshDiagnosticsButton"),
  copyDiagnostics: document.querySelector("#copyDiagnosticsButton"),
  showTaskCenter: document.querySelector("#showTaskCenterButton"),
  diagnosticsSummary: document.querySelector("#diagnosticsSummary"),
  diagnosticsModel: document.querySelector("#diagnosticsModel"),
  diagnosticsFulltext: document.querySelector("#diagnosticsFulltext"),
  diagnosticsZotero: document.querySelector("#diagnosticsZotero"),
  diagnosticsAcceptance: document.querySelector("#diagnosticsAcceptance"),
  diagnosticsPolicy: document.querySelector("#diagnosticsPolicy"),
  exportBackup: document.querySelector("#exportBackupButton"),
  importBackup: document.querySelector("#importBackupInput"),
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

function createMetaElement(text, className = "") {
  const chip = createMetaChip(text);
  if (className) {
    chip.className = className;
  }
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

function zhTranslation(paper) {
  const translations = paper && paper.translations && typeof paper.translations === "object"
    ? paper.translations
    : {};
  return translations.zh && typeof translations.zh === "object" ? translations.zh : null;
}

function looksTruncatedText(value) {
  return /(?:\.{3,}|…)\s*$/.test(String(value || "").trim());
}

function preferredAbstractText(current, candidate) {
  const currentText = String(current || "").trim();
  const candidateText = String(candidate || "").trim();
  if (!currentText) {
    return candidateText;
  }
  if (!candidateText) {
    return currentText;
  }
  const currentTruncated = looksTruncatedText(currentText);
  const candidateTruncated = looksTruncatedText(candidateText);
  if (currentTruncated && !candidateTruncated) {
    return candidateText;
  }
  if (candidateTruncated && !currentTruncated) {
    return currentText;
  }
  if (candidateText.length > currentText.length + 80) {
    return candidateText;
  }
  return currentText;
}

function createTranslationBlock(translation, compact = false, sourceComplete = true) {
  const wrap = document.createElement("div");
  const translationIncomplete = !sourceComplete || looksTruncatedText(translation.text);
  wrap.className = [
    compact ? "library-translation" : "translated-abstract",
    translation.stale ? "is-stale" : "",
    translationIncomplete ? "is-incomplete" : "",
  ].filter(Boolean).join(" ");

  const label = document.createElement("span");
  label.className = "translation-label";
  label.textContent = translation.stale
    ? "中文摘要可能已过期"
    : translationIncomplete
      ? "中文摘要可能不完整"
      : "中文摘要";

  const text = document.createElement("p");
  text.className = "translation-text";
  text.textContent = translation.text || "";

  wrap.append(label, text);
  return wrap;
}

function abstractDisplayForPaper(paper) {
  const full = String(paper.fullAbstract || "").trim();
  if (full) {
    const completeness = abstractCompletenessForPaper(paper, full);
    return { text: full, complete: completeness === "complete" && !looksTruncatedText(full), completeness };
  }
  const text = String(paper.abstract || "").trim() || "No abstract available.";
  return {
    text,
    complete: false,
    completeness: abstractCompletenessForPaper(paper, text),
  };
}

function abstractCompletenessForPaper(paper, text = "") {
  const value = String(paper && paper.abstractCompleteness || "").trim();
  if (["complete", "partial", "missing", "unknown", "needs_access"].includes(value)) {
    return value;
  }
  const sourceText = String(text || (paper && (paper.fullAbstract || paper.abstract)) || "").trim();
  if (!sourceText || sourceText === "暂无摘要。") {
    return "missing";
  }
  return looksTruncatedText(sourceText) ? "partial" : "complete";
}

function abstractSourceLabel(paper) {
  if (paper && paper.abstractSourceLabel) {
    return paper.abstractSourceLabel;
  }
  if (paper && paper.abstractSource === "zotero") {
    return "Zotero";
  }
  return (paper && (paper.sourceLabel || sourceLabels[paper.source])) || "来源元数据";
}

function abstractStatusText(paper, display = abstractDisplayForPaper(paper)) {
  const source = abstractSourceLabel(paper);
  if (display.completeness === "needs_access") {
    return `需权限 · ${source}`;
  }
  if (display.complete) {
    return `完整摘要 · ${source}`;
  }
  if (display.completeness === "missing") {
    return `暂无完整摘要 · ${source}`;
  }
  return `摘要可能不完整 · ${source}`;
}

function abstractStatusKind(paper, display = abstractDisplayForPaper(paper)) {
  if (display.complete) {
    return "complete";
  }
  if (display.completeness === "needs_access") {
    return "access";
  }
  if (display.completeness === "missing") {
    return "missing";
  }
  return "partial";
}

function createAbstractStatusBadge(paper) {
  const display = abstractDisplayForPaper(paper);
  const badge = document.createElement("span");
  badge.className = `library-abstract-badge is-${abstractStatusKind(paper, display)}`;
  badge.textContent = `${paper && paper.abstractLocked ? "已锁定 · " : ""}${abstractStatusText(paper, display)}`;
  const fetchedAt = paper && paper.abstractFetchedAt ? ` · ${formatDateTime(paper.abstractFetchedAt)}` : "";
  badge.title = `摘要来源：${abstractSourceLabel(paper)}${fetchedAt}`;
  return badge;
}

function abstractDiagnosticStatusText(status) {
  const labels = {
    selected: "已采用",
    available: "可用",
    current: "当前",
    empty: "无摘要",
    failed: "失败",
    skipped: "跳过",
  };
  return labels[status] || "未知";
}

function abstractDiagnosticStatusKind(status) {
  if (status === "selected" || status === "available") {
    return "ok";
  }
  if (status === "failed") {
    return "failed";
  }
  if (status === "skipped") {
    return "skipped";
  }
  return "empty";
}

function createAbstractDiagnosticsPanel(paper) {
  const diagnostics = Array.isArray(paper.abstractDiagnostics) ? paper.abstractDiagnostics : [];
  const conflict = paper.abstractConflict && typeof paper.abstractConflict === "object" ? paper.abstractConflict : {};
  const candidates = Array.isArray(paper.abstractCandidates) ? paper.abstractCandidates : [];
  if (!diagnostics.length && !conflict.hasConflict && !paper.abstractLocked && !candidates.length) {
    return null;
  }

  const panel = document.createElement("details");
  panel.className = "abstract-diagnostics";

  const summary = document.createElement("summary");
  summary.className = "abstract-diagnostics-toggle";
  const selected = diagnostics.find((item) => item && item.selected);
  const availableCount = diagnostics.filter((item) => item && ["selected", "available", "current"].includes(item.status)).length;
  summary.textContent = selected
    ? `${paper.abstractLocked ? "已锁定 · " : ""}摘要来源诊断 · 已采用 ${selected.sourceLabel || abstractSourceLabel(paper)}`
    : `${paper.abstractLocked ? "已锁定 · " : ""}摘要来源诊断 · ${availableCount || candidates.length} 个来源可用`;
  panel.append(summary);

  if (paper.abstractLocked) {
    const locked = document.createElement("p");
    locked.className = "abstract-lock-note";
    locked.textContent = paper.abstractConfirmedAt
      ? `用户已确认并锁定摘要来源，自动补全不会覆盖。确认时间：${formatDateTime(paper.abstractConfirmedAt)}。`
      : "用户已锁定当前摘要，自动补全不会覆盖。";
    panel.append(locked);
  }

  if (conflict.hasConflict) {
    const warning = document.createElement("p");
    warning.className = "abstract-conflict-note";
    warning.textContent = conflict.message || "多个来源返回了不完全相同的完整摘要，请按需核对。";
    panel.append(warning);
  }

  const list = document.createElement("div");
  list.className = "abstract-diagnostics-list";
  diagnostics.forEach((item) => {
    if (!item || typeof item !== "object") {
      return;
    }
    const row = document.createElement("div");
    row.className = `abstract-diagnostic-row is-${abstractDiagnosticStatusKind(item.status)}`;

    const source = document.createElement("strong");
    source.textContent = item.sourceLabel || item.source || "来源";

    const status = document.createElement("span");
    status.textContent = abstractDiagnosticStatusText(item.status);

    const detail = document.createElement("small");
    const bits = [];
    if (item.completeness && item.completeness !== "unknown") {
      bits.push(item.completeness === "complete" ? "完整" : item.completeness === "partial" ? "可能截断" : "无摘要");
    }
    if (Number(item.textLength) > 0) {
      bits.push(`${Number(item.textLength)} 字符`);
    }
    if (item.message) {
      bits.push(item.message);
    }
    detail.textContent = bits.join(" · ") || "暂无更多信息";

    row.append(source, status, detail);
    list.append(row);
  });
  panel.append(list);

  const actions = document.createElement("div");
  actions.className = "abstract-diagnostics-actions";
  const review = document.createElement("button");
  review.className = "library-item-action";
  review.type = "button";
  review.textContent = "查看候选";
  review.addEventListener("click", () => showAbstractCandidatesDialog(paper));
  actions.append(review);
  panel.append(actions);
  return panel;
}

function endpointForApiType(apiType) {
  return (state.modelApiTypes && state.modelApiTypes[apiType]) || "/v1/chat/completions";
}

function joinModelUrl(baseUrl, endpoint) {
  const base = String(baseUrl || "").trim().replace(/\/+$/, "");
  const path = String(endpoint || "").trim();
  if (!base) {
    return "未配置";
  }
  if (!path) {
    return base;
  }
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

function modelEndpointLooksLocal(baseUrl) {
  const raw = String(baseUrl || "").trim();
  if (!raw) {
    return false;
  }
  try {
    const parsed = new URL(raw);
    const host = parsed.hostname.toLowerCase();
    return host === "localhost" || host === "::1" || host.startsWith("127.") || host.endsWith(".local");
  } catch (_error) {
    return false;
  }
}

function currentModelForm() {
  return {
    provider: state.selectedProvider || "custom",
    apiType: elements.modelApiType.value,
    baseUrl: elements.modelBaseUrl.value.trim(),
    endpoint: elements.modelEndpoint.value.trim(),
    model: elements.modelName.value.trim(),
    apiKey: elements.modelApiKey.value.trim() || undefined,
    privatePdfMode: elements.privatePdfMode ? elements.privatePdfMode.value : "confirm",
    selfHostedModel: Boolean(elements.selfHostedModel && elements.selfHostedModel.checked),
  };
}

function updateModelPreview() {
  elements.modelFinalUrl.textContent = joinModelUrl(elements.modelBaseUrl.value, elements.modelEndpoint.value);
  if (!elements.modelPrivacyNote) {
    return;
  }
  const strictMode = elements.privatePdfMode && elements.privatePdfMode.value === "local_only";
  const trustedLocal = modelEndpointLooksLocal(elements.modelBaseUrl.value)
    || Boolean(elements.selfHostedModel && elements.selfHostedModel.checked);
  if (strictMode && trustedLocal) {
    elements.modelPrivacyNote.textContent = "严格模式已开启：Zotero 私有 PDF 只会发送到当前本地/自托管模型端点。";
    elements.modelPrivacyNote.className = "model-privacy-note is-safe";
  } else if (strictMode) {
    elements.modelPrivacyNote.textContent = "严格模式已开启，但当前 Base URL 看起来不是本地地址；请使用 localhost/127.0.0.1/.local，或确认这是自托管模型。";
    elements.modelPrivacyNote.className = "model-privacy-note is-warning";
  } else {
    elements.modelPrivacyNote.textContent = "Zotero 本地资料库 PDF 翻译前会先确认；确认后文本会发送到当前模型提供方。";
    elements.modelPrivacyNote.className = "model-privacy-note";
  }
}

function setModelStatus(text, type = "") {
  elements.modelStatusBadge.textContent = text;
  elements.modelStatusBadge.className = `model-status-badge${type ? ` is-${type}` : ""}`;
}

function renderProviderCards() {
  elements.modelProviders.replaceChildren();
  state.modelProviders.forEach((provider) => {
    const button = document.createElement("button");
    button.className = "provider-card";
    button.classList.toggle("is-active", provider.id === state.selectedProvider);
    button.type = "button";
    button.dataset.provider = provider.id;

    const header = document.createElement("span");
    header.className = "provider-card-title";
    header.textContent = provider.name;

    const badges = document.createElement("span");
    badges.className = "provider-badges";
    (provider.badges || []).forEach((badgeText) => {
      const badge = document.createElement("small");
      badge.textContent = badgeText;
      badges.append(badge);
    });

    const description = document.createElement("span");
    description.className = "provider-description";
    description.textContent = provider.description || provider.domain || "";

    button.append(header, badges, description);
    button.addEventListener("click", () => applyProvider(provider));
    elements.modelProviders.append(button);
  });
}

function applyProvider(provider) {
  state.selectedProvider = provider.id || "custom";
  elements.modelApiType.value = provider.apiType || "chat_completions";
  elements.modelBaseUrl.value = provider.baseUrl || "";
  elements.modelEndpoint.value = provider.endpoint || endpointForApiType(elements.modelApiType.value);
  elements.modelName.value = provider.defaultModel || "";
  elements.modelApiKey.value = "";
  renderProviderCards();
  updateModelPreview();
  setModelStatus("未测试");
}

function applyModelSettings(settings = {}) {
  state.modelSettings = settings;
  state.selectedProvider = settings.provider || "apixin_gpt";
  elements.modelApiType.value = settings.apiType || "responses";
  elements.modelBaseUrl.value = settings.baseUrl || "";
  elements.modelEndpoint.value = settings.endpoint || endpointForApiType(elements.modelApiType.value);
  elements.modelName.value = settings.model || "";
  elements.modelApiKey.value = "";
  elements.modelKeyHint.textContent = settings.hasApiKey ? `已保存 ${settings.apiKeyMasked || ""}` : "未保存";
  if (elements.privatePdfMode) {
    elements.privatePdfMode.value = settings.privatePdfMode || "confirm";
  }
  if (elements.selfHostedModel) {
    elements.selfHostedModel.checked = Boolean(settings.selfHostedModel);
  }
  renderProviderCards();
  updateModelPreview();
}

function updateModelConfig(data = {}) {
  state.modelProviders = Array.isArray(data.providers) ? data.providers : state.modelProviders;
  state.modelApiTypes = data.apiTypes || state.modelApiTypes || {};
  applyModelSettings(data.settings || {});
}

function normalizeAlertInbox(value = {}) {
  const items = Array.isArray(value.items) ? value.items : [];
  const counts = value.counts && typeof value.counts === "object" ? value.counts : {};
  return {
    items,
    counts,
    pendingCount: Number.isFinite(Number(value.pendingCount))
      ? Number(value.pendingCount)
      : items.filter((item) => item && item.status === "pending").length,
    adoptableCount: Number.isFinite(Number(value.adoptableCount))
      ? Number(value.adoptableCount)
      : items.filter((item) => item && item.canAdopt).length,
    lockedCount: Number.isFinite(Number(value.lockedCount))
      ? Number(value.lockedCount)
      : items.filter((item) => item && item.status === "locked").length,
    conflictCount: Number.isFinite(Number(value.conflictCount))
      ? Number(value.conflictCount)
      : items.filter((item) => item && item.hasConflict).length,
    partialCount: Number.isFinite(Number(value.partialCount))
      ? Number(value.partialCount)
      : items.filter((item) => item && item.status === "partial").length,
    missingCount: Number.isFinite(Number(value.missingCount))
      ? Number(value.missingCount)
      : items.filter((item) => item && item.status === "missing").length,
    adoptedCount: Number.isFinite(Number(value.adoptedCount))
      ? Number(value.adoptedCount)
      : items.filter((item) => item && item.status === "adopted").length,
  };
}

function normalizeLibrary(library = {}) {
  const favorites = Array.isArray(library.favorites) ? library.favorites : [];
  const ignored = Array.isArray(library.ignored) ? library.ignored : [];
  const subscription = library.subscription && typeof library.subscription === "object" ? library.subscription : {};
  const subscriptionSources = Array.isArray(subscription.sources)
    ? subscription.sources
    : (Array.isArray(library.subscriptionSources) ? library.subscriptionSources : []);
  const alertImportHistory = Array.isArray(subscription.alertImportHistory)
    ? subscription.alertImportHistory
    : (Array.isArray(library.alertImportHistory) ? library.alertImportHistory : []);
  const alertInbox = normalizeAlertInbox(library.alertInbox || subscription.alertInbox || {});
  [...favorites, ...ignored].forEach((paper) => {
    if (paper && paper.paperKey && paper.fulltextTask) {
      state.fulltextTasks[paper.paperKey] = paper.fulltextTask;
    }
  });
  return {
    favorites,
    ignored,
    history: Array.isArray(library.history) ? library.history : [],
    zoteroAudit: Array.isArray(library.zoteroAudit) ? library.zoteroAudit : [],
    zoteroLastSync: library.zoteroLastSync && typeof library.zoteroLastSync === "object" ? library.zoteroLastSync : {},
    favoriteKeys: Array.isArray(library.favoriteKeys) ? library.favoriteKeys : [],
    ignoredKeys: Array.isArray(library.ignoredKeys) ? library.ignoredKeys : [],
    downloadKeys: Array.isArray(library.downloadKeys) ? library.downloadKeys : [],
    subscriptionSources,
    alertImportHistory,
    alertInbox,
    subscription: {
      sources: subscriptionSources,
      alertImportHistory,
      alertInbox,
      enabledCount: Number.isFinite(Number(subscription.enabledCount))
        ? Number(subscription.enabledCount)
        : subscriptionSources.filter((source) => source && source.enabled).length,
      policy: subscription.policy || "",
      freshnessNote: subscription.freshnessNote || "",
      lastImport: subscription.lastImport && typeof subscription.lastImport === "object" ? subscription.lastImport : {},
    },
    paperKeys: Array.isArray(library.paperKeys) ? library.paperKeys : [],
  };
}

function updateSubscriptionStatus(subscription = {}) {
  const sources = Array.isArray(subscription.sources) ? subscription.sources : [];
  const alertImportHistory = Array.isArray(subscription.alertImportHistory) ? subscription.alertImportHistory : [];
  const alertInbox = normalizeAlertInbox(subscription.alertInbox || state.library.alertInbox || {});
  state.subscription = {
    sources,
    alertImportHistory,
    alertInbox,
    enabledCount: Number.isFinite(Number(subscription.enabledCount))
      ? Number(subscription.enabledCount)
      : sources.filter((source) => source && source.enabled).length,
    policy: subscription.policy || state.subscription.policy || "",
    freshnessNote: subscription.freshnessNote || state.subscription.freshnessNote || "",
    lastImport: subscription.lastImport && typeof subscription.lastImport === "object" ? subscription.lastImport : {},
  };
}

function diagnosticStatusLabel(status) {
  const labels = {
    ready: "正常",
    running: "运行中",
    queued: "排队中",
    done: "完成",
    attention: "需处理",
    incomplete: "未完整",
    partial: "部分就绪",
    empty: "暂无",
    failed: "失败",
    blocked: "受阻",
    ok: "通过",
    missing: "缺失",
  };
  return labels[status] || status || "未知";
}

function diagnosticStatusClass(status) {
  if (["ready", "ok", "running", "queued", "done"].includes(status)) {
    return "is-ok";
  }
  if (["attention", "failed", "blocked"].includes(status)) {
    return "is-warning";
  }
  if (["incomplete", "missing"].includes(status)) {
    return "is-error";
  }
  return "is-muted";
}

function diagnosticNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function appendDiagnosticMetric(parent, label, value) {
  const metric = document.createElement("span");
  metric.className = "diagnostics-metric";
  const strong = document.createElement("strong");
  strong.textContent = String(value);
  const small = document.createElement("small");
  small.textContent = label;
  metric.append(strong, small);
  parent.append(metric);
}

function diagnosticJsonSummary(value) {
  if (!value || typeof value !== "object" || !Object.keys(value).length) {
    return "";
  }
  return JSON.stringify(value);
}

function diagnosticButton(label, handler, disabled = false) {
  const button = document.createElement("button");
  button.className = "library-item-action";
  button.type = "button";
  button.textContent = label;
  button.disabled = disabled;
  button.addEventListener("click", handler);
  return button;
}

function setDiagnosticButtonBusy(button, text) {
  if (!button) {
    return () => {};
  }
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = text;
  return () => {
    button.disabled = false;
    button.textContent = originalText;
  };
}

function diagnosticsSafeReportText(diagnostics = state.diagnostics) {
  const report = diagnostics && diagnostics.safeReport && typeof diagnostics.safeReport === "object"
    ? diagnostics.safeReport
    : {};
  if (typeof report.text === "string" && report.text.trim()) {
    return report.text.trim();
  }
  const model = diagnostics && diagnostics.model ? diagnostics.model : {};
  const settings = model.settings || {};
  const fulltext = diagnostics && diagnostics.fulltext ? diagnostics.fulltext : {};
  const fulltextCounts = fulltext.counts || {};
  const zotero = diagnostics && diagnostics.zotero ? diagnostics.zotero : {};
  const zoteroCounts = zotero.counts || {};
  return [
    "PaperHunter 安全诊断摘要",
    `生成时间：${(diagnostics && diagnostics.generatedAt) || ""}`,
    `总体状态：${(diagnostics && diagnostics.status) || "unknown"}`,
    "",
    "翻译接口",
    `- apiType：${settings.apiType || ""}`,
    `- model：${settings.model || ""}`,
    `- finalUrl：${settings.finalUrl || ""}`,
    `- API Key：${settings.hasApiKey ? "已保存" : "未保存"}${settings.apiKeyMasked ? `（${settings.apiKeyMasked}）` : ""}`,
    "",
    "全文任务",
    `- done：${diagnosticNumber(fulltextCounts.done)}，failed：${diagnosticNumber(fulltextCounts.failed)}，resumable：${diagnosticNumber(fulltextCounts.resumable)}`,
    "",
    "Zotero",
    `- 可回写：${diagnosticNumber(zoteroCounts.syncReady)}，需确认：${diagnosticNumber(zoteroCounts.needsReview)}`,
  ].join("\n");
}

async function copyDiagnosticsSummary() {
  const originalText = elements.copyDiagnostics ? elements.copyDiagnostics.textContent : "";
  if (elements.copyDiagnostics) {
    elements.copyDiagnostics.disabled = true;
    elements.copyDiagnostics.textContent = "复制中";
  }
  try {
    const diagnostics = state.diagnostics || await refreshDiagnostics({ silent: true });
    if (!diagnostics) {
      throw new Error("诊断未生成，请先刷新后再复制。");
    }
    await copyText(diagnosticsSafeReportText(diagnostics));
    setMessage("已复制安全诊断摘要；API Key 和 Bridge token 只包含掩码，不含明文。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (elements.copyDiagnostics) {
      elements.copyDiagnostics.disabled = false;
      elements.copyDiagnostics.textContent = originalText;
    }
  }
}

function renderDiagnosticsCard(target, title, status, message, metrics = [], details = []) {
  if (!target) {
    return;
  }
  target.replaceChildren();
  const header = document.createElement("div");
  header.className = "diagnostics-card-header";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const badge = document.createElement("span");
  badge.className = `diagnostics-badge ${diagnosticStatusClass(status)}`;
  badge.textContent = diagnosticStatusLabel(status);
  header.append(heading, badge);

  const text = document.createElement("p");
  text.textContent = message || "暂无诊断信息。";

  const metricRow = document.createElement("div");
  metricRow.className = "diagnostics-metrics";
  metrics.forEach((item) => appendDiagnosticMetric(metricRow, item.label, item.value));

  target.append(header, text);
  if (metrics.length) {
    target.append(metricRow);
  }
  details.filter(Boolean).forEach((detail) => {
    if (detail && typeof detail === "object" && typeof detail.nodeType === "number") {
      target.append(detail);
      return;
    }
    const small = document.createElement("small");
    small.textContent = detail;
    target.append(small);
  });
}

function diagnosticTaskPaper(task) {
  const paper = libraryPaperForKey(task && task.paperKey);
  return paper || null;
}

async function resumeDiagnosticFulltextTask(task, button) {
  const paper = diagnosticTaskPaper(task);
  if (!paper) {
    setMessage("没有在本地收藏/忽略列表中找到这篇论文，无法从诊断面板续跑全文翻译。", "error");
    return;
  }
  const restore = setDiagnosticButtonBusy(button, "续跑中");
  try {
    rememberFulltextTask(task);
    await translateFulltextPaper(paper);
    await refreshDiagnostics({ silent: true });
  } finally {
    restore();
  }
}

async function openDiagnosticFulltextTask(task, button) {
  const paper = diagnosticTaskPaper(task) || { paperKey: task.paperKey || "" };
  await openFulltextFolder(paper, task, button);
}

function renderDiagnosticFulltextTasks(tasks, options = {}) {
  const limit = Number.isFinite(Number(options.limit)) ? Number(options.limit) : 4;
  const list = document.createElement("div");
  list.className = "diagnostics-detail-list";
  if (!Array.isArray(tasks) || !tasks.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = "暂无最近全文任务。";
    list.append(empty);
    return list;
  }

  tasks.slice(0, limit).forEach((task) => {
    const item = document.createElement("article");
    item.className = "diagnostics-detail-item";

    const header = document.createElement("div");
    header.className = "diagnostics-detail-header";
    const title = document.createElement("strong");
    title.textContent = task.title || task.paperKey || "全文任务";
    title.title = title.textContent;
    const badge = document.createElement("span");
    badge.className = `diagnostics-badge ${diagnosticStatusClass(task.status)}`;
    badge.textContent = diagnosticStatusLabel(task.status);
    header.append(title, badge);

    const total = diagnosticNumber(task.totalChunks);
    const done = diagnosticNumber(task.completedChunks);
    const failed = diagnosticNumber(task.failedChunks);
    const meta = document.createElement("p");
    meta.textContent = [
      `${done}/${total} 片段`,
      failed ? `失败 ${failed}` : "",
      task.updatedAt ? `更新 ${formatDateTime(task.updatedAt)}` : "",
      task.file || "",
    ].filter(Boolean).join(" · ");

    const note = document.createElement("small");
    note.textContent = task.error || (task.canResume
      ? "可从最近失败或中断的片段继续。"
      : task.status === "done" ? "译文已生成，可打开所在文件夹。" : "任务仍在队列或运行中。");

    const actions = document.createElement("div");
    actions.className = "diagnostics-card-actions";
    const paper = diagnosticTaskPaper(task);
    if (task.canResume) {
      const resume = diagnosticButton("继续全文翻译", (event) => resumeDiagnosticFulltextTask(task, event.currentTarget), !paper);
      resume.title = paper ? "从未完成片段继续全文翻译" : "本地库中没有找到对应论文";
      actions.append(resume);
    }
    if (task.status === "done" && task.file) {
      actions.append(diagnosticButton("打开译文位置", (event) => openDiagnosticFulltextTask(task, event.currentTarget)));
    }
    if (!task.canResume && task.status !== "done") {
      actions.append(diagnosticButton(task.status === "running" || task.status === "queued" ? "任务运行中" : "等待处理", () => {}, true));
    }

    item.append(header, meta, note);
    if (actions.childElementCount) {
      item.append(actions);
    }
    list.append(item);
  });
  return list;
}

async function showDiagnosticZoteroPreview(item, button) {
  const paper = libraryPaperForKey(item && item.paperKey);
  if (!paper) {
    setMessage("没有在本地收藏/忽略列表中找到这篇论文，无法生成单篇 Zotero dry-run。", "error");
    return;
  }
  const restore = setDiagnosticButtonBusy(button, "预览中");
  try {
    const preview = await requestJson("/api/zotero/sync-preview", {
      paperKey: item.paperKey,
      paper,
      includeFulltext: true,
      persistReview: false,
    }, 30000);
    await showZoteroSyncPreviewDialog({
      checked: 1,
      ready: preview.ready ? 1 : 0,
      blocked: preview.ready ? 0 : 1,
      attachments: preview.attachments || 0,
      readOnly: true,
      confirmable: false,
      items: [{
        paperKey: preview.paperKey || item.paperKey,
        title: preview.title || item.title || paper.title || "Untitled",
        ready: Boolean(preview.ready),
        status: preview.status || (preview.ready ? "ready" : item.status),
        itemKey: preview.itemKey || item.itemKey || "",
        tags: preview.tags || [],
        attachments: preview.attachments || 0,
        message: preview.message || "",
        candidates: preview.candidates || [],
      }],
    }, { confirmable: false });
    setMessage("已打开单篇 Zotero 只读 dry-run。诊断没有写入 Zotero。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    restore();
  }
}

function openDiagnosticZoteroBinding(item) {
  const paper = libraryPaperForKey(item && item.paperKey);
  if (!paper) {
    setMessage("没有在本地库中找到这篇论文，无法确认 Zotero 绑定。", "error");
    return;
  }
  showZoteroBindingDialog({
    ...paper,
    zoteroLink: {
      ...(paper.zoteroLink || {}),
      status: item.status || (paper.zoteroLink || {}).status || "ambiguous",
      itemKey: item.itemKey || (paper.zoteroLink || {}).itemKey || "",
    },
  });
}

function renderDiagnosticZoteroItems(items) {
  const list = document.createElement("div");
  list.className = "diagnostics-detail-list";
  if (!Array.isArray(items) || !items.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = "暂无 Zotero dry-run 条目。";
    list.append(empty);
    return list;
  }

  items.slice(0, 4).forEach((item) => {
    const plan = item.syncPlan && typeof item.syncPlan === "object" ? item.syncPlan : {};
    const row = document.createElement("article");
    row.className = "diagnostics-detail-item";

    const header = document.createElement("div");
    header.className = "diagnostics-detail-header";
    const title = document.createElement("strong");
    title.textContent = item.title || item.paperKey || "Zotero 条目";
    title.title = title.textContent;
    const badge = document.createElement("span");
    badge.className = `diagnostics-badge ${diagnosticStatusClass(item.needsReview ? "attention" : item.linked ? "ready" : "empty")}`;
    badge.textContent = zoteroLinkStatusLabel(item.status);
    header.append(title, badge);

    const meta = document.createElement("p");
    meta.textContent = [
      item.itemKey ? `itemKey ${item.itemKey}` : "暂无 canonical itemKey",
      item.hasAbstractTranslation ? "摘要译文" : "无摘要译文",
      `${diagnosticNumber(item.fulltextTranslations)} 个全文译文`,
      plan.ready ? `${diagnosticNumber(plan.tagCount)} 个 paperhunter:* 标签` : "",
      plan.ready ? `${diagnosticNumber(plan.attachments)} 个译文附件` : "",
    ].filter(Boolean).join(" · ");

    const note = document.createElement("small");
    note.textContent = plan.message || (item.needsReview
      ? "需要确认 canonical itemKey 后才能回写。"
      : "诊断只预览 PaperHunter 管理内容。");

    const actions = document.createElement("div");
    actions.className = "diagnostics-card-actions";
    const paper = libraryPaperForKey(item.paperKey);
    if (item.needsReview) {
      actions.append(diagnosticButton("确认绑定", () => openDiagnosticZoteroBinding(item), !paper));
    }
    if (item.linked && !item.needsReview) {
      const preview = diagnosticButton("只读 dry-run", (event) => showDiagnosticZoteroPreview(item, event.currentTarget), !paper);
      preview.title = "只生成预览，不写 Zotero，不写 audit。";
      actions.append(preview);
    }

    row.append(header, meta, note);
    if (actions.childElementCount) {
      row.append(actions);
    }
    list.append(row);
  });
  return list;
}

function renderDiagnostics(data = state.diagnostics) {
  if (!elements.diagnosticsSummary) {
    return;
  }
  const diagnostics = data && typeof data === "object" ? data : null;
  state.diagnostics = diagnostics;
  if (!diagnostics) {
    elements.diagnosticsStatusNote.textContent = "等待诊断刷新";
    elements.diagnosticsSummary.replaceChildren(Object.assign(document.createElement("span"), {
      className: "history-empty",
      textContent: "暂无诊断结果",
    }));
    return;
  }

  const model = diagnostics.model || {};
  const fulltext = diagnostics.fulltext || {};
  const fulltextCounts = fulltext.counts || {};
  const zotero = diagnostics.zotero || {};
  const zoteroCounts = zotero.counts || {};
  const acceptance = diagnostics.acceptance || {};

  elements.diagnosticsStatusNote.textContent = `${diagnosticStatusLabel(diagnostics.status)} · ${diagnostics.generatedAt || ""}`;
  elements.diagnosticsSummary.replaceChildren();
  [
    ["模型", model.configured ? "已配置" : "缺配置"],
    ["全文", `${diagnosticNumber(fulltextCounts.done)} 完成`],
    ["Zotero", `${diagnosticNumber(zoteroCounts.syncReady)} 可回写`],
    ["验收", `${diagnosticNumber(acceptance.ok)}/${diagnosticNumber(acceptance.total)}`],
  ].forEach(([label, value]) => appendDiagnosticMetric(elements.diagnosticsSummary, label, value));

  const settings = model.settings || {};
  const fallback = model.fallback || {};
  const lastTest = model.lastTest || settings.lastTest || {};
  const lastTestUsage = diagnosticJsonSummary(lastTest.usage);
  renderDiagnosticsCard(
    elements.diagnosticsModel,
    "翻译接口",
    model.status,
    model.message,
    [
      { label: "协议", value: settings.apiType || "未设" },
      { label: "Key", value: settings.hasApiKey ? "已保存" : "未保存" },
    ],
    [
      settings.finalUrl ? `最终地址：${settings.finalUrl}` : "",
      fallback.available ? `空 Responses fallback：${fallback.apiType} · ${fallback.endpoint}` : "当前协议没有启用 fallback。",
      lastTest.status ? `最近测试：${lastTest.status === "success" ? "成功" : "失败"} · ${formatDateTime(lastTest.testedAt)}` : "还没有保存的测试记录。",
      lastTest.apiType ? `测试协议：${lastTest.apiType}${lastTest.fallbackApiType ? ` → ${lastTest.fallbackApiType}` : ""}` : "",
      lastTest.finalUrl ? `测试地址：${lastTest.finalUrl}` : "",
      lastTest.status === "success" ? `返回文本：${diagnosticNumber(lastTest.textLength)} 字符${lastTest.sample ? ` · ${lastTest.sample}` : ""}` : "",
      lastTestUsage ? `Usage：${lastTestUsage}` : "",
      lastTest.error ? `错误：${lastTest.error}` : "",
    ],
  );

  renderDiagnosticsCard(
    elements.diagnosticsFulltext,
    "全文任务",
    fulltext.status,
    fulltext.message,
    [
      { label: "完成", value: diagnosticNumber(fulltextCounts.done) },
      { label: "失败", value: diagnosticNumber(fulltextCounts.failed) },
      { label: "可续跑", value: diagnosticNumber(fulltextCounts.resumable) },
    ],
    [renderDiagnosticFulltextTasks(fulltext.recent)],
  );

  renderDiagnosticsCard(
    elements.diagnosticsZotero,
    "Zotero dry-run",
    zotero.status,
    zotero.message,
    [
      { label: "可回写", value: diagnosticNumber(zoteroCounts.syncReady) },
      { label: "需确认", value: diagnosticNumber(zoteroCounts.needsReview) },
      { label: "Markdown", value: diagnosticNumber(zoteroCounts.wouldAttachMarkdown) },
    ],
    [
      "只预览 PaperHunter 管理 note、paperhunter:* 标签和译文 Markdown 附件；不覆盖用户原始条目。",
      renderDiagnosticZoteroItems(zotero.items),
    ],
  );

  if (elements.diagnosticsAcceptance) {
    elements.diagnosticsAcceptance.replaceChildren();
    const checks = Array.isArray(acceptance.checks) ? acceptance.checks : [];
    if (!checks.length) {
      const empty = document.createElement("span");
      empty.className = "history-empty";
      empty.textContent = "暂无验收检查";
      elements.diagnosticsAcceptance.append(empty);
    } else {
      checks.forEach((check) => {
        const item = document.createElement("div");
        item.className = `diagnostics-check ${diagnosticStatusClass(check.status)}`;
        const label = document.createElement("strong");
        label.textContent = check.label || check.id || "检查项";
        const badge = document.createElement("span");
        badge.className = `diagnostics-badge ${diagnosticStatusClass(check.status)}`;
        badge.textContent = diagnosticStatusLabel(check.status);
        const detail = document.createElement("small");
        detail.textContent = check.detail || "";
        item.append(label, badge, detail);
        elements.diagnosticsAcceptance.append(item);
      });
    }
  }

  if (elements.diagnosticsPolicy) {
    const policy = diagnostics.policy || {};
    elements.diagnosticsPolicy.textContent = policy.readOnly
      ? "只读诊断：不触发模型调用，不写 Zotero，不清空 PA/ZO 数据。"
      : "诊断策略未知，请刷新后重试。";
  }
}

async function showTaskCenterDialog() {
  const originalText = elements.showTaskCenter ? elements.showTaskCenter.textContent : "";
  if (elements.showTaskCenter) {
    elements.showTaskCenter.disabled = true;
    elements.showTaskCenter.textContent = "读取中";
  }
  try {
    const diagnostics = await requestJson("/api/diagnostics", { limit: 40 }, 30000);
    renderDiagnostics(diagnostics);
    const fulltext = diagnostics.fulltext || {};
    const counts = fulltext.counts || {};
    const tasks = Array.isArray(fulltext.recent) ? fulltext.recent : [];
    const { dialog } = createZoteroDialogShell({
      title: "任务中心",
      intro: "集中查看全文翻译长任务、失败片段和可续跑状态。这里读取本地任务记录；继续全文翻译时才会调用模型。",
      label: "任务中心",
      className: "task-center-dialog",
    });

    const stats = document.createElement("div");
    stats.className = "zotero-sync-preview-stats task-center-stats";
    [
      ["全部", diagnosticNumber(counts.total)],
      ["运行/排队", diagnosticNumber(counts.running) + diagnosticNumber(counts.queued)],
      ["失败", diagnosticNumber(counts.failed)],
      ["可续跑", diagnosticNumber(counts.resumable)],
    ].forEach(([labelText, value]) => stats.append(createZoteroStat(labelText, value)));

    const policy = document.createElement("p");
    policy.className = "zotero-install-note";
    policy.textContent = "任务中心不会自动重跑失败任务；点击“继续全文翻译”时，会沿用该论文的私有 PDF 策略和当前翻译接口设置。";

    const list = renderDiagnosticFulltextTasks(tasks, { limit: 40 });
    const footer = document.createElement("div");
    footer.className = "zotero-binding-footer";
    const refresh = document.createElement("button");
    refresh.className = "secondary-action compact-action";
    refresh.type = "button";
    refresh.textContent = "刷新任务";
    refresh.addEventListener("click", async () => {
      closeZoteroManagementDialog();
      await showTaskCenterDialog();
    });
    const close = document.createElement("button");
    close.className = "secondary-action compact-action";
    close.type = "button";
    close.textContent = "关闭";
    close.addEventListener("click", closeZoteroManagementDialog);
    footer.append(refresh, close);
    dialog.append(stats, policy, list, footer);
    setMessage(`任务中心已打开：${diagnosticNumber(counts.total)} 个全文任务。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (elements.showTaskCenter) {
      elements.showTaskCenter.disabled = false;
      elements.showTaskCenter.textContent = originalText;
    }
  }
}

function subscriptionSourceLabel(source) {
  return String((source && (source.sourceLabel || source.name || source.id)) || "Alert 来源");
}

function subscriptionModeLabel(mode) {
  const labels = {
    "manual-alert": "手动 Alert",
    "official-api": "官方 API",
    "email-import": "邮件导入",
    "zotero-library": "Zotero 本地库",
    custom: "自定义",
  };
  return labels[mode] || mode || "手动 Alert";
}

function alertInboxStatusLabel(status) {
  const labels = {
    pending: "待审",
    adopted: "已采用",
    locked: "已锁定",
    ignored: "已忽略",
    skipped: "已跳过",
    partial: "不完整",
    missing: "无摘要",
    stale: "已失效",
  };
  return labels[status] || status || "待审";
}

function alertInboxCompletenessLabel(value) {
  const labels = {
    complete: "完整摘要",
    partial: "可能截断",
    missing: "无摘要",
    unknown: "完整性未知",
    needs_access: "需权限",
  };
  return labels[value] || value || "完整性未知";
}

function filterAlertInboxItems(items) {
  const filter = state.alertInboxFilter || "active";
  return items.filter((item) => {
    if (!item) {
      return false;
    }
    if (filter === "all") {
      return true;
    }
    if (filter === "active") {
      return !["adopted", "skipped", "ignored"].includes(item.status);
    }
    if (filter === "adoptable") {
      return Boolean(item.canAdopt);
    }
    if (filter === "conflict") {
      return Boolean(item.hasConflict);
    }
    return item.status === filter;
  });
}

function renderAlertInboxPanel() {
  if (!elements.alertInboxList) {
    return;
  }
  const inbox = state.subscription.alertInbox || normalizeAlertInbox();
  const items = Array.isArray(inbox.items) ? inbox.items : [];
  const filteredItems = filterAlertInboxItems(items);
  if (elements.alertInboxStatusNote) {
    const conflictText = inbox.conflictCount ? ` · 冲突 ${inbox.conflictCount}` : "";
    const partialText = inbox.partialCount ? ` · 不完整 ${inbox.partialCount}` : "";
    const adoptedText = inbox.adoptedCount ? ` · 已采用 ${inbox.adoptedCount}` : "";
    elements.alertInboxStatusNote.textContent = `待审 ${inbox.pendingCount || 0} · 可采用 ${inbox.adoptableCount || 0} · 锁定 ${inbox.lockedCount || 0}${partialText}${conflictText}${adoptedText}`;
  }
  if (elements.alertInboxFilter) {
    elements.alertInboxFilter.value = state.alertInboxFilter || "active";
  }
  if (elements.adoptAlertInbox) {
    elements.adoptAlertInbox.disabled = !filteredItems.some((item) => item && item.canAdopt);
  }

  elements.alertInboxList.replaceChildren();
  if (!items.length || !filteredItems.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = items.length ? "当前过滤条件下没有 Alert" : "暂无待审 Alert";
    elements.alertInboxList.append(empty);
    return;
  }

  filteredItems.slice(0, 12).forEach((item) => {
    const card = document.createElement("article");
    card.className = `alert-inbox-item is-${item.status || "pending"}`;

    const header = document.createElement("div");
    header.className = "alert-inbox-item-header";
    const title = document.createElement("strong");
    title.textContent = item.title || "未命名论文";
    const badge = document.createElement("span");
    badge.className = `zotero-status-pill is-${item.canAdopt ? "linked" : "plain"}`;
    badge.textContent = alertInboxStatusLabel(item.status);
    header.append(title, badge);

    const candidate = item.candidate && typeof item.candidate === "object" ? item.candidate : {};
    const meta = document.createElement("p");
    const conflictText = item.hasConflict ? " · 与当前完整摘要不同" : "";
    meta.textContent = `${item.sourceLabel || "Alert 来源"} · ${alertInboxCompletenessLabel(candidate.completeness)} · ${candidate.textLength || 0} 字符${conflictText}`;

    const preview = document.createElement("small");
    preview.textContent = candidate.preview || candidate.text || "没有可预览摘要。";

    const actions = document.createElement("div");
    actions.className = "alert-inbox-actions";
    const adopt = document.createElement("button");
    adopt.className = "library-item-action";
    adopt.type = "button";
    adopt.textContent = "采用并锁定";
    adopt.disabled = !item.canAdopt;
    adopt.addEventListener("click", () => adoptAlertInboxEvents([item.id], adopt));

    const openPaper = document.createElement("button");
    openPaper.className = "library-item-action";
    openPaper.type = "button";
    openPaper.textContent = "查看候选";
    openPaper.addEventListener("click", () => {
      const paper = libraryPaperForKey(item.paperKey);
      if (paper) {
        showAbstractCandidatesDialog(paper);
      }
    });
    actions.append(adopt, openPaper);
    card.append(header, meta, preview, actions);
    elements.alertInboxList.append(card);
  });
}

async function adoptAlertInboxEvents(eventIds = [], button = null) {
  const ids = Array.isArray(eventIds) ? eventIds.filter(Boolean) : [];
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "采用中";
  }
  if (elements.adoptAlertInbox && !button) {
    elements.adoptAlertInbox.disabled = true;
    elements.adoptAlertInbox.textContent = "采用中";
  }
  try {
    const data = await requestJson("/api/alert/inbox", {
      action: "batch-adopt",
      eventIds: ids,
      lock: true,
    }, 60000);
    updateLibrary(data.library || state.library);
    renderResults();
    const skipped = data.skipped && typeof data.skipped === "object"
      ? Object.entries(data.skipped).map(([reason, count]) => `${reason} ${count}`).join("，")
      : "";
    const suffix = skipped ? `，跳过 ${skipped}` : "";
    setMessage(`已采用并锁定 ${data.adopted || 0} 条 Alert 摘要${suffix}。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  } finally {
    if (elements.adoptAlertInbox && !button) {
      elements.adoptAlertInbox.textContent = "批量采用";
      elements.adoptAlertInbox.disabled = !(state.subscription.alertInbox || {}).adoptableCount;
    }
  }
}

async function refreshAlertInbox() {
  if (elements.refreshAlertInbox) {
    elements.refreshAlertInbox.disabled = true;
    elements.refreshAlertInbox.textContent = "刷新中";
  }
  try {
    const data = await requestJson("/api/alert/inbox", { action: "status" });
    updateLibrary(data.library || state.library);
    setMessage("Alert 收件箱已刷新。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (elements.refreshAlertInbox) {
      elements.refreshAlertInbox.disabled = false;
      elements.refreshAlertInbox.textContent = "刷新收件箱";
    }
  }
}

function renderSubscriptionPanel() {
  if (!elements.subscriptionSourceList) {
    return;
  }
  const sources = state.subscription.sources || [];
  const history = state.subscription.alertImportHistory || [];
  if (elements.subscriptionStatusNote) {
    const enabled = sources.filter((source) => source && source.enabled).length;
    const imported = sources.reduce((total, source) => total + Number(source.importCount || 0), 0);
    elements.subscriptionStatusNote.textContent = `${enabled}/${sources.length || 0} 个来源启用 · 已导入 ${imported} 篇 Alert`;
  }
  if (elements.subscriptionFreshnessNote) {
    elements.subscriptionFreshnessNote.textContent = state.subscription.freshnessNote
      || "订阅 Alert 可能比开放元数据更快；只导入你已可见或已授权的内容。";
  }

  elements.subscriptionSourceList.replaceChildren();
  if (!sources.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = "暂无来源";
    elements.subscriptionSourceList.append(empty);
  } else {
    sources.forEach((source) => {
      const card = document.createElement("div");
      card.className = `subscription-source${source.enabled ? "" : " is-disabled"}`;

      const header = document.createElement("div");
      header.className = "subscription-source-header";
      const title = document.createElement("strong");
      title.textContent = subscriptionSourceLabel(source);
      const badge = document.createElement("span");
      badge.className = `zotero-status-pill is-${source.enabled ? "linked" : "plain"}`;
      badge.textContent = source.enabled ? "已启用" : "已停用";
      header.append(title, badge);

      const meta = document.createElement("p");
      const lastImport = source.lastImportedAt ? ` · ${formatDateTime(source.lastImportedAt)}` : "";
      meta.textContent = `${subscriptionModeLabel(source.authorizationMode)} · ${source.importCount || 0} 篇${lastImport}`;

      const note = document.createElement("small");
      note.textContent = source.freshnessNote || source.policy || "只处理用户可见或已授权的来源内容。";

      const actions = document.createElement("div");
      actions.className = "subscription-source-actions";
      const importButton = document.createElement("button");
      importButton.className = "library-item-action";
      importButton.type = "button";
      importButton.textContent = "导入";
      importButton.disabled = !source.enabled;
      importButton.addEventListener("click", () => showAlertImportDialog(source));
      const toggleButton = document.createElement("button");
      toggleButton.className = "library-item-action";
      toggleButton.type = "button";
      toggleButton.textContent = source.enabled ? "停用" : "启用";
      toggleButton.addEventListener("click", () => toggleSubscriptionSource(source, toggleButton));
      actions.append(importButton, toggleButton);

      card.append(header, meta, note, actions);
      elements.subscriptionSourceList.append(card);
    });
  }

  if (!elements.subscriptionImportHistory) {
    return;
  }
  elements.subscriptionImportHistory.replaceChildren();
  if (!history.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = "暂无导入历史";
    elements.subscriptionImportHistory.append(empty);
  } else {
    history.slice(0, 6).forEach((item) => {
      const row = document.createElement("button");
      row.className = "history-item";
      row.type = "button";
      row.title = item.summary || "";
      const title = document.createElement("strong");
      title.textContent = item.sourceLabel || "Alert 来源";
      const meta = document.createElement("span");
      meta.textContent = `${item.count || 0} 篇 · 新增 ${item.imported || 0} · 更新 ${item.updated || 0} · ${formatDateTime(item.createdAt)}`;
      row.append(title, meta);
      elements.subscriptionImportHistory.append(row);
    });
  }
  renderAlertInboxPanel();
}

async function toggleSubscriptionSource(source, button) {
  if (!source || !source.id || (button && button.disabled)) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = source.enabled ? "停用中" : "启用中";
  }
  try {
    const data = await requestJson("/api/subscription/sources", {
      action: "toggle",
      source,
    });
    updateLibrary(data.library || state.library);
    setMessage(`${subscriptionSourceLabel(source)} 已${source.enabled ? "停用" : "启用"}。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function closeSubscriptionSourceDialog() {
  const existing = document.querySelector(".subscription-source-backdrop");
  if (existing) {
    existing.remove();
  }
}

async function saveCustomSubscriptionSource(sourceLabel, submit, cancel) {
  if (!sourceLabel || !sourceLabel.trim()) {
    setMessage("请先填写来源名称。", "error");
    return;
  }
  const originalText = submit ? submit.textContent : "";
  if (submit) {
    submit.disabled = true;
    submit.textContent = "添加中";
  }
  if (cancel) {
    cancel.disabled = true;
  }
  const trimmedLabel = sourceLabel.trim();
  try {
    const data = await requestJson("/api/subscription/sources", {
      action: "upsert",
      source: {
        id: trimmedLabel,
        name: trimmedLabel,
        provider: "custom",
        sourceLabel: trimmedLabel,
        sourceType: "custom",
        authorizationMode: "manual-alert",
        enabled: true,
        status: "ready",
        policy: "Uses user-visible alert text or authorized exports.",
        freshnessNote: "Use this for publisher, society, email, or institutional alerts.",
      },
    });
    updateLibrary(data.library || state.library);
    closeSubscriptionSourceDialog();
    setMessage(`已添加 ${trimmedLabel}。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
    if (submit) {
      submit.disabled = false;
      submit.textContent = originalText;
    }
    if (cancel) {
      cancel.disabled = false;
    }
  }
}

function addCustomSubscriptionSource() {
  closeSubscriptionSourceDialog();

  const backdrop = document.createElement("div");
  backdrop.className = "zotero-binding-backdrop subscription-source-backdrop";

  const dialog = document.createElement("section");
  dialog.className = "zotero-binding-dialog subscription-source-dialog";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", "添加订阅来源");

  const heading = document.createElement("div");
  heading.className = "zotero-binding-heading";
  const title = document.createElement("h3");
  title.textContent = "添加订阅来源";
  const intro = document.createElement("p");
  intro.textContent = "用于你已经可见或已授权的 publisher、society、邮件或机构 Alert。";
  heading.append(title, intro);

  const form = document.createElement("div");
  form.className = "alert-import-form";

  const nameLabel = document.createElement("label");
  nameLabel.className = "alert-import-field";
  const nameText = document.createElement("span");
  nameText.textContent = "来源名称";
  const nameInput = document.createElement("input");
  nameInput.className = "paper-editor-input";
  nameInput.type = "text";
  nameInput.value = "Institution Alert";
  nameInput.placeholder = "ScienceDirect / WoS Alert";
  nameInput.maxLength = 80;
  const hint = document.createElement("small");
  hint.className = "alert-import-hint";
  hint.textContent = "只会登记入口，不会自动抓取未授权网页。导入时仍由你粘贴或选择已可见的 Alert 内容。";
  nameLabel.append(nameText, nameInput, hint);
  form.append(nameLabel);

  const footer = document.createElement("div");
  footer.className = "zotero-binding-footer";
  const cancel = document.createElement("button");
  cancel.className = "secondary-action compact-action";
  cancel.type = "button";
  cancel.textContent = "取消";
  cancel.addEventListener("click", closeSubscriptionSourceDialog);

  const submit = document.createElement("button");
  submit.className = "primary-action compact-action";
  submit.type = "button";
  submit.textContent = "添加";
  submit.addEventListener("click", () => saveCustomSubscriptionSource(nameInput.value, submit, cancel));
  nameInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveCustomSubscriptionSource(nameInput.value, submit, cancel);
    }
  });
  footer.append(cancel, submit);

  dialog.append(heading, form, footer);
  backdrop.append(dialog);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) {
      closeSubscriptionSourceDialog();
    }
  });
  document.body.append(backdrop);
  nameInput.focus();
  nameInput.select();
}

function isFavorite(paper) {
  return state.library.favoriteKeys.includes(paper.paperKey);
}

function libraryPaperForKey(key) {
  if (!key) {
    return null;
  }
  return [...state.library.favorites, ...state.library.ignored]
    .find((paper) => paper && paper.paperKey === key) || null;
}

function mergeStoredPaperState(paper, stored) {
  if (!stored) {
    return { ...paper };
  }
  const merged = { ...paper };
    const preferredFullAbstract = preferredAbstractText(merged.fullAbstract, stored.fullAbstract);
  if (preferredFullAbstract) {
    const inheritedStoredAbstract = preferredFullAbstract === String(stored.fullAbstract || "").trim();
    merged.fullAbstract = preferredFullAbstract;
    if (inheritedStoredAbstract) {
      abstractMetadataFields.forEach((field) => {
        const value = stored[field];
        if (value !== undefined && value !== null && value !== "") {
          merged[field] = value;
        }
      });
    }
  }
  const hasMergedTranslations = merged.translations
    && typeof merged.translations === "object"
    && Object.keys(merged.translations).length > 0;
  if (!hasMergedTranslations && stored.translations) {
    merged.translations = stored.translations;
  }
  ["fulltextTranslations", "note", "tags", "readingStatus", "fulltextTask"].forEach((field) => {
    const value = stored[field];
    if (value !== undefined && value !== null && value !== "") {
      merged[field] = value;
    }
  });
  if (stored.isDownloaded !== undefined) {
    merged.isDownloaded = Boolean(stored.isDownloaded);
  }
  if (stored.downloadable !== undefined) {
    merged.downloadable = Boolean(stored.downloadable);
  }
  ["localPdfPath", "localPdfFilename", "access", "zotero", "zoteroLink", "zoteroSync", ...abstractMetadataFields].forEach((field) => {
    const value = stored[field];
    if (value !== undefined && value !== null && value !== "") {
      merged[field] = value;
    }
  });
  return merged;
}

function annotatePaper(paper) {
  const stored = libraryPaperForKey(paper.paperKey);
  const annotated = mergeStoredPaperState(paper, stored);
  annotated.isFavorite = isFavorite(annotated);
  annotated.isIgnored = state.library.ignoredKeys.includes(annotated.paperKey);
  if (state.library.downloadKeys.includes(annotated.paperKey)) {
    annotated.isDownloaded = true;
  }
  return annotated;
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

function zoteroLinked(paper) {
  if (zoteroBindingNeedsReview(paper)) {
    return false;
  }
  return Boolean(zoteroCanonicalItemKey(paper));
}

function zoteroLinkStatus(paper) {
  const link = paper && paper.zoteroLink && typeof paper.zoteroLink === "object" ? paper.zoteroLink : {};
  return String(link.status || (paper && paper.zotero && paper.zotero.itemKey ? "auto" : "unlinked"));
}

function zoteroCanonicalItemKey(paper) {
  const link = paper && paper.zoteroLink && typeof paper.zoteroLink === "object" ? paper.zoteroLink : {};
  return String(link.itemKey || (paper && paper.zotero && paper.zotero.itemKey) || "").trim();
}

function zoteroBindingNeedsReview(paper) {
  return ["ambiguous", "conflict", "missing"].includes(zoteroLinkStatus(paper));
}

function zoteroBindingCandidates(paper) {
  const link = paper && paper.zoteroLink && typeof paper.zoteroLink === "object" ? paper.zoteroLink : {};
  return Array.isArray(link.candidates) ? link.candidates : [];
}

function zoteroHealthCounts() {
  const favorites = state.library.favorites || [];
  return favorites.reduce((counts, paper) => {
    if (zoteroLinked(paper)) {
      counts.linked += 1;
    }
    if (paper && paper.zoteroSync && paper.zoteroSync.status === "synced") {
      counts.synced += 1;
    }
    const status = zoteroLinkStatus(paper);
    if (status === "ambiguous") {
      counts.ambiguous += 1;
    }
    if (status === "conflict") {
      counts.conflict += 1;
    }
    if (status === "missing") {
      counts.missing += 1;
    }
    if (zoteroBindingNeedsReview(paper)) {
      counts.review += 1;
    }
    return counts;
  }, { linked: 0, synced: 0, ambiguous: 0, conflict: 0, missing: 0, review: 0 });
}

function zoteroHealthSummaryText(favoriteCount, counts) {
  if (!favoriteCount) {
    return "收藏后可保存到 Zotero；PaperHunter 会自动回绑同篇条目。";
  }
  const parts = [
    `安全绑定 ${counts.linked}/${favoriteCount} 篇`,
    `已回写 ${counts.synced} 篇`,
  ];
  if (counts.review) {
    parts.push(`需确认 ${counts.review} 篇`);
  }
  if (counts.ambiguous) {
    parts.push(`重复候选 ${counts.ambiguous} 篇`);
  }
  if (counts.conflict) {
    parts.push(`绑定冲突 ${counts.conflict} 篇`);
  }
  return `${parts.join(" · ")}。不会自动合并 Zotero 条目，也不会修改原始 PDF、用户笔记、用户标签或 collections。`;
}

function zoteroAuditSummaryText() {
  const lastSync = state.library.zoteroLastSync || {};
  if (lastSync.itemKey) {
    const title = lastSync.title ? ` · ${lastSync.title}` : "";
    return `最近一次回写目标：itemKey ${lastSync.itemKey}${title}`;
  }
  const audit = Array.isArray(state.library.zoteroAudit) ? state.library.zoteroAudit : [];
  const latest = audit[0] || {};
  if (latest.action) {
    const itemKey = latest.itemKey ? ` · itemKey ${latest.itemKey}` : "";
    return `最近 Zotero 操作：${latest.action}${itemKey}${latest.status ? ` · ${latest.status}` : ""}`;
  }
  return "最近一次回写目标会在同步后显示。";
}

function formatDateTime(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "未知时间";
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function zoteroLinkStatusLabel(status) {
  const labels = {
    auto: "自动绑定",
    confirmed: "已确认绑定",
    ambiguous: "发现重复条目",
    conflict: "绑定冲突",
    missing: "目标缺失",
    unmatched: "未匹配",
    unlinked: "未绑定",
  };
  return labels[status] || status || "未绑定";
}

function zoteroSyncStatusLabel(status) {
  const labels = {
    synced: "已回写",
    failed: "回写失败",
    pending: "待回写",
  };
  return labels[status] || status || "未回写";
}

function zoteroBindingRows() {
  return (state.library.favorites || []).map((paper) => {
    const link = paper && paper.zoteroLink && typeof paper.zoteroLink === "object" ? paper.zoteroLink : {};
    const sync = paper && paper.zoteroSync && typeof paper.zoteroSync === "object" ? paper.zoteroSync : {};
    const status = zoteroLinkStatus(paper);
    const itemKey = zoteroCanonicalItemKey(paper);
    return {
      paper,
      paperKey: paper.paperKey || "",
      title: paper.title || "Untitled",
      meta: paperDisplayMeta(paper),
      status,
      statusLabel: zoteroLinkStatusLabel(status),
      itemKey,
      syncStatus: sync.status || "",
      syncLabel: zoteroSyncStatusLabel(sync.status),
      syncError: sync.error || "",
      message: link.message || "",
      candidates: zoteroBindingCandidates(paper),
      needsReview: zoteroBindingNeedsReview(paper),
      isLinked: zoteroLinked(paper),
    };
  });
}

function bridgeCapabilityLabels(capabilities = {}) {
  const labels = [];
  if (capabilities.canUpsertManagedNote) {
    labels.push("upsert PaperHunter note");
  }
  if (capabilities.canApplyPaperHunterTags) {
    labels.push("添加 paperhunter:* 标签");
  }
  if (capabilities.canLinkMarkdownAttachment) {
    labels.push("链接译文 Markdown 附件");
  }
  if (capabilities.preserveUserContent) {
    labels.push("保护用户原始内容");
  }
  return labels.length
    ? `Bridge 声明能力：${labels.join("、")}。`
    : "同步只会写入 PaperHunter note、paperhunter:* 标签和全文译文 Markdown 附件。";
}

function bridgeDownloadHref() {
  const base = state.zotero.bridgeDownloadUrl || "/api/zotero/bridge-xpi";
  const version = state.zotero.expectedBridgeVersion || state.zotero.bridgeVersion || "current";
  const separator = base.includes("?") ? "&" : "?";
  return `${base}${separator}version=${encodeURIComponent(version)}&t=${Date.now()}`;
}

function bridgePairingStatusText(pairing = {}) {
  if (pairing.verified) {
    return `已配对 ${pairing.tokenMasked || ""}`.trim();
  }
  if (pairing.configured) {
    const check = pairing.check && typeof pairing.check === "object" ? pairing.check : {};
    return check.message || `待验证 ${pairing.tokenMasked || ""}`.trim();
  }
  return "未配置";
}

function bridgeWizardSteps(bridgePackage = {}) {
  const downloaded = Boolean(bridgePackage.valid);
  const installed = Boolean(state.zotero.bridgeAvailable);
  const compatible = Boolean(state.zotero.bridgeCompatible);
  const paired = Boolean((state.zotero.bridgePairing || {}).verified);
  return [
    {
      label: "下载当前 XPI",
      status: downloaded ? "ready" : "blocked",
      detail: downloaded
        ? `${bridgePackage.filename || "paperhunter-zotero-bridge.xpi"} 可用，版本 ${bridgePackage.version || state.zotero.expectedBridgeVersion || ""}`
        : bridgePackage.message || "安装包不可用，需要先修复 XPI 构建。",
    },
    {
      label: "覆盖安装到 Zotero",
      status: installed ? "ready" : "pending",
      detail: installed
        ? `Zotero 已响应 Bridge ${state.zotero.bridgeVersion || "未知版本"}`
        : "在 Zotero Tools → Add-ons 中选择 Install Add-on From File。",
    },
    {
      label: "版本/协议兼容",
      status: compatible ? "ready" : installed ? "blocked" : "pending",
      detail: compatible
        ? "当前 Bridge 与 PaperHunter 后端版本、协议兼容。"
        : state.zotero.bridgeReason === "pairing_not_supported"
          ? `检测到旧 Bridge ${state.zotero.bridgeVersion || ""}，缺少配对能力，请覆盖安装 ${state.zotero.expectedBridgeVersion || "最新版"}。`
          : state.zotero.bridgeNextStep || "安装后重启 Zotero 并刷新检测。",
    },
    {
      label: "配对 token 验证",
      status: paired ? "ready" : compatible ? "pending" : "blocked",
      detail: bridgePairingStatusText(state.zotero.bridgePairing),
    },
  ];
}

function renderBridgeWizard(bridgePackage = {}) {
  const list = document.createElement("div");
  list.className = "bridge-wizard";
  bridgeWizardSteps(bridgePackage).forEach((step, index) => {
    const item = document.createElement("article");
    item.className = `bridge-wizard-step is-${step.status}`;
    const badge = document.createElement("span");
    badge.textContent = String(index + 1);
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = step.label;
    const detail = document.createElement("small");
    detail.textContent = step.detail;
    body.append(title, detail);
    item.append(badge, body);
    list.append(item);
  });
  return list;
}

function stopBridgeInstallPolling() {
  if (state.bridgeInstallPoller) {
    window.clearInterval(state.bridgeInstallPoller);
    state.bridgeInstallPoller = null;
  }
  state.bridgeInstallPollStartedAt = 0;
}

function startBridgeInstallPolling() {
  stopBridgeInstallPolling();
  state.bridgeInstallPollStartedAt = Date.now();
  const poll = async () => {
    try {
      await refreshStatus();
      const elapsedMs = Date.now() - state.bridgeInstallPollStartedAt;
      if (state.zotero.syncAvailable) {
        stopBridgeInstallPolling();
        setMessage("已检测到兼容并完成配对的 PaperHunter Zotero Bridge。", "success");
        if (elements.zoteroInstallNote) {
          elements.zoteroInstallNote.textContent = "Bridge 已安装、版本兼容且配对成功；同步前仍会先走 dry-run。";
        }
      } else if (elapsedMs > 90000) {
        stopBridgeInstallPolling();
        setMessage("仍未检测到兼容 Bridge。请确认 XPI 已在 Zotero 中覆盖安装，并已重启 Zotero。", "error");
      } else if (elements.zoteroInstallNote) {
        elements.zoteroInstallNote.textContent = "已开始检测 Bridge 安装状态。完成 Zotero 覆盖安装并重启后，PaperHunter 会自动刷新检测结果。";
      }
    } catch (error) {
      if (Date.now() - state.bridgeInstallPollStartedAt > 90000) {
        stopBridgeInstallPolling();
        setMessage(error.message, "error");
      }
    }
  };
  state.bridgeInstallPoller = window.setInterval(poll, 3000);
  poll();
}

function downloadActionLabel(paper) {
  if (!paper.downloadable) {
    return "无 PDF";
  }
  if (paper.localPdfPath) {
    return "Zotero PDF";
  }
  return paper.isDownloaded ? "已下载" : "下载 PDF";
}

function favoriteActionLabel(paper) {
  return paper.isFavorite ? "取消收藏" : "收藏";
}

function abstractActionLabel(paper) {
  return zhTranslation(paper) ? "重译摘要" : "翻译摘要";
}

function fulltextTaskForPaper(paper) {
  return state.fulltextTasks[paper.paperKey || ""];
}

function fulltextProgressPercent(task) {
  const total = Number(task && task.totalChunks) || 0;
  if (!total) {
    return 0;
  }
  return Math.round(((Number(task.completedChunks) || 0) / total) * 100);
}

function fulltextActionLabel(paper) {
  const task = fulltextTaskForPaper(paper);
  if (!task) {
    return "全文翻译";
  }
  if (task.status === "done") {
    return "重新全文翻译";
  }
  if (task.status === "failed" || task.canResume) {
    return "继续全文翻译";
  }
  if (task.status === "running" || task.status === "queued") {
    return "翻译中";
  }
  return "全文翻译";
}

function fulltextActionDisabled(paper) {
  const task = fulltextTaskForPaper(paper);
  return !paper.isDownloaded || Boolean(task && ["running", "queued"].includes(task.status));
}

function fulltextConsentRequired(paper) {
  if (!paper) {
    return false;
  }
  const access = String(paper.access || "").toLowerCase();
  const source = String(paper.source || "").toLowerCase();
  const normalizedPath = String(paper.localPdfPath || "").replace(/\\/g, "/").toLowerCase();
  return access === "user_library"
    || source === "zotero"
    || normalizedPath.includes("/zotero/storage/")
    || normalizedPath.includes("zotero/storage/");
}

function pdfAccessInfo(paper) {
  if (!paper) {
    return null;
  }
  const access = String(paper.access || "").toLowerCase();
  const source = String(paper.source || "").toLowerCase();
  if (fulltextConsentRequired(paper)) {
    return {
      kind: "private",
      label: "Zotero 私有 PDF",
      description: "来自用户本地 Zotero 资料库；PaperHunter 可读取本地路径，但不会把它当作公开资源或重新分发。",
    };
  }
  if (paper.localPdfPath) {
    return {
      kind: "local",
      label: "PaperHunter 本地 PDF",
      description: "位于本机工作区；不会覆盖原始文件。",
    };
  }
  if (paper.pdfUrl && (access.includes("open") || ["arxiv", "cvf", "acl", "openreview", "chinarxiv", "sciopen", "nso"].includes(source))) {
    return {
      kind: "open",
      label: "开放 PDF",
      description: "来自开放访问来源，可按来源链接下载。",
    };
  }
  if (paper.pdfUrl) {
    return {
      kind: "external",
      label: "外部 PDF",
      description: "来自外部来源；请按来源页面确认访问权限。",
    };
  }
  return null;
}

function fulltextConsentKey(paper) {
  const settings = state.modelSettings || {};
  const provider = settings.provider || state.selectedProvider || "custom";
  const apiType = settings.apiType || elements.modelApiType.value || "unknown-api";
  const model = settings.model || elements.modelName.value || "unknown-model";
  const privatePdfMode = settings.privatePdfMode || (elements.privatePdfMode && elements.privatePdfMode.value) || "confirm";
  return `paperhunter:fulltext-consent:${paper.paperKey || paper.title || "paper"}:${provider}:${apiType}:${model}:${privatePdfMode}`;
}

function storedFulltextConsentGranted(key) {
  try {
    return window.localStorage.getItem(key) === "granted";
  } catch (_error) {
    return false;
  }
}

function rememberFulltextConsent(key) {
  try {
    window.localStorage.setItem(key, "granted");
  } catch (_error) {
    // If localStorage is unavailable, this one translation can still proceed after confirmation.
  }
}

function closeAppConfirmDialog() {
  const existing = document.querySelector(".app-confirm-backdrop");
  if (existing) {
    existing.remove();
  }
}

function showAppConfirmDialog({
  title = "请确认",
  intro = "",
  details = [],
  confirmText = "确认",
  cancelText = "取消",
} = {}) {
  closeAppConfirmDialog();
  return new Promise((resolve) => {
    let settled = false;
    const backdrop = document.createElement("div");
    backdrop.className = "zotero-binding-backdrop app-confirm-backdrop";

    const dialog = document.createElement("section");
    dialog.className = "zotero-binding-dialog app-confirm-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", title);

    const heading = document.createElement("div");
    heading.className = "zotero-binding-heading";
    const headingTitle = document.createElement("h3");
    headingTitle.textContent = title;
    const headingIntro = document.createElement("p");
    headingIntro.textContent = intro;
    heading.append(headingTitle, headingIntro);

    const detailList = document.createElement("div");
    detailList.className = "app-confirm-details";
    details.filter(Boolean).forEach((detail) => {
      const item = document.createElement("span");
      item.textContent = detail;
      detailList.append(item);
    });

    const footer = document.createElement("div");
    footer.className = "zotero-binding-footer";
    const cancel = document.createElement("button");
    cancel.className = "secondary-action compact-action";
    cancel.type = "button";
    cancel.textContent = cancelText;
    const confirm = document.createElement("button");
    confirm.className = "primary-action compact-action";
    confirm.type = "button";
    confirm.textContent = confirmText;
    footer.append(cancel, confirm);

    const finish = (value) => {
      if (settled) {
        return;
      }
      settled = true;
      document.removeEventListener("keydown", handleKeydown);
      closeAppConfirmDialog();
      resolve(value);
    };
    const handleKeydown = (event) => {
      if (event.key === "Escape") {
        finish(false);
      }
    };

    cancel.addEventListener("click", () => finish(false));
    confirm.addEventListener("click", () => finish(true));
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) {
        finish(false);
      }
    });
    document.addEventListener("keydown", handleKeydown);

    dialog.append(heading);
    if (details.length) {
      dialog.append(detailList);
    }
    dialog.append(footer);
    backdrop.append(dialog);
    document.body.append(backdrop);
    confirm.focus();
  });
}

async function confirmUserLibraryFulltextConsent(paper) {
  if (!fulltextConsentRequired(paper)) {
    return true;
  }
  const settings = state.modelSettings || {};
  const strictMode = settings.privatePdfMode === "local_only";
  const endpointTrusted = Boolean(settings.modelEndpointIsLocal)
    || Boolean(settings.selfHostedModel)
    || modelEndpointLooksLocal(elements.modelBaseUrl.value)
    || Boolean(elements.selfHostedModel && elements.selfHostedModel.checked);
  if (strictMode && !endpointTrusted) {
    setMessage("当前已开启“仅本地/自托管模型”模式，但模型 Base URL 看起来不是本地地址。请改用 localhost/127.0.0.1/.local，或确认这是自托管模型后再继续。", "error");
    return false;
  }
  const key = fulltextConsentKey(paper);
  if (storedFulltextConsentGranted(key)) {
    return true;
  }
  const provider = settings.provider || state.selectedProvider || "当前模型提供方";
  const model = settings.model || elements.modelName.value || "当前模型";
  const privacyLine = strictMode
    ? "当前已开启仅本地/自托管模型模式；PaperHunter 仍会在发送提取文本前要求你确认。"
    : "全文翻译会先提取 PDF 正文，并发送给当前模型提供方用于翻译。";
  const ok = await showAppConfirmDialog({
    title: "确认全文翻译",
    intro: "这篇 PDF 来自 Zotero 本地资料库，可能是非开放或闭源论文。",
    details: [
      privacyLine,
      `当前目标：${provider} / ${model}`,
      "PaperHunter 不会上传、移动、删除或覆盖你的 Zotero 原始 PDF；但提取文本会发送给你配置的模型服务。",
    ],
    confirmText: "继续翻译",
  });
  if (ok) {
    rememberFulltextConsent(key);
  }
  return ok;
}

function canOpenFulltextFolder(task) {
  return Boolean(task && task.status === "done" && task.file);
}

function createFulltextProgress(paper) {
  const task = fulltextTaskForPaper(paper);
  if (!task) {
    return null;
  }

  const wrap = document.createElement("div");
  wrap.className = `fulltext-task is-${task.status || "queued"}`;

  const header = document.createElement("div");
  header.className = "fulltext-task-header";

  const status = document.createElement("span");
  const total = Number(task.totalChunks) || 0;
  const done = Number(task.completedChunks) || 0;
  const failed = Number(task.failedChunks) || 0;
  status.textContent = task.status === "done"
    ? `全文翻译完成 ${done}/${total}`
    : (task.status === "failed" || task.status === "partial")
      ? `全文翻译暂停 ${done}/${total}${failed ? `，失败 ${failed}` : ""}`
      : `全文翻译进行中 ${done}/${total}`;

  const percent = document.createElement("strong");
  percent.textContent = `${fulltextProgressPercent(task)}%`;
  header.append(status, percent);

  const track = document.createElement("div");
  track.className = "fulltext-progress";
  const bar = document.createElement("span");
  bar.style.width = `${fulltextProgressPercent(task)}%`;
  track.append(bar);

  wrap.append(header, track);

  if (task.error) {
    const error = document.createElement("p");
    error.className = "fulltext-task-error";
    error.textContent = task.error;
    wrap.append(error);
  } else if (task.file) {
    const file = document.createElement("p");
    file.className = "fulltext-task-file";
    file.textContent = task.file;
    wrap.append(file);
  }
  if (canOpenFulltextFolder(task)) {
    const openButton = createLibraryAction("打开所在文件夹", (event) => openFulltextFolder(paper, task, event.currentTarget));
    openButton.classList.add("fulltext-open-folder");
    wrap.append(openButton);
  }
  return wrap;
}

function libraryStatusText(paper) {
  const badges = [];
  if (zoteroLinkStatus(paper) === "ambiguous") {
    badges.push("Zotero 需确认绑定");
  } else if (zoteroLinkStatus(paper) === "conflict") {
    badges.push("Zotero 绑定冲突");
  } else if (zoteroLinked(paper)) {
    badges.push("已关联 Zotero");
  }
  if (paper.zoteroSync && paper.zoteroSync.status === "synced") {
    badges.push("已回写 Zotero");
  } else if (paper.zoteroSync && paper.zoteroSync.status === "failed") {
    badges.push("Zotero 回写失败");
  }
  const status = readingStatusLabels[paper.readingStatus || ""];
  if (status && paper.readingStatus) {
    badges.push(status);
  }
  if (zhTranslation(paper)) {
    badges.push("摘要已翻译");
  }
  const task = fulltextTaskForPaper(paper);
  if (task) {
    badges.push(task.status === "done" ? "全文翻译完成" : "全文处理中");
  }
  if (paper.isDownloaded) {
    badges.push(paper.localPdfPath ? "有本地 PDF" : "已下载");
  }
  const accessInfo = pdfAccessInfo(paper);
  if (accessInfo) {
    badges.push(accessInfo.label);
  }
  return badges.join(" · ");
}

function createPdfAccessBadge(paper) {
  const info = pdfAccessInfo(paper);
  if (!info) {
    return null;
  }
  const badge = document.createElement("div");
  badge.className = `library-access-badge is-${info.kind}`;
  badge.title = info.description;
  const label = document.createElement("strong");
  label.textContent = info.label;
  const description = document.createElement("span");
  description.textContent = info.description;
  badge.append(label, description);
  return badge;
}

function createLibraryTagList(paper) {
  if (!Array.isArray(paper.tags) || !paper.tags.length) {
    return null;
  }
  const wrap = document.createElement("div");
  wrap.className = "library-tag-list";
  paper.tags
    .map((tag) => String(tag || "").trim())
    .filter(Boolean)
    .forEach((tag) => {
      const chip = document.createElement("span");
      chip.className = "library-tag";
      chip.textContent = tag;
      wrap.append(chip);
    });
  return wrap;
}

function createLibraryNote(paper) {
  const text = String(paper.note || "").trim();
  if (!text) {
    return null;
  }
  const wrap = document.createElement("div");
  wrap.className = "library-note-block";

  const label = document.createElement("span");
  label.className = "library-note-label";
  label.textContent = "备注";

  const note = document.createElement("p");
  note.className = "library-note";
  note.textContent = text;

  wrap.append(label, note);
  return wrap;
}

function createLibraryMoreActions(actions) {
  const wrap = document.createElement("details");
  wrap.className = "library-more-actions";

  const summary = document.createElement("summary");
  summary.className = "library-more-toggle";
  summary.textContent = "更多操作";

  const panel = document.createElement("div");
  panel.className = "library-more-panel";
  actions.forEach((action) => panel.append(action));

  wrap.append(summary, panel);
  return wrap;
}

function closeZoteroBindingDialog() {
  const existing = document.querySelector(".zotero-binding-backdrop");
  if (existing) {
    existing.remove();
  }
}

async function confirmZoteroBinding(paper, itemKey, button = null) {
  if (!paper || !itemKey) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "绑定中";
  }
  try {
    const data = await requestJson("/api/zotero/confirm-link", {
      paperKey: paper.paperKey,
      paper,
      itemKey,
    }, 30000);
    updateLibrary(data.library || state.library);
    closeZoteroBindingDialog();
    setMessage(`已确认 Zotero 绑定：${itemKey}`, "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function refreshZoteroBindingCandidates(paper) {
  const preview = await requestJson("/api/zotero/sync-preview", {
    paperKey: paper.paperKey,
    paper,
    includeFulltext: true,
  }, 30000);
  if (preview.library) {
    updateLibrary(preview.library);
  }
  const storedPaper = libraryPaperForKey(paper.paperKey) || paper;
  return {
    ...storedPaper,
    zoteroLink: {
      ...(storedPaper.zoteroLink || {}),
      status: preview.status || zoteroLinkStatus(storedPaper),
      message: preview.message || "",
      candidates: Array.isArray(preview.candidates) ? preview.candidates : zoteroBindingCandidates(storedPaper),
    },
  };
}

async function showZoteroBindingDialog(paper) {
  let dialogPaper = paper;
  let candidates = zoteroBindingCandidates(dialogPaper);
  if (!candidates.length) {
    setMessage("正在刷新 Zotero 绑定候选...");
    try {
      dialogPaper = await refreshZoteroBindingCandidates(paper);
      candidates = zoteroBindingCandidates(dialogPaper);
    } catch (error) {
      setMessage(error.message, "error");
      return;
    }
  }
  if (!candidates.length) {
    setMessage("这篇论文没有可确认的 Zotero 候选，请先刷新 Zotero 状态或重新导入。", "error");
    return;
  }
  closeZoteroBindingDialog();

  const backdrop = document.createElement("div");
  backdrop.className = "zotero-binding-backdrop";

  const dialog = document.createElement("section");
  dialog.className = "zotero-binding-dialog";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", "确认 Zotero 绑定");

  const heading = document.createElement("div");
  heading.className = "zotero-binding-heading";
  const title = document.createElement("h3");
  title.textContent = "确认 Zotero 绑定";
  const intro = document.createElement("p");
  intro.textContent = "发现多个可能对应的 Zotero 条目。请选择 PaperHunter 后续保存和同步要使用的 canonical itemKey。PaperHunter 不会合并或删除 Zotero 条目。";
  heading.append(title, intro);

  const list = document.createElement("div");
  list.className = "zotero-candidate-list";
  candidates.forEach((candidate) => {
    const card = document.createElement("article");
    card.className = "zotero-candidate";
    const itemTitle = document.createElement("strong");
    itemTitle.textContent = candidate.title || "Untitled Zotero item";
    const meta = document.createElement("p");
    const bits = [
      candidate.authors,
      candidate.year,
      candidate.itemKey ? `itemKey ${candidate.itemKey}` : "",
      Number.isFinite(Number(candidate.score)) ? `score ${candidate.score}` : "",
    ].filter(Boolean);
    meta.textContent = bits.join(" · ");
    const flags = document.createElement("small");
    const flagBits = [];
    if (candidate.hasPdf) {
      flagBits.push("含 Zotero 本地 PDF");
    }
    if (candidate.hasPaperHunterNote) {
      flagBits.push("已有 PaperHunter note");
    }
    if (candidate.userNoteCount) {
      flagBits.push(`${candidate.userNoteCount} 条用户笔记`);
    }
    if (candidate.attachmentCount) {
      flagBits.push(`${candidate.attachmentCount} 个附件`);
    }
    flags.textContent = flagBits.join(" · ") || "无明显附加内容";
    const choose = document.createElement("button");
    choose.className = "library-item-action";
    choose.type = "button";
    choose.textContent = "绑定此条目";
    choose.addEventListener("click", () => confirmZoteroBinding(dialogPaper, candidate.itemKey, choose));
    card.append(itemTitle, meta, flags, choose);
    list.append(card);
  });

  const footer = document.createElement("div");
  footer.className = "zotero-binding-footer";
  const cancel = document.createElement("button");
  cancel.className = "secondary-action compact-action";
  cancel.type = "button";
  cancel.textContent = "稍后处理";
  cancel.addEventListener("click", closeZoteroBindingDialog);
  footer.append(cancel);

  dialog.append(heading, list, footer);
  backdrop.append(dialog);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) {
      closeZoteroBindingDialog();
    }
  });
  document.body.append(backdrop);
}

function closeZoteroSyncPreviewDialog() {
  const existing = document.querySelector(".zotero-sync-preview-backdrop");
  if (existing) {
    existing.remove();
  }
}

function showZoteroSyncPreviewDialog(preview, options = {}) {
  closeZoteroSyncPreviewDialog();
  return new Promise((resolve) => {
    const confirmable = options.confirmable !== false && preview.confirmable !== false && preview.readOnly !== true;
    const items = Array.isArray(preview.items) ? preview.items : [];
    const readyItems = items.filter((item) => item.ready);

    const backdrop = document.createElement("div");
    backdrop.className = "zotero-binding-backdrop zotero-sync-preview-backdrop";

    const dialog = document.createElement("section");
    dialog.className = "zotero-binding-dialog zotero-sync-preview-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", "Zotero 同步预览");

    const heading = document.createElement("div");
    heading.className = "zotero-binding-heading";
    const title = document.createElement("h3");
    title.textContent = "同步前 dry-run 预览";
    const intro = document.createElement("p");
    intro.textContent = confirmable
      ? "请确认 PaperHunter 将写入的 Zotero itemKey、paperhunter:* 标签和译文 Markdown 附件。不会删除、移动、覆盖 Zotero 原始条目、PDF、用户笔记、用户标签或 collections。"
      : "这是只读 dry-run 查看。这里只展示 PaperHunter 将管理的 note、paperhunter:* 标签和译文 Markdown 附件，不会写入 Zotero。";
    heading.append(title, intro);

    const stats = document.createElement("div");
    stats.className = "zotero-sync-preview-stats";
    [
      ["检查收藏", preview.checked || 0],
      ["可回写", preview.ready || 0],
      ["需确认", preview.blocked || 0],
      ["译文附件", preview.attachments || 0],
    ].forEach(([labelText, value]) => {
      const stat = document.createElement("span");
      const number = document.createElement("strong");
      number.textContent = String(value);
      stat.append(number, labelText);
      stats.append(stat);
    });

    const list = document.createElement("div");
    list.className = "zotero-sync-preview-list";
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = `zotero-sync-preview-item ${item.ready ? "is-ready" : "is-blocked"}`;

      const itemTitle = document.createElement("strong");
      itemTitle.textContent = item.title || "Untitled";

      const meta = document.createElement("p");
      const statusLabel = item.ready ? "可回写" : (item.status || "需处理");
      const bits = [
        statusLabel,
        item.itemKey ? `itemKey ${item.itemKey}` : "",
        item.ready ? `${(item.tags || []).length} 个 paperhunter:* 标签` : "",
        item.ready ? `${item.attachments || 0} 个译文附件` : "",
      ].filter(Boolean);
      meta.textContent = bits.join(" · ");

      const message = document.createElement("small");
      message.textContent = item.message || (item.ready ? "将 upsert PaperHunter 管理的 note。" : "需要确认绑定后才能回写。");

      card.append(itemTitle, meta, message);
      if (confirmable && !item.ready && Array.isArray(item.candidates) && item.candidates.length) {
        const bind = document.createElement("button");
        bind.className = "library-item-action";
        bind.type = "button";
        bind.textContent = "确认绑定";
        bind.addEventListener("click", () => {
          closeZoteroSyncPreviewDialog();
          const paper = libraryPaperForKey(item.paperKey) || { paperKey: item.paperKey, title: item.title };
          showZoteroBindingDialog({
            ...paper,
            zoteroLink: {
              ...(paper.zoteroLink || {}),
              status: item.status || "ambiguous",
              message: item.message || "",
              candidates: item.candidates,
            },
          });
          resolve(false);
        });
        card.append(bind);
      }
      list.append(card);
    });

    const footer = document.createElement("div");
    footer.className = "zotero-binding-footer";
    const cancel = document.createElement("button");
    cancel.className = "secondary-action compact-action";
    cancel.type = "button";
    cancel.textContent = confirmable ? "取消" : "关闭";
    cancel.addEventListener("click", () => {
      closeZoteroSyncPreviewDialog();
      resolve(false);
    });
    const confirm = document.createElement("button");
    confirm.className = "secondary-action compact-action";
    confirm.type = "button";
    confirm.textContent = readyItems.length ? `确认回写 ${readyItems.length} 篇` : "没有可回写条目";
    confirm.disabled = readyItems.length === 0;
    confirm.addEventListener("click", () => {
      closeZoteroSyncPreviewDialog();
      resolve(true);
    });
    footer.append(cancel);
    if (confirmable) {
      footer.append(confirm);
    }

    dialog.append(heading, stats, list, footer);
    backdrop.append(dialog);
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) {
        closeZoteroSyncPreviewDialog();
        resolve(false);
      }
    });
    document.body.append(backdrop);
  });
}

function closeZoteroManagementDialog() {
  const existing = document.querySelector(".zotero-management-backdrop");
  if (existing) {
    existing.remove();
  }
}

function createZoteroStat(labelText, value) {
  const stat = document.createElement("span");
  const number = document.createElement("strong");
  number.textContent = String(value);
  stat.append(number, labelText);
  return stat;
}

function createZoteroDialogShell({ title, intro, className = "", label = "" }) {
  closeZoteroManagementDialog();

  const backdrop = document.createElement("div");
  backdrop.className = "zotero-binding-backdrop zotero-management-backdrop";

  const dialog = document.createElement("section");
  dialog.className = `zotero-binding-dialog zotero-management-dialog ${className}`.trim();
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", label || title);

  const heading = document.createElement("div");
  heading.className = "zotero-binding-heading";
  const headingTitle = document.createElement("h3");
  headingTitle.textContent = title;
  const headingIntro = document.createElement("p");
  headingIntro.textContent = intro;
  heading.append(headingTitle, headingIntro);

  dialog.append(heading);
  backdrop.append(dialog);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) {
      closeZoteroManagementDialog();
    }
  });
  document.body.append(backdrop);
  return { backdrop, dialog };
}

function abstractCandidateMeta(candidate) {
  const parts = [
    candidate.sourceLabel || candidate.source || "来源",
    candidate.completeness === "complete" ? "完整" : candidate.completeness === "partial" ? "可能截断" : "未知完整度",
    Number(candidate.textLength) > 0 ? `${Number(candidate.textLength)} 字符` : "",
    candidate.accessMode ? `权限：${candidate.accessMode}` : "",
    candidate.fetchedAt ? formatDateTime(candidate.fetchedAt) : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

async function confirmAbstractCandidate(paper, candidate, { lock = true, action = "confirm", button = null } = {}) {
  if (!paper) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = action === "unlock" ? "解除中" : lock ? "锁定中" : "采用中";
  }
  try {
    const data = await requestJson("/api/abstract/confirm", {
      paperKey: paper.paperKey,
      paper,
      candidateId: candidate && candidate.id,
      textHash: candidate && candidate.textHash,
      source: candidate && candidate.source,
      candidate: candidate || {},
      lock,
      action,
    }, 30000);
    updateLibrary(data.library || state.library);
    closeZoteroManagementDialog();
    setMessage(action === "unlock"
      ? "已解除摘要锁定，后续补全可再次更新摘要。"
      : lock
        ? "已采用并锁定摘要来源，自动补全不会覆盖。"
        : "已采用摘要候选。", "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function showAbstractCandidatesDialog(paper) {
  if (!paper) {
    return;
  }
  setMessage("正在整理摘要候选...");
  let data = null;
  try {
    data = await requestJson("/api/abstract/candidates", {
      paperKey: paper.paperKey,
      paper,
      includeSourceRefresh: true,
      persist: true,
    }, 35000);
  } catch (error) {
    setMessage(error.message, "error");
    return;
  }
  if (data.library) {
    updateLibrary(data.library);
  }

  const dialogPaper = libraryPaperForKey(data.paperKey || paper.paperKey) || data.paper || paper;
  const candidates = Array.isArray(data.candidates) ? data.candidates : [];
  const { dialog } = createZoteroDialogShell({
    title: "摘要来源确认",
    intro: "对比当前记录、Zotero、Alert、开放元数据和来源刷新返回的摘要。采用候选只更新 PaperHunter 摘要字段，不会改 Zotero 绑定或回写状态。",
    label: "摘要来源确认",
    className: "abstract-candidates-dialog",
  });

  const stats = document.createElement("div");
  stats.className = "zotero-sync-preview-stats";
  [
    ["候选", candidates.length],
    ["当前来源", abstractSourceLabel(dialogPaper)],
    ["锁定", dialogPaper.abstractLocked ? "是" : "否"],
  ].forEach(([labelText, value]) => stats.append(createZoteroStat(labelText, value)));

  const list = document.createElement("div");
  list.className = "abstract-candidate-list";
  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.className = "zotero-management-empty";
    empty.textContent = "暂时没有可确认的摘要候选。可以先导入 Alert，或稍后再次补全开放元数据。";
    list.append(empty);
  } else {
    const currentHash = String(dialogPaper.fullAbstract || dialogPaper.abstract || "").trim();
    candidates.forEach((candidate) => {
      const card = document.createElement("article");
      card.className = "abstract-candidate";

      const title = document.createElement("strong");
      title.textContent = candidate.sourceLabel || candidate.source || "摘要候选";

      const meta = document.createElement("p");
      meta.textContent = abstractCandidateMeta(candidate);

      const preview = document.createElement("small");
      preview.textContent = candidate.preview || candidate.text || "";

      const actions = document.createElement("div");
      actions.className = "abstract-candidate-actions";
      const useAndLock = document.createElement("button");
      useAndLock.className = "library-item-action";
      useAndLock.type = "button";
      useAndLock.textContent = "采用并锁定";
      useAndLock.addEventListener("click", () => confirmAbstractCandidate(dialogPaper, candidate, { lock: true, button: useAndLock }));

      const useOnly = document.createElement("button");
      useOnly.className = "library-item-action";
      useOnly.type = "button";
      useOnly.textContent = "仅采用";
      useOnly.addEventListener("click", () => confirmAbstractCandidate(dialogPaper, candidate, { lock: false, button: useOnly }));
      actions.append(useAndLock, useOnly);

      if (currentHash && String(candidate.text || "").trim() === currentHash) {
        const current = document.createElement("span");
        current.className = "abstract-current-pill";
        current.textContent = "当前";
        actions.prepend(current);
      }

      card.append(title, meta, preview, actions);
      list.append(card);
    });
  }

  const footer = document.createElement("div");
  footer.className = "zotero-binding-footer";
  const lockCurrent = document.createElement("button");
  lockCurrent.className = "secondary-action compact-action";
  lockCurrent.type = "button";
  lockCurrent.textContent = "锁定当前";
  lockCurrent.addEventListener("click", () => confirmAbstractCandidate(dialogPaper, null, {
    action: "lock-current",
    lock: true,
    button: lockCurrent,
  }));

  const unlock = document.createElement("button");
  unlock.className = "secondary-action compact-action";
  unlock.type = "button";
  unlock.textContent = "解除锁定";
  unlock.disabled = !dialogPaper.abstractLocked;
  unlock.addEventListener("click", () => confirmAbstractCandidate(dialogPaper, null, {
    action: "unlock",
    lock: false,
    button: unlock,
  }));

  const close = document.createElement("button");
  close.className = "secondary-action compact-action";
  close.type = "button";
  close.textContent = "关闭";
  close.addEventListener("click", closeZoteroManagementDialog);
  footer.append(lockCurrent, unlock, close);

  dialog.append(stats, list, footer);
}

async function previewZoteroBindingFromManager(paper, button = null) {
  if (!paper) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "预览中";
  }
  try {
    const preview = await requestJson("/api/zotero/sync-preview", {
      paperKey: paper.paperKey,
      paper,
      includeFulltext: true,
    }, 30000);
    if (preview.library) {
      updateLibrary(preview.library);
    }
    if (!preview.ready && Array.isArray(preview.candidates) && preview.candidates.length) {
      closeZoteroManagementDialog();
      const storedPaper = libraryPaperForKey(paper.paperKey) || paper;
      showZoteroBindingDialog({
        ...storedPaper,
        zoteroLink: {
          ...(storedPaper.zoteroLink || {}),
          status: preview.status || "ambiguous",
          message: preview.message || "",
          candidates: preview.candidates,
        },
      });
      return;
    }
    if (!preview.ready) {
      setMessage(preview.message || "这篇论文还不能回写 Zotero。", "error");
      return;
    }
    setMessage(`dry-run 通过：将写入 Zotero itemKey ${preview.itemKey}，${(preview.tags || []).length} 个 paperhunter:* 标签，${preview.attachments || 0} 个译文附件。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function showZoteroBindingManager() {
  const rows = zoteroBindingRows();
  const counts = zoteroHealthCounts();
  const { dialog } = createZoteroDialogShell({
    title: "Zotero 绑定管理",
    intro: "集中查看收藏论文的 canonical itemKey、重复候选和回写状态。这里不会合并 Zotero 条目，也不会修改原始 PDF、用户笔记、用户标签或 collections。",
    label: "Zotero 绑定管理",
  });

  const stats = document.createElement("div");
  stats.className = "zotero-sync-preview-stats";
  [
    ["收藏", rows.length],
    ["安全绑定", counts.linked],
    ["需确认", counts.review],
    ["已回写", counts.synced],
  ].forEach(([labelText, value]) => stats.append(createZoteroStat(labelText, value)));

  const list = document.createElement("div");
  list.className = "zotero-management-list";

  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "zotero-management-empty";
    empty.textContent = "还没有收藏论文。收藏后 PaperHunter 会在保存、导入或 dry-run 时建立 Zotero 绑定状态。";
    list.append(empty);
  } else {
    const priority = { conflict: 0, ambiguous: 1, missing: 2, unmatched: 3, unlinked: 4, confirmed: 5, auto: 6 };
    [...rows]
      .sort((a, b) => (priority[a.status] ?? 9) - (priority[b.status] ?? 9))
      .forEach((row) => {
        const card = document.createElement("article");
        card.className = [
          "zotero-management-item",
          row.needsReview ? "needs-review" : "",
          row.isLinked ? "is-linked" : "",
        ].filter(Boolean).join(" ");

        const header = document.createElement("div");
        header.className = "zotero-management-item-header";
        const title = document.createElement("strong");
        title.textContent = row.title;
        title.title = row.title;
        const status = document.createElement("span");
        status.className = `zotero-status-pill is-${row.needsReview ? "review" : row.isLinked ? "linked" : "plain"}`;
        status.textContent = row.statusLabel;
        header.append(title, status);

        const meta = document.createElement("p");
        const bits = [
          row.meta,
          row.itemKey ? `itemKey ${row.itemKey}` : "尚无 canonical itemKey",
          row.syncStatus ? row.syncLabel : "",
          row.candidates.length ? `${row.candidates.length} 个候选` : "",
        ].filter(Boolean);
        meta.textContent = bits.join(" · ");

        const message = document.createElement("small");
        message.textContent = row.message || row.syncError || (row.needsReview
          ? "需要先确认绑定，PaperHunter 才会继续回写。"
          : "绑定信息正常；真实回写仍会经过 dry-run 预览。");

        const actions = document.createElement("div");
        actions.className = "zotero-management-actions";
        const preview = document.createElement("button");
        preview.className = "library-item-action";
        preview.type = "button";
        preview.textContent = "单篇 dry-run";
        preview.addEventListener("click", () => previewZoteroBindingFromManager(row.paper, preview));
        actions.append(preview);

        if (row.needsReview) {
          const confirm = document.createElement("button");
          confirm.className = "library-item-action";
          confirm.type = "button";
          confirm.textContent = row.candidates.length ? "确认绑定" : "刷新候选";
          confirm.addEventListener("click", () => {
            closeZoteroManagementDialog();
            showZoteroBindingDialog(row.paper);
          });
          actions.append(confirm);
        }

        card.append(header, meta, message, actions);
        list.append(card);
      });
  }

  const footer = document.createElement("div");
  footer.className = "zotero-binding-footer";
  const refresh = document.createElement("button");
  refresh.className = "secondary-action compact-action";
  refresh.type = "button";
  refresh.textContent = "刷新状态";
  refresh.addEventListener("click", async () => {
    refresh.disabled = true;
    refresh.textContent = "刷新中";
    try {
      await refreshStatus();
      closeZoteroManagementDialog();
      showZoteroBindingManager();
      setMessage("Zotero 绑定状态已刷新。", "success");
    } catch (error) {
      setMessage(error.message, "error");
      refresh.disabled = false;
      refresh.textContent = "刷新状态";
    }
  });
  const close = document.createElement("button");
  close.className = "secondary-action compact-action";
  close.type = "button";
  close.textContent = "关闭";
  close.addEventListener("click", closeZoteroManagementDialog);
  footer.append(refresh, close);

  dialog.append(stats, list, footer);
}

async function showZoteroAuditDialog() {
  setMessage("正在读取 Zotero 操作历史...");
  try {
    const data = await requestGetJson("/api/zotero/audit?limit=120", 15000);
    const audit = Array.isArray(data.items) ? data.items : [];
    const { dialog } = createZoteroDialogShell({
      title: "Zotero 操作历史",
      intro: "这里记录 PaperHunter 侧的 Zotero 预览、确认绑定和同步结果，用来排查“写到哪里、为什么暂停”。它不是 Zotero 原生历史，也不会修改任何条目。",
      label: "Zotero 操作历史",
      className: "zotero-audit-dialog",
    });

    const stats = document.createElement("div");
    stats.className = "zotero-sync-preview-stats";
    stats.append(
      createZoteroStat("历史总数", data.total || audit.length),
      createZoteroStat("本次显示", audit.length),
      createZoteroStat("上限", data.limit || 120),
      createZoteroStat("只读", "是"),
    );

    const list = document.createElement("div");
    list.className = "zotero-audit-list";
    if (!audit.length) {
      const empty = document.createElement("p");
      empty.className = "zotero-management-empty";
      empty.textContent = "还没有 Zotero 操作记录。执行 dry-run、确认绑定或同步后会出现在这里。";
      list.append(empty);
    } else {
      audit.forEach((event) => {
        const card = document.createElement("article");
        card.className = "zotero-audit-item";
        const title = document.createElement("strong");
        title.textContent = [event.action, event.status].filter(Boolean).join(" · ");
        const meta = document.createElement("p");
        const bits = [
          formatDateTime(event.createdAt),
          event.itemKey ? `itemKey ${event.itemKey}` : "",
          event.title || event.paperKey || "",
        ].filter(Boolean);
        meta.textContent = bits.join(" · ");
        const message = document.createElement("small");
        message.textContent = event.message || "无附加说明。";
        card.append(title, meta, message);

        const details = event.details && typeof event.details === "object" ? event.details : {};
        if (Object.keys(details).length) {
          const detail = document.createElement("details");
          detail.className = "zotero-audit-details";
          const summary = document.createElement("summary");
          summary.textContent = "查看细节";
          const pre = document.createElement("pre");
          pre.textContent = JSON.stringify(details, null, 2);
          detail.append(summary, pre);
          card.append(detail);
        }
        list.append(card);
      });
    }

    const footer = document.createElement("div");
    footer.className = "zotero-binding-footer";
    const close = document.createElement("button");
    close.className = "secondary-action compact-action";
    close.type = "button";
    close.textContent = "关闭";
    close.addEventListener("click", closeZoteroManagementDialog);
    footer.append(close);

    dialog.append(stats, list, footer);
    setMessage("Zotero 操作历史已打开。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

function showZoteroBridgeHelpDialog() {
  const bridgePackage = state.zotero.bridgePackage || {};
  const capabilities = state.zotero.bridgeCapabilities || {};
  const installSteps = state.zotero.bridgeInstallSteps.length
    ? state.zotero.bridgeInstallSteps
    : ["下载 PaperHunter Zotero Bridge XPI", "在 Zotero 中打开插件管理器", "从文件安装 XPI", "重启 Zotero", "刷新 PaperHunter 状态"];
  const { dialog } = createZoteroDialogShell({
    title: "Bridge 安装与排障",
    intro: "Bridge 只负责把 PaperHunter 管理的 note、paperhunter:* 标签和译文 Markdown 附件回写到已确认的 Zotero itemKey；不会自动合并、删除、移动或覆盖 Zotero 原始内容。",
    label: "Bridge 安装与排障",
    className: "zotero-bridge-help-dialog",
  });

  const stats = document.createElement("div");
  stats.className = "zotero-sync-preview-stats";
  [
    ["保存", state.zotero.available ? "可用" : "不可用"],
    ["导入", state.zotero.importAvailable ? "可用" : "不可用"],
    ["回写", state.zotero.syncAvailable ? "可用" : "需 Bridge"],
    ["安装包", bridgePackage.valid ? "有效" : "不可用"],
  ].forEach(([labelText, value]) => stats.append(createZoteroStat(labelText, value)));

  const status = document.createElement("div");
  status.className = "zotero-bridge-help-grid";
  [
    ["当前 Bridge", state.zotero.bridgeAvailable ? (state.zotero.bridgeVersion || "已响应") : "未检测到"],
    ["期望版本", state.zotero.expectedBridgeVersion || "随 PaperHunter 内置"],
    ["兼容性", state.zotero.bridgeCompatible ? "版本、协议、配对均兼容" : "尚未确认兼容"],
    ["排障原因", state.zotero.bridgeReason || "未返回原因"],
    ["配对 token", bridgePairingStatusText(state.zotero.bridgePairing)],
    ["安装包", bridgePackage.message || "未读取安装包状态"],
    ["导入状态", state.zotero.importMessage || "未检测 Zotero 本地资料库。"],
    ["回写状态", state.zotero.syncMessage || "未检测 PaperHunter Zotero Bridge。"],
    ["下一步", state.zotero.bridgeNextStep || "下载当前 XPI，安装后重启 Zotero 并刷新 PaperHunter。"],
  ].forEach(([labelText, value]) => {
    const item = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = labelText;
    const text = document.createElement("strong");
    text.textContent = value;
    item.append(label, text);
    status.append(item);
  });

  const steps = document.createElement("ol");
  steps.className = "zotero-bridge-steps";
  installSteps.forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    steps.append(item);
  });

  const checklist = document.createElement("div");
  checklist.className = "zotero-bridge-checklist";
  [
    "确认 Zotero 桌面端已打开，并在同一台电脑上运行。",
    "如果导入可用但回写不可用，通常说明 Zotero 本地资料库可读，但 Bridge 插件未安装或未响应。",
    "如果提示版本、协议或配对不兼容，下载当前页面提供的 XPI，覆盖安装后重启 Zotero。",
    "同步前始终先 dry-run；发现重复 itemKey 时，先在 PaperHunter 里确认 canonical 绑定。",
    "闭源或非开放 PDF 的全文翻译仍按私有 PDF 策略确认，不因为 Bridge 可用而自动上传。",
  ].forEach((text) => {
    const item = document.createElement("p");
    item.textContent = text;
    checklist.append(item);
  });

  const capabilityNote = document.createElement("p");
  capabilityNote.className = "zotero-install-note";
  capabilityNote.textContent = bridgeCapabilityLabels(capabilities);

  const installLoopNote = document.createElement("p");
  installLoopNote.className = "zotero-install-note bridge-install-loop-note";
  installLoopNote.textContent = state.bridgeInstallPoller
    ? "正在自动检测 Bridge 安装状态；覆盖安装并重启 Zotero 后会自动更新。"
    : "点击下载 XPI 后，PaperHunter 会开始轮询检测当前 Bridge 是否安装、版本兼容且配对成功。";

  const wizard = renderBridgeWizard(bridgePackage);

  const footer = document.createElement("div");
  footer.className = "zotero-binding-footer";
  const download = document.createElement("a");
  download.className = "secondary-action compact-action";
  download.href = bridgeDownloadHref();
  download.download = "paperhunter-zotero-bridge.xpi";
  download.textContent = "下载 XPI";
  download.setAttribute("aria-disabled", bridgePackage.valid ? "false" : "true");
  if (!bridgePackage.valid) {
    download.addEventListener("click", (event) => event.preventDefault());
  } else {
    download.addEventListener("click", () => {
      startBridgeInstallPolling();
      installLoopNote.textContent = "已开始自动检测 Bridge。请在 Zotero 中覆盖安装刚下载的 XPI，并重启 Zotero。";
      setMessage("Bridge XPI 已开始下载；安装并重启 Zotero 后，PaperHunter 会自动检测配对状态。", "success");
    });
  }
  const copyPath = document.createElement("button");
  copyPath.className = "secondary-action compact-action";
  copyPath.type = "button";
  copyPath.textContent = "复制 XPI 路径";
  copyPath.disabled = !bridgePackage.path;
  copyPath.addEventListener("click", async () => {
    try {
      await copyText(bridgePackage.path || "");
      setMessage("已复制 Bridge XPI 本地路径，可在 Zotero 从文件安装时粘贴使用。", "success");
    } catch (error) {
      setMessage(error.message, "error");
    }
  });
  const refresh = document.createElement("button");
  refresh.className = "secondary-action compact-action";
  refresh.type = "button";
  refresh.textContent = "刷新检测";
  refresh.addEventListener("click", async () => {
    refresh.disabled = true;
    refresh.textContent = "刷新中";
    try {
      await refreshStatus();
      closeZoteroManagementDialog();
      showZoteroBridgeHelpDialog();
      setMessage("Bridge 状态已刷新。", "success");
    } catch (error) {
      setMessage(error.message, "error");
      refresh.disabled = false;
      refresh.textContent = "刷新检测";
    }
  });
  const close = document.createElement("button");
  close.className = "secondary-action compact-action";
  close.type = "button";
  close.textContent = "关闭";
  close.addEventListener("click", closeZoteroManagementDialog);
  footer.append(download, copyPath, refresh, close);

  dialog.append(stats, status, wizard, steps, checklist, capabilityNote, installLoopNote, footer);
}

function createLibraryItem(paper, view) {
  const key = paper.paperKey || `${paper.source || "paper"}-${paper.paperId || paper.title || "untitled"}`;
  const item = document.createElement("details");
  item.className = "library-item";
  item.open = Boolean(state.expandedLibraryItems[key]);
  item.addEventListener("toggle", () => {
    state.expandedLibraryItems[key] = item.open;
  });

  const header = document.createElement("summary");
  header.className = "library-item-header";

  const headerText = document.createElement("span");
  headerText.className = "library-item-title-block";

  const title = document.createElement("strong");
  title.textContent = paper.title || "Untitled";
  title.title = paper.title || "";

  const meta = document.createElement("span");
  meta.textContent = paperDisplayMeta(paper);

  headerText.append(title, meta);

  const status = document.createElement("small");
  status.className = "library-item-status";
  status.textContent = libraryStatusText(paper) || (view === "ignored" ? "已忽略" : "展开");
  header.append(headerText, status);

  const body = document.createElement("div");
  body.className = "library-item-body";

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
  let moreActions = null;

  if (view === "favorites") {
    const translation = zhTranslation(paper);
    const abstractDisplay = abstractDisplayForPaper(paper);
    const accessBadge = createPdfAccessBadge(paper);
    const tags = createLibraryTagList(paper);
    const note = createLibraryNote(paper);
    body.append(createAbstractStatusBadge(paper));
    const diagnosticsPanel = createAbstractDiagnosticsPanel(paper);
    if (diagnosticsPanel) {
      body.append(diagnosticsPanel);
    }
    if (accessBadge) {
      body.append(accessBadge);
    }
    if (tags) {
      body.append(tags);
    }
    if (note) {
      body.append(note);
    }
    if (translation) {
      body.append(createTranslationBlock(translation, true, abstractDisplay.complete));
    }
    const fulltextProgress = createFulltextProgress(paper);
    if (fulltextProgress) {
      body.append(fulltextProgress);
    }
    body.append(createPaperEditor(paper));
    actions.append(
      createLibraryAction(downloadActionLabel(paper), () => downloadLibraryPaper(paper), !paper.downloadable || paper.isDownloaded),
      createLibraryAction(abstractActionLabel(paper), () => translateLibraryPaper(paper)),
      createLibraryAction(fulltextActionLabel(paper), () => translateFulltextPaper(paper), fulltextActionDisabled(paper)),
    );
    moreActions = createLibraryMoreActions([
      createLibraryAction("确认摘要来源", () => showAbstractCandidatesDialog(paper)),
      createLibraryAction("确认 Zotero 绑定", () => showZoteroBindingDialog(paper), !zoteroBindingNeedsReview(paper)),
      createLibraryAction("导出 BibTeX", (event) => exportLibraryPaperFile(paper, "bibtex", event.currentTarget)),
      createLibraryAction("导出 RIS", (event) => exportLibraryPaperFile(paper, "ris", event.currentTarget)),
      createLibraryAction("保存到 Zotero", (event) => saveLibraryPaperToZotero(paper, event.currentTarget)),
      createLibraryAction("同步译文回 Zotero", (event) => syncLibraryPaperToZotero(paper, event.currentTarget), !state.zotero.syncAvailable || zoteroBindingNeedsReview(paper)),
      createLibraryAction("导出原文摘要", (event) => exportLibraryPaperFile(paper, "markdown", event.currentTarget)),
      createLibraryAction("导出带译文摘要", (event) => exportLibraryPaperFile(paper, "bilingual_markdown", event.currentTarget), !zhTranslation(paper)),
      createLibraryAction("取消收藏", () => updateLibraryPaperFromPanel("unfavorite", paper)),
    ]);
  } else {
    actions.append(createLibraryAction("恢复", () => updateLibraryPaperFromPanel("unignore", paper)));
  }

  body.append(actions);
  if (moreActions) {
    body.append(moreActions);
  }
  item.append(header, body);
  return item;
}

function createPaperEditor(paper) {
  const editorWrap = document.createElement("details");
  editorWrap.className = "paper-editor-wrap";

  const summary = document.createElement("summary");
  summary.className = "paper-editor-toggle";
  summary.textContent = "管理信息";

  const editor = document.createElement("div");
  editor.className = "paper-editor";

  const status = document.createElement("select");
  status.className = "paper-editor-input";
  Object.entries(readingStatusLabels).forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    status.append(option);
  });
  status.value = paper.readingStatus || "";

  const tags = document.createElement("input");
  tags.className = "paper-editor-input";
  tags.type = "text";
  tags.placeholder = "标签，用逗号分隔";
  tags.value = Array.isArray(paper.tags) ? paper.tags.join(", ") : "";

  const note = document.createElement("textarea");
  note.className = "paper-editor-input";
  note.rows = 2;
  note.placeholder = "备注";
  note.value = paper.note || "";

  const save = document.createElement("button");
  save.className = "library-item-action";
  save.type = "button";
  save.textContent = "保存管理信息";
  save.addEventListener("click", () => updatePaperMetadata(paper, {
    readingStatus: status.value,
    tags: tags.value,
    note: note.value,
  }, save));

  editor.append(status, tags, note, save);
  editorWrap.append(summary, editor);
  return editorWrap;
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
  elements.exportFavoritesRis.disabled = favoriteCount === 0;
  elements.saveFavoritesZotero.disabled = favoriteCount === 0 || !state.zotero.available;
  elements.saveFavoritesZotero.title = state.zotero.message;
  elements.saveFavoritesZotero.textContent = state.zotero.available ? "保存到 Zotero" : "未检测 Zotero";
  elements.importZotero.disabled = !state.zotero.importAvailable;
  elements.importZotero.title = state.zotero.importMessage || state.zotero.message;
  elements.importZoteroPdf.disabled = !state.zotero.importAvailable;
  elements.importZoteroPdf.title = state.zotero.importMessage || state.zotero.message;
  elements.zoteroLinkSummary.textContent = zoteroHealthSummaryText(favoriteCount, zoteroHealthCounts());
  if (elements.zoteroAuditSummary) {
    elements.zoteroAuditSummary.textContent = zoteroAuditSummaryText();
  }
  elements.syncFavoritesZotero.disabled = favoriteCount === 0 || !state.zotero.syncAvailable;
  elements.syncFavoritesZotero.title = state.zotero.syncAvailable
    ? "会先自动关联 Zotero 中的同篇条目，再同步译文和标签。"
    : (state.zotero.syncMessage || state.zotero.message);
  elements.exportFavoritesMarkdown.disabled = favoriteCount === 0;
  elements.exportFavoritesBilingual.disabled = favoriteCount === 0;
  elements.batchTranslate.disabled = favoriteCount === 0;
  elements.refreshFavorites.disabled = favoriteCount === 0;
  elements.enrichAbstracts.disabled = favoriteCount === 0;
  elements.clearHistory.disabled = state.library.history.length === 0;
  const staleCount = state.library.favorites.filter((paper) => !abstractDisplayForPaper(paper).complete).length;
  elements.libraryRefreshNote.textContent = staleCount
    ? `${staleCount} 篇收藏摘要可能不完整，可补全 Zotero / 开放元数据，或导入 Alert 中你已可见的摘要。`
    : "收藏摘要看起来完整；Alert 导入仍可更新你已可见的订阅摘要。";
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
  const normalized = normalizeLibrary(library);
  state.library = normalized;
  updateSubscriptionStatus(normalized.subscription || {});
  syncResultsWithLibrary();
  renderLibrary();
  renderSubscriptionPanel();
  renderResearchRadar();
}

function radarStatLabel(key) {
  const labels = {
    favorites: "收藏",
    alertPending: "Alert 待审",
    alertAdoptable: "可采用",
    translationMissing: "待翻译",
    translationStale: "译文过期",
    zoteroReview: "Zotero 待确认",
    zoteroSynced: "已回写",
    openLagging: "开放源滞后",
    abstractPartial: "摘要不完整",
    abstractMissing: "无摘要",
  };
  return labels[key] || key;
}

function radarActionLabel(type) {
  const labels = {
    "alert-adopt": "采用 Alert",
    "review-source-health": "看源诊断",
    translate: "翻译摘要",
    "zotero-confirm": "确认绑定",
    "zotero-sync": "同步 Zotero",
    "read-later": "标为待读",
    ignore: "忽略",
  };
  return labels[type] || type || "处理";
}

function radarPaper(action) {
  return libraryPaperForKey(action && action.paperKey);
}

async function runRadarAction(action, button = null) {
  if (!action || !action.type) {
    return;
  }
  const paper = radarPaper(action);
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "处理中";
  }
  try {
    if (action.type === "alert-adopt") {
      await adoptAlertInboxEvents(action.eventId ? [action.eventId] : [], button);
    } else if (action.type === "translate") {
      if (!paper) {
        throw new Error("没有找到对应论文。");
      }
      await translatePaper(paper, button);
    } else if (action.type === "zotero-confirm") {
      if (!paper) {
        throw new Error("没有找到对应论文。");
      }
      showZoteroBindingDialog(paper);
    } else if (action.type === "zotero-sync") {
      if (!paper) {
        throw new Error("没有找到对应论文。");
      }
      await syncLibraryPaperToZotero(paper, button);
    } else if (action.type === "read-later") {
      if (!paper) {
        throw new Error("没有找到对应论文。");
      }
      const data = await requestJson("/api/library", {
        action: "update-paper",
        paper,
        paperKey: paper.paperKey,
        updates: { readingStatus: "unread" },
      });
      updateLibrary(data.library || state.library);
      setMessage("已标记为待读。", "success");
    } else if (action.type === "ignore") {
      if (!paper) {
        throw new Error("没有找到对应论文。");
      }
      await updatePaperLibrary("ignore", paper);
      setMessage("已忽略该论文。", "success");
    } else if (action.type === "review-source-health") {
      if (paper) {
        showAbstractCandidatesDialog(paper);
      }
      setMessage("这类条目通常说明 Alert 已有完整摘要，但开放元数据还没更新。", "success");
    }
    refreshResearchRadar(false).catch(() => {});
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function renderResearchRadar() {
  if (!elements.researchRadarStats) {
    return;
  }
  const radar = state.researchRadar || {};
  const stats = radar.stats || {};
  const digest = radar.digest || {};
  const actions = Array.isArray(radar.actions) ? radar.actions : [];
  const items = Array.isArray(digest.items) ? digest.items : [];

  if (elements.researchRadarStatus) {
    elements.researchRadarStatus.textContent = radar.generatedAt
      ? `生成于 ${formatDateTime(radar.generatedAt)} · digest ${digest.hash || "local"}`
      : "基于收藏、Alert、翻译和 Zotero 状态生成行动队列";
  }

  elements.researchRadarStats.replaceChildren();
  const statKeys = ["favorites", "alertPending", "alertAdoptable", "translationMissing", "translationStale", "zoteroReview", "zoteroSynced", "openLagging"];
  if (!radar.generatedAt) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = "暂无雷达统计";
    elements.researchRadarStats.append(empty);
  } else {
    statKeys.forEach((key) => {
      const chip = document.createElement("div");
      chip.className = "radar-stat";
      const label = document.createElement("span");
      label.textContent = radarStatLabel(key);
      const value = document.createElement("strong");
      value.textContent = String(stats[key] || 0);
      chip.append(label, value);
      elements.researchRadarStats.append(chip);
    });
  }

  if (elements.researchRadarBrief) {
    elements.researchRadarBrief.replaceChildren();
    const smart = radar.smartBrief || {};
    const brief = document.createElement("p");
    if (smart.status === "done" && smart.text) {
      brief.textContent = smart.text;
    } else if (smart.status === "failed") {
      brief.textContent = `智能简报失败：${smart.error || "模型没有返回内容"}`;
      brief.className = "is-error";
    } else {
      brief.textContent = digest.summary || "智能简报会在点击后生成。";
    }
    elements.researchRadarBrief.append(brief);
  }

  elements.researchRadarActions.replaceChildren();
  if (!actions.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = radar.generatedAt ? "暂无待办动作" : "刷新后显示行动队列";
    elements.researchRadarActions.append(empty);
  } else {
    actions.slice(0, 10).forEach((action) => {
      const card = document.createElement("article");
      card.className = "radar-action-item";
      const title = document.createElement("strong");
      title.textContent = action.title || "未命名论文";
      const reason = document.createElement("p");
      reason.textContent = action.reason || radarActionLabel(action.type);
      const button = document.createElement("button");
      button.className = "library-item-action";
      button.type = "button";
      button.textContent = radarActionLabel(action.type);
      button.addEventListener("click", () => runRadarAction(action, button));
      card.append(title, reason, button);
      elements.researchRadarActions.append(card);
    });
  }

  elements.researchRadarDigest.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = radar.generatedAt ? "暂无重点条目" : "刷新后显示重点条目";
    elements.researchRadarDigest.append(empty);
  } else {
    items.slice(0, 8).forEach((item) => {
      const card = document.createElement("article");
      card.className = "radar-digest-item";
      const title = document.createElement("strong");
      title.textContent = item.title || "Untitled";
      const meta = document.createElement("p");
      const lag = item.sourceHealth && item.sourceHealth.openLagging ? " · 开放源滞后" : "";
      const trans = item.translation && (item.translation.missing || item.translation.stale) ? " · 待翻译" : "";
      meta.textContent = `${item.sourceLabel || "来源"} · ${item.year || "年份未知"} · ${item.abstractCompleteness || "摘要未知"}${lag}${trans}`;
      const preview = document.createElement("small");
      preview.textContent = item.abstractPreview || "暂无摘要预览。";
      card.append(title, meta, preview);
      elements.researchRadarDigest.append(card);
    });
  }
}

async function refreshResearchRadar(smart = false) {
  const button = smart ? elements.smartResearchBrief : elements.refreshResearchRadar;
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = smart ? "生成中" : "刷新中";
  }
  try {
    const data = await requestJson("/api/research/radar", { smart, limit: 12 }, smart ? 90000 : 30000);
    state.researchRadar = data;
    if (data.library) {
      updateLibrary(data.library);
    } else {
      renderResearchRadar();
    }
    const smartFailed = data.smartBrief && data.smartBrief.status === "failed";
    if (smartFailed) {
      const errorText = data.smartBrief.error ? `：${data.smartBrief.error}` : "";
      setMessage(`研究雷达已刷新，但智能简报生成失败${errorText}`, "error");
    } else {
      setMessage(smart ? "研究雷达智能简报已更新。" : "研究雷达已刷新。", "success");
    }
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function updateZoteroStatus(zotero = {}) {
  const database = zotero.database || {};
  const bridge = zotero.bridge || {};
  state.zotero = {
    available: Boolean(zotero.available),
    importAvailable: Boolean(zotero.importAvailable),
    syncAvailable: Boolean(zotero.syncAvailable),
    bridgeAvailable: Boolean(bridge.available),
    bridgeCompatible: Boolean(bridge.compatible),
    bridgeVersion: bridge.version || "",
    expectedBridgeVersion: bridge.expectedVersion || "",
    bridgeDownloadUrl: bridge.downloadUrl || "/api/zotero/bridge-xpi",
    bridgeInstallHint: bridge.installHint || "",
    bridgeInstallSteps: Array.isArray(bridge.installSteps) ? bridge.installSteps : [],
    bridgePackage: bridge.package || {},
    bridgeCapabilities: bridge.capabilities && typeof bridge.capabilities === "object" ? bridge.capabilities : {},
    bridgeReason: bridge.reason || "",
    bridgeNextStep: bridge.nextStep || "",
    bridgePairing: bridge.pairing && typeof bridge.pairing === "object" ? bridge.pairing : {},
    message: zotero.message || (zotero.available
      ? "已检测到本机 Zotero，可直接保存题录。"
      : "未检测到本机 Zotero。可以导出 RIS 后导入 Zotero 或 EndNote。"),
    importMessage: database.message || "未检测到 Zotero 本地资料库。",
    syncMessage: bridge.message || "未检测到 PaperHunter Zotero Bridge。",
  };
  const bridgePackage = state.zotero.bridgePackage || {};
  const connectorText = state.zotero.available ? "保存可用" : "保存不可用";
  const importText = state.zotero.importAvailable ? "导入可用" : "导入不可用";
  const syncText = state.zotero.syncAvailable ? "回写可用" : "回写需 Bridge";
  elements.zoteroStatusNote.textContent = `${connectorText} · ${importText} · ${syncText}`;
  if (elements.downloadZoteroBridge) {
    elements.downloadZoteroBridge.href = bridgeDownloadHref();
    elements.downloadZoteroBridge.disabled = !bridgePackage.valid;
    elements.downloadZoteroBridge.setAttribute("aria-disabled", bridgePackage.valid ? "false" : "true");
    elements.downloadZoteroBridge.tabIndex = bridgePackage.valid ? 0 : -1;
    elements.downloadZoteroBridge.title = `${bridgePackage.message || "下载 PaperHunter Zotero Bridge XPI"} 下载后请覆盖安装并重启 Zotero。`;
  }
  elements.zoteroBridgeNote.textContent = state.zotero.syncAvailable
    ? `${state.zotero.syncMessage} ${bridgePairingStatusText(state.zotero.bridgePairing)}。${bridgeCapabilityLabels(state.zotero.bridgeCapabilities)}`
    : `${state.zotero.importMessage} 已关联不等于已回写；同步译文、标签和附件前需要启用并配对 PaperHunter Zotero Bridge。${state.zotero.syncMessage} ${state.zotero.bridgeNextStep || ""}`;
  if (elements.zoteroInstallNote) {
    if (state.zotero.syncAvailable) {
      const versionText = state.zotero.bridgeVersion ? `Bridge ${state.zotero.bridgeVersion}` : "Bridge";
      elements.zoteroInstallNote.textContent = `${versionText} 已可用，${bridgePairingStatusText(state.zotero.bridgePairing)}；不会删除、覆盖或移动 Zotero 原始条目、PDF、标签和用户笔记。`;
    } else if (state.zotero.bridgeAvailable && !state.zotero.bridgeCompatible) {
      elements.zoteroInstallNote.textContent = `${state.zotero.bridgeNextStep || `当前 Bridge 版本不兼容，请安装 ${state.zotero.expectedBridgeVersion || "最新版"}，然后重启 Zotero。`}`;
    } else if (!bridgePackage.valid) {
      elements.zoteroInstallNote.textContent = bridgePackage.message || "Bridge 安装包不可用，请重新构建 XPI。";
    } else {
      const steps = state.zotero.bridgeInstallSteps.length
        ? state.zotero.bridgeInstallSteps.join(" → ")
        : "下载 XPI → Zotero 插件管理器 → 从文件安装 → 重启 Zotero → 刷新状态";
      elements.zoteroInstallNote.textContent = `${steps}。Bridge 只回写 PaperHunter 管理的同步结果。`;
    }
  }
  renderLibrary();
  renderResults();
}

function sentenceJoin(parts) {
  return parts
    .map((part) => String(part || "").trim().replace(/[。.!?]+$/u, ""))
    .filter(Boolean)
    .join("。");
}

function downloadTextFile(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType || "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadBinaryFile(filename, base64Content, mimeType) {
  const bytes = Uint8Array.from(atob(base64Content), (char) => char.charCodeAt(0));
  const blob = new Blob([bytes], { type: mimeType || "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",").pop() : result);
    };
    reader.onerror = () => reject(reader.error || new Error("文件读取失败。"));
    reader.readAsDataURL(file);
  });
}

async function filesToAlertDocuments(files) {
  const selected = Array.from(files || []);
  return Promise.all(selected.map(async (file) => ({
    name: file.name || "alert.txt",
    type: file.type || "",
    contentBase64: await fileToBase64(file),
  })));
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (error) {
      // Some embedded browsers expose Clipboard API but deny write permission.
    }
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
  const abstractDisplay = abstractDisplayForPaper(paper);
  meta.append(
    createMetaChip(paper.sourceLabel || "Source"),
    createMetaChip(paper.category || paper.venue || "Paper"),
    createMetaChip(paper.published || String(paper.year || "")),
    createMetaChip(paper.paperId || paper.arxivId || ""),
    createMetaElement(abstractStatusText(paper, abstractDisplay), `abstract-source-chip is-${abstractStatusKind(paper, abstractDisplay)}`),
  );

  const title = document.createElement("h3");
  title.textContent = paper.title || "Untitled";

  const authors = document.createElement("p");
  authors.className = "authors";
  authors.textContent = paper.authors || "Unknown authors";

  const abstractWrap = document.createElement("div");
  abstractWrap.className = `abstract-block${abstractDisplay.complete ? "" : " is-fallback"}`;

  const abstractLabel = document.createElement("span");
  abstractLabel.className = "abstract-label";
  abstractLabel.textContent = abstractStatusText(paper, abstractDisplay);

  const abstract = document.createElement("p");
  abstract.className = "abstract";
  abstract.textContent = abstractDisplay.text;
  abstractWrap.append(abstractLabel, abstract);

  content.append(meta, title, authors, abstractWrap);

  const translation = zhTranslation(paper);
  if (translation) {
    content.append(createTranslationBlock(translation, false, abstractDisplay.complete));
  }

  const actions = document.createElement("div");
  actions.className = "paper-actions";

  const downloadButton = document.createElement("button");
  downloadButton.className = "paper-action";
  downloadButton.type = "button";
  downloadButton.dataset.index = String(index);
  downloadButton.textContent = downloadActionLabel(paper);
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
  favoriteButton.textContent = favoriteActionLabel(paper);
  favoriteButton.addEventListener("click", () => toggleFavorite(index, favoriteButton));

  const ignoreButton = document.createElement("button");
  ignoreButton.className = "paper-action";
  ignoreButton.type = "button";
  ignoreButton.textContent = "忽略";
  ignoreButton.addEventListener("click", () => ignorePaper(index, ignoreButton));

  const copyBibButton = document.createElement("button");
  copyBibButton.className = "paper-action";
  copyBibButton.type = "button";
  copyBibButton.textContent = "导出 BibTeX";
  copyBibButton.addEventListener("click", () => exportPaperFile(index, "bibtex", copyBibButton));

  const exportRisButton = document.createElement("button");
  exportRisButton.className = "paper-action";
  exportRisButton.type = "button";
  exportRisButton.textContent = "导出 RIS";
  exportRisButton.title = "导出可导入 Zotero 或 EndNote 的 RIS 题录";
  exportRisButton.addEventListener("click", () => exportPaperFile(index, "ris", exportRisButton));

  const saveZoteroButton = document.createElement("button");
  saveZoteroButton.className = "paper-action";
  saveZoteroButton.type = "button";
  saveZoteroButton.textContent = state.zotero.available ? "保存到 Zotero" : "未检测 Zotero";
  saveZoteroButton.disabled = !state.zotero.available;
  saveZoteroButton.title = state.zotero.message;
  saveZoteroButton.addEventListener("click", () => saveResultPaperToZotero(index, saveZoteroButton));

  const copyOriginalMarkdownButton = document.createElement("button");
  copyOriginalMarkdownButton.className = "paper-action";
  copyOriginalMarkdownButton.type = "button";
  copyOriginalMarkdownButton.textContent = "导出原文摘要";
  copyOriginalMarkdownButton.addEventListener("click", () => exportPaperFile(index, "markdown", copyOriginalMarkdownButton));

  const copyBilingualMarkdownButton = document.createElement("button");
  copyBilingualMarkdownButton.className = "paper-action";
  copyBilingualMarkdownButton.type = "button";
  copyBilingualMarkdownButton.textContent = "导出带译文摘要";
  copyBilingualMarkdownButton.disabled = !translation;
  copyBilingualMarkdownButton.title = translation ? "导出包含中英文摘要的 Markdown" : "先翻译摘要后可导出带译文摘要";
  copyBilingualMarkdownButton.addEventListener("click", () => exportPaperFile(index, "bilingual_markdown", copyBilingualMarkdownButton));

  const translateButton = document.createElement("button");
  translateButton.className = "paper-action";
  translateButton.type = "button";
  translateButton.textContent = abstractActionLabel(paper);
  translateButton.addEventListener("click", () => translateResultPaper(index, translateButton));

  const secondaryActions = document.createElement("div");
  secondaryActions.className = "paper-secondary-actions";
  secondaryActions.append(
    favoriteButton,
    translateButton,
    ignoreButton,
    copyBibButton,
    exportRisButton,
    saveZoteroButton,
    copyOriginalMarkdownButton,
    copyBilingualMarkdownButton,
  );

  actions.append(downloadButton, link, secondaryActions);
  card.append(content, actions);
  return card;
}

function renderResults() {
  elements.results.replaceChildren();
  elements.resultCount.textContent = String(state.results.length);
  elements.downloadAll.disabled = state.results.filter((paper) => paper.downloadable && !paper.isDownloaded).length === 0;
  elements.exportResults.disabled = state.results.length === 0;
  elements.exportResultsRis.disabled = state.results.length === 0;
  elements.saveResultsZotero.disabled = state.results.length === 0 || !state.zotero.available;
  elements.saveResultsZotero.title = state.zotero.message;
  elements.saveResultsZotero.textContent = state.zotero.available ? "保存到 Zotero" : "未检测 Zotero";

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

function timeoutMessageForRequest(url) {
  if (url.includes("/api/search")) {
    return "检索超时。可以减少数据源，或先只选 arXiv / CVF 试一次。";
  }
  if (url.includes("/api/settings/test")) {
    return "模型连接测试超时。请检查 Base URL、Endpoint、模型名称，或稍后再试。";
  }
  if (url.includes("/api/translate/fulltext")) {
    return "全文翻译任务创建超时。PDF 文本抽取或分块可能仍在进行，可以稍后刷新运行健康或再次点击续跑。";
  }
  if (url.includes("/api/translate")) {
    return "摘要翻译超时。可以稍后重试，或换用响应更快的模型。";
  }
  if (url.includes("/api/download")) {
    return "PDF 下载超时。可以稍后重试，或打开来源页面手动下载。";
  }
  if (url.includes("/api/abstract/enrich")) {
    return "摘要补全超时。开放元数据服务可能较慢，可以稍后再试。";
  }
  if (url.includes("/api/abstract/candidates") || url.includes("/api/abstract/confirm")) {
    return "摘要候选处理超时。可以稍后重试，或先导入 Alert 中你已可见的摘要。";
  }
  if (url.includes("/api/alert/import")) {
    return "Alert 导入超时。可以先减少粘贴内容，或稍后重试。";
  }
  if (url.includes("/api/diagnostics")) {
    return "运行健康检查超时。诊断只读不写入数据，可以稍后重试。";
  }
  if (url.includes("/api/backup")) {
    return "备份操作超时。请确认文件大小和本地服务状态后重试。";
  }
  return "请求超时，请稍后重试。";
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
      throw new Error(timeoutMessageForRequest(url));
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

async function requestGetJson(url, timeoutMs = 22000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      throw new Error(data.error || "请求失败。");
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(timeoutMessageForRequest(url));
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
  updateModelConfig({
    providers: data.modelProviders || [],
    apiTypes: data.modelApiTypes || {},
    settings: data.modelSettings || {},
  });
  updateLibrary(data.library || {});
  updateZoteroStatus(data.zotero || {});
}

async function refreshDiagnostics({ silent = false } = {}) {
  if (!elements.diagnosticsSummary) {
    return null;
  }
  const originalText = elements.refreshDiagnostics ? elements.refreshDiagnostics.textContent : "";
  if (elements.refreshDiagnostics) {
    elements.refreshDiagnostics.disabled = true;
    elements.refreshDiagnostics.textContent = "刷新中";
  }
  if (elements.diagnosticsStatusNote && !silent) {
    elements.diagnosticsStatusNote.textContent = "正在读取只读诊断...";
  }
  try {
    const data = await requestGetJson("/api/diagnostics", 30000);
    renderDiagnostics(data);
    return data;
  } catch (error) {
    if (elements.diagnosticsStatusNote) {
      elements.diagnosticsStatusNote.textContent = "诊断失败";
    }
    if (!silent) {
      setMessage(error.message, "error");
    }
    return null;
  } finally {
    if (elements.refreshDiagnostics) {
      elements.refreshDiagnostics.disabled = false;
      elements.refreshDiagnostics.textContent = originalText;
    }
  }
}

async function refreshModelSettings() {
  const response = await fetch("/api/settings");
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "模型设置读取失败。");
  }
  updateModelConfig(data);
}

async function saveModelSettings() {
  const originalText = elements.saveModel.textContent;
  elements.saveModel.disabled = true;
  elements.saveModel.textContent = "保存中";
  try {
    const data = await requestJson("/api/settings", { settings: currentModelForm() });
    updateModelConfig(data);
    setModelStatus("已保存", "success");
    setMessage("模型设置已保存。", "success");
  } catch (error) {
    setModelStatus("保存失败", "error");
    setMessage(error.message, "error");
  } finally {
    elements.saveModel.disabled = false;
    elements.saveModel.textContent = originalText;
  }
}

async function testModelConnection() {
  const originalText = elements.testModel.textContent;
  elements.testModel.disabled = true;
  elements.testModel.textContent = "测试中";
  setModelStatus("测试中");
  try {
    const data = await requestJson("/api/settings/test", { settings: currentModelForm() }, 60000);
    setModelStatus("连接正常", "success");
    const usageText = data.usage && Object.keys(data.usage).length
      ? ` Usage: ${JSON.stringify(data.usage)}`
      : "";
    const fallbackText = data.usage && data.usage.fallbackApiType
      ? ` 实际使用 fallback：${data.usage.fallbackApiType}。`
      : "";
    setMessage(`${data.message} 返回：${data.sample || "OK"}。${fallbackText}${usageText}`, "success");
    refreshDiagnostics({ silent: true });
  } catch (error) {
    setModelStatus("测试失败", "error");
    setMessage(error.message, "error");
  } finally {
    elements.testModel.disabled = false;
    elements.testModel.textContent = originalText;
  }
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

function exportFormatLabel(format) {
  if (format === "bibtex") {
    return "BibTeX";
  }
  if (format === "ris") {
    return "RIS";
  }
  if (format === "bilingual_markdown") {
    return "带译文摘要 Markdown";
  }
  return "原文摘要 Markdown";
}

function safeFilenamePart(text) {
  return String(text || "paper")
    .trim()
    .replace(/[\\/:*?"<>|]+/g, " ")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 90) || "paper";
}

function singlePaperExportFilename(paper, format) {
  const base = safeFilenamePart(paper.title || paper.paperId || paper.paperKey || "paper");
  if (format === "bibtex") {
    return `${base}.bib`;
  }
  if (format === "ris") {
    return `${base}.ris`;
  }
  if (format === "bilingual_markdown") {
    return `${base}.bilingual.md`;
  }
  return `${base}.abstract.md`;
}

async function exportLibraryPaperFile(paper, format, button = null) {
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "导出中";
  }
  try {
    const data = await exportPapers({ scope: "results", format, papers: [paper], download: false });
    downloadTextFile(singlePaperExportFilename(paper, format), data.content, data.mimeType);
    setMessage(`收藏 ${exportFormatLabel(format)} 已导出。`, "success");
    if (button) {
      button.textContent = "已导出";
      window.setTimeout(() => {
        button.textContent = originalText;
      }, 900);
    }
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.textContent = originalText;
    }
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function savePapersToZotero({ scope = "results", papers = state.results, button = null } = {}) {
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "保存中";
  }
  try {
    const data = await requestJson("/api/zotero/save", { scope, papers }, 15000);
    if (data.library) {
      updateLibrary(data.library);
      renderResults();
    }
    const linkText = data.linked || data.alreadyLinked
      ? ` 已关联 ${Number(data.linked || 0) + Number(data.alreadyLinked || 0)} 篇，可继续同步译文。`
      : (data.unmatched ? " 已保存，稍后可点“同步译文回 Zotero”自动尝试关联。" : "");
    setMessage(`已保存 ${data.saved || 0} 篇题录到 Zotero。${linkText}`, "success");
    if (button) {
      button.textContent = "已保存";
      window.setTimeout(() => {
        button.textContent = originalText;
      }, 900);
    }
  } catch (error) {
    setMessage(`${error.message} 也可以先导出 RIS 后导入 Zotero/EndNote。`, "error");
    if (button) {
      button.textContent = originalText;
    }
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function saveLibraryPaperToZotero(paper, button = null) {
  await savePapersToZotero({ scope: "results", papers: [paper], button });
}

async function importZoteroLibrary(requirePdf = false, button = null) {
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "导入中";
  }
  setMessage(requirePdf ? "正在从 Zotero 导入带 PDF 的条目..." : "正在从 Zotero 导入文献条目...");
  try {
    const data = await requestJson("/api/zotero/import", { requirePdf, limit: 120 }, 60000);
    updateLibrary(data.library || state.library);
    setMessage(`已从 Zotero 导入 ${data.imported || 0} 篇，更新 ${data.updated || 0} 篇，其中 ${data.withPdf || 0} 篇有 PDF。`, "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (button) {
      button.textContent = originalText;
      button.disabled = !state.zotero.importAvailable;
    }
  }
}

async function syncLibraryPaperToZotero(paper, button = null) {
  if (!paper) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "同步中";
  }
  try {
    const preview = await requestJson("/api/zotero/sync-preview", { paperKey: paper.paperKey, paper, includeFulltext: true }, 30000);
    if (preview.library) {
      updateLibrary(preview.library);
    }
    if (!preview.ready) {
      if (Array.isArray(preview.candidates) && preview.candidates.length) {
        showZoteroBindingDialog({
          ...paper,
          zoteroLink: {
            ...(paper.zoteroLink || {}),
            status: preview.status || "ambiguous",
            message: preview.message || "",
            candidates: preview.candidates,
          },
        });
      }
      setMessage(preview.message || "请先确认 Zotero 绑定，再同步。", "error");
      return;
    }
    const ok = await showAppConfirmDialog({
      title: "确认同步到 Zotero",
      intro: `将同步到 Zotero itemKey ${preview.itemKey}。`,
      details: [
        `会写入 ${preview.tags.length} 个 PaperHunter 标签。`,
        `会写入 ${preview.attachments} 个译文附件，并 upsert PaperHunter 管理的 note。`,
        "不会修改原始 PDF、用户笔记、用户标签或分类。",
      ],
      confirmText: "确认同步",
    });
    if (!ok) {
      setMessage("已取消 Zotero 同步。");
      return;
    }
    const data = await requestJson("/api/zotero/sync", { paperKey: paper.paperKey, paper, includeFulltext: true }, 30000);
    if (data.library) {
      updateLibrary(data.library);
      renderResults();
    }
    const linkedText = data.linked ? "已先自动关联 Zotero 条目，" : "";
    const bridgeAttachments = data.zotero && Number.isFinite(Number(data.zotero.attachments))
      ? Number(data.zotero.attachments)
      : (data.attachments || 0);
    const noteText = data.zotero && data.zotero.noteID ? `，note #${data.zotero.noteID}` : "";
    setMessage(`${linkedText}已同步到 Zotero：${data.tags.length} 个 PaperHunter 标签，${bridgeAttachments} 个译文附件${noteText}。`, "success");
    if (button) {
      button.textContent = "已同步";
      window.setTimeout(() => {
        button.textContent = originalText;
      }, 900);
    }
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.textContent = originalText;
    }
  } finally {
    if (button) {
      button.disabled = !state.zotero.syncAvailable || zoteroBindingNeedsReview(paper);
    }
  }
}

async function syncFavoritesToZotero() {
  const originalText = elements.syncFavoritesZotero.textContent;
  elements.syncFavoritesZotero.disabled = true;
  elements.syncFavoritesZotero.textContent = "预览中";
  setMessage("正在生成 Zotero 同步 dry-run 预览...");
  try {
    const preview = await requestJson("/api/zotero/sync-favorites-preview", { includeFulltext: true }, 60000);
    if (preview.library) {
      updateLibrary(preview.library);
      renderResults();
    }
    const ok = await showZoteroSyncPreviewDialog(preview);
    if (!ok) {
      setMessage("已取消 Zotero 批量同步。dry-run 未写入 Zotero。");
      return;
    }
    elements.syncFavoritesZotero.textContent = "同步中";
    setMessage("正在把已确认的 PaperHunter 摘要/译文同步回 Zotero...");
    const data = await requestJson("/api/zotero/sync-favorites", { includeFulltext: true }, 120000);
    if (data.library) {
      updateLibrary(data.library);
      renderResults();
    }
    const failedText = data.failed ? `，${data.failed} 篇失败` : "";
    const reviewParts = [];
    if (data.ambiguous) {
      reviewParts.push(`${data.ambiguous} 篇发现重复条目，需确认绑定`);
    }
    if (data.conflict) {
      reviewParts.push(`${data.conflict} 篇绑定冲突，已暂停回写`);
    }
    const reviewText = reviewParts.length ? `；${reviewParts.join("；")}` : "";
    setMessage(`已同步 ${data.synced || 0}/${data.eligible || 0} 篇已关联收藏${failedText}${reviewText}。未关联条目会先自动尝试匹配 Zotero，但不会自动合并或选错重复条目。`, data.failed || reviewParts.length ? "" : "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.syncFavoritesZotero.textContent = originalText;
    elements.syncFavoritesZotero.disabled = state.library.favorites.length === 0 || !state.zotero.syncAvailable;
  }
}

async function openFulltextFolder(paper, task, button) {
  if (!task || !task.file) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "打开中";
  }
  try {
    const data = await requestJson("/api/open/fulltext-folder", {
      paperKey: paper.paperKey,
      taskId: task.taskId,
      file: task.file,
    });
    setMessage(`已打开译文所在位置：${data.file || task.file}`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function translatePaper(paper, button) {
  if (!paper) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "翻译中";
  }
  setMessage("正在翻译摘要，内容会发送到你配置的模型接口...");
  try {
    const data = await requestJson("/api/translate/abstract", { paper, paperKey: paper.paperKey }, 90000);
    if (!paper.translations || typeof paper.translations !== "object") {
      paper.translations = {};
    }
    paper.translations.zh = data.translation;
    updateLibrary(data.library || state.library);
    setMessage("中文摘要已保存到本地论文记录。加入收藏后可在收件箱集中管理。", "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

async function translateLibraryPaper(paper) {
  await translatePaper(paper, null);
}

async function translateResultPaper(index, button) {
  await translatePaper(state.results[index], button);
}

function rememberFulltextTask(task) {
  if (!task || !task.paperKey) {
    return;
  }
  state.fulltextTasks[task.paperKey] = task;
  renderLibrary();
}

function stopFulltextPolling(paperKey) {
  const timer = state.fulltextPollers[paperKey];
  if (timer) {
    window.clearInterval(timer);
    delete state.fulltextPollers[paperKey];
  }
}

async function pollFulltextTask(task, paper) {
  if (!task || !task.taskId || !paper || !paper.paperKey) {
    return;
  }

  stopFulltextPolling(paper.paperKey);
  const poll = async () => {
    try {
      const data = await requestJson("/api/translate/fulltext/status", {
        taskId: task.taskId,
        paperKey: paper.paperKey,
      }, 20000);
      rememberFulltextTask(data.task);
      if (data.library) {
        updateLibrary(data.library);
      }

      const current = data.task || {};
      if (current.status === "done") {
        stopFulltextPolling(paper.paperKey);
        await refreshStatus();
        setMessage(`全文翻译完成：${current.file || current.filename}。已确认所有片段连续写入。`, "success");
        renderResults();
      } else if (current.status === "failed") {
        stopFulltextPolling(paper.paperKey);
        setMessage(`全文翻译暂停，可点击“继续全文翻译”续跑。${current.error || ""}`, "error");
      }
    } catch (error) {
      stopFulltextPolling(paper.paperKey);
      setMessage(error.message, "error");
    }
  };

  await poll();
  if (state.fulltextTasks[paper.paperKey] && ["queued", "running"].includes(state.fulltextTasks[paper.paperKey].status)) {
    state.fulltextPollers[paper.paperKey] = window.setInterval(poll, 2000);
  }
}

async function translateFulltextPaper(paper) {
  if (!paper) {
    return;
  }
  const existingTask = fulltextTaskForPaper(paper);
  const force = Boolean(existingTask && existingTask.status === "done");
  const userLibraryConsent = fulltextConsentRequired(paper);
  if (userLibraryConsent && !(await confirmUserLibraryFulltextConsent(paper))) {
    setMessage("已取消全文翻译。Zotero 本地资料库 PDF 需要确认后才会把提取文本发送给模型服务。");
    return;
  }
  setMessage("正在创建全文翻译任务：先提取 PDF 正文并分块，随后会后台逐块翻译。");
  try {
    const data = await requestJson("/api/translate/fulltext", { paper, paperKey: paper.paperKey, force, userLibraryConsent }, 60000);
    rememberFulltextTask(data.task);
    updateLibrary(data.library || state.library);
    setMessage("全文翻译任务已创建，正在后台翻译并校验片段连续性。");
    await pollFulltextTask(data.task, paper);
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function updatePaperMetadata(paper, updates, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "保存中";
  try {
    const data = await requestJson("/api/library", {
      action: "update-paper",
      paper,
      paperKey: paper.paperKey,
      updates,
    });
    updateLibrary(data.library || {});
    setMessage("阅读状态、标签和备注已保存。", "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = originalText;
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

async function enrichFavoriteAbstracts() {
  if (elements.enrichAbstracts.disabled) {
    return;
  }

  const originalText = elements.enrichAbstracts.textContent;
  elements.enrichAbstracts.disabled = true;
  elements.enrichAbstracts.textContent = "补全中";
  setMessage("正在补全收藏摘要，会优先使用 Zotero、本地可见记录和开放元数据...");

  try {
    const data = await requestJson("/api/abstract/enrich", { onlyIncomplete: true }, 120000);
    updateLibrary(data.library || state.library);
    const errorCount = data.errors ? Object.keys(data.errors).length : 0;
    const suffix = errorCount ? `，${errorCount} 篇暂时失败` : "";
    const diagnosticsText = data.diagnosticsUpdated ? `，更新 ${data.diagnosticsUpdated} 篇来源诊断` : "";
    const message = data.checked
      ? `已补全 ${data.enriched || 0}/${data.checked || 0} 篇收藏摘要${diagnosticsText}${suffix}。`
      : "没有需要补全的收藏摘要。";
    setMessage(message, errorCount ? "" : "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.enrichAbstracts.textContent = originalText;
    elements.enrichAbstracts.disabled = state.library.favorites.length === 0;
  }
}

function closeAlertImportDialog() {
  const existing = document.querySelector(".alert-import-backdrop");
  if (existing) {
    existing.remove();
  }
}

function showAlertImportDialog(defaultSource = null) {
  closeAlertImportDialog();

  const backdrop = document.createElement("div");
  backdrop.className = "zotero-binding-backdrop alert-import-backdrop";

  const dialog = document.createElement("section");
  dialog.className = "zotero-binding-dialog alert-import-dialog";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", "导入 Alert 摘要");

  const heading = document.createElement("div");
  heading.className = "zotero-binding-heading";
  const title = document.createElement("h3");
  title.textContent = "导入 Alert 摘要";
  const intro = document.createElement("p");
  intro.textContent = "粘贴你已可见的订阅 Alert、邮件或页面摘要文本。";
  heading.append(title, intro);

  const form = document.createElement("div");
  form.className = "alert-import-form";

  const sources = (state.subscription.sources || []).filter((source) => source && source.enabled);
  const selectedSource = defaultSource && defaultSource.id ? defaultSource : (sources[0] || null);

  const sourceSelectLabel = document.createElement("label");
  sourceSelectLabel.className = "alert-import-field";
  const sourceSelectText = document.createElement("span");
  sourceSelectText.textContent = "来源入口";
  const sourceSelect = document.createElement("select");
  sourceSelect.className = "paper-editor-input";
  sources.forEach((source) => {
    const option = document.createElement("option");
    option.value = source.id || "";
    option.textContent = subscriptionSourceLabel(source);
    sourceSelect.append(option);
  });
  const customOption = document.createElement("option");
  customOption.value = "__custom__";
  customOption.textContent = "自定义来源";
  sourceSelect.append(customOption);
  sourceSelect.value = selectedSource && selectedSource.id ? selectedSource.id : "__custom__";
  sourceSelectLabel.append(sourceSelectText, sourceSelect);

  const sourceLabel = document.createElement("label");
  sourceLabel.className = "alert-import-field";
  const sourceLabelText = document.createElement("span");
  sourceLabelText.textContent = "来源名称";
  const sourceInput = document.createElement("input");
  sourceInput.className = "paper-editor-input";
  sourceInput.type = "text";
  sourceInput.value = selectedSource ? subscriptionSourceLabel(selectedSource) : "ScienceDirect / WoS Alert";
  sourceInput.placeholder = "ScienceDirect / WoS Alert";
  sourceInput.readOnly = Boolean(selectedSource);
  sourceLabel.append(sourceLabelText, sourceInput);

  sourceSelect.addEventListener("change", () => {
    const source = sources.find((item) => item.id === sourceSelect.value);
    sourceInput.readOnly = Boolean(source);
    sourceInput.value = source ? subscriptionSourceLabel(source) : "";
    if (!source) {
      sourceInput.focus();
    }
  });

  const textLabel = document.createElement("label");
  textLabel.className = "alert-import-field";
  const textLabelText = document.createElement("span");
  textLabelText.textContent = "Alert 文本";
  const textarea = document.createElement("textarea");
  textarea.className = "paper-editor-input alert-import-textarea";
  textarea.placeholder = "Title: ...\nDOI: 10.xxxx/...\nAbstract: ...";
  textLabel.append(textLabelText, textarea);

  const fileLabel = document.createElement("label");
  fileLabel.className = "alert-import-field";
  const fileLabelText = document.createElement("span");
  fileLabelText.textContent = "Alert 文件";
  const fileInput = document.createElement("input");
  fileInput.className = "paper-editor-input";
  fileInput.type = "file";
  fileInput.multiple = true;
  fileInput.accept = ".txt,.text,.html,.htm,.eml,.ris,.csv,text/plain,text/html,message/rfc822,text/csv";
  const fileHint = document.createElement("small");
  fileHint.className = "alert-import-hint";
  fileHint.textContent = "可选择 ScienceDirect / WoS 导出的 TXT、HTML、EML、RIS 或 CSV；不会抓取未授权页面。";
  fileLabel.append(fileLabelText, fileInput, fileHint);

  const reviewLabel = document.createElement("label");
  reviewLabel.className = "checkbox-row alert-review-toggle";
  const reviewInput = document.createElement("input");
  reviewInput.type = "checkbox";
  reviewInput.checked = true;
  const reviewText = document.createElement("span");
  reviewText.textContent = "先加入 Alert 收件箱审阅，再由我确认采用";
  reviewLabel.append(reviewInput, reviewText);

  const openMetadataLabel = document.createElement("label");
  openMetadataLabel.className = "checkbox-row alert-review-toggle";
  const openMetadataInput = document.createElement("input");
  openMetadataInput.type = "checkbox";
  openMetadataInput.checked = false;
  const openMetadataText = document.createElement("span");
  openMetadataText.textContent = "同时查询开放元数据补全摘要";
  openMetadataLabel.append(openMetadataInput, openMetadataText);

  form.append(sourceSelectLabel, sourceLabel, reviewLabel, openMetadataLabel, fileLabel, textLabel);

  const footer = document.createElement("div");
  footer.className = "zotero-binding-footer";
  const cancel = document.createElement("button");
  cancel.className = "secondary-action compact-action";
  cancel.type = "button";
  cancel.textContent = "取消";
  cancel.addEventListener("click", closeAlertImportDialog);

  const submit = document.createElement("button");
  submit.className = "primary-action compact-action";
  submit.type = "button";
  submit.textContent = "导入";
  submit.addEventListener("click", async () => {
    const text = textarea.value.trim();
    const selectedFiles = Array.from(fileInput.files || []);
    if (!text && !selectedFiles.length) {
      setMessage("请先粘贴 Alert 文本，或选择 Alert 文件。", "error");
      textarea.focus();
      return;
    }
    const originalText = submit.textContent;
    submit.disabled = true;
    cancel.disabled = true;
    submit.textContent = "导入中";
    try {
      const files = await filesToAlertDocuments(selectedFiles);
      const data = await requestJson("/api/alert/import", {
        text,
        files,
        sourceId: sourceSelect.value === "__custom__" ? "" : sourceSelect.value,
        sourceLabel: sourceInput.value.trim() || "Alert 导入",
        enrich: true,
        reviewOnly: reviewInput.checked,
        checkOpenMetadata: openMetadataInput.checked,
      }, 90000);
      updateLibrary(data.library || state.library);
      renderResults();
      closeAlertImportDialog();
      const updatedText = data.updated ? `，更新 ${data.updated} 篇` : "";
      const ignoredText = data.ignoredUpdated ? `，更新已忽略 ${data.ignoredUpdated} 篇` : "";
      const reviewText = data.reviewOnly
        ? `，${(data.alertInboxEvents || []).length} 条进入 Alert 收件箱待审`
        : "，已直接加入收藏，不进入 Alert 收件箱";
      const report = data.parseReport || {};
      const health = data.sourceHealth || {};
      const reportText = report.documents ? `，解析 ${report.documents} 份文件 / ${report.parsed || 0} 条记录` : "";
      const lagText = health.openLagging ? `，${health.openLagging} 条开放元数据可能滞后` : "";
      const metadataText = data.checkOpenMetadata ? "，已查询开放元数据" : "，未查询开放元数据";
      setMessage(`已导入 ${data.imported || 0} 篇 Alert 论文${updatedText}${ignoredText}${reviewText}${metadataText}${reportText}${lagText}。`, "success");
    } catch (error) {
      setMessage(error.message, "error");
      submit.disabled = false;
      cancel.disabled = false;
      submit.textContent = originalText;
    }
  });
  footer.append(cancel, submit);

  dialog.append(heading, form, footer);
  backdrop.append(dialog);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) {
      closeAlertImportDialog();
    }
  });
  document.body.append(backdrop);
  textarea.focus();
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

async function exportCurrentResultsRis() {
  try {
    const data = await exportPapers({ scope: "results", format: "ris", papers: state.results });
    setMessage(`已导出 ${data.count} 篇当前结果，可导入 Zotero 或 EndNote。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function saveCurrentResultsToZotero() {
  await savePapersToZotero({ scope: "results", papers: state.results, button: elements.saveResultsZotero });
}

async function exportFavorites(format) {
  try {
    const data = await exportPapers({ scope: "favorites", format });
    const suffix = format === "ris" ? "，可导入 Zotero 或 EndNote" : "";
    setMessage(`已导出 ${data.count} 篇收藏论文${suffix}。`, "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function saveFavoritesToZotero() {
  await savePapersToZotero({ scope: "favorites", button: elements.saveFavoritesZotero });
}

async function batchTranslateFavorites() {
  const originalText = elements.batchTranslate.textContent;
  elements.batchTranslate.disabled = true;
  elements.batchTranslate.textContent = "翻译中";
  setMessage("正在批量翻译收藏摘要，只处理未翻译或可能过期的条目...");
  try {
    const data = await requestJson("/api/translate/batch", { scope: "favorites" }, 180000);
    updateLibrary(data.library || state.library);
    const usageText = data.usage && Object.keys(data.usage).length
      ? ` Usage: ${JSON.stringify(data.usage)}`
      : "";
    const failedText = data.failed ? `，${data.failed} 篇失败` : "";
    setMessage(`批量翻译完成：已翻译 ${data.translated || 0} 篇，跳过 ${data.skipped || 0} 篇${failedText}。${usageText}`, data.failed ? "" : "success");
    renderResults();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.batchTranslate.textContent = originalText;
    elements.batchTranslate.disabled = state.library.favorites.length === 0;
  }
}

async function exportWorkspaceBackup() {
  const originalText = elements.exportBackup.textContent;
  elements.exportBackup.disabled = true;
  elements.exportBackup.textContent = "导出中";
  try {
    window.open("/api/backup/export", "_blank", "noopener");
    setMessage("已开始导出全量备份。大文件可能需要等待几秒。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.exportBackup.disabled = false;
    elements.exportBackup.textContent = originalText;
  }
}

function backupCountText(preview = {}) {
  const files = preview.files || {};
  const counts = files.counts || {};
  const library = preview.library || {};
  const settings = preview.settings || {};
  return [
    library.present ? `收藏/库：${diagnosticNumber(library.favorites)} 收藏，${diagnosticNumber(library.papers)} 论文` : "",
    settings.present ? `设置：${settings.provider || "custom"} · ${settings.model || "未设置模型"}` : "",
    `全文任务文件：${diagnosticNumber(counts.tasks)}`,
    `下载 PDF：${diagnosticNumber(counts.downloaded)}`,
    `译文文件：${diagnosticNumber(counts.translated)}`,
  ].filter(Boolean).join(" · ");
}

function renderBackupPreviewDialog(preview, fileName) {
  const { dialog } = createZoteroDialogShell({
    title: "导入备份预览",
    intro: "先确认备份包内容和影响范围。正式导入前会创建本机恢复点；导入失败会自动回滚。",
    label: "导入备份预览",
    className: "backup-preview-dialog",
  });

  const stats = document.createElement("div");
  stats.className = "zotero-sync-preview-stats backup-preview-stats";
  const files = preview.files || {};
  const counts = files.counts || {};
  [
    ["论文", diagnosticNumber((preview.library || {}).papers)],
    ["任务", diagnosticNumber(counts.tasks)],
    ["PDF", diagnosticNumber(counts.downloaded)],
    ["译文", diagnosticNumber(counts.translated)],
  ].forEach(([labelText, value]) => stats.append(createZoteroStat(labelText, value)));

  const summary = document.createElement("div");
  summary.className = "backup-preview-summary";
  [
    ["文件", fileName || "PaperHunter 备份包"],
    ["创建时间", (preview.manifest || {}).createdAt || "未知"],
    ["导入策略", "merge：合并到当前库，不清空现有数据"],
    ["影响", backupCountText(preview)],
  ].forEach(([labelText, value]) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = labelText;
    const text = document.createElement("strong");
    text.textContent = value;
    row.append(label, text);
    summary.append(row);
  });

  const warnings = document.createElement("div");
  warnings.className = "zotero-bridge-checklist backup-preview-warnings";
  const warningItems = Array.isArray(preview.warnings) ? preview.warnings : [];
  warningItems.forEach((text) => {
    const item = document.createElement("p");
    item.textContent = text;
    warnings.append(item);
  });

  const footer = document.createElement("div");
  footer.className = "zotero-binding-footer";
  const cancel = document.createElement("button");
  cancel.className = "secondary-action compact-action";
  cancel.type = "button";
  cancel.textContent = "取消";
  cancel.addEventListener("click", () => {
    state.pendingBackupImport = null;
    closeZoteroManagementDialog();
    setMessage("已取消备份导入。");
  });
  const confirm = document.createElement("button");
  confirm.className = "secondary-action compact-action";
  confirm.type = "button";
  confirm.textContent = "创建恢复点并导入";
  confirm.addEventListener("click", () => confirmWorkspaceBackupImport(confirm));
  footer.append(cancel, confirm);

  dialog.append(stats, summary, warnings, footer);
}

async function confirmWorkspaceBackupImport(button) {
  const pending = state.pendingBackupImport;
  if (!pending || !pending.contentBase64) {
    setMessage("没有待导入的备份包，请重新选择文件。", "error");
    closeZoteroManagementDialog();
    return;
  }
  const restore = setDiagnosticButtonBusy(button, "导入中");
  try {
    const data = await requestJson("/api/backup/import", {
      contentBase64: pending.contentBase64,
      strategy: "merge",
    }, 120000);
    closeZoteroManagementDialog();
    state.pendingBackupImport = null;
    updateLibrary(data.library || state.library);
    updateModelConfig({ settings: data.settings || state.modelSettings });
    const reminder = data.bridgeReminder && typeof data.bridgeReminder === "object" ? data.bridgeReminder : {};
    const restorePointText = data.restorePoint && data.restorePoint.id ? ` 已创建恢复点 ${data.restorePoint.id}。` : "";
    if (data.bridgeReinstallRequired || reminder.required) {
      await refreshStatus();
      setMessage(`${reminder.message || "备份已导入，Bridge 配对已更新，请重新下载并覆盖安装当前 XPI。"}${restorePointText} API Key 不会从备份恢复，请按需重新填写。`, "success");
      if (elements.zoteroInstallNote) {
        elements.zoteroInstallNote.textContent = reminder.message || "备份导入后 Bridge token 已更新，请重新下载 XPI 并覆盖安装到 Zotero。";
      }
    } else {
      setMessage(`备份已导入。${restorePointText} API Key 不会从备份恢复，请按需重新填写。`, "success");
    }
    renderResults();
  } catch (error) {
    setMessage(`${error.message} 如果导入已经开始，后端会尝试自动回滚到导入前恢复点。`, "error");
  } finally {
    restore();
  }
}

async function importWorkspaceBackup(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) {
    return;
  }
  setMessage("正在解析备份包...");
  try {
    const contentBase64 = await fileToBase64(file);
    const preview = await requestJson("/api/backup/preview", { contentBase64 }, 60000);
    state.pendingBackupImport = {
      fileName: file.name || "paperhunter-backup.zip",
      contentBase64,
      preview,
    };
    renderBackupPreviewDialog(preview, file.name || "paperhunter-backup.zip");
    setMessage("备份预览已生成，请确认后再导入。", "success");
  } catch (error) {
    state.pendingBackupImport = null;
    setMessage(error.message, "error");
  } finally {
    event.target.value = "";
  }
}

async function exportPaperFile(index, format, button = null) {
  const paper = state.results[index];
  if (!paper || (button && button.disabled)) {
    return;
  }
  const originalText = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "导出中";
  }
  try {
    const data = await exportPapers({ scope: "results", format, papers: [paper], download: false });
    downloadTextFile(singlePaperExportFilename(paper, format), data.content, data.mimeType);
    setMessage(`${exportFormatLabel(format)} 已导出。`, "success");
    if (button) {
      button.textContent = "已导出";
      window.setTimeout(() => {
        button.textContent = originalText;
      }, 900);
    }
  } catch (error) {
    setMessage(error.message, "error");
    if (button) {
      button.textContent = originalText;
    }
  } finally {
    if (button) {
      button.disabled = false;
    }
  }
}

async function saveResultPaperToZotero(index, button = null) {
  const paper = state.results[index];
  if (!paper || (button && button.disabled)) {
    return;
  }
  await savePapersToZotero({ scope: "results", papers: [paper], button });
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
    const messageParts = [`找到 ${state.results.length} 篇论文${countText}`];
    if (sourceBreakdown) {
      messageParts.push(`来源分布：${sourceBreakdown}`);
    }
    if (data.hiddenIgnoredCount) {
      messageParts.push(`已隐藏 ${data.hiddenIgnoredCount} 篇忽略论文`);
    }
    if (errorCount) {
      messageParts.push(`有 ${errorCount} 个来源暂时失败${issueText ? `：${issueText}` : ""}`);
    }
    setMessage(`${sentenceJoin(messageParts)}。`, state.results.length ? "success" : "");
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
elements.exportResultsRis.addEventListener("click", exportCurrentResultsRis);
elements.saveResultsZotero.addEventListener("click", saveCurrentResultsToZotero);
elements.exportFavoritesBib.addEventListener("click", () => exportFavorites("bibtex"));
elements.exportFavoritesRis.addEventListener("click", () => exportFavorites("ris"));
elements.saveFavoritesZotero.addEventListener("click", saveFavoritesToZotero);
elements.importZotero.addEventListener("click", () => importZoteroLibrary(false, elements.importZotero));
elements.importZoteroPdf.addEventListener("click", () => importZoteroLibrary(true, elements.importZoteroPdf));
elements.syncFavoritesZotero.addEventListener("click", syncFavoritesToZotero);
elements.manageZoteroBindings.addEventListener("click", showZoteroBindingManager);
elements.showZoteroAudit.addEventListener("click", showZoteroAuditDialog);
elements.showZoteroBridgeHelp.addEventListener("click", showZoteroBridgeHelpDialog);
elements.exportFavoritesMarkdown.addEventListener("click", () => exportFavorites("markdown"));
elements.exportFavoritesBilingual.addEventListener("click", () => exportFavorites("bilingual_markdown"));
elements.batchTranslate.addEventListener("click", batchTranslateFavorites);
elements.refreshFavorites.addEventListener("click", refreshFavoritesMetadata);
elements.enrichAbstracts.addEventListener("click", enrichFavoriteAbstracts);
elements.importAlert.addEventListener("click", () => showAlertImportDialog());
if (elements.importSubscriptionAlert) {
  elements.importSubscriptionAlert.addEventListener("click", () => showAlertImportDialog());
}
if (elements.adoptAlertInbox) {
  elements.adoptAlertInbox.addEventListener("click", () => adoptAlertInboxEvents());
}
if (elements.refreshAlertInbox) {
  elements.refreshAlertInbox.addEventListener("click", refreshAlertInbox);
}
if (elements.alertInboxFilter) {
  elements.alertInboxFilter.addEventListener("change", () => {
    state.alertInboxFilter = elements.alertInboxFilter.value || "active";
    renderAlertInboxPanel();
  });
}
if (elements.addSubscriptionSource) {
  elements.addSubscriptionSource.addEventListener("click", addCustomSubscriptionSource);
}
if (elements.refreshResearchRadar) {
  elements.refreshResearchRadar.addEventListener("click", () => refreshResearchRadar(false));
}
if (elements.smartResearchBrief) {
  elements.smartResearchBrief.addEventListener("click", () => refreshResearchRadar(true));
}
if (elements.refreshDiagnostics) {
  elements.refreshDiagnostics.addEventListener("click", () => refreshDiagnostics());
}
if (elements.copyDiagnostics) {
  elements.copyDiagnostics.addEventListener("click", copyDiagnosticsSummary);
}
if (elements.showTaskCenter) {
  elements.showTaskCenter.addEventListener("click", showTaskCenterDialog);
}
elements.clearHistory.addEventListener("click", clearHistory);
elements.modelApiType.addEventListener("change", () => {
  elements.modelEndpoint.value = endpointForApiType(elements.modelApiType.value);
  updateModelPreview();
});
elements.modelBaseUrl.addEventListener("input", updateModelPreview);
elements.modelEndpoint.addEventListener("input", updateModelPreview);
if (elements.privatePdfMode) {
  elements.privatePdfMode.addEventListener("change", updateModelPreview);
}
if (elements.selfHostedModel) {
  elements.selfHostedModel.addEventListener("change", updateModelPreview);
}
elements.saveModel.addEventListener("click", saveModelSettings);
elements.testModel.addEventListener("click", testModelConnection);
elements.exportBackup.addEventListener("click", exportWorkspaceBackup);
elements.importBackup.addEventListener("change", importWorkspaceBackup);
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
refreshModelSettings().catch(() => {});
refreshDiagnostics({ silent: true }).catch(() => {});
