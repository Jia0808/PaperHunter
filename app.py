import gzip
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
import base64
import csv
import secrets
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html import escape, unescape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock, Thread
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import arxiv
import requests


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"


def runtime_path(env_name: str, default: Path) -> Path:
    value = os.environ.get(env_name, "").strip()
    if not value:
        return default
    return Path(value).expanduser().resolve()


def runtime_int(env_name: str, default: int, minimum: int = 1, maximum: int = 65535) -> int:
    try:
        value = int(str(os.environ.get(env_name, "")).strip())
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


DOWNLOAD_DIR = runtime_path("DOWNLOAD_DIR", ROOT_DIR / "downloaded_papers")
TRANSLATED_DIR = runtime_path("TRANSLATED_DIR", ROOT_DIR / "translated_papers")
CACHE_DIR = runtime_path("CACHE_DIR", ROOT_DIR / ".cache")
DATA_DIR = runtime_path("DATA_DIR", ROOT_DIR / "data")
FULLTEXT_TASK_DIR = runtime_path("FULLTEXT_TASK_DIR", DATA_DIR / "fulltext_tasks")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
TRANSLATED_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
FULLTEXT_TASK_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_RESTORE_POINT_DIR = CACHE_DIR / "backup-restore-points"

HOST = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = runtime_int("PORT", 8000)
MAX_RESULTS_LIMIT = 50
PER_SOURCE_LIMIT_MAX = 20
TITLE_TEXT_LIMIT = 220
AUTHOR_TEXT_LIMIT = 180
ABSTRACT_TEXT_LIMIT = 460
SEARCH_TIMEOUT_SECONDS = 9
CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 6
REQUEST_HEADERS = {
    "User-Agent": "PaperHunter/1.0 (local research PDF downloader)"
}
ZOTERO_CONNECTOR_SAVE_ITEMS_URL = "http://127.0.0.1:23119/connector/saveItems"
ZOTERO_CONNECTOR_PING_URL = "http://127.0.0.1:23119/connector/ping"
ZOTERO_CONNECTOR_TIMEOUT_SECONDS = 4
ZOTERO_BRIDGE_PING_URL = "http://127.0.0.1:23119/paperhunter/ping"
ZOTERO_BRIDGE_PAIRING_CHECK_URL = "http://127.0.0.1:23119/paperhunter/pairing-check"
ZOTERO_BRIDGE_SYNC_URL = "http://127.0.0.1:23119/paperhunter/sync"
ZOTERO_BRIDGE_TIMEOUT_SECONDS = 12
ZOTERO_BRIDGE_DIR = ROOT_DIR / "zotero-bridge"
ZOTERO_BRIDGE_MANIFEST_PATH = ZOTERO_BRIDGE_DIR / "manifest.json"
ZOTERO_BRIDGE_BOOTSTRAP_PATH = ZOTERO_BRIDGE_DIR / "bootstrap.js"
ZOTERO_BRIDGE_XPI_PATH = ROOT_DIR / "zotero-bridge" / "paperhunter-zotero-bridge.xpi"
ZOTERO_BRIDGE_DOWNLOAD_URL = "/api/zotero/bridge-xpi"
ZOTERO_BRIDGE_VERSION = "0.2.2"
ZOTERO_BRIDGE_PROTOCOL_VERSION = 1
ZOTERO_BRIDGE_TOKEN_PLACEHOLDER = "__PAPERHUNTER_BRIDGE_TOKEN__"
ZOTERO_MANAGED_NOTE_MARKER = "PaperHunter 同步结果"
ZOTERO_BRIDGE_INSTALL_STEPS = [
    "从当前 PaperHunter 页面下载 Bridge XPI",
    "在 Zotero 中打开 Tools → Add-ons",
    "点击齿轮菜单，选择 Install Add-on From File",
    "选择刚下载的 paperhunter-zotero-bridge.xpi 并覆盖安装",
    "重启 Zotero，然后刷新 PaperHunter 状态",
]
ZOTERO_DATA_DIR = runtime_path("ZOTERO_DATA_DIR", Path.home() / "Zotero")
ZOTERO_DB_PATH = runtime_path("ZOTERO_DB_PATH", ZOTERO_DATA_DIR / "zotero.sqlite")
ZOTERO_STORAGE_DIR = runtime_path("ZOTERO_STORAGE_DIR", ZOTERO_DATA_DIR / "storage")
SOURCE_LABELS = {
    "arxiv": "arXiv",
    "semantic": "Semantic Scholar",
    "cvf": "CVF Open Access",
    "acl": "ACL Anthology",
    "openreview": "OpenReview",
    "chinarxiv": "ChinaRxiv / ChinaXiv",
    "sciopen": "SciOpen",
    "nso": "National Science Open",
    "alert": "Alert 导入",
    "zotero": "Zotero",
}
EXTERNAL_GATEWAYS = {
    "google_scholar": "Google Scholar",
    "cnki": "CNKI 知网",
    "wanfang": "万方数据",
    "xmol": "X-MOL",
    "nso": "National Science Open",
}
OPEN_PDF_HOSTS = {
    "openreview.net",
    "arxiv.org",
    "openaccess.thecvf.com",
    "aclanthology.org",
    "proceedings.mlr.press",
    "jmlr.org",
    "chinarxiv.org",
    "chinaxiv.org",
    "f004.backblazeb2.com",
    "sciopen.com",
    "nso-journal.org",
}
FIELD_QUERY_TERMS = {
    "ai-ml": "artificial intelligence machine learning deep learning neural network language vision model",
    "cs": "computer science algorithm software systems computing database security network",
    "math": "mathematics theorem proof optimization algebra analysis geometry probability",
    "physics": "physics astronomy astrophysics quantum cosmology optics particle",
    "stats": "statistics statistical modeling inference probability regression causal",
    "eess": "electrical engineering signal processing image video sensor communication",
    "bio": "biology biomedical medicine neuroscience genomics healthcare clinical",
    "econ-fin": "economics finance econometrics market risk policy trading",
}
FIELD_CATEGORY_PREFIXES = {
    "ai-ml": ("cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.RO", "stat.ML"),
    "cs": ("cs.",),
    "math": ("math.",),
    "physics": ("physics.", "astro-ph", "cond-mat", "gr-qc", "hep-", "nucl-", "quant-ph"),
    "stats": ("stat.",),
    "eess": ("eess.",),
    "bio": ("q-bio.",),
    "econ-fin": ("econ.", "q-fin."),
}
SOURCE_FIELD_HINTS = {
    "cvf": {"ai-ml", "cs"},
    "acl": {"ai-ml", "cs"},
}
INTENT_QUERY_TERMS = {
    "general": "",
    "latest": "",
    "survey": "survey review overview taxonomy",
    "benchmark": "benchmark dataset evaluation leaderboard",
    "method": "method framework model approach algorithm",
    "application": "application case study real world deployment",
}
CVF_ENDPOINTS = [
    ("CVPR 2025", "https://openaccess.thecvf.com/CVPR2025?day=all"),
    ("CVPR 2024", "https://openaccess.thecvf.com/CVPR2024?day=all"),
    ("ICCV 2025", "https://openaccess.thecvf.com/ICCV2025?day=all"),
    ("ICCV 2023", "https://openaccess.thecvf.com/ICCV2023?day=all"),
    ("ECCV 2024", "https://openaccess.thecvf.com/ECCV2024?day=all"),
]
CHINARXIV_FEEDS = [
    "https://chinarxiv.org/feed/atom.xml",
    "https://chinarxiv.org/feed/rss.xml",
]
NSO_SOLR_URL = "https://www.nso-journal.org/index.php"
NSO_BASE_URL = "https://www.nso-journal.org"
ACL_BIB_URL = "https://aclanthology.org/anthology+abstracts.bib.gz"
ACL_BIB_CACHE = CACHE_DIR / "acl-anthology-abstracts.bib.gz"
ACL_CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
ACL_ENTRY_CACHE: list[dict] | None = None
LIBRARY_PATH = runtime_path("LIBRARY_PATH", DATA_DIR / "library.json")
SETTINGS_PATH = runtime_path("SETTINGS_PATH", DATA_DIR / "settings.json")
LIBRARY_LOCK = RLock()
LIBRARY_SCHEMA_VERSION = 3
SETTINGS_SCHEMA_VERSION = 1
TRANSLATION_PROMPT_VERSION = "abstract-zh-v1"
MAX_SEARCH_HISTORY = 30
MAX_ZOTERO_AUDIT_EVENTS = 120
MAX_ALERT_IMPORT_HISTORY = 80
MAX_ALERT_INBOX_EVENTS = 200
MAX_ALERT_BATCH_DOCUMENTS = 24
MAX_RESEARCH_RADAR_ITEMS = 12
FULLTEXT_TASK_SCHEMA_VERSION = 1
FULLTEXT_PROMPT_VERSION = "fulltext-zh-v2"
FULLTEXT_CHUNK_SIZE = 1400
FULLTEXT_MODEL_READ_TIMEOUT_SECONDS = 120
FULLTEXT_TASK_THREADS: dict[str, Thread] = {}
FULLTEXT_TASK_LOCK = RLock()
API_TYPE_ENDPOINTS = {
    "responses": "/v1/responses",
    "chat_completions": "/v1/chat/completions",
    "anthropic_messages": "/v1/messages",
}
MODEL_PROVIDER_PRESETS = [
    {
        "id": "apixin_gpt",
        "name": "APIXIN GPT 中转",
        "domain": "apixin.top",
        "recommended": True,
        "apiType": "responses",
        "baseUrl": "https://apixin.top",
        "endpoint": "/v1/responses",
        "defaultModel": "gpt-5.5",
        "badges": ["推荐", "GPT", "Responses"],
        "description": "适合快速启用 GPT 摘要翻译，配置简单。",
    },
    {
        "id": "apixin_multi",
        "name": "APIXIN 多模型中转",
        "domain": "apixin.cn",
        "recommended": False,
        "apiType": "chat_completions",
        "baseUrl": "https://apixin.cn",
        "endpoint": "/v1/chat/completions",
        "defaultModel": "",
        "badges": ["多模型", "Chat Completions"],
        "description": "适合需要 Claude、DeepSeek、GPT 等多模型选择的用户。",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "domain": "api.deepseek.com",
        "recommended": False,
        "apiType": "chat_completions",
        "baseUrl": "https://api.deepseek.com",
        "endpoint": "/v1/chat/completions",
        "defaultModel": "deepseek-chat",
        "badges": ["自带 Key", "Chat Completions"],
        "description": "适合已有 DeepSeek API Key 的用户。",
    },
    {
        "id": "claude",
        "name": "Claude",
        "domain": "api.anthropic.com",
        "recommended": False,
        "apiType": "anthropic_messages",
        "baseUrl": "https://api.anthropic.com",
        "endpoint": "/v1/messages",
        "defaultModel": "",
        "badges": ["自带 Key", "Messages API"],
        "description": "适合已有 Anthropic / Claude API Key 的用户。",
    },
    {
        "id": "custom",
        "name": "自定义接口",
        "domain": "custom",
        "recommended": False,
        "apiType": "chat_completions",
        "baseUrl": "",
        "endpoint": "/v1/chat/completions",
        "defaultModel": "",
        "badges": ["高级", "协议自选"],
        "description": "适合 Qwen、Kimi、智谱、OpenRouter、SiliconFlow、火山方舟等兼容接口。",
    },
]
PAPER_SNAPSHOT_FIELDS = (
    "title",
    "authors",
    "published",
    "year",
    "pdfUrl",
    "localPdfPath",
    "localPdfFilename",
    "access",
    "entryUrl",
    "pageUrl",
    "arxivId",
    "paperId",
    "doi",
    "source",
    "sourceLabel",
    "venue",
    "category",
    "abstract",
    "fullAbstract",
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
    "downloadable",
    "isDownloaded",
    "readingStatus",
    "note",
    "tags",
    "translations",
    "fulltextTranslations",
    "zotero",
    "zoteroLink",
    "zoteroSync",
)
ZOTERO_LINK_STATUSES = {"unlinked", "auto", "confirmed", "ambiguous", "conflict", "missing"}
ZOTERO_AUTO_LINK_STATUSES = {"auto", "confirmed"}
ZOTERO_BLOCKED_LINK_STATUSES = {"ambiguous", "conflict", "missing"}
ZOTERO_MATCH_THRESHOLD = 70
ZOTERO_AMBIGUOUS_SCORE_GAP = 4
ZOTERO_BRIDGE_CAPABILITIES = {
    "canUpsertManagedNote": True,
    "canApplyPaperHunterTags": True,
    "canLinkMarkdownAttachment": True,
    "preserveUserContent": True,
    "requiresPairingToken": True,
}
ABSTRACT_COMPLETENESS_VALUES = {"complete", "partial", "missing", "unknown", "needs_access"}
ABSTRACT_DIAGNOSTIC_STATUSES = {"selected", "available", "current", "empty", "failed", "skipped"}
ABSTRACT_SOURCE_LABELS = {
    "existing": "现有记录",
    "source": "来源元数据",
    "source-refresh": "来源刷新",
    "alert": "Alert 导入",
    "zotero": "Zotero",
    "crossref": "Crossref",
    "openalex": "OpenAlex",
    "semantic": "Semantic Scholar",
}
ABSTRACT_SOURCE_PRIORITY = {
    "zotero": 95,
    "alert": 88,
    "crossref": 78,
    "openalex": 76,
    "semantic": 72,
    "source-refresh": 68,
    "source": 55,
    "existing": 50,
}
OPEN_METADATA_ABSTRACT_SOURCES = {"semantic", "crossref", "openalex"}
ALERT_SOURCE_HEALTH_STATUSES = {
    "unknown",
    "alert_complete",
    "alert_partial",
    "alert_missing",
    "open_has_abstract",
    "open_lagging",
    "open_missing",
    "open_failed",
}
ABSTRACT_METADATA_FIELDS = (
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
)
STATE_PRESERVE_FIELDS = (
    "readingStatus",
    "note",
    "tags",
    "translations",
    "fulltextTranslations",
    "isDownloaded",
    "downloadable",
    "localPdfPath",
    "localPdfFilename",
    "access",
    "zotero",
    "zoteroLink",
    "zoteroSync",
    "abstractLocked",
    "abstractConfirmedAt",
    "abstractConfirmedBy",
    "abstractAudit",
)
ABSTRACT_LOCKED_CONTENT_FIELDS = (
    "abstract",
    "fullAbstract",
    "abstractSource",
    "abstractSourceLabel",
    "abstractFetchedAt",
    "abstractCompleteness",
    "abstractAccessMode",
)
SUBSCRIPTION_AUTHORIZATION_MODES = {"manual-alert", "official-api", "email-import", "zotero-library", "custom"}
SUBSCRIPTION_SOURCE_TYPES = {"publisher-alert", "index-alert", "library", "custom"}
SUBSCRIPTION_SOURCE_PRESETS = [
    {
        "id": "sciencedirect-alert",
        "name": "ScienceDirect Alert",
        "provider": "sciencedirect",
        "sourceLabel": "ScienceDirect Alert",
        "sourceType": "publisher-alert",
        "authorizationMode": "manual-alert",
        "enabled": True,
        "status": "ready",
        "policy": "Uses only user-visible alert text or official user-authorized exports.",
        "freshnessNote": "Publisher alerts can be newer than open metadata indexes.",
    },
    {
        "id": "wos-alert",
        "name": "Web of Science Alert",
        "provider": "wos",
        "sourceLabel": "WoS Alert",
        "sourceType": "index-alert",
        "authorizationMode": "manual-alert",
        "enabled": True,
        "status": "ready",
        "policy": "Uses only user-visible alert text or official user-authorized exports.",
        "freshnessNote": "WoS/Clarivate alert updates may arrive before open metadata catches up.",
    },
    {
        "id": "zotero-library",
        "name": "Zotero Library",
        "provider": "zotero",
        "sourceLabel": "Zotero",
        "sourceType": "library",
        "authorizationMode": "zotero-library",
        "enabled": True,
        "status": "ready",
        "policy": "Reads the local Zotero library already available to the user.",
        "freshnessNote": "Zotero abstracts are treated as authorized candidates, not a second binding system.",
    },
    {
        "id": "custom-alert",
        "name": "Custom Alert",
        "provider": "custom",
        "sourceLabel": "Custom Alert",
        "sourceType": "custom",
        "authorizationMode": "manual-alert",
        "enabled": True,
        "status": "ready",
        "policy": "Uses pasted text that the user can already view.",
        "freshnessNote": "Use this for publisher, society, email, or institutional alerts not listed above.",
    },
]


def compact_text(value: str, limit: int) -> str:
    value = " ".join(str(value).split())
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


def clamp_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def sanitize_filename(title: str, paper_id: str) -> str:
    safe_title = re.sub(r"[^\w\s\-]", "", title, flags=re.UNICODE)
    safe_title = re.sub(r"\s+", " ", safe_title).strip()[:72]
    safe_paper_id = re.sub(r"[^\w.\-]", "_", paper_id, flags=re.UNICODE).strip()
    if not safe_title:
        safe_title = "paper"
    if not safe_paper_id:
        safe_paper_id = "unknown"
    return f"{safe_title} ({safe_paper_id}).pdf"


def clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def looks_truncated_text(value: str) -> bool:
    text = clean_html(str(value or "")).strip()
    if not text:
        return False
    return bool(re.search(r"(?:\.{3,}|…)\s*$", text))


def abstract_completeness_for_text(value: str, *, access_required: bool = False) -> str:
    text = clean_html(str(value or "")).strip()
    if access_required and not text:
        return "needs_access"
    if not text or text == "暂无摘要。":
        return "missing"
    if looks_truncated_text(text):
        return "partial"
    return "complete"


def normalize_abstract_source(value: object, fallback: str = "source") -> str:
    text = normalize_key(str(value or "")).replace(" ", "-")
    return text[:48] or fallback


def abstract_source_label(source: str, fallback: str = "") -> str:
    return ABSTRACT_SOURCE_LABELS.get(source, fallback or source or "来源元数据")


def normalize_abstract_diagnostic(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    source = normalize_abstract_source(item.get("source"), "source")
    status = str(item.get("status") or "").strip()
    if status not in ABSTRACT_DIAGNOSTIC_STATUSES:
        status = "available" if item.get("textLength") else "empty"
    completeness = str(item.get("completeness") or "").strip()
    if completeness not in ABSTRACT_COMPLETENESS_VALUES:
        completeness = "unknown"
    return {
        "source": source,
        "sourceLabel": clean_display_text(str(item.get("sourceLabel") or abstract_source_label(source)), 80),
        "status": status,
        "message": clean_display_text(str(item.get("message") or ""), 180),
        "completeness": completeness,
        "textLength": clamp_int(item.get("textLength"), default=0, minimum=0, maximum=100000),
        "accessMode": clean_display_text(str(item.get("accessMode") or ""), 64),
        "checkedAt": str(item.get("checkedAt") or item.get("fetchedAt") or ""),
        "selected": bool(item.get("selected") or status == "selected"),
    }


def normalize_abstract_diagnostics(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    diagnostics = []
    seen = set()
    for item in value[:16]:
        diagnostic = normalize_abstract_diagnostic(item)
        if not diagnostic:
            continue
        key = (diagnostic["source"], diagnostic["status"], diagnostic["message"])
        if key in seen:
            continue
        seen.add(key)
        diagnostics.append(diagnostic)
    return diagnostics


def normalize_abstract_conflict(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    sources = value.get("sources") if isinstance(value.get("sources"), list) else []
    normalized_sources = [
        clean_display_text(str(source), 80)
        for source in sources
        if str(source).strip()
    ][:8]
    has_conflict = bool(value.get("hasConflict")) and len(normalized_sources) >= 2
    return {
        "hasConflict": has_conflict,
        "sources": normalized_sources,
        "message": clean_display_text(str(value.get("message") or ""), 180),
    } if has_conflict else {}


def normalize_alert_source_health(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    status = str(value.get("status") or "unknown").strip()
    if status not in ALERT_SOURCE_HEALTH_STATUSES:
        status = "unknown"
    open_sources = []
    raw_sources = value.get("openSources") if isinstance(value.get("openSources"), list) else []
    for item in raw_sources[:8]:
        if not isinstance(item, dict):
            continue
        source = normalize_abstract_source(item.get("source"), "")
        if not source:
            continue
        open_sources.append({
            "source": source,
            "sourceLabel": clean_display_text(str(item.get("sourceLabel") or abstract_source_label(source)), 80),
            "status": clean_display_text(str(item.get("status") or ""), 32),
            "completeness": str(item.get("completeness") or "unknown")
                if str(item.get("completeness") or "unknown") in ABSTRACT_COMPLETENESS_VALUES
                else "unknown",
            "textLength": clamp_int(item.get("textLength"), default=0, minimum=0, maximum=100000),
        })
    return {
        "status": status,
        "alertComplete": bool(value.get("alertComplete")),
        "alertCompleteness": str(value.get("alertCompleteness") or "unknown")
            if str(value.get("alertCompleteness") or "unknown") in ABSTRACT_COMPLETENESS_VALUES
            else "unknown",
        "openHasAbstract": bool(value.get("openHasAbstract")),
        "openLagging": bool(value.get("openLagging")),
        "openMissing": bool(value.get("openMissing")),
        "openFailed": bool(value.get("openFailed")),
        "doi": clean_display_text(str(value.get("doi") or ""), 120),
        "checkedAt": str(value.get("checkedAt") or ""),
        "sourceLabel": clean_display_text(str(value.get("sourceLabel") or ""), 80),
        "note": clean_display_text(str(value.get("note") or ""), 220),
        "openSources": open_sources,
    }


def normalize_abstract_candidate(item: object) -> dict | None:
    best = best_abstract_candidate([item]) if isinstance(item, dict) else {}
    if not best:
        return None
    text = clean_html(str(best.get("text") or ""))
    return {
        "id": stable_text_hash(f"{best.get('source') or ''}\n{text}")[:16],
        "source": normalize_abstract_source(best.get("source"), "source"),
        "sourceLabel": clean_display_text(str(best.get("sourceLabel") or abstract_source_label(best.get("source"))), 80),
        "accessMode": clean_display_text(str(best.get("accessMode") or ""), 64),
        "fetchedAt": str(best.get("fetchedAt") or now_iso()),
        "completeness": str(best.get("completeness") or abstract_completeness_for_text(text)),
        "text": text,
        "textLength": len(text),
        "textHash": stable_text_hash(text),
        "preview": compact_text(text, 320),
    }


def normalize_abstract_candidates(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    candidates = []
    seen = set()
    for item in value[:12]:
        candidate = normalize_abstract_candidate(item)
        if not candidate:
            continue
        key = candidate["textHash"]
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def normalize_abstract_audit_event(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    action = clean_display_text(str(item.get("action") or ""), 48)
    created_at = str(item.get("createdAt") or "")
    if not action or not created_at:
        return None
    return {
        "createdAt": created_at,
        "action": action,
        "source": normalize_abstract_source(item.get("source"), ""),
        "sourceLabel": clean_display_text(str(item.get("sourceLabel") or ""), 80),
        "locked": bool(item.get("locked")),
        "message": clean_display_text(str(item.get("message") or ""), 220),
        "textHash": str(item.get("textHash") or "")[:64],
        "textLength": clamp_int(item.get("textLength"), default=0, minimum=0, maximum=100000),
    }


def normalize_abstract_audit(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    audit = []
    for item in value[:24]:
        event = normalize_abstract_audit_event(item)
        if event:
            audit.append(event)
    return audit[:24]


def add_abstract_audit_event(paper: dict, action: str, *, candidate: dict | None = None,
                             locked: bool | None = None, message: str = "") -> list[dict]:
    candidate = normalize_abstract_candidate(candidate) if isinstance(candidate, dict) else None
    current_text = clean_html(str(paper.get("fullAbstract") or paper.get("abstract") or ""))
    event = {
        "createdAt": now_iso(),
        "action": action,
        "source": (candidate or {}).get("source") or normalize_abstract_source(paper.get("abstractSource"), ""),
        "sourceLabel": (candidate or {}).get("sourceLabel") or clean_display_text(str(paper.get("abstractSourceLabel") or ""), 80),
        "locked": bool(paper.get("abstractLocked") if locked is None else locked),
        "message": message,
        "textHash": (candidate or {}).get("textHash") or stable_text_hash(current_text),
        "textLength": (candidate or {}).get("textLength") or len(current_text),
    }
    return normalize_abstract_audit([event, *(paper.get("abstractAudit") or [])])


def normalize_abstract_metadata(snapshot: dict, paper: dict, full_abstract: str) -> None:
    default_source = "existing"
    if full_abstract:
        default_source = str(paper.get("source") or "")
        default_source = "zotero" if default_source == "zotero" else "source"
    source = normalize_abstract_source(paper.get("abstractSource") or default_source)
    source_label = clean_display_text(
        str(paper.get("abstractSourceLabel") or abstract_source_label(source)),
        80,
    )
    completeness = str(paper.get("abstractCompleteness") or "").strip()
    if completeness not in ABSTRACT_COMPLETENESS_VALUES:
        completeness = abstract_completeness_for_text(full_abstract or str(snapshot.get("abstract") or ""))
    snapshot["abstractSource"] = source
    snapshot["abstractSourceLabel"] = source_label
    snapshot["abstractFetchedAt"] = str(paper.get("abstractFetchedAt") or "")
    snapshot["abstractCompleteness"] = completeness
    snapshot["abstractAccessMode"] = clean_display_text(str(paper.get("abstractAccessMode") or ""), 64)
    snapshot["abstractDiagnostics"] = normalize_abstract_diagnostics(paper.get("abstractDiagnostics"))
    snapshot["abstractConflict"] = normalize_abstract_conflict(paper.get("abstractConflict"))
    snapshot["abstractLocked"] = bool(paper.get("abstractLocked"))
    snapshot["abstractConfirmedAt"] = str(paper.get("abstractConfirmedAt") or "")
    snapshot["abstractConfirmedBy"] = clean_display_text(str(paper.get("abstractConfirmedBy") or ""), 48)
    snapshot["abstractCandidates"] = normalize_abstract_candidates(paper.get("abstractCandidates"))
    snapshot["abstractAudit"] = normalize_abstract_audit(paper.get("abstractAudit"))
    snapshot["alertSourceHealth"] = normalize_alert_source_health(paper.get("alertSourceHealth"))
    snapshot["metadataUpdatedAt"] = str(paper.get("metadataUpdatedAt") or "")


def abstract_candidate_score(candidate: dict) -> tuple[int, int, int]:
    text = clean_html(str(candidate.get("text") or ""))
    source = normalize_abstract_source(candidate.get("source"))
    completeness = str(candidate.get("completeness") or abstract_completeness_for_text(text))
    completeness_score = {
        "complete": 3,
        "partial": 2,
        "unknown": 1,
        "missing": 0,
        "needs_access": 0,
    }.get(completeness, 0)
    source_score = ABSTRACT_SOURCE_PRIORITY.get(source, 40)
    truncated_penalty = -80 if looks_truncated_text(text) else 0
    return (completeness_score, source_score + truncated_penalty, len(text))


def best_abstract_candidate(candidates: list[dict]) -> dict:
    cleaned = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        text = clean_html(str(candidate.get("text") or ""))
        if not text or text == "暂无摘要。":
            continue
        source = normalize_abstract_source(candidate.get("source"))
        cleaned.append({
            "text": text,
            "source": source,
            "sourceLabel": clean_display_text(
                str(candidate.get("sourceLabel") or abstract_source_label(source)),
                80,
            ),
            "accessMode": clean_display_text(str(candidate.get("accessMode") or ""), 64),
            "fetchedAt": str(candidate.get("fetchedAt") or now_iso()),
            "completeness": str(candidate.get("completeness") or abstract_completeness_for_text(text)),
        })
    if not cleaned:
        return {}
    return max(cleaned, key=abstract_candidate_score)


def abstract_candidate_from_paper(paper: dict, source: str = "source", label: str = "") -> dict:
    text = clean_html(str(paper.get("fullAbstract") or paper.get("abstract") or ""))
    return {
        "text": text,
        "source": source,
        "sourceLabel": label or abstract_source_label(source),
        "accessMode": str(paper.get("abstractAccessMode") or ""),
        "fetchedAt": str(paper.get("abstractFetchedAt") or ""),
        "completeness": str(paper.get("abstractCompleteness") or abstract_completeness_for_text(text)),
    }


def abstract_diagnostic_from_candidate(candidate: dict, status: str = "available", message: str = "") -> dict:
    source = normalize_abstract_source(candidate.get("source"), "source")
    text = clean_html(str(candidate.get("text") or ""))
    return {
        "source": source,
        "sourceLabel": clean_display_text(str(candidate.get("sourceLabel") or abstract_source_label(source)), 80),
        "status": status if status in ABSTRACT_DIAGNOSTIC_STATUSES else "available",
        "message": clean_display_text(message, 180),
        "completeness": str(candidate.get("completeness") or abstract_completeness_for_text(text)),
        "textLength": len(text),
        "accessMode": clean_display_text(str(candidate.get("accessMode") or ""), 64),
        "checkedAt": str(candidate.get("fetchedAt") or now_iso()),
        "selected": status == "selected",
    }


def abstract_diagnostic_empty(source: str, label: str = "", message: str = "", status: str = "empty") -> dict:
    normalized_source = normalize_abstract_source(source, "source")
    return {
        "source": normalized_source,
        "sourceLabel": clean_display_text(label or abstract_source_label(normalized_source), 80),
        "status": status if status in ABSTRACT_DIAGNOSTIC_STATUSES else "empty",
        "message": clean_display_text(message, 180),
        "completeness": "missing",
        "textLength": 0,
        "accessMode": "",
        "checkedAt": now_iso(),
        "selected": False,
    }


def selected_abstract_diagnostics(diagnostics: list[dict], selected_source: str) -> list[dict]:
    selected_source = normalize_abstract_source(selected_source, "source")
    normalized = normalize_abstract_diagnostics(diagnostics)
    for index, diagnostic in enumerate(normalized):
        normalized[index] = {
            **diagnostic,
            "status": "available" if diagnostic.get("status") == "selected" else diagnostic.get("status"),
            "selected": False,
        }
    selected_index = next(
        (
            index for index, diagnostic in enumerate(normalized)
            if diagnostic.get("source") == selected_source and diagnostic.get("status") in {"available", "current", "selected"}
        ),
        -1,
    )
    if selected_index >= 0:
        normalized[selected_index] = {
            **normalized[selected_index],
            "status": "selected",
            "selected": True,
        }
    return normalized


def abstract_conflict_from_candidates(candidates: list[dict], selected_source: str = "") -> dict:
    complete = []
    seen = set()
    for candidate in candidates:
        best = best_abstract_candidate([candidate])
        if not best or str(best.get("completeness") or "") != "complete":
            continue
        text_hash = stable_text_hash(best.get("text") or "")
        if not text_hash or text_hash in seen:
            continue
        seen.add(text_hash)
        complete.append(best)
    if len(complete) < 2:
        return {}
    labels = [str(candidate.get("sourceLabel") or abstract_source_label(candidate.get("source"))) for candidate in complete]
    selected_label = abstract_source_label(selected_source) if selected_source else ""
    message = "多个来源返回了不完全相同的完整摘要，请按需核对。"
    if selected_label:
        message = f"当前保留 {selected_label}；多个来源返回了不完全相同的完整摘要。"
    return {
        "hasConflict": True,
        "sources": labels,
        "message": message,
    }


def should_replace_abstract(current: dict, candidate: dict) -> bool:
    current_best = best_abstract_candidate([current])
    candidate_best = best_abstract_candidate([candidate])
    if not candidate_best:
        return False
    if not current_best:
        return True

    current_text = clean_html(str(current_best.get("text") or ""))
    candidate_text = clean_html(str(candidate_best.get("text") or ""))
    current_complete = str(current_best.get("completeness") or "") == "complete"
    candidate_complete = str(candidate_best.get("completeness") or "") == "complete"

    if current_complete and not candidate_complete:
        return False
    if candidate_complete and not current_complete:
        return True
    if current_complete and candidate_complete and len(candidate_text) + 80 < len(current_text):
        return False
    return abstract_candidate_score(candidate_best) > abstract_candidate_score(current_best)


def merge_paper_abstract(base: dict, candidate: dict) -> dict:
    snapshot_base = paper_snapshot(base)
    if snapshot_base.get("abstractLocked"):
        return snapshot_base
    current = abstract_candidate_from_paper(snapshot_base, snapshot_base.get("abstractSource") or "existing")
    best = best_abstract_candidate([candidate])
    if not should_replace_abstract(current, best):
        return snapshot_base
    merged = {
        **snapshot_base,
        "fullAbstract": best["text"],
        "abstract": compact_text(best["text"], ABSTRACT_TEXT_LIMIT),
        "abstractSource": best["source"],
        "abstractSourceLabel": best["sourceLabel"],
        "abstractFetchedAt": best["fetchedAt"] or now_iso(),
        "abstractCompleteness": best["completeness"],
        "abstractAccessMode": best["accessMode"],
        "metadataUpdatedAt": now_iso(),
    }
    return paper_snapshot(merged)


def stage_paper_abstract_for_review(paper: dict, *, message: str = "Alert inbox candidate awaiting user confirmation.") -> dict:
    snapshot = paper_snapshot(paper)
    candidate = normalize_abstract_candidate(
        abstract_candidate_from_paper(
            snapshot,
            snapshot.get("abstractSource") or "source",
            snapshot.get("abstractSourceLabel") or "",
        )
    )
    candidates = normalize_abstract_candidates([
        candidate,
        *(snapshot.get("abstractCandidates") or []),
    ] if candidate else snapshot.get("abstractCandidates"))
    diagnostics = []
    for diagnostic in normalize_abstract_diagnostics(snapshot.get("abstractDiagnostics")):
        if diagnostic.get("status") == "selected":
            diagnostic = {**diagnostic, "status": "available", "selected": False}
        diagnostics.append(diagnostic)
    if candidate:
        diagnostics.append(abstract_diagnostic_from_candidate(candidate, "available", message))
    staged = {
        **snapshot,
        "abstract": "",
        "fullAbstract": "",
        "abstractSource": "source",
        "abstractSourceLabel": abstract_source_label("source"),
        "abstractFetchedAt": "",
        "abstractCompleteness": "missing",
        "abstractAccessMode": "",
        "abstractDiagnostics": normalize_abstract_diagnostics(diagnostics),
        "abstractConflict": abstract_conflict_from_candidates(candidates, ""),
        "abstractCandidates": candidates,
        "metadataUpdatedAt": now_iso(),
    }
    return paper_snapshot(staged)


def preferred_abstract_text(current: str, candidate: str) -> str:
    current_text = clean_html(str(current or ""))
    candidate_text = clean_html(str(candidate or ""))
    if not current_text:
        return candidate_text
    if not candidate_text:
        return current_text

    current_truncated = looks_truncated_text(current_text)
    candidate_truncated = looks_truncated_text(candidate_text)
    if current_truncated and not candidate_truncated:
        return candidate_text
    if candidate_truncated and not current_truncated:
        return current_text
    if len(candidate_text) > len(current_text) + 80:
        return candidate_text
    return current_text


def clean_display_text(value: str, limit: int) -> str:
    return compact_text(clean_html(str(value or "")), limit)


def stable_text_hash(value: str) -> str:
    normalized = clean_html(str(value or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def translation_source_text(paper: dict) -> str:
    return clean_html(str(paper.get("fullAbstract") or paper.get("abstract") or ""))


def normalize_translations(value: object, paper: dict) -> dict:
    if not isinstance(value, dict):
        return {}

    current_hash = stable_text_hash(translation_source_text(paper))
    normalized = {}
    for language, item in value.items():
        if not isinstance(item, dict):
            continue
        text = clean_html(str(item.get("text") or ""))
        if not text:
            continue
        source_hash = str(item.get("sourceHash") or "")
        normalized[str(language)] = {
            "text": text,
            "language": str(item.get("language") or language),
            "provider": str(item.get("provider") or ""),
            "model": str(item.get("model") or ""),
            "translatedAt": str(item.get("translatedAt") or ""),
            "promptVersion": str(item.get("promptVersion") or ""),
            "sourceHash": source_hash,
            "stale": bool(source_hash and source_hash != current_hash),
        }
    return normalized


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def paper_key(paper: dict) -> str:
    for field in ("source", "paperId", "arxivId", "title"):
        value = str(paper.get(field, "")).strip()
        if value and value.lower() not in {"unknown", "untitled"}:
            break
    else:
        value = "unknown"

    source = str(paper.get("source", "")).strip() or "paper"
    identifier = str(paper.get("paperId") or paper.get("arxivId") or paper.get("title") or value)
    normalized = normalize_key(f"{source} {identifier}").replace(" ", "-")
    return normalized[:120] or "paper"


def clean_zotero_item_key(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "").strip())[:16]


def zotero_meta_item_key(zotero: object) -> str:
    if not isinstance(zotero, dict):
        return ""
    return clean_zotero_item_key(zotero.get("itemKey") or zotero.get("key"))


def zotero_link_candidate(candidate: dict, score: int = 0) -> dict:
    zotero = candidate.get("zotero") if isinstance(candidate.get("zotero"), dict) else {}
    notes = zotero.get("notes") if isinstance(zotero.get("notes"), list) else []
    tags = [str(tag) for tag in (candidate.get("tags") or []) if str(tag).strip()] if isinstance(candidate.get("tags"), list) else []
    paperhunter_tags = [tag for tag in tags if tag == "paperhunter" or tag.startswith("paperhunter:")]
    return {
        "itemKey": zotero_meta_item_key(zotero),
        "libraryID": zotero.get("libraryID"),
        "itemID": zotero.get("itemID"),
        "score": int(score),
        "title": clean_display_text(str(candidate.get("title") or ""), 120),
        "authors": clean_display_text(str(candidate.get("authors") or ""), 96),
        "year": str(candidate.get("year") or ""),
        "source": str(candidate.get("source") or ""),
        "url": paper_url(candidate),
        "hasPdf": bool(candidate.get("localPdfPath")),
        "hasPaperHunterNote": any(bool(note.get("managedByPaperHunter")) for note in notes if isinstance(note, dict)),
        "userNoteCount": sum(1 for note in notes if isinstance(note, dict) and not note.get("managedByPaperHunter")),
        "paperhunterTags": paperhunter_tags[:8],
        "tagCount": len(tags),
        "attachmentCount": len(zotero.get("attachments") or []) if isinstance(zotero.get("attachments"), list) else 0,
        "dateModified": str(zotero.get("dateModified") or ""),
    }


def normalize_zotero_link(value: object, paper: dict) -> dict:
    link = value if isinstance(value, dict) else {}
    zotero = paper.get("zotero") if isinstance(paper.get("zotero"), dict) else {}
    sync = paper.get("zoteroSync") if isinstance(paper.get("zoteroSync"), dict) else {}

    item_key = clean_zotero_item_key(link.get("itemKey") or zotero_meta_item_key(zotero))
    sync_item_key = clean_zotero_item_key(sync.get("itemKey")) if sync.get("status") == "synced" else ""
    status = str(link.get("status") or "").strip()
    if status not in ZOTERO_LINK_STATUSES:
        status = "auto" if item_key else "unlinked"

    message = clean_display_text(str(link.get("message") or ""), 220)
    if item_key and sync_item_key and item_key != sync_item_key:
        status = "conflict"
        message = "PaperHunter local link and last synced Zotero itemKey differ. Confirm the canonical Zotero item before syncing."
    elif status == "unlinked" and item_key:
        status = "auto"

    candidates = link.get("candidates") if isinstance(link.get("candidates"), list) else []
    normalized_candidates = []
    for candidate in candidates[:8]:
        if not isinstance(candidate, dict):
            continue
        normalized_candidates.append({
            "itemKey": clean_zotero_item_key(candidate.get("itemKey")),
            "libraryID": candidate.get("libraryID"),
            "itemID": candidate.get("itemID"),
            "score": clamp_int(candidate.get("score"), default=0, minimum=0, maximum=100),
            "title": clean_display_text(str(candidate.get("title") or ""), 120),
            "authors": clean_display_text(str(candidate.get("authors") or ""), 96),
            "year": str(candidate.get("year") or ""),
            "source": str(candidate.get("source") or ""),
            "url": clean_html(str(candidate.get("url") or "")),
            "hasPdf": bool(candidate.get("hasPdf")),
            "hasPaperHunterNote": bool(candidate.get("hasPaperHunterNote")),
            "userNoteCount": clamp_int(candidate.get("userNoteCount"), default=0, minimum=0, maximum=999),
            "paperhunterTags": [str(tag) for tag in (candidate.get("paperhunterTags") or []) if str(tag).strip()][:8]
                if isinstance(candidate.get("paperhunterTags"), list)
                else [],
            "tagCount": clamp_int(candidate.get("tagCount"), default=0, minimum=0, maximum=999),
            "attachmentCount": clamp_int(candidate.get("attachmentCount"), default=0, minimum=0, maximum=999),
            "dateModified": str(candidate.get("dateModified") or ""),
        })

    return {
        "status": status,
        "itemKey": item_key,
        "libraryID": link.get("libraryID") if link.get("libraryID") is not None else zotero.get("libraryID"),
        "itemID": link.get("itemID") if link.get("itemID") is not None else zotero.get("itemID"),
        "confidence": clamp_int(link.get("confidence"), default=100 if item_key else 0, minimum=0, maximum=100),
        "source": clean_display_text(str(link.get("source") or ("legacy" if item_key else "")), 48),
        "confirmedAt": str(link.get("confirmedAt") or ""),
        "updatedAt": str(link.get("updatedAt") or ""),
        "message": message,
        "candidates": normalized_candidates,
    }


def paper_snapshot(paper: dict) -> dict:
    snapshot = {field: paper.get(field, "") for field in PAPER_SNAPSHOT_FIELDS}
    full_abstract = clean_html(str(snapshot.get("fullAbstract") or ""))
    abstract_source = full_abstract or str(snapshot.get("abstract") or "暂无摘要。")
    snapshot["paperKey"] = paper_key(paper)
    snapshot["title"] = clean_display_text(str(snapshot.get("title") or "Untitled"), TITLE_TEXT_LIMIT)
    snapshot["authors"] = clean_display_text(str(snapshot.get("authors") or "Unknown authors"), AUTHOR_TEXT_LIMIT)
    snapshot["abstract"] = clean_display_text(abstract_source, ABSTRACT_TEXT_LIMIT)
    snapshot["fullAbstract"] = full_abstract
    normalize_abstract_metadata(snapshot, paper, full_abstract)
    local_pdf_path = clean_html(str(snapshot.get("localPdfPath") or ""))
    snapshot["localPdfPath"] = local_pdf_path
    snapshot["localPdfFilename"] = clean_html(
        str(snapshot.get("localPdfFilename") or (Path(local_pdf_path).name if local_pdf_path else ""))
    )
    snapshot["access"] = clean_html(str(snapshot.get("access") or ""))
    snapshot["downloadable"] = bool(snapshot.get("pdfUrl") or local_pdf_path)
    snapshot["isDownloaded"] = bool(snapshot.get("isDownloaded"))
    if local_pdf_path:
        snapshot["isDownloaded"] = True
    if snapshot.get("readingStatus") not in {"", "unread", "reading", "read", "to_translate"}:
        snapshot["readingStatus"] = ""
    if not isinstance(snapshot.get("tags"), list):
        snapshot["tags"] = []
    else:
        snapshot["tags"] = [clean_display_text(str(tag), 32) for tag in snapshot["tags"] if str(tag).strip()][:12]
    if not isinstance(snapshot.get("translations"), dict):
        snapshot["translations"] = {}
    else:
        snapshot["translations"] = normalize_translations(snapshot["translations"], snapshot)
    if not isinstance(snapshot.get("fulltextTranslations"), list):
        snapshot["fulltextTranslations"] = []
    if not isinstance(snapshot.get("zotero"), dict):
        snapshot["zotero"] = {}
    if not isinstance(snapshot.get("zoteroSync"), dict):
        snapshot["zoteroSync"] = {}
    else:
        sync = snapshot["zoteroSync"]
        snapshot["zoteroSync"] = {
            "status": str(sync.get("status") or ""),
            "itemKey": str(sync.get("itemKey") or ""),
            "syncedAt": str(sync.get("syncedAt") or ""),
            "noteID": sync.get("noteID") if isinstance(sync.get("noteID"), int) else None,
            "attachments": clamp_int(sync.get("attachments"), default=0, minimum=0, maximum=999),
            "tags": [str(tag) for tag in (sync.get("tags") or []) if str(tag).strip()][:12]
                if isinstance(sync.get("tags"), list)
                else [],
            "error": clean_display_text(str(sync.get("error") or ""), 240),
        }
    snapshot["zoteroLink"] = normalize_zotero_link(snapshot.get("zoteroLink"), snapshot)
    snapshot["note"] = clean_display_text(str(snapshot.get("note") or ""), 1000)
    return snapshot


def query_terms(query: str, min_length: int = 3) -> list[str]:
    return [term for term in normalize_key(query).split() if len(term) >= min_length]


def query_matches(text: str, query: str) -> bool:
    haystack = normalize_key(text)
    terms = query_terms(query)
    if not terms:
        return True
    matches = sum(1 for term in terms if term in haystack)
    return matches >= max(1, min(len(terms), (len(terms) + 1) // 2))


def contains_text(text: str, needle: str) -> bool:
    if not needle:
        return True
    return normalize_key(needle) in normalize_key(text)


def contains_any_term(text: str, terms: str) -> bool:
    haystack = normalize_key(text)
    needles = query_terms(terms, min_length=4)
    if not needles:
        return True
    return any(term in haystack for term in needles)


def request_timeout(read_timeout: int = READ_TIMEOUT_SECONDS) -> tuple[int, int]:
    return (CONNECT_TIMEOUT_SECONDS, read_timeout)


def model_request_timeout(read_timeout: int = 30) -> tuple[int, int]:
    return (CONNECT_TIMEOUT_SECONDS, max(1, read_timeout))


def join_url(base_url: str, endpoint: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    path = str(endpoint or "").strip()
    if not path:
        path = API_TYPE_ENDPOINTS["chat_completions"]
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}" if base else path


def normalized_request_path(path: str) -> str:
    request_path = urlparse(str(path or "")).path or "/"
    if not request_path.startswith("/"):
        request_path = f"/{request_path}"
    return request_path


def provider_preset(provider_id: str) -> dict:
    for preset in MODEL_PROVIDER_PRESETS:
        if preset["id"] == provider_id:
            return preset
    return MODEL_PROVIDER_PRESETS[-1]


def mask_secret(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 10:
        return f"{text[:2]}...{text[-2:]}"
    return f"{text[:6]}...{text[-4:]}"


def format_source_error(source: str, exc: Exception | str) -> str:
    label = SOURCE_LABELS.get(source, source)
    message = str(exc)
    normalized = message.lower()
    if "429" in normalized:
        return f"{label} 当前限流，已跳过。"
    if "timed out" in normalized or "timeout" in normalized or "超时" in message:
        return f"{label} 请求超时，已跳过。"
    return compact_text(f"{label}: {message}", 180)


def normalized_host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def is_trusted_open_pdf_url(url: str) -> bool:
    host = normalized_host(url)
    if host in OPEN_PDF_HOSTS:
        return True
    if host.endswith(".arxiv.org") or host.endswith(".thecvf.com") or host.endswith(".aclanthology.org"):
        return True
    if host.endswith(".backblazeb2.com"):
        return True
    return False


def normalize_openreview_pdf_url(pdf_path: str) -> str:
    if not pdf_path:
        return ""
    candidate = urljoin("https://openreview.net", pdf_path)
    if is_trusted_open_pdf_url(candidate):
        return candidate
    return ""


def make_paper(
    *,
    source: str,
    title: str,
    authors: str = "",
    year: int | str = "",
    published: str = "",
    venue: str = "",
    category: str = "",
    abstract: str = "",
    pdf_url: str = "",
    page_url: str = "",
    paper_id: str = "",
    doi: str = "",
    local_pdf_path: str = "",
    access: str = "",
    zotero: dict | None = None,
) -> dict:
    source_label = SOURCE_LABELS.get(source, source)
    resolved_id = paper_id or normalize_key(title).replace(" ", "-")[:48] or "unknown"
    full_abstract = clean_html(str(abstract or "暂无摘要。"))
    local_pdf_filename = Path(local_pdf_path).name if local_pdf_path else ""
    is_downloaded = bool(local_pdf_path) or (bool(pdf_url) and (DOWNLOAD_DIR / sanitize_filename(title, resolved_id)).exists())
    return {
        "title": clean_display_text(title, TITLE_TEXT_LIMIT) or "Untitled",
        "authors": clean_display_text(authors, AUTHOR_TEXT_LIMIT) or "Unknown authors",
        "published": published or str(year or ""),
        "year": year,
        "pdfUrl": pdf_url,
        "localPdfPath": local_pdf_path,
        "localPdfFilename": local_pdf_filename,
        "access": access,
        "entryUrl": page_url,
        "pageUrl": page_url,
        "arxivId": resolved_id,
        "paperId": resolved_id,
        "doi": doi,
        "source": source,
        "sourceLabel": source_label,
        "venue": clean_display_text(venue, 120),
        "category": clean_display_text(category or venue or source_label, 120),
        "abstract": compact_text(full_abstract, ABSTRACT_TEXT_LIMIT),
        "fullAbstract": full_abstract,
        "downloadable": bool(pdf_url or local_pdf_path),
        "isDownloaded": is_downloaded,
        "zotero": zotero or {},
    }


def build_arxiv_query(raw_query: str, categories: list[str]) -> str:
    query = raw_query.strip()
    if not query:
        return ""

    if "All" in categories:
        return query

    selected_categories = [category for category in categories if category != "All"]
    if not selected_categories:
        return query

    category_filter = " OR ".join(f"cat:{category}" for category in selected_categories)
    return f"({query}) AND ({category_filter})"


def existing_pdf_count() -> int:
    return len(list(DOWNLOAD_DIR.glob("*.pdf")))


def empty_library() -> dict:
    return {
        "version": LIBRARY_SCHEMA_VERSION,
        "papers": {},
        "favorites": {},
        "ignored": {},
        "downloads": {},
        "history": [],
        "subscriptionSources": normalize_subscription_sources([]),
        "alertImportHistory": [],
        "alertInbox": [],
        "zoteroAudit": [],
    }


def normalize_library_entry(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    paper = value.get("paper") if isinstance(value.get("paper"), dict) else value
    snapshot = paper_snapshot(paper)
    entry = {
        "createdAt": str(value.get("createdAt") or value.get("favoritedAt") or value.get("ignoredAt") or now_iso()),
        "paper": snapshot,
    }
    for field in ("updatedAt", "refreshedAt"):
        if value.get(field):
            entry[field] = str(value.get(field))
    return entry


def normalize_download_entry(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None

    paper = value.get("paper") if isinstance(value.get("paper"), dict) else value
    snapshot = paper_snapshot({**paper, "isDownloaded": True})
    entry = {
        "createdAt": str(value.get("createdAt") or now_iso()),
        "filename": str(value.get("filename") or ""),
        "paper": snapshot,
    }
    for field in ("updatedAt", "path", "source"):
        if value.get(field):
            entry[field] = str(value.get(field))
    return entry


def normalize_history(items: object) -> list[dict]:
    if not isinstance(items, list):
        return []

    history = []
    for item in items[:MAX_SEARCH_HISTORY]:
        if not isinstance(item, dict):
            continue
        query = str(item.get("query", "")).strip()
        if not query:
            continue
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        source_counts = item.get("sourceCounts") if isinstance(item.get("sourceCounts"), dict) else {}
        history.append({
            "query": query,
            "createdAt": str(item.get("createdAt") or ""),
            "resultCount": clamp_int(item.get("resultCount"), 0, 0, MAX_RESULTS_LIMIT * len(SOURCE_LABELS)),
            "sources": [str(source) for source in sources if str(source) in SOURCE_LABELS],
            "fieldPreset": str(item.get("fieldPreset", "all")),
            "intent": str(item.get("intent", "general")),
            "sortBy": str(item.get("sortBy", "recent")),
            "sourceCounts": source_counts,
        })
    return history


def clean_subscription_source_id(value: object, fallback: str = "custom-alert") -> str:
    source_id = normalize_key(str(value or "")).replace(" ", "-")
    return source_id[:64] or fallback


def source_preset_by_id(source_id: str) -> dict:
    normalized = clean_subscription_source_id(source_id, "")
    for preset in SUBSCRIPTION_SOURCE_PRESETS:
        if preset["id"] == normalized:
            return {**preset}
    return {}


def normalize_subscription_source(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None

    source_id = clean_subscription_source_id(
        item.get("id") or item.get("sourceId") or item.get("provider") or item.get("sourceLabel") or item.get("name")
    )
    preset = source_preset_by_id(source_id)
    source_type = str(item.get("sourceType") or preset.get("sourceType") or "custom")
    if source_type not in SUBSCRIPTION_SOURCE_TYPES:
        source_type = "custom"
    authorization_mode = str(item.get("authorizationMode") or preset.get("authorizationMode") or "manual-alert")
    if authorization_mode not in SUBSCRIPTION_AUTHORIZATION_MODES:
        authorization_mode = "manual-alert"
    name = clean_display_text(str(item.get("name") or preset.get("name") or source_id.replace("-", " ").title()), 80)
    source_label = clean_display_text(str(item.get("sourceLabel") or preset.get("sourceLabel") or name), 80)
    provider = clean_subscription_source_id(item.get("provider") or preset.get("provider") or source_id, source_id)
    return {
        "id": source_id,
        "name": name,
        "provider": provider,
        "sourceLabel": source_label,
        "sourceType": source_type,
        "authorizationMode": authorization_mode,
        "enabled": bool(item.get("enabled", preset.get("enabled", True))),
        "status": clean_display_text(str(item.get("status") or preset.get("status") or "ready"), 32),
        "lastChecked": str(item.get("lastChecked") or ""),
        "lastImportedAt": str(item.get("lastImportedAt") or ""),
        "importCount": clamp_int(item.get("importCount"), default=0, minimum=0, maximum=1_000_000),
        "updatedCount": clamp_int(item.get("updatedCount"), default=0, minimum=0, maximum=1_000_000),
        "ignoredUpdatedCount": clamp_int(item.get("ignoredUpdatedCount"), default=0, minimum=0, maximum=1_000_000),
        "policy": clean_display_text(str(item.get("policy") or preset.get("policy") or ""), 240),
        "freshnessNote": clean_display_text(str(item.get("freshnessNote") or preset.get("freshnessNote") or ""), 240),
        "createdAt": str(item.get("createdAt") or ""),
        "updatedAt": str(item.get("updatedAt") or ""),
    }


def normalize_subscription_sources(value: object) -> list[dict]:
    raw_items = value if isinstance(value, list) else []
    by_id: dict[str, dict] = {}
    for preset in SUBSCRIPTION_SOURCE_PRESETS:
        normalized = normalize_subscription_source(preset)
        if normalized:
            by_id[normalized["id"]] = normalized
    for item in raw_items:
        normalized = normalize_subscription_source(item)
        if normalized:
            existing = by_id.get(normalized["id"], {})
            by_id[normalized["id"]] = {**existing, **normalized}
    return list(by_id.values())


def subscription_source_by_id(sources: list[dict], source_id: str) -> dict:
    normalized = clean_subscription_source_id(source_id, "")
    for source in normalize_subscription_sources(sources):
        if source.get("id") == normalized:
            return source
    return {}


def detect_subscription_source(text: str = "", source_label: str = "", source_id: str = "",
                               sources: list[dict] | None = None) -> dict:
    available_sources = normalize_subscription_sources(sources or [])
    explicit = subscription_source_by_id(available_sources, source_id)
    if explicit:
        return {**explicit, "detected": False}

    raw_text = str(text or "")
    raw_label = str(source_label or "")
    text_key = normalize_key(raw_text)
    label_key = normalize_key(raw_label)

    def source_with_detection(candidate_id: str) -> dict:
        source = subscription_source_by_id(available_sources, candidate_id) or source_preset_by_id(candidate_id)
        return {**normalize_subscription_source(source), "detected": True} if source else {}

    sciencedirect_tokens = ("sciencedirect", "science direct", "elsevier")
    wos_tokens = ("web of science", "clarivate", "wos")
    if any(token in text_key for token in sciencedirect_tokens) or "sciencedirect.com" in raw_text.lower():
        return source_with_detection("sciencedirect-alert")
    if any(token in text_key for token in wos_tokens):
        return source_with_detection("wos-alert")
    if any(token in label_key for token in sciencedirect_tokens):
        return source_with_detection("sciencedirect-alert")
    if any(token in label_key for token in wos_tokens):
        return source_with_detection("wos-alert")

    custom_label = clean_display_text(raw_label or "Custom Alert", 80)
    custom_id = clean_subscription_source_id(source_id or custom_label or "custom-alert")
    if custom_id in {"alert", "custom", "custom-alert"}:
        custom_id = "custom-alert"
    base = subscription_source_by_id(available_sources, custom_id) or source_preset_by_id("custom-alert")
    return {
        **normalize_subscription_source({
            **base,
            "id": custom_id,
            "name": custom_label,
            "provider": "custom",
            "sourceLabel": custom_label,
            "sourceType": "custom",
            "authorizationMode": "manual-alert",
        }),
        "detected": False,
    }


def normalize_alert_import_history(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []

    history = []
    for item in value[:MAX_ALERT_IMPORT_HISTORY]:
        if not isinstance(item, dict):
            continue
        created_at = str(item.get("createdAt") or "")
        source_id = clean_subscription_source_id(item.get("sourceId") or item.get("id"), "")
        source_label = clean_display_text(str(item.get("sourceLabel") or ""), 80)
        if not created_at or not source_label:
            continue
        count = clamp_int(item.get("count"), default=0, minimum=0, maximum=10000)
        imported = clamp_int(item.get("imported"), default=0, minimum=0, maximum=10000)
        updated = clamp_int(item.get("updated"), default=0, minimum=0, maximum=10000)
        ignored_updated = clamp_int(item.get("ignoredUpdated"), default=0, minimum=0, maximum=10000)
        parse_report = normalize_alert_parse_report(item.get("parseReport"))
        source_health = normalize_alert_source_health_summary(item.get("sourceHealth"))
        history.append({
            "createdAt": created_at,
            "sourceId": source_id,
            "sourceLabel": source_label,
            "provider": clean_subscription_source_id(item.get("provider"), ""),
            "authorizationMode": str(item.get("authorizationMode") or "manual-alert")
                if str(item.get("authorizationMode") or "manual-alert") in SUBSCRIPTION_AUTHORIZATION_MODES
                else "manual-alert",
            "count": count,
            "imported": imported,
            "updated": updated,
            "ignoredUpdated": ignored_updated,
            "detected": bool(item.get("detected")),
            "summary": clean_display_text(str(item.get("summary") or ""), 220),
            "parseReport": parse_report,
            "sourceHealth": source_health,
        })
    return history[:MAX_ALERT_IMPORT_HISTORY]


def empty_alert_parse_report() -> dict:
    return {
        "documents": 0,
        "parsedBlocks": 0,
        "parsed": 0,
        "doiCount": 0,
        "completeAbstracts": 0,
        "partialAbstracts": 0,
        "missingAbstracts": 0,
        "failedDocuments": 0,
        "unrecognizedFragments": 0,
    }


def normalize_alert_parse_report(value: object) -> dict:
    report = empty_alert_parse_report()
    if not isinstance(value, dict):
        return report
    for key in report:
        report[key] = clamp_int(value.get(key), default=report[key], minimum=0, maximum=10000)
    return report


def empty_alert_source_health_summary() -> dict:
    return {
        "alertComplete": 0,
        "alertPartial": 0,
        "alertMissing": 0,
        "openHasAbstract": 0,
        "openLagging": 0,
        "openMissing": 0,
        "openFailed": 0,
    }


def normalize_alert_source_health_summary(value: object) -> dict:
    summary = empty_alert_source_health_summary()
    if not isinstance(value, dict):
        return summary
    for key in summary:
        summary[key] = clamp_int(value.get(key), default=0, minimum=0, maximum=10000)
    return summary


def alert_import_history_summary(source: dict, *, count: int, imported: int,
                                 updated: int, ignored_updated: int,
                                 report: dict | None = None,
                                 source_health: dict | None = None) -> str:
    label = clean_display_text(str(source.get("sourceLabel") or source.get("name") or "Alert"), 80)
    report = normalize_alert_parse_report(report)
    source_health = normalize_alert_source_health_summary(source_health)
    health_note = ""
    if source_health.get("openLagging"):
        health_note = f", {source_health['openLagging']} open-metadata lagging"
    return (
        f"{label}: {count} parsed, {imported} new, "
        f"{updated} updated, {ignored_updated} ignored-updated, "
        f"{report.get('completeAbstracts', 0)} complete abstracts{health_note}."
    )


def upsert_subscription_source_import_stats(library: dict, source: dict, *,
                                            count: int, imported: int,
                                            updated: int, ignored_updated: int,
                                            timestamp: str) -> dict:
    normalized_source = normalize_subscription_source(source) or normalize_subscription_source(source_preset_by_id("custom-alert"))
    sources = normalize_subscription_sources(library.get("subscriptionSources"))
    by_id = {item["id"]: item for item in sources}
    existing = by_id.get(normalized_source["id"], normalized_source)
    merged = {
        **existing,
        **normalized_source,
        "lastChecked": timestamp,
        "lastImportedAt": timestamp,
        "importCount": clamp_int(existing.get("importCount"), 0, 0, 1_000_000) + count,
        "updatedCount": clamp_int(existing.get("updatedCount"), 0, 0, 1_000_000) + updated,
        "ignoredUpdatedCount": clamp_int(existing.get("ignoredUpdatedCount"), 0, 0, 1_000_000) + ignored_updated,
        "status": "imported" if count else "ready",
        "updatedAt": timestamp,
        "createdAt": existing.get("createdAt") or timestamp,
    }
    by_id[merged["id"]] = normalize_subscription_source(merged)
    library["subscriptionSources"] = list(by_id.values())
    return merged


def add_alert_import_history_event(library: dict, source: dict, *, count: int,
                                   imported: int, updated: int,
                                   ignored_updated: int, timestamp: str,
                                   report: dict | None = None,
                                   source_health: dict | None = None) -> dict:
    normalized_source = normalize_subscription_source(source) or normalize_subscription_source(source_preset_by_id("custom-alert"))
    report = normalize_alert_parse_report(report)
    source_health = normalize_alert_source_health_summary(source_health)
    event = {
        "createdAt": timestamp,
        "sourceId": normalized_source["id"],
        "sourceLabel": normalized_source["sourceLabel"],
        "provider": normalized_source["provider"],
        "authorizationMode": normalized_source["authorizationMode"],
        "count": count,
        "imported": imported,
        "updated": updated,
        "ignoredUpdated": ignored_updated,
        "detected": bool(source.get("detected")),
        "parseReport": report,
        "sourceHealth": source_health,
        "summary": alert_import_history_summary(
            normalized_source,
            count=count,
            imported=imported,
            updated=updated,
            ignored_updated=ignored_updated,
            report=report,
            source_health=source_health,
        ),
    }
    library["alertImportHistory"] = normalize_alert_import_history([
        event,
        *(library.get("alertImportHistory") or []),
    ])
    return event


ALERT_INBOX_STATUSES = {"pending", "adopted", "locked", "ignored", "skipped", "partial", "missing", "stale"}
ALERT_INBOX_TERMINAL_STATUSES = {"adopted", "skipped"}


def normalize_alert_inbox_event(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    created_at = str(item.get("createdAt") or "")
    paper_key_value = clean_display_text(str(item.get("paperKey") or ""), 160)
    candidate = normalize_abstract_candidate(item.get("candidate"))
    source_label = clean_display_text(str(item.get("sourceLabel") or ""), 80)
    if not created_at or not paper_key_value or not source_label or not candidate:
        return None

    status = str(item.get("status") or "pending").strip().lower()
    if status not in ALERT_INBOX_STATUSES:
        status = "pending"
    source_id = clean_subscription_source_id(item.get("sourceId"), "")
    event_id = clean_display_text(
        str(item.get("id") or stable_text_hash(f"{created_at}\n{source_id}\n{paper_key_value}\n{candidate['textHash']}")[:16]),
        32,
    )
    return {
        "id": event_id,
        "createdAt": created_at,
        "updatedAt": str(item.get("updatedAt") or created_at),
        "sourceId": source_id,
        "sourceLabel": source_label,
        "provider": clean_subscription_source_id(item.get("provider"), ""),
        "authorizationMode": str(item.get("authorizationMode") or "manual-alert")
            if str(item.get("authorizationMode") or "manual-alert") in SUBSCRIPTION_AUTHORIZATION_MODES
            else "manual-alert",
        "paperKey": paper_key_value,
        "title": clean_display_text(str(item.get("title") or ""), 180),
        "doi": clean_display_text(str(item.get("doi") or ""), 120),
        "status": status,
        "importState": clean_display_text(str(item.get("importState") or ""), 32),
        "candidate": candidate,
        "currentSourceLabel": clean_display_text(str(item.get("currentSourceLabel") or ""), 80),
        "currentTextHash": str(item.get("currentTextHash") or "")[:64],
        "locked": bool(item.get("locked")),
        "ignored": bool(item.get("ignored")),
        "hasConflict": bool(item.get("hasConflict")),
        "canAdopt": bool(item.get("canAdopt")),
        "summary": clean_display_text(str(item.get("summary") or ""), 240),
        "actionAt": str(item.get("actionAt") or ""),
        "action": clean_display_text(str(item.get("action") or ""), 48),
    }


def alert_inbox_event_summary(event: dict) -> str:
    candidate = event.get("candidate") if isinstance(event.get("candidate"), dict) else {}
    title = clean_display_text(str(event.get("title") or "Untitled"), 120)
    status = str(event.get("status") or "pending")
    label = clean_display_text(str(event.get("sourceLabel") or "Alert"), 80)
    completeness = str(candidate.get("completeness") or "unknown")
    return f"{label}: {title} ({completeness}, {status})."


def resolve_alert_inbox_event_state(event: dict, library: dict) -> dict:
    normalized = normalize_alert_inbox_event(event)
    if not normalized:
        return {}
    candidate = normalized["candidate"]
    key = normalized["paperKey"]
    item = library_entry_for_key(library, key)
    paper = item.get("paper") if isinstance(item, dict) and isinstance(item.get("paper"), dict) else {}
    snapshot = paper_snapshot(paper) if paper else {}
    ignored = key in (library.get("ignored") or {})
    locked = bool(snapshot.get("abstractLocked"))
    current_text = clean_html(str(snapshot.get("fullAbstract") or snapshot.get("abstract") or ""))
    current_hash = stable_text_hash(current_text)
    candidate_hash = str(candidate.get("textHash") or "")
    current_source = normalize_abstract_source(snapshot.get("abstractSource"), "")
    user_confirmed_current = bool(snapshot.get("abstractConfirmedBy") == "user" and snapshot.get("abstractConfirmedAt"))
    adopted = bool(
        normalized.get("status") == "adopted"
        or (
            current_hash
            and candidate_hash
            and current_hash == candidate_hash
            and current_source == candidate.get("source")
            and user_confirmed_current
        )
    )
    candidate_complete = str(candidate.get("completeness") or "") == "complete" and not looks_truncated_text(candidate.get("text") or "")
    has_conflict = bool(
        current_hash
        and candidate_hash
        and current_hash != candidate_hash
        and abstract_completeness_for_text(current_text) == "complete"
        and candidate_complete
    )

    status = str(normalized.get("status") or "pending")
    if not snapshot:
        status = "stale"
    elif ignored:
        status = "ignored"
    elif adopted:
        status = "adopted"
    elif status in ALERT_INBOX_TERMINAL_STATUSES:
        status = status
    elif locked:
        status = "locked"
    elif not candidate_complete:
        status = "partial" if candidate.get("text") else "missing"
    elif status not in ALERT_INBOX_TERMINAL_STATUSES:
        status = "pending"

    resolved = {
        **normalized,
        "status": status,
        "title": normalized.get("title") or clean_display_text(str(snapshot.get("title") or ""), 180),
        "doi": normalized.get("doi") or clean_display_text(str(snapshot.get("doi") or ""), 120),
        "currentSourceLabel": clean_display_text(str(snapshot.get("abstractSourceLabel") or abstract_source_label(current_source)), 80),
        "currentTextHash": current_hash,
        "locked": locked,
        "ignored": ignored,
        "hasConflict": has_conflict,
        "canAdopt": bool(
            snapshot
            and not ignored
            and not locked
            and candidate_complete
            and not adopted
            and status not in ALERT_INBOX_TERMINAL_STATUSES
        ),
    }
    resolved["summary"] = normalized.get("summary") or alert_inbox_event_summary(resolved)
    return resolved


def normalize_alert_inbox(value: object, library: dict | None = None) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    seen = set()
    for raw_item in value[:MAX_ALERT_INBOX_EVENTS]:
        item = normalize_alert_inbox_event(raw_item)
        if not item:
            continue
        if library is not None:
            item = resolve_alert_inbox_event_state(item, library)
            if not item:
                continue
        key = item["id"]
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return items[:MAX_ALERT_INBOX_EVENTS]


def public_alert_inbox_status(library: dict) -> dict:
    items = normalize_alert_inbox(library.get("alertInbox"), library)
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
    return {
        "items": items,
        "counts": counts,
        "pendingCount": counts.get("pending", 0),
        "adoptableCount": sum(1 for item in items if item.get("canAdopt")),
        "lockedCount": counts.get("locked", 0),
        "conflictCount": sum(1 for item in items if item.get("hasConflict")),
        "partialCount": counts.get("partial", 0),
        "missingCount": counts.get("missing", 0),
        "adoptedCount": counts.get("adopted", 0),
    }


def add_alert_inbox_event(library: dict, source: dict, *, paper_key_value: str,
                          imported_paper: dict, stored_paper: dict,
                          import_state: str, timestamp: str) -> dict:
    normalized_source = normalize_subscription_source(source) or normalize_subscription_source(source_preset_by_id("custom-alert"))
    source_label = normalized_source["sourceLabel"]
    candidate = normalize_abstract_candidate(
        abstract_candidate_from_paper(
            {
                **imported_paper,
                "abstractSource": "alert",
                "abstractSourceLabel": source_label,
                "abstractAccessMode": "user-visible",
            },
            "alert",
            source_label,
        )
    )
    if not candidate:
        return {}
    event = normalize_alert_inbox_event({
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "sourceId": normalized_source["id"],
        "sourceLabel": source_label,
        "provider": normalized_source["provider"],
        "authorizationMode": normalized_source["authorizationMode"],
        "paperKey": paper_key_value,
        "title": stored_paper.get("title") or imported_paper.get("title"),
        "doi": stored_paper.get("doi") or imported_paper.get("doi"),
        "status": "pending",
        "importState": import_state,
        "candidate": candidate,
    })
    if not event:
        return {}
    event = resolve_alert_inbox_event_state(event, library)
    event["summary"] = alert_inbox_event_summary(event)
    library["alertInbox"] = normalize_alert_inbox([
        event,
        *(library.get("alertInbox") or []),
    ], library)
    return event


def mark_alert_inbox_event(library: dict, event_id: str, *, action: str, status: str,
                           timestamp: str, paper: dict | None = None) -> dict:
    updated_items = []
    updated_event = {}
    for item in normalize_alert_inbox(library.get("alertInbox"), library):
        if item.get("id") == event_id:
            item = {
                **item,
                "status": status,
                "updatedAt": timestamp,
                "actionAt": timestamp,
                "action": action,
            }
            if paper:
                snapshot = paper_snapshot(paper)
                item.update({
                    "currentSourceLabel": clean_display_text(str(snapshot.get("abstractSourceLabel") or ""), 80),
                    "currentTextHash": stable_text_hash(snapshot.get("fullAbstract") or snapshot.get("abstract") or ""),
                    "locked": bool(snapshot.get("abstractLocked")),
                })
            updated_event = item
        updated_items.append(item)
    library["alertInbox"] = normalize_alert_inbox(updated_items, library)
    return updated_event


def adopt_alert_inbox_candidate(library: dict, event: dict, *, lock: bool,
                                timestamp: str) -> tuple[bool, str, dict]:
    resolved = resolve_alert_inbox_event_state(event, library)
    if not resolved:
        return False, "missing", {}
    key = resolved["paperKey"]
    item = library_entry_for_key(library, key)
    if not isinstance(item, dict) or not isinstance(item.get("paper"), dict):
        mark_alert_inbox_event(library, resolved["id"], action="stale", status="stale", timestamp=timestamp)
        return False, "stale", resolved
    snapshot = paper_snapshot(item["paper"])
    if snapshot.get("abstractLocked"):
        mark_alert_inbox_event(library, resolved["id"], action="skip-locked", status="locked", timestamp=timestamp)
        return False, "locked", resolved
    candidate = normalize_abstract_candidate(resolved.get("candidate"))
    if not candidate or candidate.get("completeness") != "complete" or looks_truncated_text(candidate.get("text") or ""):
        mark_alert_inbox_event(library, resolved["id"], action="skip-incomplete", status="partial", timestamp=timestamp)
        return False, "partial", resolved

    all_candidates = normalize_abstract_candidates([candidate, *(snapshot.get("abstractCandidates") or [])])
    diagnostics = selected_abstract_diagnostics(
        [
            *normalize_abstract_diagnostics(snapshot.get("abstractDiagnostics")),
            abstract_diagnostic_from_candidate(candidate, "available", "User adopted this Alert inbox abstract."),
        ],
        candidate.get("source") or "",
    )
    updated = paper_snapshot({
        **snapshot,
        "fullAbstract": candidate["text"],
        "abstract": compact_text(candidate["text"], ABSTRACT_TEXT_LIMIT),
        "abstractSource": candidate["source"],
        "abstractSourceLabel": candidate["sourceLabel"],
        "abstractFetchedAt": candidate.get("fetchedAt") or timestamp,
        "abstractCompleteness": candidate["completeness"],
        "abstractAccessMode": candidate.get("accessMode") or "user-visible",
        "abstractDiagnostics": diagnostics,
        "abstractConflict": abstract_conflict_from_candidates(all_candidates, candidate.get("source") or ""),
        "abstractCandidates": all_candidates,
        "abstractLocked": lock,
        "abstractConfirmedAt": timestamp,
        "abstractConfirmedBy": "user",
        "abstractAudit": add_abstract_audit_event(
            snapshot,
            "alert-inbox-adopt",
            candidate=candidate,
            locked=lock,
            message="User adopted an Alert inbox abstract.",
        ),
        "metadataUpdatedAt": timestamp,
    })
    updated["paperKey"] = key
    update_library_entry_with_snapshot(library, key, updated, now=timestamp)
    mark_alert_inbox_event(library, resolved["id"], action="adopt", status="adopted", timestamp=timestamp, paper=updated)
    return True, "adopted", resolved


def alert_inbox_payload(payload: dict | None = None) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    action = str(payload.get("action") or "status").strip().lower()
    with LIBRARY_LOCK:
        library = load_library()
        timestamp = now_iso()
        if action in {"adopt", "batch-adopt"}:
            requested_ids = payload.get("eventIds") if isinstance(payload.get("eventIds"), list) else []
            requested = {str(item).strip() for item in requested_ids if str(item).strip()}
            limit = clamp_int(payload.get("limit"), default=80, minimum=1, maximum=MAX_ALERT_INBOX_EVENTS)
            lock = bool(payload.get("lock", True))
            adopted = 0
            skipped: dict[str, int] = {}
            checked = 0
            for event in normalize_alert_inbox(library.get("alertInbox"), library):
                if requested and event.get("id") not in requested:
                    continue
                if not requested and not event.get("canAdopt"):
                    continue
                if checked >= limit:
                    break
                checked += 1
                ok, reason, _event = adopt_alert_inbox_candidate(library, event, lock=lock, timestamp=timestamp)
                if ok:
                    adopted += 1
                else:
                    skipped[reason] = skipped.get(reason, 0) + 1
            save_library(library)
            library_view = compact_library(library)
            return {
                "ok": True,
                "action": action,
                "checked": checked,
                "adopted": adopted,
                "skipped": skipped,
                "alertInbox": public_alert_inbox_status(library),
                "library": library_view,
            }
        if action in {"skip", "dismiss"}:
            requested_ids = payload.get("eventIds") if isinstance(payload.get("eventIds"), list) else []
            requested = {str(item).strip() for item in requested_ids if str(item).strip()}
            if not requested:
                raise ValueError("Missing Alert inbox event IDs.")
            items = []
            updated = []
            for event in normalize_alert_inbox(library.get("alertInbox"), library):
                if event.get("id") in requested:
                    event = {
                        **event,
                        "status": "skipped",
                        "action": "skip",
                        "actionAt": timestamp,
                        "updatedAt": timestamp,
                    }
                    updated.append(event.get("id"))
                items.append(event)
            library["alertInbox"] = normalize_alert_inbox(items, library)
            save_library(library)
            return {
                "ok": True,
                "action": action,
                "updated": [item for item in updated if item],
                "alertInbox": public_alert_inbox_status(library),
                "library": compact_library(library),
            }
        if action != "status":
            raise ValueError("Unsupported Alert inbox action.")
        library["alertInbox"] = normalize_alert_inbox(library.get("alertInbox"), library)
        save_library(library)
        return {
            "ok": True,
            "alertInbox": public_alert_inbox_status(library),
            "library": compact_library(library),
        }


def radar_zotero_state(paper: dict) -> dict:
    link = paper.get("zoteroLink") if isinstance(paper.get("zoteroLink"), dict) else {}
    sync = paper.get("zoteroSync") if isinstance(paper.get("zoteroSync"), dict) else {}
    status = str(link.get("status") or ("auto" if (paper.get("zotero") or {}).get("itemKey") else "unlinked"))
    item_key = clean_zotero_item_key(link.get("itemKey") or (paper.get("zotero") or {}).get("itemKey"))
    needs_review = status in ZOTERO_BLOCKED_LINK_STATUSES
    linked = bool(item_key and not needs_review)
    return {
        "status": status,
        "itemKey": item_key,
        "linked": linked,
        "needsReview": needs_review,
        "syncStatus": str(sync.get("status") or ""),
        "synced": bool(sync.get("status") == "synced"),
    }


def radar_translation_state(paper: dict) -> dict:
    source_text = translation_source_text(paper)
    translations = normalize_translations(paper.get("translations"), paper)
    zh = translations.get("zh") if isinstance(translations.get("zh"), dict) else {}
    has_source = bool(source_text and str(paper.get("abstractCompleteness") or "") != "missing")
    stale = bool(zh.get("stale"))
    translated = bool(zh.get("text")) and not stale
    return {
        "hasSource": has_source,
        "translated": translated,
        "stale": stale,
        "missing": bool(has_source and not zh.get("text")),
        "sourceHash": stable_text_hash(source_text) if source_text else "",
    }


def radar_action_item(kind: str, title: str, reason: str, *,
                      paper: dict | None = None, event: dict | None = None,
                      priority: int = 0) -> dict:
    paper = paper if isinstance(paper, dict) else {}
    event = event if isinstance(event, dict) else {}
    paper_key_value = str(paper.get("paperKey") or event.get("paperKey") or "")
    event_id = str(event.get("id") or "")
    action_id = stable_text_hash(f"{kind}\n{paper_key_value}\n{event_id}\n{title}")[:16]
    return {
        "id": action_id,
        "type": clean_display_text(kind, 48),
        "paperKey": clean_display_text(paper_key_value, 160),
        "eventId": clean_display_text(event_id, 32),
        "title": clean_display_text(title or paper.get("title") or event.get("title") or "Untitled", 180),
        "reason": clean_display_text(reason, 240),
        "sourceLabel": clean_display_text(str(paper.get("sourceLabel") or event.get("sourceLabel") or ""), 80),
        "priority": clamp_int(priority, default=0, minimum=0, maximum=1000),
    }


def research_radar_digest_item(paper: dict) -> dict:
    snapshot = paper_snapshot(paper)
    translation = radar_translation_state(snapshot)
    zotero = radar_zotero_state(snapshot)
    health = normalize_alert_source_health(snapshot.get("alertSourceHealth"))
    completeness = str(snapshot.get("abstractCompleteness") or "unknown")
    score = 0
    if health.get("openLagging"):
        score += 70
    if translation.get("missing") or translation.get("stale"):
        score += 55
    if zotero.get("needsReview"):
        score += 50
    if zotero.get("linked") and not zotero.get("synced"):
        score += 35
    if completeness in {"missing", "partial", "needs_access"}:
        score += 30
    if not snapshot.get("readingStatus"):
        score += 8
    year = paper_year(snapshot) or 0
    if year >= 2025:
        score += 8
    abstract_text = translation_source_text(snapshot)
    return {
        "paperKey": str(snapshot.get("paperKey") or paper_key(snapshot)),
        "title": snapshot.get("title") or "Untitled",
        "sourceLabel": snapshot.get("sourceLabel") or snapshot.get("abstractSourceLabel") or "",
        "venue": snapshot.get("venue") or "",
        "year": year,
        "abstractCompleteness": completeness,
        "translation": translation,
        "zotero": zotero,
        "sourceHealth": health,
        "readingStatus": str(snapshot.get("readingStatus") or ""),
        "abstractPreview": compact_text(abstract_text, 520),
        "score": score,
    }


def research_radar_action_queue(favorites: list[dict], inbox: dict, limit: int) -> list[dict]:
    actions: list[dict] = []
    for event in (inbox.get("items") or []):
        if event.get("canAdopt"):
            actions.append(radar_action_item(
                "alert-adopt",
                event.get("title") or "Alert abstract",
                "Alert inbox has a complete user-visible abstract waiting for adoption.",
                event=event,
                priority=950,
            ))

    for paper in favorites:
        item = research_radar_digest_item(paper)
        title = item["title"]
        translation = item["translation"]
        zotero = item["zotero"]
        health = item["sourceHealth"]
        completeness = item["abstractCompleteness"]
        if health.get("openLagging"):
            actions.append(radar_action_item(
                "review-source-health",
                title,
                "Alert has the abstract, while open metadata still looks missing or delayed.",
                paper=paper,
                priority=850,
            ))
        if translation.get("missing") or translation.get("stale"):
            reason = "Chinese abstract translation is stale." if translation.get("stale") else "Chinese abstract translation is missing."
            actions.append(radar_action_item("translate", title, reason, paper=paper, priority=780))
        if zotero.get("needsReview"):
            actions.append(radar_action_item(
                "zotero-confirm",
                title,
                "Zotero binding needs confirmation before safe sync.",
                paper=paper,
                priority=740,
            ))
        elif zotero.get("linked") and not zotero.get("synced"):
            actions.append(radar_action_item(
                "zotero-sync",
                title,
                "Paper is linked to Zotero but PaperHunter translation/note sync is not current.",
                paper=paper,
                priority=610,
            ))
        if not str(paper.get("readingStatus") or ""):
            actions.append(radar_action_item(
                "read-later",
                title,
                "No reading status has been assigned yet.",
                paper=paper,
                priority=360,
            ))
        if completeness == "missing" and not paper.get("localPdfPath") and not paper.get("isDownloaded"):
            actions.append(radar_action_item(
                "ignore",
                title,
                "No usable abstract or local PDF is attached; consider moving it out of the active queue.",
                paper=paper,
                priority=220,
            ))

    seen = set()
    unique = []
    for action in sorted(actions, key=lambda item: (-int(item.get("priority") or 0), item.get("title") or "")):
        key = (action.get("type"), action.get("paperKey"), action.get("eventId"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(action)
    return unique[:limit]


def research_radar_prompt(digest: dict, actions: list[dict]) -> str:
    item_lines = []
    for item in (digest.get("items") or [])[:8]:
        item_lines.append(
            "\n".join([
                f"Title: {item.get('title') or 'Untitled'}",
                f"Source: {item.get('sourceLabel') or ''}; Year: {item.get('year') or ''}",
                f"Abstract status: {item.get('abstractCompleteness') or ''}",
                f"Abstract preview: {compact_text(str(item.get('abstractPreview') or ''), 420)}",
            ])
        )
    action_lines = [
        f"- {action.get('type')}: {action.get('title')} ({action.get('reason')})"
        for action in actions[:10]
    ]
    return (
        "You are helping a researcher triage a local paper inbox. "
        "Use only the titles and abstract previews below; do not invent paper details. "
        "Write a concise Simplified Chinese brief with: 1) today focus, 2) risks, 3) next actions.\n\n"
        f"Deterministic summary: {digest.get('summary') or ''}\n\n"
        "Papers:\n"
        f"{'\n\n'.join(item_lines) if item_lines else 'None'}\n\n"
        "Action queue:\n"
        f"{'\n'.join(action_lines) if action_lines else 'None'}"
    )


def research_radar_payload(payload: dict | None = None) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    limit = clamp_int(payload.get("limit"), default=MAX_RESEARCH_RADAR_ITEMS, minimum=4, maximum=32)
    smart = bool(payload.get("smart") or payload.get("smartBrief"))
    library = load_library()
    library_view = compact_library(library)
    favorites = library_view.get("favorites") if isinstance(library_view.get("favorites"), list) else []
    ignored = library_view.get("ignored") if isinstance(library_view.get("ignored"), list) else []
    inbox = public_alert_inbox_status(library)

    all_digest_items = [research_radar_digest_item(paper) for paper in favorites]
    all_digest_items.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("title") or "")))
    digest_items = all_digest_items[:limit]

    translation_missing = sum(1 for item in all_digest_items if item.get("translation", {}).get("missing"))
    translation_stale = sum(1 for item in all_digest_items if item.get("translation", {}).get("stale"))
    zotero_review = sum(1 for item in all_digest_items if item.get("zotero", {}).get("needsReview"))
    zotero_synced = sum(1 for paper in favorites if radar_zotero_state(paper).get("synced"))
    zotero_linked = sum(1 for paper in favorites if radar_zotero_state(paper).get("linked"))
    open_lagging = sum(1 for item in all_digest_items if item.get("sourceHealth", {}).get("openLagging"))
    abstract_partial = sum(1 for paper in favorites if str(paper.get("abstractCompleteness") or "") == "partial")
    abstract_missing = sum(1 for paper in favorites if str(paper.get("abstractCompleteness") or "") == "missing")
    actions = research_radar_action_queue(favorites, inbox, limit)

    summary_parts = [
        f"{len(favorites)} favorites",
        f"{inbox.get('pendingCount', 0)} alert pending",
        f"{translation_missing} translation missing",
        f"{translation_stale} translation stale",
        f"{zotero_review} Zotero review",
        f"{open_lagging} open metadata lagging",
    ]
    digest = {
        "generatedAt": now_iso(),
        "summary": ", ".join(summary_parts) + ".",
        "items": digest_items,
        "hash": stable_text_hash(json.dumps({
            "summary": summary_parts,
            "items": [
                {
                    "paperKey": item.get("paperKey"),
                    "score": item.get("score"),
                    "abstractCompleteness": item.get("abstractCompleteness"),
                    "translation": item.get("translation"),
                    "zotero": item.get("zotero"),
                    "sourceHealth": item.get("sourceHealth"),
                }
                for item in digest_items
            ],
            "actions": [(item.get("type"), item.get("paperKey"), item.get("eventId")) for item in actions],
        }, sort_keys=True, ensure_ascii=False))[:16],
    }
    smart_brief = {"enabled": False, "status": "skipped", "text": "", "usage": {}, "error": ""}
    if smart:
        smart_brief["enabled"] = True
        settings = load_settings()
        if not settings.get("baseUrl") or not settings.get("model") or not settings.get("apiKey"):
            smart_brief.update({"status": "failed", "error": "Model settings are incomplete."})
        else:
            try:
                text, usage = invoke_model_text(
                    settings,
                    research_radar_prompt(digest, actions),
                    max_tokens=700,
                    read_timeout=60,
                )
                smart_brief.update({"status": "done", "text": text, "usage": usage})
            except Exception as exc:
                smart_brief.update({"status": "failed", "error": normalize_model_error(exc)})

    return {
        "ok": True,
        "generatedAt": digest["generatedAt"],
        "stats": {
            "favorites": len(favorites),
            "ignored": len(ignored),
            "downloaded": sum(1 for paper in favorites if paper.get("isDownloaded")),
            "alertPending": inbox.get("pendingCount", 0),
            "alertAdoptable": inbox.get("adoptableCount", 0),
            "alertLocked": inbox.get("lockedCount", 0),
            "alertPartial": inbox.get("partialCount", 0),
            "alertAdopted": inbox.get("adoptedCount", 0),
            "translationMissing": translation_missing,
            "translationStale": translation_stale,
            "zoteroLinked": zotero_linked,
            "zoteroSynced": zotero_synced,
            "zoteroReview": zotero_review,
            "openLagging": open_lagging,
            "abstractPartial": abstract_partial,
            "abstractMissing": abstract_missing,
        },
        "digest": digest,
        "actions": actions,
        "smartBrief": smart_brief,
        "alertInbox": inbox,
        "library": library_view,
    }


def model_diagnostics(settings: dict | None = None) -> dict:
    settings = normalize_settings(settings or load_settings())
    public = public_settings(settings)
    missing = []
    if not settings.get("baseUrl"):
        missing.append("Base URL")
    if not settings.get("endpoint"):
        missing.append("Endpoint")
    if not settings.get("model"):
        missing.append("Model")
    if not settings.get("apiKey"):
        missing.append("API Key")
    configured = not missing
    api_type = normalize_api_type(settings.get("apiType"))
    fallback = {
        "available": False,
        "apiType": "",
        "endpoint": "",
        "finalUrl": "",
        "reason": "",
    }
    if api_type == "responses":
        fallback_settings = chat_fallback_settings(settings)
        fallback = {
            "available": configured,
            "apiType": "chat_completions",
            "endpoint": fallback_settings.get("endpoint", API_TYPE_ENDPOINTS["chat_completions"]),
            "finalUrl": join_url(str(fallback_settings.get("baseUrl") or ""), str(fallback_settings.get("endpoint") or "")),
            "reason": "Responses 返回 completed 但没有可见文本时，会改用 Chat Completions 路由重试。",
        }
    status = "ready" if configured else "incomplete"
    message = (
        f"{public.get('apiType')} · {public.get('model')} · {public.get('finalUrl')}"
        if configured
        else f"缺少 {', '.join(missing)}。"
    )
    return {
        "status": status,
        "configured": configured,
        "missing": missing,
        "settings": public,
        "fallback": fallback,
        "lastTest": normalize_model_test_record(settings.get("lastTest")),
        "message": message,
    }


def fulltext_task_diagnostics(limit: int = 8) -> dict:
    limit = clamp_int(limit, default=8, minimum=1, maximum=40)
    tasks = []
    if FULLTEXT_TASK_DIR.exists():
        for path in FULLTEXT_TASK_DIR.glob("*.json"):
            if not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8") as file:
                    raw_task = json.load(file)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw_task, dict):
                continue
            task = public_fulltext_task(raw_task)
            if not task.get("taskId"):
                continue
            tasks.append(task)
    tasks.sort(key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""), reverse=True)
    counts = {
        "total": len(tasks),
        "done": 0,
        "running": 0,
        "queued": 0,
        "failed": 0,
        "partial": 0,
        "resumable": 0,
    }
    for task in tasks:
        status = str(task.get("status") or "")
        if status in counts:
            counts[status] += 1
        if task.get("canResume"):
            counts["resumable"] += 1
    if counts["failed"]:
        status = "attention"
        message = f"{counts['failed']} 个全文翻译任务失败，{counts['resumable']} 个可续跑。"
    elif counts["partial"]:
        status = "attention"
        message = f"{counts['partial']} 个全文翻译任务处于可续跑状态。"
    elif counts["running"] or counts["queued"]:
        status = "running"
        message = f"{counts['running'] + counts['queued']} 个全文翻译任务正在处理或排队。"
    elif counts["done"]:
        status = "ready"
        message = f"{counts['done']} 个全文翻译任务已完成。"
    else:
        status = "empty"
        message = "暂无全文翻译任务。"
    return {
        "status": status,
        "counts": counts,
        "recent": tasks[:limit],
        "message": message,
    }


def zotero_binding_diagnostics(library: dict, limit: int = 8) -> dict:
    limit = clamp_int(limit, default=8, minimum=1, maximum=40)
    favorites = [
        (str(key), item.get("paper"))
        for key, item in (library.get("favorites") or {}).items()
        if isinstance(item, dict) and isinstance(item.get("paper"), dict)
    ]
    counts = {
        "checked": len(favorites),
        "linked": 0,
        "synced": 0,
        "needsReview": 0,
        "unlinked": 0,
        "syncReady": 0,
        "withAbstractTranslation": 0,
        "withFulltextTranslation": 0,
        "wouldAttachMarkdown": 0,
    }
    items = []
    for key, paper in favorites:
        snapshot = paper_snapshot({**paper, "paperKey": key})
        zotero_state = radar_zotero_state(snapshot)
        translation = normalize_translations(snapshot.get("translations"), snapshot).get("zh")
        fulltext = snapshot.get("fulltextTranslations") if isinstance(snapshot.get("fulltextTranslations"), list) else []
        if zotero_state.get("linked"):
            counts["linked"] += 1
        if zotero_state.get("synced"):
            counts["synced"] += 1
        if zotero_state.get("needsReview"):
            counts["needsReview"] += 1
        if not zotero_state.get("linked") and not zotero_state.get("needsReview"):
            counts["unlinked"] += 1
        if zotero_state.get("linked") and not zotero_state.get("needsReview"):
            counts["syncReady"] += 1
        if translation and translation.get("text") and not translation.get("stale"):
            counts["withAbstractTranslation"] += 1
        if fulltext:
            counts["withFulltextTranslation"] += 1
            counts["wouldAttachMarkdown"] += len(fulltext)
        sync_plan = {
            "ready": False,
            "tags": [],
            "tagCount": 0,
            "attachments": 0,
            "policy": {
                "tagPrefix": "paperhunter",
                "noteMode": "upsert-managed-note-only",
                "attachmentMode": "link-translated-markdown-only",
                "preserveUserContent": True,
            },
            "message": "需要确认 Zotero 绑定后才能生成回写计划。" if zotero_state.get("needsReview") else "暂无 canonical Zotero itemKey。",
        }
        if zotero_state.get("linked") and not zotero_state.get("needsReview"):
            try:
                payload = zotero_sync_payload(snapshot, include_fulltext=True)
                sync_plan.update({
                    "ready": True,
                    "tags": payload.get("tags") or [],
                    "tagCount": len(payload.get("tags") or []),
                    "attachments": len(payload.get("attachments") or []),
                    "policy": payload.get("policy") or sync_plan["policy"],
                    "message": "dry-run 将只写 PaperHunter 管理的 note、paperhunter:* 标签和译文 Markdown 附件。",
                })
            except Exception as exc:
                sync_plan["message"] = compact_text(str(exc), 220)
        items.append({
            "paperKey": key,
            "title": snapshot.get("title") or "",
            "status": zotero_state.get("status") or "unlinked",
            "itemKey": zotero_state.get("itemKey") or "",
            "linked": bool(zotero_state.get("linked")),
            "synced": bool(zotero_state.get("synced")),
            "needsReview": bool(zotero_state.get("needsReview")),
            "hasAbstractTranslation": bool(translation and translation.get("text") and not translation.get("stale")),
            "fulltextTranslations": len(fulltext),
            "syncPlan": sync_plan,
        })
    items.sort(key=lambda item: (not item["needsReview"], not item["linked"], item["title"]))
    if counts["needsReview"]:
        status = "attention"
        message = f"{counts['needsReview']} 篇 Zotero 绑定需要确认后才能安全回写。"
    elif counts["syncReady"]:
        status = "ready"
        message = f"{counts['syncReady']} 篇收藏已有 Zotero itemKey，可进行只写 PaperHunter 管理内容的 dry-run。"
    else:
        status = "empty"
        message = "暂无可回写的 Zotero 绑定。"
    return {
        "status": status,
        "counts": counts,
        "items": items[:limit],
        "policy": {
            "dryRunOnly": True,
            "noteMode": "upsert-managed-note-only",
            "tagPrefix": "paperhunter",
            "attachmentMode": "link-translated-markdown-only",
            "preserveUserContent": True,
        },
        "message": message,
    }


def stage8_acceptance_diagnostics(radar: dict, fulltext: dict, model: dict, zotero: dict) -> dict:
    stats = radar.get("stats") if isinstance(radar.get("stats"), dict) else {}
    fulltext_counts = fulltext.get("counts") if isinstance(fulltext.get("counts"), dict) else {}
    zotero_counts = zotero.get("counts") if isinstance(zotero.get("counts"), dict) else {}
    checks = [
        {
            "id": "model-configured",
            "label": "翻译接口已配置",
            "status": "ok" if model.get("configured") else "missing",
            "detail": model.get("message") or "",
        },
        {
            "id": "alert-entry",
            "label": "Alert 入口可见",
            "status": "ok" if (stats.get("alertAdopted", 0) or stats.get("alertPending", 0) or stats.get("alertAdoptable", 0)) else "missing",
            "detail": f"已采用 {stats.get('alertAdopted', 0)}，待处理 {stats.get('alertPending', 0)}。",
        },
        {
            "id": "abstract-translation",
            "label": "摘要翻译状态",
            "status": "ok" if stats.get("favorites", 0) and not stats.get("translationMissing", 0) and not stats.get("translationStale", 0) else "attention",
            "detail": f"缺失 {stats.get('translationMissing', 0)}，过期 {stats.get('translationStale', 0)}。",
        },
        {
            "id": "fulltext-output",
            "label": "全文译文输出",
            "status": "ok" if fulltext_counts.get("done", 0) else ("attention" if fulltext_counts.get("failed", 0) or fulltext_counts.get("partial", 0) else "missing"),
            "detail": f"完成 {fulltext_counts.get('done', 0)}，失败 {fulltext_counts.get('failed', 0)}，可续跑 {fulltext_counts.get('resumable', 0)}。",
        },
        {
            "id": "zotero-binding",
            "label": "Zotero 绑定保护",
            "status": "ok" if zotero_counts.get("syncReady", 0) else ("attention" if zotero_counts.get("needsReview", 0) else "missing"),
            "detail": f"可回写 {zotero_counts.get('syncReady', 0)}，需确认 {zotero_counts.get('needsReview', 0)}，已同步 {zotero_counts.get('synced', 0)}。",
        },
        {
            "id": "dry-run-policy",
            "label": "只读验收策略",
            "status": "ok",
            "detail": "健康检查不会触发模型调用、不会写 Zotero、不会清空 PA/ZO 数据。",
        },
    ]
    ok_count = sum(1 for item in checks if item["status"] == "ok")
    attention_count = sum(1 for item in checks if item["status"] == "attention")
    missing_count = sum(1 for item in checks if item["status"] == "missing")
    status = "ready" if ok_count == len(checks) else ("attention" if attention_count else "incomplete")
    return {
        "status": status,
        "ok": ok_count,
        "attention": attention_count,
        "missing": missing_count,
        "total": len(checks),
        "checks": checks,
        "message": f"阶段 8/9 验收检查：{ok_count}/{len(checks)} 项就绪。",
    }


def diagnostics_payload(payload: dict | None = None) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    limit = clamp_int(payload.get("limit"), default=8, minimum=4, maximum=40)
    library = load_library()
    model = model_diagnostics()
    fulltext = fulltext_task_diagnostics(limit)
    radar = research_radar_payload({"smart": False, "limit": limit})
    zotero = zotero_binding_diagnostics(library, limit)
    acceptance = stage8_acceptance_diagnostics(radar, fulltext, model, zotero)
    statuses = [model.get("status"), fulltext.get("status"), zotero.get("status"), acceptance.get("status")]
    if any(status in {"attention", "incomplete"} for status in statuses):
        overall = "attention"
    elif any(status == "empty" for status in statuses):
        overall = "partial"
    else:
        overall = "ready"
    generated_at = now_iso()
    response = {
        "ok": True,
        "generatedAt": generated_at,
        "status": overall,
        "model": model,
        "fulltext": fulltext,
        "alertInbox": radar.get("alertInbox") or {},
        "radar": {
            "stats": radar.get("stats") or {},
            "actions": radar.get("actions") or [],
            "digest": radar.get("digest") or {},
        },
        "zotero": zotero,
        "acceptance": acceptance,
        "policy": {
            "readOnly": True,
            "noModelCall": True,
            "noZoteroWrite": True,
            "preservePaperHunterZoteroBinding": True,
            "preserveUserAuthorizedEntrances": True,
        },
        "message": acceptance.get("message") or "",
    }
    response["safeReport"] = diagnostics_safe_report(response)
    return response


def diagnostics_safe_report(diagnostics: dict) -> dict:
    model = diagnostics.get("model") if isinstance(diagnostics.get("model"), dict) else {}
    settings = model.get("settings") if isinstance(model.get("settings"), dict) else {}
    fallback = model.get("fallback") if isinstance(model.get("fallback"), dict) else {}
    last_test = model.get("lastTest") if isinstance(model.get("lastTest"), dict) else {}
    fulltext = diagnostics.get("fulltext") if isinstance(diagnostics.get("fulltext"), dict) else {}
    fulltext_counts = fulltext.get("counts") if isinstance(fulltext.get("counts"), dict) else {}
    zotero = diagnostics.get("zotero") if isinstance(diagnostics.get("zotero"), dict) else {}
    zotero_counts = zotero.get("counts") if isinstance(zotero.get("counts"), dict) else {}
    acceptance = diagnostics.get("acceptance") if isinstance(diagnostics.get("acceptance"), dict) else {}
    policy = diagnostics.get("policy") if isinstance(diagnostics.get("policy"), dict) else {}
    radar = diagnostics.get("radar") if isinstance(diagnostics.get("radar"), dict) else {}
    radar_stats = radar.get("stats") if isinstance(radar.get("stats"), dict) else {}
    tasks = fulltext.get("recent") if isinstance(fulltext.get("recent"), list) else []

    recent_tasks = []
    for task in tasks[:10]:
        if not isinstance(task, dict):
            continue
        recent_tasks.append({
            "taskId": compact_text(str(task.get("taskId") or ""), 24),
            "paperKey": compact_text(str(task.get("paperKey") or ""), 80),
            "title": compact_text(str(task.get("title") or ""), 140),
            "status": task.get("status") or "",
            "completedChunks": task.get("completedChunks") or 0,
            "totalChunks": task.get("totalChunks") or 0,
            "failedChunks": task.get("failedChunks") or 0,
            "canResume": bool(task.get("canResume")),
            "updatedAt": task.get("updatedAt") or "",
            "file": compact_text(str(task.get("file") or ""), 180),
            "error": compact_text(str(task.get("error") or ""), 220),
        })

    bridge_token_masked = str(settings.get("zoteroBridgeTokenMasked") or "")
    lines = [
        "PaperHunter 安全诊断摘要",
        f"生成时间：{diagnostics.get('generatedAt') or ''}",
        f"总体状态：{diagnostics.get('status') or 'unknown'}",
        "",
        "翻译接口",
        f"- provider：{settings.get('provider') or 'custom'}",
        f"- apiType：{settings.get('apiType') or ''}",
        f"- model：{settings.get('model') or ''}",
        f"- finalUrl：{settings.get('finalUrl') or ''}",
        f"- API Key：{'已保存' if settings.get('hasApiKey') else '未保存'}"
        + (f"（{settings.get('apiKeyMasked')}）" if settings.get("apiKeyMasked") else ""),
        f"- 最近测试：{last_test.get('status') or '未测试'}"
        + (f"，{last_test.get('testedAt')}" if last_test.get("testedAt") else ""),
        f"- fallback：{fallback.get('apiType') if fallback.get('available') else '未启用'}",
        "",
        "全文任务",
        f"- total：{fulltext_counts.get('total', 0)}，done：{fulltext_counts.get('done', 0)}，running：{fulltext_counts.get('running', 0)}，queued：{fulltext_counts.get('queued', 0)}，failed：{fulltext_counts.get('failed', 0)}，resumable：{fulltext_counts.get('resumable', 0)}",
        f"- 状态：{fulltext.get('status') or ''}，{fulltext.get('message') or ''}",
        "",
        "Zotero / Bridge",
        f"- Zotero 可回写条目：{zotero_counts.get('syncReady', 0)}，需确认：{zotero_counts.get('needsReview', 0)}，已同步：{zotero_counts.get('synced', 0)}",
        f"- Bridge token：{'已配置' if settings.get('hasZoteroBridgeToken') else '未配置'}"
        + (f"（{bridge_token_masked}）" if bridge_token_masked else ""),
        f"- 期望 Bridge：{ZOTERO_BRIDGE_VERSION} / protocol {ZOTERO_BRIDGE_PROTOCOL_VERSION}",
        "",
        "验收与策略",
        f"- 验收：{acceptance.get('ok', 0)}/{acceptance.get('total', 0)}，attention：{acceptance.get('attention', 0)}，missing：{acceptance.get('missing', 0)}",
        f"- 只读：{bool(policy.get('readOnly'))}，不触发模型调用：{bool(policy.get('noModelCall'))}，不写 Zotero：{bool(policy.get('noZoteroWrite'))}",
    ]
    if recent_tasks:
        lines.extend(["", "最近全文任务"])
        for task in recent_tasks[:5]:
            lines.append(
                f"- {task.get('status') or 'unknown'} · {task.get('completedChunks', 0)}/{task.get('totalChunks', 0)} · "
                f"{task.get('title') or task.get('paperKey') or task.get('taskId')}"
            )

    return {
        "generatedAt": diagnostics.get("generatedAt") or "",
        "status": diagnostics.get("status") or "",
        "text": "\n".join(lines),
        "json": {
            "generatedAt": diagnostics.get("generatedAt") or "",
            "status": diagnostics.get("status") or "",
            "model": {
                "status": model.get("status") or "",
                "configured": bool(model.get("configured")),
                "provider": settings.get("provider") or "",
                "apiType": settings.get("apiType") or "",
                "model": settings.get("model") or "",
                "finalUrl": settings.get("finalUrl") or "",
                "hasApiKey": bool(settings.get("hasApiKey")),
                "apiKeyMasked": settings.get("apiKeyMasked") or "",
                "lastTest": {
                    "status": last_test.get("status") or "",
                    "testedAt": last_test.get("testedAt") or "",
                    "apiType": last_test.get("apiType") or "",
                    "finalUrl": last_test.get("finalUrl") or "",
                    "textLength": last_test.get("textLength") or 0,
                    "error": compact_text(str(last_test.get("error") or ""), 220),
                },
                "fallback": {
                    "available": bool(fallback.get("available")),
                    "apiType": fallback.get("apiType") or "",
                    "endpoint": fallback.get("endpoint") or "",
                    "finalUrl": fallback.get("finalUrl") or "",
                },
            },
            "fulltext": {
                "status": fulltext.get("status") or "",
                "counts": fulltext_counts,
                "recent": recent_tasks,
            },
            "zotero": {
                "status": zotero.get("status") or "",
                "counts": zotero_counts,
                "hasBridgeToken": bool(settings.get("hasZoteroBridgeToken")),
                "bridgeTokenMasked": bridge_token_masked,
                "expectedBridgeVersion": ZOTERO_BRIDGE_VERSION,
                "expectedBridgeProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
            },
            "radar": {
                "favorites": radar_stats.get("favorites", 0),
                "alertPending": radar_stats.get("alertPending", 0),
                "alertAdopted": radar_stats.get("alertAdopted", 0),
                "translationMissing": radar_stats.get("translationMissing", 0),
                "translationStale": radar_stats.get("translationStale", 0),
            },
            "acceptance": {
                "status": acceptance.get("status") or "",
                "ok": acceptance.get("ok", 0),
                "attention": acceptance.get("attention", 0),
                "missing": acceptance.get("missing", 0),
                "total": acceptance.get("total", 0),
            },
            "policy": {
                "readOnly": bool(policy.get("readOnly")),
                "noModelCall": bool(policy.get("noModelCall")),
                "noZoteroWrite": bool(policy.get("noZoteroWrite")),
                "preservePaperHunterZoteroBinding": bool(policy.get("preservePaperHunterZoteroBinding")),
            },
        },
        "privacy": {
            "redacted": ["apiKey", "zoteroBridgeToken"],
            "containsRawSecrets": False,
        },
    }


def bridge_reinstall_reminder(imported_settings: bool, settings: dict | None = None) -> dict:
    current_settings = public_settings(settings or load_settings())
    required = bool(imported_settings)
    return {
        "required": required,
        "reason": "settings_import_rotated_pairing_token" if required else "",
        "expectedVersion": ZOTERO_BRIDGE_VERSION,
        "expectedProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
        "downloadUrl": ZOTERO_BRIDGE_DOWNLOAD_URL,
        "downloadUrlWithVersion": f"{ZOTERO_BRIDGE_DOWNLOAD_URL}?version={ZOTERO_BRIDGE_VERSION}",
        "tokenMasked": current_settings.get("zoteroBridgeTokenMasked") or "",
        "message": (
            "备份导入后已为这台 PaperHunter 重新生成 Bridge 配对 token。"
            f"请重新下载并覆盖安装 Bridge {ZOTERO_BRIDGE_VERSION} XPI，然后重启 Zotero 并刷新状态。"
            if required
            else "未导入设置，当前 Bridge 配对无需因本次备份导入而重装。"
        ),
        "steps": ZOTERO_BRIDGE_INSTALL_STEPS if required else [],
    }


def public_subscription_status(library: dict) -> dict:
    sources = normalize_subscription_sources(library.get("subscriptionSources"))
    history = normalize_alert_import_history(library.get("alertImportHistory"))
    inbox = public_alert_inbox_status(library)
    enabled_count = sum(1 for source in sources if source.get("enabled"))
    last_import = history[0] if history else {}
    return {
        "sources": sources,
        "alertImportHistory": history[:MAX_ALERT_IMPORT_HISTORY],
        "alertInbox": inbox,
        "enabledCount": enabled_count,
        "lastImport": last_import,
        "policy": "No scraping or access bypass. PaperHunter uses user-visible alert text, official APIs/exports, and local Zotero data.",
        "freshnessNote": "Subscription alerts may arrive before open metadata indexes; open sources can lag new journals or newly published records.",
    }


def subscription_sources_payload(payload: dict | None = None) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    action = str(payload.get("action") or "status").strip().lower()
    with LIBRARY_LOCK:
        library = load_library()
        now = now_iso()
        if action == "reset":
            library["subscriptionSources"] = normalize_subscription_sources([])
            save_library(library)
        elif action in {"save", "update", "upsert", "toggle"}:
            source_payload = payload.get("source") if isinstance(payload.get("source"), dict) else {}
            if not source_payload:
                raise ValueError("Missing subscription source configuration.")
            source = normalize_subscription_source({
                **source_payload,
                "updatedAt": now,
            })
            if not source:
                raise ValueError("Invalid subscription source configuration.")
            sources = normalize_subscription_sources(library.get("subscriptionSources"))
            by_id = {item["id"]: item for item in sources}
            existing = by_id.get(source["id"], {})
            if action == "toggle":
                source["enabled"] = not bool(existing.get("enabled", source.get("enabled", True)))
            source["createdAt"] = existing.get("createdAt") or now
            by_id[source["id"]] = normalize_subscription_source({**existing, **source})
            library["subscriptionSources"] = list(by_id.values())
            save_library(library)
        elif action != "status":
            raise ValueError("Unsupported subscription source action.")
        status = public_subscription_status(library)
        library_view = compact_library(library)
    return {"ok": True, **status, "library": library_view}


def normalize_zotero_audit(items: object) -> list[dict]:
    if not isinstance(items, list):
        return []

    audit = []
    for item in items[:MAX_ZOTERO_AUDIT_EVENTS]:
        if not isinstance(item, dict):
            continue
        action = clean_display_text(str(item.get("action") or ""), 48)
        created_at = str(item.get("createdAt") or "")
        if not action or not created_at:
            continue
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        audit.append({
            "createdAt": created_at,
            "action": action,
            "paperKey": clean_display_text(str(item.get("paperKey") or ""), 140),
            "title": clean_display_text(str(item.get("title") or ""), 160),
            "itemKey": clean_zotero_item_key(item.get("itemKey")),
            "status": clean_display_text(str(item.get("status") or ""), 32),
            "message": clean_display_text(str(item.get("message") or ""), 260),
            "details": details,
        })
    return audit[:MAX_ZOTERO_AUDIT_EVENTS]


def migrate_library(data: object) -> dict:
    library = empty_library()
    if not isinstance(data, dict):
        return library

    entries = data.get("papers")
    if isinstance(entries, dict):
        for raw_key, raw_entry in entries.items():
            entry = normalize_library_entry(raw_entry)
            if not entry:
                continue
            key = str(raw_key or entry["paper"].get("paperKey") or paper_key(entry["paper"])).strip()
            entry["paper"]["paperKey"] = key
            library["papers"][key] = entry

    for section in ("favorites", "ignored"):
        entries = data.get(section)
        if not isinstance(entries, dict):
            continue
        for raw_key, raw_entry in entries.items():
            entry = normalize_library_entry(raw_entry)
            if not entry:
                continue
            key = str(raw_key or entry["paper"].get("paperKey") or paper_key(entry["paper"])).strip()
            entry["paper"]["paperKey"] = key
            library[section][key] = entry
            library["papers"].setdefault(key, entry)

    downloads = data.get("downloads")
    if isinstance(downloads, dict):
        for raw_key, raw_entry in downloads.items():
            entry = normalize_download_entry(raw_entry)
            if not entry:
                continue
            key = str(raw_key or entry["paper"].get("paperKey") or paper_key(entry["paper"])).strip()
            entry["paper"]["paperKey"] = key
            library["downloads"][key] = entry
            library["papers"].setdefault(key, entry)
            if key in library["favorites"]:
                library["favorites"][key]["paper"]["isDownloaded"] = True

    library["history"] = normalize_history(data.get("history"))
    library["subscriptionSources"] = normalize_subscription_sources(data.get("subscriptionSources"))
    library["alertImportHistory"] = normalize_alert_import_history(data.get("alertImportHistory"))
    library["alertInbox"] = normalize_alert_inbox(data.get("alertInbox"), library)
    library["zoteroAudit"] = normalize_zotero_audit(data.get("zoteroAudit"))
    return library


def load_library() -> dict:
    with LIBRARY_LOCK:
        if not LIBRARY_PATH.exists():
            return empty_library()
        try:
            with LIBRARY_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return empty_library()

    return migrate_library(data)


def save_library(library: dict) -> None:
    with LIBRARY_LOCK:
        LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = LIBRARY_PATH.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(library, file, ensure_ascii=False, indent=2)
            file.write("\n")
        tmp_path.replace(LIBRARY_PATH)


def add_zotero_audit_event(
    library: dict,
    action: str,
    *,
    paper_key: str = "",
    paper: dict | None = None,
    item_key: str = "",
    status: str = "",
    message: str = "",
    details: dict | None = None,
) -> None:
    paper = paper if isinstance(paper, dict) else {}
    event = {
        "createdAt": now_iso(),
        "action": clean_display_text(action, 48),
        "paperKey": clean_display_text(paper_key or str(paper.get("paperKey") or ""), 140),
        "title": clean_display_text(str(paper.get("title") or ""), 160),
        "itemKey": clean_zotero_item_key(item_key),
        "status": clean_display_text(status, 32),
        "message": clean_display_text(message, 260),
        "details": details if isinstance(details, dict) else {},
    }
    audit = normalize_zotero_audit([event, *(library.get("zoteroAudit") or [])])
    library["zoteroAudit"] = audit[:MAX_ZOTERO_AUDIT_EVENTS]


def recent_zotero_audit(library: dict, limit: int = 8) -> list[dict]:
    return normalize_zotero_audit(library.get("zoteroAudit"))[:max(0, min(limit, MAX_ZOTERO_AUDIT_EVENTS))]


def latest_zotero_sync_event(library: dict) -> dict:
    for event in recent_zotero_audit(library, MAX_ZOTERO_AUDIT_EVENTS):
        if event.get("action") == "sync" and event.get("status") == "synced":
            return event
    return {}


def zotero_audit_status(payload: dict | None = None) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    limit = clamp_int(payload.get("limit"), default=MAX_ZOTERO_AUDIT_EVENTS, minimum=1, maximum=MAX_ZOTERO_AUDIT_EVENTS)
    library = load_library()
    audit = normalize_zotero_audit(library.get("zoteroAudit"))
    return {
        "ok": True,
        "total": len(audit),
        "limit": limit,
        "items": audit[:limit],
    }


def task_storage_dir() -> Path:
    FULLTEXT_TASK_DIR.mkdir(parents=True, exist_ok=True)
    return FULLTEXT_TASK_DIR


def safe_task_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-")[:140]


def fulltext_task_id(key: str) -> str:
    return safe_task_id(f"fulltext-{key}") or "fulltext-paper"


def fulltext_task_path(task_id: str) -> Path:
    safe_id = safe_task_id(task_id)
    if not safe_id:
        raise ValueError("Missing fulltext translation task ID.")
    path = (task_storage_dir() / f"{safe_id}.json").resolve()
    if task_storage_dir().resolve() not in path.parents and path != task_storage_dir().resolve():
        raise ValueError("Unsafe fulltext translation task path.")
    return path


def load_fulltext_task(task_id: str) -> dict | None:
    path = fulltext_task_path(task_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_fulltext_task(task: dict) -> None:
    with FULLTEXT_TASK_LOCK:
        path = fulltext_task_path(str(task.get("taskId") or ""))
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(task, file, ensure_ascii=False, indent=2)
            file.write("\n")
        tmp_path.replace(path)


def fulltext_thread_alive(task_id: str) -> bool:
    with FULLTEXT_TASK_LOCK:
        thread = FULLTEXT_TASK_THREADS.get(task_id)
        return bool(thread and thread.is_alive())


def public_fulltext_task(task: dict) -> dict:
    chunks = [chunk for chunk in task.get("chunks", []) if isinstance(chunk, dict)]
    total = len(chunks)
    completed = sum(1 for chunk in chunks if chunk.get("status") == "done" and chunk.get("translation"))
    failed = sum(1 for chunk in chunks if chunk.get("status") == "failed")
    current = next((chunk.get("index") for chunk in chunks if chunk.get("status") == "running"), None)
    task_id = str(task.get("taskId") or "")
    status = str(task.get("status") or "queued")
    if status in {"running", "queued"} and task_id and not fulltext_thread_alive(task_id):
        status = "partial"
    return {
        "taskId": task_id,
        "paperKey": task.get("paperKey", ""),
        "title": task.get("title", ""),
        "status": status,
        "totalChunks": total,
        "completedChunks": completed,
        "failedChunks": failed,
        "currentChunk": current,
        "canResume": bool(status in {"failed", "partial"}),
        "createdAt": task.get("createdAt", ""),
        "updatedAt": task.get("updatedAt", ""),
        "startedAt": task.get("startedAt", ""),
        "finishedAt": task.get("finishedAt", ""),
        "file": task.get("file", ""),
        "filename": task.get("filename", ""),
        "error": task.get("error", ""),
        "usage": task.get("usage", {}),
        "chunkSize": task.get("chunkSize", FULLTEXT_CHUNK_SIZE),
    }


def fulltext_task_for_paper(key: str) -> dict | None:
    task = load_fulltext_task(fulltext_task_id(key))
    if not task or task.get("paperKey") != key:
        return None
    return public_fulltext_task(task)


def empty_settings() -> dict:
    preset = provider_preset("apixin_gpt")
    return {
        "version": SETTINGS_SCHEMA_VERSION,
        "provider": preset["id"],
        "apiType": preset["apiType"],
        "baseUrl": preset["baseUrl"],
        "endpoint": preset["endpoint"],
        "model": preset["defaultModel"],
        "apiKey": "",
        "zoteroBridgeToken": "",
        "privatePdfMode": "confirm",
        "selfHostedModel": False,
        "updatedAt": "",
    }


def normalize_api_type(value: object) -> str:
    api_type = str(value or "").strip()
    return api_type if api_type in API_TYPE_ENDPOINTS else "chat_completions"


def normalize_settings(data: object, existing: dict | None = None) -> dict:
    base = existing.copy() if isinstance(existing, dict) else empty_settings()
    raw = data if isinstance(data, dict) else {}
    provider = str(raw.get("provider") or base.get("provider") or "custom").strip()
    preset = provider_preset(provider)
    api_type = normalize_api_type(raw.get("apiType") or base.get("apiType") or preset["apiType"])
    endpoint = str(raw.get("endpoint") or base.get("endpoint") or API_TYPE_ENDPOINTS[api_type]).strip()
    if not endpoint or endpoint == API_TYPE_ENDPOINTS.get(normalize_api_type(base.get("apiType"))):
        endpoint = API_TYPE_ENDPOINTS[api_type]

    api_key = raw.get("apiKey")
    if api_key is None:
        api_key = base.get("apiKey", "")
    private_pdf_mode = str(raw.get("privatePdfMode") if raw.get("privatePdfMode") is not None else base.get("privatePdfMode") or "confirm").strip()
    if private_pdf_mode not in {"confirm", "local_only"}:
        private_pdf_mode = "confirm"
    bridge_token = str(raw.get("zoteroBridgeToken") or base.get("zoteroBridgeToken") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{24,96}", bridge_token):
        bridge_token = secrets.token_urlsafe(32)

    settings = {
        "version": SETTINGS_SCHEMA_VERSION,
        "provider": provider,
        "apiType": api_type,
        "baseUrl": str(raw.get("baseUrl") if raw.get("baseUrl") is not None else base.get("baseUrl") or preset["baseUrl"]).strip().rstrip("/"),
        "endpoint": endpoint if endpoint.startswith("/") else f"/{endpoint}",
        "model": str(raw.get("model") if raw.get("model") is not None else base.get("model") or preset["defaultModel"]).strip(),
        "apiKey": str(api_key or "").strip(),
        "zoteroBridgeToken": bridge_token,
        "privatePdfMode": private_pdf_mode,
        "selfHostedModel": bool(raw.get("selfHostedModel") if raw.get("selfHostedModel") is not None else base.get("selfHostedModel")),
        "updatedAt": str(raw.get("updatedAt") or base.get("updatedAt") or ""),
    }
    last_test = raw.get("lastTest") if isinstance(raw.get("lastTest"), dict) else base.get("lastTest")
    if isinstance(last_test, dict):
        settings["lastTest"] = normalize_model_test_record(last_test)
    return settings


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return empty_settings()
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as file:
            return normalize_settings(json.load(file))
    except (OSError, json.JSONDecodeError):
        return empty_settings()


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)
        file.write("\n")
    tmp_path.replace(SETTINGS_PATH)


def model_endpoint_is_local_or_self_hosted(settings: dict) -> bool:
    if bool(settings.get("selfHostedModel")):
        return True
    parsed = urlparse(str(settings.get("baseUrl") or ""))
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    return host in {"localhost", "::1"} or host.startswith("127.") or host.endswith(".local")


def public_settings(settings: dict) -> dict:
    endpoint = settings.get("endpoint") or API_TYPE_ENDPOINTS[normalize_api_type(settings.get("apiType"))]
    public = {
        "version": SETTINGS_SCHEMA_VERSION,
        "provider": settings.get("provider", "custom"),
        "apiType": normalize_api_type(settings.get("apiType")),
        "baseUrl": settings.get("baseUrl", ""),
        "endpoint": endpoint,
        "model": settings.get("model", ""),
        "hasApiKey": bool(settings.get("apiKey")),
        "apiKeyMasked": mask_secret(str(settings.get("apiKey", ""))),
        "hasZoteroBridgeToken": bool(settings.get("zoteroBridgeToken")),
        "zoteroBridgeTokenMasked": mask_secret(str(settings.get("zoteroBridgeToken", ""))),
        "finalUrl": join_url(str(settings.get("baseUrl", "")), str(endpoint)),
        "privatePdfMode": settings.get("privatePdfMode", "confirm"),
        "selfHostedModel": bool(settings.get("selfHostedModel")),
        "modelEndpointIsLocal": model_endpoint_is_local_or_self_hosted(settings),
        "updatedAt": settings.get("updatedAt", ""),
    }
    if isinstance(settings.get("lastTest"), dict):
        public["lastTest"] = normalize_model_test_record(settings["lastTest"])
    return public


def normalize_model_test_record(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    status = str(value.get("status") or "")
    if status not in {"success", "failed"}:
        status = "failed" if value.get("error") else "success"
    usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
    return {
        "status": status,
        "testedAt": str(value.get("testedAt") or ""),
        "provider": clean_display_text(str(value.get("provider") or ""), 48),
        "apiType": normalize_api_type(value.get("apiType")),
        "fallbackApiType": clean_display_text(str(value.get("fallbackApiType") or ""), 48),
        "baseUrl": clean_display_text(str(value.get("baseUrl") or ""), 220),
        "endpoint": clean_display_text(str(value.get("endpoint") or ""), 120),
        "finalUrl": clean_display_text(str(value.get("finalUrl") or ""), 260),
        "model": clean_display_text(str(value.get("model") or ""), 120),
        "sample": compact_text(str(value.get("sample") or ""), 160),
        "textLength": clamp_int(value.get("textLength"), default=0, minimum=0, maximum=100000),
        "usage": usage,
        "error": compact_text(str(value.get("error") or ""), 500),
    }


def model_test_record(settings: dict, *, status: str, text: str = "", usage: dict | None = None,
                      error: str = "") -> dict:
    usage = usage if isinstance(usage, dict) else {}
    api_type = normalize_api_type(settings.get("apiType"))
    fallback_api_type = str(usage.get("fallbackApiType") or "")
    return normalize_model_test_record({
        "status": status,
        "testedAt": now_iso(),
        "provider": settings.get("provider", ""),
        "apiType": api_type,
        "fallbackApiType": fallback_api_type,
        "baseUrl": settings.get("baseUrl", ""),
        "endpoint": settings.get("endpoint", ""),
        "finalUrl": join_url(str(settings.get("baseUrl", "")), str(settings.get("endpoint", ""))),
        "model": settings.get("model", ""),
        "sample": compact_text(text, 160),
        "textLength": len(clean_html(text)),
        "usage": usage,
        "error": error,
    })


def persist_model_test_record(record: dict) -> None:
    try:
        current = load_settings()
        current["lastTest"] = normalize_model_test_record(record)
        save_settings(current)
    except Exception:
        return


def model_settings_status() -> dict:
    settings = load_settings()
    return {
        "ok": True,
        "providers": MODEL_PROVIDER_PRESETS,
        "apiTypes": API_TYPE_ENDPOINTS,
        "settings": public_settings(settings),
    }


def save_model_settings(payload: dict) -> dict:
    existing = load_settings()
    raw_settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
    settings = normalize_settings(raw_settings, existing)
    settings["updatedAt"] = now_iso()
    save_settings(settings)
    return {
        "ok": True,
        "providers": MODEL_PROVIDER_PRESETS,
        "apiTypes": API_TYPE_ENDPOINTS,
        "settings": public_settings(settings),
    }


def settings_without_api_key(settings: dict) -> dict:
    cleaned = settings.copy()
    cleaned["apiKey"] = ""
    cleaned["zoteroBridgeToken"] = ""
    cleaned["apiKeyRemoved"] = True
    cleaned["zoteroBridgeTokenRemoved"] = True
    return cleaned


def extract_responses_text(data: dict) -> str:
    if data.get("output_text"):
        return str(data.get("output_text"))
    if isinstance(data.get("choices"), list):
        text = extract_chat_completion_text(data)
        if text:
            return text
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("text"), str) and item.get("text"):
            return str(item.get("text"))
        if isinstance(item.get("content"), str) and item.get("content"):
            return str(item.get("content"))
        for content in item.get("content") or []:
            if isinstance(content, str) and content:
                return content
            if not isinstance(content, dict):
                continue
            if content.get("text"):
                return str(content.get("text"))
            if content.get("output_text"):
                return str(content.get("output_text"))
            if isinstance(content.get("content"), str) and content.get("content"):
                return str(content.get("content"))
    return ""


def extract_chat_completion_text(data: dict) -> str:
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
    return str(message.get("content") or choices[0].get("text") or "")


def extract_anthropic_text(data: dict) -> str:
    for item in data.get("content") or []:
        if isinstance(item, dict) and item.get("text"):
            return str(item.get("text"))
    return ""


def normalize_model_error(exc: Exception) -> str:
    if isinstance(exc, requests.Timeout):
        return "测试连接超时，请检查网络、Base URL 或稍后重试。"
    if isinstance(exc, requests.ConnectionError):
        return "无法连接到模型接口，请检查 Base URL 和网络。"
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        response = exc.response
        status = response.status_code
        body = compact_text(response.text, 260)
        lowered = body.lower()
        if status in {401, 403}:
            return "API Key 无效或没有权限，请检查密钥和服务商权限。"
        if status == 404:
            return "接口地址或模型不存在，请检查 Endpoint 和 Model。"
        if status == 429:
            return "请求被限流，请稍后重试或检查服务商额度。"
        if status in {402, 409} or "insufficient" in lowered or "quota" in lowered or "balance" in lowered:
            return "服务商返回额度或权限不足，请到对应控制台检查。"
        return f"模型接口返回 HTTP {status}: {body}"
    return compact_text(str(exc), 260) or "测试连接失败。"


def post_model_json(url: str, headers: dict, body: dict, read_timeout: int = 30) -> dict:
    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=model_request_timeout(read_timeout),
    )
    response.raise_for_status()
    try:
        # Some model gateways send UTF-8 JSON with a missing or wrong charset header.
        content = getattr(response, "content", None)
        if isinstance(content, (bytes, bytearray)):
            data = json.loads(bytes(content).decode("utf-8-sig"))
        else:
            data = response.json()
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("模型接口没有返回 JSON。") from exc
    if not isinstance(data, dict):
        raise RuntimeError("模型接口返回格式不是 JSON 对象。")
    return data


def responses_input_message(prompt: str) -> list[dict]:
    return [{"role": "user", "content": prompt}]


def test_responses_connection(settings: dict) -> tuple[str, dict]:
    url = join_url(settings["baseUrl"], settings["endpoint"])
    data = post_model_json(
        url,
        {
            "Authorization": f"Bearer {settings['apiKey']}",
            "Content-Type": "application/json",
        },
        {
            "model": settings["model"],
            "input": responses_input_message("Reply with exactly OK."),
            "max_output_tokens": 64,
        },
    )
    text = extract_responses_text(data)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    if not text:
        text, usage = responses_empty_fallback(settings, "Reply with exactly OK.", 64)
        usage = {**usage, "fallbackApiType": "chat_completions"} if isinstance(usage, dict) else {"fallbackApiType": "chat_completions"}
    return text, usage


def test_chat_completions_connection(settings: dict) -> tuple[str, dict]:
    url = join_url(settings["baseUrl"], settings["endpoint"])
    data = post_model_json(
        url,
        {
            "Authorization": f"Bearer {settings['apiKey']}",
            "Content-Type": "application/json",
        },
        {
            "model": settings["model"],
            "messages": [{"role": "user", "content": "Reply with exactly OK."}],
            "max_tokens": 8,
            "temperature": 0,
        },
    )
    return extract_chat_completion_text(data), data.get("usage") if isinstance(data.get("usage"), dict) else {}


def chat_fallback_settings(settings: dict) -> dict:
    fallback = settings.copy()
    fallback["apiType"] = "chat_completions"
    fallback["endpoint"] = API_TYPE_ENDPOINTS["chat_completions"]
    return normalize_settings(fallback, settings)


def responses_empty_fallback(settings: dict, prompt: str, max_tokens: int, read_timeout: int = 30) -> tuple[str, dict]:
    fallback = chat_fallback_settings(settings)
    data = post_model_json(
        join_url(fallback["baseUrl"], fallback["endpoint"]),
        model_headers(fallback),
        {
            "model": fallback["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        },
        read_timeout=read_timeout,
    )
    text = extract_chat_completion_text(data)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return text, usage


def test_anthropic_connection(settings: dict) -> tuple[str, dict]:
    url = join_url(settings["baseUrl"], settings["endpoint"])
    data = post_model_json(
        url,
        {
            "x-api-key": settings["apiKey"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        {
            "model": settings["model"],
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "Reply with exactly OK."}],
        },
    )
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return extract_anthropic_text(data), usage


def model_headers(settings: dict) -> dict:
    api_type = normalize_api_type(settings.get("apiType"))
    if api_type == "anthropic_messages":
        return {
            "x-api-key": settings["apiKey"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    return {
        "Authorization": f"Bearer {settings['apiKey']}",
        "Content-Type": "application/json",
    }


def invoke_model_text(settings: dict, prompt: str, max_tokens: int = 900, read_timeout: int = 30) -> tuple[str, dict]:
    api_type = normalize_api_type(settings.get("apiType"))
    url = join_url(settings["baseUrl"], settings["endpoint"])
    if api_type == "responses":
        data = post_model_json(
            url,
            model_headers(settings),
            {
                "model": settings["model"],
                "input": responses_input_message(prompt),
                "max_output_tokens": max_tokens,
            },
            read_timeout=read_timeout,
        )
        text = extract_responses_text(data)
        if not text:
            text, usage = responses_empty_fallback(settings, prompt, max_tokens, read_timeout=read_timeout)
            usage = {**usage, "fallbackApiType": "chat_completions"} if isinstance(usage, dict) else {"fallbackApiType": "chat_completions"}
            return clean_html(text), usage
    elif api_type == "anthropic_messages":
        data = post_model_json(
            url,
            model_headers(settings),
            {
                "model": settings["model"],
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            read_timeout=read_timeout,
        )
        text = extract_anthropic_text(data)
    else:
        data = post_model_json(
            url,
            model_headers(settings),
            {
                "model": settings["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
            read_timeout=read_timeout,
        )
        text = extract_chat_completion_text(data)
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return clean_html(text), usage


def test_model_connection(payload: dict) -> dict:
    existing = load_settings()
    raw_settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
    settings = normalize_settings(raw_settings, existing)
    if not settings.get("baseUrl"):
        raise ValueError("请填写 Base URL。")
    if not settings.get("model"):
        raise ValueError("请填写模型名称。")
    if not settings.get("apiKey"):
        raise ValueError("请填写 API Key，或先保存已有密钥。")

    api_type = normalize_api_type(settings.get("apiType"))
    testers = {
        "responses": test_responses_connection,
        "chat_completions": test_chat_completions_connection,
        "anthropic_messages": test_anthropic_connection,
    }
    try:
        text, usage = testers[api_type](settings)
    except Exception as exc:
        message = normalize_model_error(exc)
        persist_model_test_record(model_test_record(settings, status="failed", usage={}, error=message))
        raise RuntimeError(message) from exc
    if not clean_html(text):
        message = "模型接口没有返回文本。请检查模型名称、接口类型或服务商兼容性。"
        persist_model_test_record(model_test_record(settings, status="failed", usage=usage, error=message))
        raise RuntimeError(message)

    record = model_test_record(settings, status="success", text=text or "OK", usage=usage)
    persist_model_test_record(record)

    return {
        "ok": True,
        "message": "测试连接成功。",
        "provider": settings.get("provider"),
        "apiType": api_type,
        "finalUrl": join_url(settings["baseUrl"], settings["endpoint"]),
        "model": settings.get("model"),
        "sample": compact_text(text or "OK", 120),
        "usage": usage,
        "lastTest": record,
    }


def abstract_translation_prompt(paper: dict, source_text: str) -> str:
    title = clean_html(str(paper.get("title") or "Untitled"))
    return (
        "你是严谨的学术论文摘要翻译助手。请把下面英文论文摘要翻译为简体中文。\n"
        "要求：保留术语准确性；不要添加原文没有的信息；不要输出解释、标题或项目符号；只输出中文译文。\n\n"
        f"论文标题：{title}\n\n"
        f"英文摘要：\n{source_text}"
    )


def update_paper_translation(library: dict, key: str, paper: dict, translation: dict) -> None:
    snapshot = paper_snapshot(paper)
    translations = snapshot.get("translations") if isinstance(snapshot.get("translations"), dict) else {}
    translations["zh"] = translation
    snapshot["translations"] = normalize_translations(translations, snapshot)
    now = now_iso()
    library["papers"][key] = {
        "createdAt": (library.get("papers", {}).get(key) or {}).get("createdAt", now),
        "updatedAt": now,
        "paper": snapshot,
    }
    for section in ("favorites", "ignored"):
        item = library.get(section, {}).get(key)
        if isinstance(item, dict):
            item["paper"] = snapshot
            item["updatedAt"] = now


def translate_abstract(payload: dict) -> dict:
    paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
    if not paper:
        raise ValueError("缺少论文数据。")

    source_text = translation_source_text(paper)
    if not source_text or source_text == "暂无摘要。":
        raise ValueError("这篇论文没有可翻译的摘要。")

    settings = load_settings()
    if not settings.get("baseUrl") or not settings.get("model") or not settings.get("apiKey"):
        raise ValueError("请先在模型设置中配置 Base URL、Model 和 API Key。")

    source_hash = stable_text_hash(source_text)
    prompt = abstract_translation_prompt(paper, source_text)
    try:
        translated_text, usage = invoke_model_text(settings, prompt, max_tokens=1000)
    except Exception as exc:
        raise RuntimeError(normalize_model_error(exc)) from exc
    if not translated_text:
        raise RuntimeError("模型没有返回译文。")

    key = str(payload.get("paperKey") or paper.get("paperKey") or paper_key(paper)).strip()
    translation = {
        "text": translated_text,
        "language": "zh",
        "provider": settings.get("provider", ""),
        "model": settings.get("model", ""),
        "translatedAt": now_iso(),
        "promptVersion": TRANSLATION_PROMPT_VERSION,
        "sourceHash": source_hash,
        "stale": False,
    }

    with LIBRARY_LOCK:
        library = load_library()
        update_paper_translation(library, key, {**paper, "paperKey": key}, translation)
        save_library(library)
        library_view = compact_library(library)

    return {
        "ok": True,
        "paperKey": key,
        "translation": translation,
        "usage": usage,
        "library": library_view,
    }


def should_translate_paper(paper: dict, force: bool = False) -> bool:
    if force:
        return True
    translation = normalize_translations(paper.get("translations"), paper).get("zh")
    return not translation or bool(translation.get("stale"))


def batch_translate_abstracts(payload: dict) -> dict:
    force = bool(payload.get("force", False))
    limit = clamp_int(payload.get("limit"), default=50, minimum=1, maximum=200)
    with LIBRARY_LOCK:
        library = load_library()
        favorites = [
            item.get("paper")
            for item in (library.get("favorites") or {}).values()
            if isinstance(item, dict) and isinstance(item.get("paper"), dict)
        ]

    candidates = [paper for paper in favorites if should_translate_paper(paper, force)][:limit]
    if not candidates:
        return {
            "ok": True,
            "checked": len(favorites),
            "translated": 0,
            "skipped": len(favorites),
            "failed": 0,
            "errors": {},
            "usage": {},
            "library": compact_library(library),
        }

    translated = 0
    errors = {}
    total_usage: dict[str, int] = {}
    for paper in candidates:
        key = str(paper.get("paperKey") or paper_key(paper))
        try:
            result = translate_abstract({"paper": paper, "paperKey": key})
            translated += 1
            for usage_key, value in (result.get("usage") or {}).items():
                if isinstance(value, int):
                    total_usage[usage_key] = total_usage.get(usage_key, 0) + value
        except Exception as exc:
            errors[key] = compact_text(str(exc), 220)

    library = load_library()
    return {
        "ok": True,
        "checked": len(favorites),
        "translated": translated,
        "skipped": max(0, len(favorites) - len(candidates)),
        "failed": len(errors),
        "errors": errors,
        "usage": total_usage,
        "library": compact_library(library),
    }


def find_download_record(library: dict, key: str, paper: dict) -> tuple[str, Path]:
    local_pdf_path = str(paper.get("localPdfPath") or "")
    if local_pdf_path:
        path = Path(local_pdf_path).expanduser().resolve()
        allowed_roots = [ZOTERO_STORAGE_DIR.resolve(), DOWNLOAD_DIR.resolve()]
        if not any(path == root or root in path.parents for root in allowed_roots):
            raise ValueError("本地 PDF 路径不在允许的 PaperHunter 或 Zotero 存储目录中。")
        if not path.exists() or path.suffix.lower() != ".pdf":
            raise ValueError("未找到 Zotero PDF 附件，请确认附件仍在本机。")
        return path.name, path

    item = (library.get("downloads") or {}).get(key)
    filename = str((item or {}).get("filename") or "")
    if not filename:
        title = str(paper.get("title") or "")
        paper_id = str(paper.get("paperId") or paper.get("arxivId") or "")
        filename = sanitize_filename(title, paper_id)
    path = (DOWNLOAD_DIR / filename).resolve()
    if DOWNLOAD_DIR.resolve() not in path.parents and path != DOWNLOAD_DIR.resolve():
        raise ValueError("下载文件路径不安全。")
    if not path.exists():
        raise ValueError("未找到已下载 PDF，请先下载这篇论文。")
    return filename, path


def is_zotero_user_library_pdf(paper: dict, pdf_path: Path | None = None) -> bool:
    if str(paper.get("access") or "") == "user_library":
        return True
    if str(paper.get("source") or "") == "zotero":
        return True
    if pdf_path:
        try:
            resolved = pdf_path.resolve()
            storage_root = ZOTERO_STORAGE_DIR.resolve()
            if resolved == storage_root or storage_root in resolved.parents:
                return True
        except OSError:
            return False
    return False


def fulltext_consent_context(paper: dict, settings: dict, pdf_path: Path | None = None) -> dict:
    provider = str(settings.get("provider") or "")
    api_type = str(settings.get("apiType") or "")
    model = str(settings.get("model") or "")
    required = is_zotero_user_library_pdf(paper, pdf_path)
    private_pdf_mode = str(settings.get("privatePdfMode") or "confirm")
    endpoint_is_local = model_endpoint_is_local_or_self_hosted(settings)
    return {
        "required": required,
        "scope": "zotero-user-library-pdf" if required else "",
        "provider": provider,
        "apiType": api_type,
        "model": model,
        "privatePdfMode": private_pdf_mode,
        "selfHostedModel": bool(settings.get("selfHostedModel")),
        "modelEndpointIsLocal": endpoint_is_local,
        "strictLocalOnlySatisfied": private_pdf_mode != "local_only" or endpoint_is_local,
        "message": (
            "This PDF comes from the local Zotero library. Full-text translation sends extracted text to the configured model provider."
            if required else ""
        ),
    }


def extract_pdf_text(pdf_path: Path, max_pages: int = 12) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("全文翻译需要安装 pypdf，请先运行 pip install -r requirements.txt。") from exc

    reader = PdfReader(str(pdf_path))
    chunks = []
    for page in reader.pages[:max_pages]:
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(clean_html(text))
    extracted = "\n\n".join(chunks).strip()
    if not extracted:
        raise RuntimeError("无法从 PDF 中提取正文文本。")
    return extracted


def split_text_chunks(text: str, size: int = FULLTEXT_CHUNK_SIZE) -> list[str]:
    normalized = clean_html(text)
    chunks = []
    while normalized:
        chunk = normalized[:size]
        cut = max(chunk.rfind("\n"), chunk.rfind(". "), chunk.rfind("。"))
        if cut > size * 0.45:
            chunk = chunk[: cut + 1]
        chunks.append(chunk.strip())
        normalized = normalized[len(chunk):].strip()
    return [chunk for chunk in chunks if chunk]


def fulltext_chunk_items(text: str, size: int = FULLTEXT_CHUNK_SIZE, max_chunks: int = 30) -> list[dict]:
    return [
        {
            "index": index,
            "source": chunk,
            "sourceHash": stable_text_hash(chunk),
            "status": "pending",
            "translation": "",
            "usage": {},
            "error": "",
        }
        for index, chunk in enumerate(split_text_chunks(text, size=size)[:max_chunks], start=1)
    ]


def fulltext_translation_prompt(title: str, chunk: str, index: int, total: int) -> str:
    return (
        "你是严谨的学术论文全文翻译助手。请把下面论文正文片段翻译为简体中文。\n"
        "要求：保留公式、变量、引用编号和专有名词；不要添加原文没有的信息；"
        "保持本片段与上下文的术语和代词连续；只输出中文译文。\n\n"
        f"论文标题：{title}\n"
        f"片段：{index}/{total}\n\n"
        f"英文正文片段：\n{chunk}"
    )


def write_fulltext_markdown(paper: dict, filename: str, chunks: list[str], translations: list[str]) -> Path:
    key = paper_key(paper)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", key).strip("-") or "paper"
    output_path = (TRANSLATED_DIR / f"{safe_name}.bilingual.md").resolve()
    if TRANSLATED_DIR.resolve() not in output_path.parents and output_path != TRANSLATED_DIR.resolve():
        raise ValueError("全文翻译输出路径不安全。")
    TRANSLATED_DIR.mkdir(exist_ok=True)
    lines = [
        f"# {clean_html(str(paper.get('title') or 'Untitled'))}",
        "",
        "> PaperHunter 全文翻译实验输出。该功能不承诺 PDF 版式还原。",
        "",
        f"- 来源 PDF: `{filename}`",
        f"- 翻译时间: {now_iso()}",
        "",
    ]
    for index, (source, translated) in enumerate(zip(chunks, translations), start=1):
        lines.extend([
            f"## 片段 {index}",
            "",
            "### English",
            "",
            source,
            "",
            "### 中文",
            "",
            translated,
            "",
        ])
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return output_path


def completed_fulltext_chunks(task: dict) -> list[dict]:
    chunks = [chunk for chunk in task.get("chunks", []) if isinstance(chunk, dict)]
    if not chunks:
        raise RuntimeError("全文翻译任务没有可导出的片段。")
    ordered = sorted(chunks, key=lambda chunk: int(chunk.get("index") or 0))
    expected = list(range(1, len(ordered) + 1))
    actual = [int(chunk.get("index") or 0) for chunk in ordered]
    if actual != expected:
        raise RuntimeError("全文翻译片段编号不连续，已停止导出。")
    missing = [
        str(chunk.get("index"))
        for chunk in ordered
        if chunk.get("status") != "done" or not str(chunk.get("translation") or "").strip()
    ]
    if missing:
        raise RuntimeError(f"全文翻译还有未完成片段：{', '.join(missing)}。")
    return ordered


def write_fulltext_task_markdown(task: dict) -> Path:
    chunks = completed_fulltext_chunks(task)
    sources = [str(chunk.get("source") or "") for chunk in chunks]
    translations = [str(chunk.get("translation") or "") for chunk in chunks]
    return write_fulltext_markdown(
        task.get("paper") if isinstance(task.get("paper"), dict) else {},
        str(task.get("sourceFilename") or ""),
        sources,
        translations,
    )


def translated_relative_path(path: Path) -> str:
    clean_path = Path(path).resolve()
    try:
        return f"translated_papers/{clean_path.relative_to(TRANSLATED_DIR).as_posix()}"
    except ValueError:
        parts = clean_path.parts
        translated_dir_name = TRANSLATED_DIR.name.lower()
        for index, part in enumerate(parts):
            if part.lower() == translated_dir_name:
                relative_parts = parts[index + 1 :]
                if relative_parts:
                    return Path("translated_papers", *relative_parts).as_posix()
        raise


def update_fulltext_translation_index(library: dict, key: str, paper: dict, output_path: Path, model: str) -> None:
    existing = (
        library.get("papers", {}).get(key)
        or library.get("favorites", {}).get(key)
        or library.get("downloads", {}).get(key)
        or {}
    )
    base_paper = existing.get("paper") if isinstance(existing.get("paper"), dict) else {}
    snapshot_source = {**paper, **base_paper} if base_paper else paper
    snapshot = paper_snapshot(snapshot_source)
    fulltext = snapshot.get("fulltextTranslations")
    if not isinstance(fulltext, list):
        fulltext = []
    relative = translated_relative_path(output_path)
    fulltext = [
        item for item in fulltext
        if not (isinstance(item, dict) and str(item.get("file") or "") == relative)
    ]
    fulltext.append({
        "type": "fulltext",
        "language": "zh",
        "format": "markdown",
        "file": relative,
        "model": model,
        "createdAt": now_iso(),
    })
    snapshot["fulltextTranslations"] = fulltext
    now = now_iso()
    library["papers"][key] = {"createdAt": existing.get("createdAt", now), "updatedAt": now, "paper": snapshot}
    for section in ("favorites", "ignored"):
        if key in library.get(section, {}):
            library[section][key]["paper"] = snapshot
            library[section][key]["updatedAt"] = now


def new_fulltext_task(payload: dict) -> dict:
    paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
    if not paper:
        raise ValueError("缺少论文数据。")

    key = str(payload.get("paperKey") or paper.get("paperKey") or paper_key(paper)).strip()
    with LIBRARY_LOCK:
        library = load_library()
        filename, pdf_path = find_download_record(library, key, paper)

    settings = load_settings()
    consent = fulltext_consent_context(paper, settings, pdf_path)
    if consent.get("required") and not bool(payload.get("userLibraryConsent")):
        raise ValueError("This Zotero library PDF needs confirmation before full-text translation because extracted text will be sent to the configured model provider.")
    if consent.get("required") and not consent.get("strictLocalOnlySatisfied"):
        raise ValueError("Private Zotero PDF translation is set to local/self-hosted only. Use a localhost/self-hosted model endpoint or turn off strict private PDF mode.")

    text = extract_pdf_text(pdf_path, max_pages=clamp_int(payload.get("maxPages"), 12, 1, 30))
    chunk_size = clamp_int(payload.get("chunkSize"), FULLTEXT_CHUNK_SIZE, 500, 2400)
    max_chunks = clamp_int(payload.get("maxChunks"), 30, 1, 80)
    chunks = fulltext_chunk_items(text, size=chunk_size, max_chunks=max_chunks)
    if not chunks:
        raise RuntimeError("PDF 没有可翻译的正文片段。")

    now = now_iso()
    task = {
        "version": FULLTEXT_TASK_SCHEMA_VERSION,
        "taskId": fulltext_task_id(key),
        "paperKey": key,
        "paper": paper_snapshot(paper),
        "title": clean_html(str(paper.get("title") or "Untitled")),
        "sourceFilename": filename,
        "sourceTextHash": stable_text_hash(text),
        "chunkSize": chunk_size,
        "maxPages": clamp_int(payload.get("maxPages"), 12, 1, 30),
        "promptVersion": FULLTEXT_PROMPT_VERSION,
        "status": "queued",
        "createdAt": now,
        "updatedAt": now,
        "startedAt": "",
        "finishedAt": "",
        "file": "",
        "filename": "",
        "error": "",
        "usage": {},
        "settings": {
            "provider": settings.get("provider", ""),
            "apiType": settings.get("apiType", ""),
            "model": settings.get("model", ""),
        },
        "chunks": chunks,
    }
    save_fulltext_task(task)
    return task


def reusable_fulltext_task(payload: dict) -> dict:
    paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
    key = str(payload.get("paperKey") or paper.get("paperKey") or paper_key(paper)).strip()
    task_id = str(payload.get("taskId") or fulltext_task_id(key))
    force = bool(payload.get("force"))
    existing = None if force else load_fulltext_task(task_id)
    if existing and existing.get("paperKey") == key:
        if existing.get("status") in {"running", "queued", "done", "failed", "partial"}:
            return existing
    return new_fulltext_task(payload)


def merge_usage(total: dict, usage: dict) -> dict:
    for usage_key, value in (usage or {}).items():
        if isinstance(value, int):
            total[usage_key] = total.get(usage_key, 0) + value
    return total


def mark_fulltext_task_failed(task: dict, message: str) -> dict:
    task["status"] = "failed"
    task["error"] = compact_text(message, 500)
    task["updatedAt"] = now_iso()
    save_fulltext_task(task)
    return task


def run_fulltext_task(task_id: str) -> None:
    task = load_fulltext_task(task_id)
    if not task:
        return

    settings = load_settings()
    if not settings.get("baseUrl") or not settings.get("model") or not settings.get("apiKey"):
        mark_fulltext_task_failed(task, "请先在模型设置中配置 Base URL、Model 和 API Key。")
        return

    task["status"] = "running"
    task["error"] = ""
    task["startedAt"] = task.get("startedAt") or now_iso()
    task["updatedAt"] = now_iso()
    save_fulltext_task(task)

    chunks = [chunk for chunk in task.get("chunks", []) if isinstance(chunk, dict)]
    total = len(chunks)
    title = str(task.get("title") or "Untitled")
    usage_total = task.get("usage") if isinstance(task.get("usage"), dict) else {}

    try:
        for chunk in chunks:
            if chunk.get("status") == "done" and chunk.get("translation"):
                continue

            chunk["status"] = "running"
            chunk["error"] = ""
            task["updatedAt"] = now_iso()
            save_fulltext_task(task)

            index = clamp_int(chunk.get("index"), 1, 1, max(total, 1))
            try:
                translated, usage = invoke_model_text(
                    settings,
                    fulltext_translation_prompt(title, str(chunk.get("source") or ""), index, total),
                    max_tokens=1400,
                    read_timeout=FULLTEXT_MODEL_READ_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                chunk["status"] = "failed"
                chunk["error"] = compact_text(normalize_model_error(exc), 500)
                task["status"] = "failed"
                task["error"] = f"片段 {index} 翻译失败：{chunk['error']}"
                task["updatedAt"] = now_iso()
                save_fulltext_task(task)
                return

            if not translated:
                chunk["status"] = "failed"
                chunk["error"] = "模型没有返回译文。"
                task["status"] = "failed"
                task["error"] = f"片段 {index} 翻译失败：模型没有返回译文。"
                task["updatedAt"] = now_iso()
                save_fulltext_task(task)
                return

            chunk["translation"] = translated
            chunk["usage"] = usage
            chunk["status"] = "done"
            chunk["translatedAt"] = now_iso()
            usage_total = merge_usage(usage_total, usage)
            task["usage"] = usage_total
            task["updatedAt"] = now_iso()
            save_fulltext_task(task)

        output_path = write_fulltext_task_markdown(task)
        with LIBRARY_LOCK:
            library = load_library()
            paper = task.get("paper") if isinstance(task.get("paper"), dict) else {}
            update_fulltext_translation_index(library, str(task.get("paperKey") or ""), paper, output_path, settings.get("model", ""))
            save_library(library)

        task["status"] = "done"
        task["file"] = translated_relative_path(output_path)
        task["filename"] = output_path.name
        task["finishedAt"] = now_iso()
        task["updatedAt"] = task["finishedAt"]
        task["error"] = ""
        save_fulltext_task(task)
    finally:
        with FULLTEXT_TASK_LOCK:
            FULLTEXT_TASK_THREADS.pop(task_id, None)


def ensure_fulltext_task_running(task: dict) -> bool:
    task_id = str(task.get("taskId") or "")
    if not task_id:
        return False
    if task.get("status") == "done":
        return False
    with FULLTEXT_TASK_LOCK:
        thread = FULLTEXT_TASK_THREADS.get(task_id)
        if thread and thread.is_alive():
            return True
        task["status"] = "queued"
        task["updatedAt"] = now_iso()
        save_fulltext_task(task)
        thread = Thread(target=run_fulltext_task, args=(task_id,), daemon=True)
        FULLTEXT_TASK_THREADS[task_id] = thread
        thread.start()
        return True


def translate_fulltext(payload: dict) -> dict:
    task = reusable_fulltext_task(payload)
    ensure_fulltext_task_running(task)
    return {
        "ok": True,
        "task": public_fulltext_task(load_fulltext_task(str(task.get("taskId"))) or task),
        "library": compact_library(load_library()),
    }


def fulltext_task_status(payload: dict) -> dict:
    task_id = str(payload.get("taskId") or "")
    if not task_id:
        paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
        key = str(payload.get("paperKey") or paper.get("paperKey") or paper_key(paper)).strip()
        task_id = fulltext_task_id(key)
    task = load_fulltext_task(task_id)
    if not task:
        raise ValueError("未找到全文翻译任务。")
    return {
        "ok": True,
        "task": public_fulltext_task(task),
        "library": compact_library(load_library()),
    }


def resolve_translated_file(file_value: str) -> Path:
    value = str(file_value or "").strip().replace("\\", "/")
    if not value:
        raise ValueError("缺少全文译文文件路径。")
    if value.startswith("translated_papers/"):
        path = TRANSLATED_DIR / value[len("translated_papers/"):]
    else:
        path = TRANSLATED_DIR / value
    resolved = path.resolve()
    translated_root = TRANSLATED_DIR.resolve()
    if translated_root not in [resolved, *resolved.parents]:
        raise ValueError("全文译文文件路径不在 translated_papers 目录内。")
    if not resolved.exists() or not resolved.is_file():
        raise ValueError("全文译文文件不存在。")
    return resolved


def open_fulltext_folder(payload: dict) -> dict:
    task_id = str(payload.get("taskId") or "")
    task = load_fulltext_task(task_id) if task_id else None
    file_value = str(payload.get("file") or "")
    if not file_value and task:
        file_value = str(task.get("file") or "")
    path = resolve_translated_file(file_value)

    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", f"/select,{path}"])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        opener = "xdg-open"
        subprocess.Popen([opener, str(path.parent)])
    return {"ok": True, "file": translated_relative_path(path)}


def compact_library(library: dict) -> dict:
    favorites = []
    for key, item in (library.get("favorites") or {}).items():
        if isinstance(item, dict):
            paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            favorites.append({
                **paper,
                "paperKey": key,
                "favoritedAt": item.get("createdAt", ""),
                "refreshedAt": item.get("refreshedAt", ""),
                "fulltextTask": fulltext_task_for_paper(key),
            })

    ignored = []
    for key, item in (library.get("ignored") or {}).items():
        if isinstance(item, dict):
            paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            ignored.append({
                **paper,
                "paperKey": key,
                "ignoredAt": item.get("createdAt", ""),
                "fulltextTask": fulltext_task_for_paper(key),
            })

    favorites.sort(key=lambda paper: str(paper.get("favoritedAt", "")), reverse=True)
    ignored.sort(key=lambda paper: str(paper.get("ignoredAt", "")), reverse=True)
    recent_audit = recent_zotero_audit(library)
    latest_sync = latest_zotero_sync_event(library)
    return {
        "version": LIBRARY_SCHEMA_VERSION,
        "favorites": favorites,
        "ignored": ignored,
        "history": (library.get("history") or [])[:MAX_SEARCH_HISTORY],
        "subscriptionSources": normalize_subscription_sources(library.get("subscriptionSources")),
        "alertImportHistory": normalize_alert_import_history(library.get("alertImportHistory")),
        "alertInbox": public_alert_inbox_status(library),
        "subscription": public_subscription_status(library),
        "zoteroAudit": recent_audit,
        "zoteroLastSync": latest_sync,
        "favoriteKeys": sorted((library.get("favorites") or {}).keys()),
        "ignoredKeys": sorted((library.get("ignored") or {}).keys()),
        "downloadKeys": sorted((library.get("downloads") or {}).keys()),
        "paperKeys": sorted((library.get("papers") or {}).keys()),
    }


def apply_library_state(results: list[dict], library: dict) -> tuple[list[dict], int]:
    favorites = library.get("favorites") or {}
    ignored = library.get("ignored") or {}
    papers = library.get("papers") or {}
    annotated = []
    hidden_ignored = 0
    for paper in results:
        key = paper_key(paper)
        if key in ignored:
            hidden_ignored += 1
            continue
        stored = papers.get(key)
        if isinstance(stored, dict) and isinstance(stored.get("paper"), dict):
            stored_paper = stored["paper"]
            translations = stored_paper.get("translations")
            fulltext_translations = stored_paper.get("fulltextTranslations")
            full_abstract = stored_paper.get("fullAbstract")
            note = stored_paper.get("note")
            tags = stored_paper.get("tags")
            reading_status = stored_paper.get("readingStatus")
            is_downloaded = stored_paper.get("isDownloaded")
            zotero = stored_paper.get("zotero")
            zotero_link = stored_paper.get("zoteroLink")
            zotero_sync = stored_paper.get("zoteroSync")
            for field in ABSTRACT_METADATA_FIELDS:
                value = stored_paper.get(field)
                if value not in (None, ""):
                    paper[field] = value
            if full_abstract:
                preferred_full_abstract = full_abstract if stored_paper.get("abstractLocked") else preferred_abstract_text(paper.get("fullAbstract"), full_abstract)
                paper["fullAbstract"] = preferred_full_abstract
                paper["abstract"] = compact_text(preferred_full_abstract, ABSTRACT_TEXT_LIMIT)
            if translations:
                paper["translations"] = normalize_translations(translations, paper)
            if fulltext_translations:
                paper["fulltextTranslations"] = fulltext_translations
            if note:
                paper["note"] = note
            if tags:
                paper["tags"] = tags
            if reading_status:
                paper["readingStatus"] = reading_status
            if is_downloaded is not None:
                paper["isDownloaded"] = bool(is_downloaded)
            if isinstance(zotero, dict) and zotero.get("itemKey"):
                paper["zotero"] = zotero
            if isinstance(zotero_link, dict):
                paper["zoteroLink"] = zotero_link
            if isinstance(zotero_sync, dict):
                paper["zoteroSync"] = zotero_sync
        paper["paperKey"] = key
        paper["isFavorite"] = key in favorites
        if key in library.get("downloads", {}):
            paper["isDownloaded"] = True
        paper["isIgnored"] = False
        annotated.append(paper)
    return annotated, hidden_ignored


def add_search_history(library: dict, payload: dict, result_count: int, source_counts: dict[str, int]) -> None:
    query = str(payload.get("query", "")).strip()
    if not query:
        return

    entry = {
        "query": query,
        "createdAt": now_iso(),
        "resultCount": result_count,
        "sources": get_selected_sources(payload),
        "fieldPreset": str(payload.get("fieldPreset", "all")),
        "intent": str(payload.get("intent", "general")),
        "sortBy": str(payload.get("sortBy", "recent")),
        "sourceCounts": source_counts,
    }
    existing = [
        item for item in library.get("history", [])
        if normalize_key(str(item.get("query", ""))) != normalize_key(query)
    ]
    library["history"] = [entry, *existing][:MAX_SEARCH_HISTORY]


def paper_identity_values(paper: dict) -> set[str]:
    values = set()
    for field in ("paperId", "arxivId", "doi", "DOI", "pageUrl", "entryUrl", "pdfUrl", "title"):
        value = normalize_key(str(paper.get(field, "")))
        if value:
            values.add(value)
    return values


def normalized_identity_url(value: object) -> str:
    text = clean_html(str(value or "")).strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme and not parsed.netloc:
        return normalize_key(text)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = unquote(parsed.path or "").rstrip("/")
    return f"{host}{path}".lower()


def paper_url_values(paper: dict) -> set[str]:
    values = set()
    for field in ("pageUrl", "entryUrl", "pdfUrl", "url"):
        value = normalized_identity_url(paper.get(field))
        if value:
            values.add(value)
    return values


def paper_identifier_values(paper: dict) -> set[str]:
    values = set()
    for field in ("paperId", "arxivId", "archiveLocation"):
        value = normalize_key(str(paper.get(field, "")))
        if value:
            values.add(value)
    doi = normalize_key(paper_doi(paper))
    if doi:
        values.add(doi)
    return values


def title_similarity(left: str, right: str) -> float:
    left_terms = set(query_terms(left, min_length=3))
    right_terms = set(query_terms(right, min_length=3))
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def paper_match_score(left: dict, right: dict) -> int:
    left_doi = normalize_key(paper_doi(left))
    right_doi = normalize_key(paper_doi(right))
    if left_doi and right_doi and left_doi == right_doi:
        return 100

    if paper_url_values(left) & paper_url_values(right):
        return 92

    if paper_identifier_values(left) & paper_identifier_values(right):
        return 88

    left_title = normalize_key(str(left.get("title", "")))
    right_title = normalize_key(str(right.get("title", "")))
    if left_title and right_title and left_title == right_title:
        return 82

    similarity = title_similarity(left_title, right_title)
    left_year = paper_year_text(left)
    right_year = paper_year_text(right)
    if similarity >= 0.9 and (not left_year or not right_year or left_year == right_year):
        return 76
    if similarity >= 0.78 and left_year and right_year and left_year == right_year:
        return 70
    return 0


def same_paper(left: dict, right: dict) -> bool:
    if paper_match_score(left, right) >= 70:
        return True

    left_ids = paper_identity_values(left)
    right_ids = paper_identity_values(right)
    if left_ids & right_ids:
        return True

    left_title = normalize_key(str(left.get("title", "")))
    right_title = normalize_key(str(right.get("title", "")))
    return bool(left_title and right_title and left_title == right_title)


def preserve_existing_state(candidate: dict, existing: dict) -> dict:
    merged = {**candidate}
    existing_snapshot = paper_snapshot(existing) if isinstance(existing, dict) and existing else {}
    for field in STATE_PRESERVE_FIELDS:
        value = existing_snapshot.get(field)
        if value in (None, ""):
            continue
        if field in {"tags", "fulltextTranslations"} and not value:
            continue
        if field in {"zotero", "zoteroLink", "zoteroSync", "translations"} and not isinstance(value, dict):
            continue
        merged[field] = value
    if existing_snapshot.get("abstractLocked"):
        for field in ABSTRACT_LOCKED_CONTENT_FIELDS:
            merged[field] = existing_snapshot.get(field, "")
    if existing_snapshot.get("isDownloaded"):
        merged["isDownloaded"] = True
    if existing_snapshot.get("localPdfPath"):
        merged["downloadable"] = True
    return merged


def merge_library_paper_metadata(existing: dict, incoming: dict, *, adopt_abstract: bool = True) -> dict:
    existing_snapshot = paper_snapshot(existing)
    incoming_snapshot = paper_snapshot(incoming)
    merged = {**existing_snapshot}
    fill_fields = (
        "doi",
        "pageUrl",
        "entryUrl",
        "pdfUrl",
        "published",
        "year",
        "venue",
        "category",
        "authors",
        "paperId",
        "arxivId",
    )
    for field in fill_fields:
        current = str(merged.get(field) or "").strip()
        incoming_value = incoming_snapshot.get(field)
        if (not current or current.lower() in {"unknown", "unknown authors", "untitled"}) and incoming_value:
            merged[field] = incoming_value
    if normalize_key(str(merged.get("title") or "")) in {"", "untitled"} and incoming_snapshot.get("title"):
        merged["title"] = incoming_snapshot["title"]
    if incoming_snapshot.get("alertSourceHealth"):
        merged["alertSourceHealth"] = incoming_snapshot["alertSourceHealth"]
    abstract_candidate = abstract_candidate_from_paper(
        incoming_snapshot,
        incoming_snapshot.get("abstractSource") or "source",
        incoming_snapshot.get("abstractSourceLabel") or "",
    )
    if adopt_abstract:
        merged = merge_paper_abstract(merged, abstract_candidate)
    else:
        candidate = normalize_abstract_candidate(abstract_candidate)
        if candidate:
            candidates = normalize_abstract_candidates([candidate, *(merged.get("abstractCandidates") or [])])
            diagnostics = selected_abstract_diagnostics(
                [
                    *normalize_abstract_diagnostics(merged.get("abstractDiagnostics")),
                    abstract_diagnostic_from_candidate(candidate, "available", "Alert inbox candidate awaiting user confirmation."),
                ],
                merged.get("abstractSource") or "",
            )
            merged = paper_snapshot({
                **merged,
                "abstractCandidates": candidates,
                "abstractDiagnostics": diagnostics,
                "abstractConflict": abstract_conflict_from_candidates(
                    [abstract_candidate_from_paper(merged, merged.get("abstractSource") or "existing"), *candidates],
                    merged.get("abstractSource") or "",
                ),
                "metadataUpdatedAt": now_iso(),
            })
    return paper_snapshot(preserve_existing_state(merged, existing_snapshot))


def refresh_queries_for_paper(paper: dict) -> list[str]:
    candidates = [
        paper_doi(paper),
        str(paper.get("paperId") or "").strip(),
        str(paper.get("arxivId") or "").strip(),
        str(paper.get("title") or "").strip(),
    ]
    seen = set()
    queries = []
    for query in candidates:
        key = normalize_key(query)
        if not key or key in seen:
            continue
        seen.add(key)
        queries.append(query)
    return queries


def refresh_source_candidates(source: str, query: str) -> list[dict]:
    limit = 8
    if source == "arxiv":
        return search_arxiv_source(query, ["All"], limit, "relevance")
    if source == "semantic":
        return search_semantic_source(query, limit)
    if source == "cvf":
        return search_cvf_source(query, limit)
    if source == "acl":
        return search_acl_source(query, limit)
    if source == "openreview":
        return search_openreview_source(query, limit)
    if source == "chinarxiv":
        return search_chinarxiv_source(query, limit)
    if source == "sciopen":
        return search_sciopen_source(query, limit)
    if source == "nso":
        return search_nso_source(query, limit)
    return []


def find_refreshed_paper(paper: dict) -> dict | None:
    source = str(paper.get("source", "")).strip()
    if source not in SOURCE_LABELS:
        return None

    for query in refresh_queries_for_paper(paper):
        candidates = refresh_source_candidates(source, query)
        for candidate in candidates:
            if same_paper(paper, candidate):
                return candidate
    return None


def refresh_favorite_entry(key: str, item: dict) -> tuple[str, dict | None, str]:
    paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
    if not paper:
        return key, None, "缺少论文数据"

    try:
        refreshed = find_refreshed_paper(paper)
    except Exception as exc:
        return key, None, format_source_error(str(paper.get("source", "")), exc)

    if not refreshed:
        return key, None, "未找到匹配结果"

    refreshed = {
        **refreshed,
        "abstractSource": "source-refresh",
        "abstractSourceLabel": SOURCE_LABELS.get(str(refreshed.get("source") or ""), "来源刷新"),
        "abstractFetchedAt": now_iso(),
        "abstractCompleteness": abstract_completeness_for_text(refreshed.get("fullAbstract") or refreshed.get("abstract")),
    }
    snapshot = paper_snapshot(preserve_existing_state(refreshed, paper))
    snapshot = merge_paper_abstract(snapshot, abstract_candidate_from_paper(refreshed, "source-refresh", "来源刷新"))
    snapshot = paper_snapshot({
        **snapshot,
        "readingStatus": paper.get("readingStatus"),
        "note": paper.get("note"),
        "tags": paper.get("tags"),
        "translations": paper.get("translations"),
        "fulltextTranslations": paper.get("fulltextTranslations"),
        "isDownloaded": bool(paper.get("isDownloaded")) or bool(refreshed.get("isDownloaded")),
    })
    snapshot["paperKey"] = key
    return key, snapshot, ""


def refresh_favorites_metadata() -> dict:
    library = load_library()
    favorites = {
        key: item
        for key, item in (library.get("favorites") or {}).items()
        if isinstance(item, dict)
    }
    if not favorites:
        return {
            "ok": True,
            "library": compact_library(library),
            "refreshed": 0,
            "checked": 0,
            "errors": {},
        }

    refreshed = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=min(len(favorites), 3)) as executor:
        future_to_key = {
            executor.submit(refresh_favorite_entry, key, item): key
            for key, item in favorites.items()
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                entry_key, snapshot, error = future.result()
            except Exception as exc:
                errors[key] = str(exc)
                continue
            if snapshot:
                refreshed[entry_key] = snapshot
            elif error:
                errors[key] = error

    with LIBRARY_LOCK:
        library = load_library()
        for key, snapshot in refreshed.items():
            item = library.get("favorites", {}).get(key)
            if not isinstance(item, dict):
                continue
            now = now_iso()
            existing = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            snapshot = paper_snapshot(preserve_existing_state(snapshot, existing))
            snapshot["paperKey"] = key
            item["paper"] = snapshot
            item["refreshedAt"] = now
            library["papers"][key] = {
                "createdAt": (library.get("papers", {}).get(key) or item).get("createdAt", now),
                "updatedAt": now,
                "refreshedAt": now,
                "paper": snapshot,
            }
        save_library(library)
        library_view = compact_library(library)

    return {
        "ok": True,
        "library": library_view,
        "refreshed": len(refreshed),
        "checked": len(favorites),
        "errors": errors,
    }


def update_library(payload: dict) -> dict:
    action = str(payload.get("action", "")).strip().lower()
    if action == "refresh-favorites":
        return refresh_favorites_metadata()

    paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
    key = str(payload.get("paperKey") or paper_key(paper)).strip()
    if not key:
        raise ValueError("缺少论文标识。")

    with LIBRARY_LOCK:
        library = load_library()
        now = now_iso()
        snapshot = paper_snapshot(paper) if paper else {}

        if action == "favorite":
            library["favorites"][key] = {"createdAt": now, "paper": snapshot}
            library["papers"][key] = {"createdAt": now, "paper": snapshot}
            library["ignored"].pop(key, None)
        elif action == "unfavorite":
            library["favorites"].pop(key, None)
        elif action == "ignore":
            library["ignored"][key] = {"createdAt": now, "paper": snapshot}
            library["papers"][key] = {"createdAt": now, "paper": snapshot}
            library["favorites"].pop(key, None)
        elif action == "unignore":
            library["ignored"].pop(key, None)
        elif action == "clear-history":
            library["history"] = []
        elif action == "update-paper":
            existing = (
                library.get("papers", {}).get(key)
                or library.get("favorites", {}).get(key)
                or library.get("ignored", {}).get(key)
            )
            base_paper = existing.get("paper") if isinstance(existing, dict) and isinstance(existing.get("paper"), dict) else {}
            updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
            merged = preserve_existing_state({**base_paper, **snapshot}, base_paper)
            if "readingStatus" in updates:
                merged["readingStatus"] = str(updates.get("readingStatus") or "")
            if "note" in updates:
                merged["note"] = str(updates.get("note") or "")
            if "tags" in updates:
                raw_tags = updates.get("tags")
                if isinstance(raw_tags, str):
                    merged["tags"] = [tag.strip() for tag in re.split(r"[,，]", raw_tags) if tag.strip()]
                elif isinstance(raw_tags, list):
                    merged["tags"] = raw_tags
            updated_snapshot = paper_snapshot(merged)
            library["papers"][key] = {"createdAt": (existing or {}).get("createdAt", now), "updatedAt": now, "paper": updated_snapshot}
            for section in ("favorites", "ignored"):
                if key in library.get(section, {}):
                    library[section][key]["paper"] = updated_snapshot
                    library[section][key]["updatedAt"] = now
        else:
            raise ValueError("不支持的资料库操作。")

        save_library(library)
    return {"ok": True, "library": compact_library(library)}


def record_download(paper: dict, filename: str) -> None:
    key = paper_key(paper)
    snapshot = paper_snapshot({**paper, "isDownloaded": True})
    with LIBRARY_LOCK:
        library = load_library()
        library["downloads"][key] = {
            "createdAt": now_iso(),
            "filename": filename,
            "paper": snapshot,
        }
        library["papers"][key] = {"createdAt": now_iso(), "paper": snapshot}
        if key in library.get("favorites", {}):
            library["favorites"][key]["paper"] = snapshot
        save_library(library)


def bibtex_key(paper: dict) -> str:
    authors = str(paper.get("authors", "")).split(",")[0].strip().split()
    author = authors[-1] if authors else "paper"
    year = str(paper.get("year") or paper.get("published") or "n.d.")
    year_match = re.search(r"\d{4}", year)
    title_terms = query_terms(str(paper.get("title", "")), min_length=4)[:2]
    parts = [author, year_match.group(0) if year_match else "paper", *title_terms]
    key = "".join(part[:28] for part in parts if part)
    return re.sub(r"[^A-Za-z0-9:_-]", "", key) or "paper"


def bibtex_entry_type(paper: dict) -> str:
    source = str(paper.get("source", "")).lower()
    if source in {"arxiv", "openreview", "chinarxiv"}:
        return "misc"
    if source in {"cvf", "acl"}:
        return "inproceedings"
    return "article"


def paper_doi(paper: dict) -> str:
    candidates = (
        paper.get("doi"),
        paper.get("DOI"),
        paper.get("paperId"),
        paper.get("arxivId"),
    )
    for candidate in candidates:
        text = clean_html(str(candidate or "")).strip()
        match = re.search(r"10\.\d{4,9}/[^\s\"<>]+", text, flags=re.IGNORECASE)
        if match:
            return match.group(0).rstrip(".,;)")
    return ""


def escape_bibtex(value: object) -> str:
    text = clean_html(str(value or ""))
    replacements = {
        "\\": "\\textbackslash{}",
        "{": "\\{",
        "}": "\\}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
    }
    return "".join(replacements.get(char, char) for char in text)


def paper_year_text(paper: dict) -> str:
    year = paper_year(paper)
    return str(year) if year else ""


def paper_url(paper: dict) -> str:
    return str(paper.get("pageUrl") or paper.get("entryUrl") or paper.get("pdfUrl") or "")


def split_author_names(authors: object) -> list[str]:
    if isinstance(authors, list):
        raw_names = [str(author.get("name") if isinstance(author, dict) else author) for author in authors]
    else:
        raw_names = re.split(r"\s*(?:,|;|\band\b)\s*", str(authors or ""))
    names = []
    for name in raw_names:
        clean_name = clean_html(str(name or "")).strip()
        if not clean_name or clean_name.lower() in {"et al.", "et al", "others", "unknown authors"}:
            continue
        names.append(clean_name)
    return names


def papers_from_export_payload(payload: dict) -> list[dict]:
    scope = str(payload.get("scope", "results")).lower()
    if scope == "favorites":
        library = load_library()
        return [
            item.get("paper")
            for item in (library.get("favorites") or {}).values()
            if isinstance(item, dict) and isinstance(item.get("paper"), dict)
        ]

    papers = payload.get("papers") or []
    if not isinstance(papers, list):
        return []
    return [paper_snapshot(paper) for paper in papers if isinstance(paper, dict)]


def export_bibtex(papers: list[dict]) -> str:
    entries = []
    seen_keys: dict[str, int] = {}
    for paper in papers:
        key = bibtex_key(paper)
        seen_keys[key] = seen_keys.get(key, 0) + 1
        if seen_keys[key] > 1:
            key = f"{key}{seen_keys[key]}"
        entry_type = bibtex_entry_type(paper)
        authors = str(paper.get("authors", "")).replace(", et al.", " and others").replace(", ", " and ")
        fields = {
            "title": paper.get("title"),
            "author": authors,
            "year": paper_year_text(paper),
            "doi": paper_doi(paper),
            "journal": (paper.get("venue") or paper.get("sourceLabel")) if entry_type == "article" else "",
            "booktitle": paper.get("venue") if entry_type == "inproceedings" else "",
            "howpublished": paper.get("category") if entry_type == "misc" else "",
            "url": paper_url(paper),
            "note": f"arXiv:{paper.get('paperId')}" if str(paper.get("source", "")) == "arxiv" else "",
        }
        if str(paper.get("source", "")) == "arxiv":
            fields["eprint"] = paper.get("paperId")
            fields["archivePrefix"] = "arXiv"
            fields["primaryClass"] = paper.get("category")
        elif str(paper.get("source", "")) == "openreview":
            fields["note"] = paper.get("venue") or "OpenReview"
        body = "\n".join(
            f"  {field} = {{{escape_bibtex(value)}}},"
            for field, value in fields.items()
            if value
        )
        entries.append(f"@{entry_type}{{{key},\n{body}\n}}")
    return "\n\n".join(entries)


def ris_entry_type(paper: dict) -> str:
    entry_type = bibtex_entry_type(paper)
    if entry_type == "inproceedings":
        return "CONF"
    if entry_type == "misc":
        return "ELEC"
    return "JOUR"


def ris_value(value: object) -> str:
    return clean_html(str(value or "")).replace("\r", " ").replace("\n", " ").strip()


def ris_publication_date(paper: dict) -> str:
    published = ris_value(paper.get("published"))
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", published)
    if match:
        year, month, day = match.groups()
        return f"{year}/{int(month):02d}/{int(day):02d}"
    return paper_year_text(paper)


def export_ris(papers: list[dict]) -> str:
    entries = []
    for paper in papers:
        lines = [f"TY  - {ris_entry_type(paper)}"]
        fields = [
            ("TI", paper.get("title")),
            ("PY", paper_year_text(paper)),
            ("Y1", ris_publication_date(paper)),
            ("T2", paper.get("venue") or paper.get("sourceLabel")),
            ("AB", paper.get("fullAbstract") or paper.get("abstract")),
            ("DO", paper_doi(paper)),
            ("UR", paper_url(paper)),
            ("L1", paper.get("pdfUrl")),
        ]
        for author in split_author_names(paper.get("authors")):
            lines.append(f"AU  - {ris_value(author)}")
        for tag_value in fields:
            tag, value = tag_value
            text = ris_value(value)
            if text:
                lines.append(f"{tag}  - {text}")
        for keyword in (paper.get("category"), *(paper.get("tags") if isinstance(paper.get("tags"), list) else [])):
            text = ris_value(keyword)
            if text:
                lines.append(f"KW  - {text}")
        source_label = ris_value(paper.get("sourceLabel") or paper.get("source"))
        note = ris_value(paper.get("note"))
        notes = [value for value in (f"Source: {source_label}" if source_label else "", note) if value]
        if notes:
            lines.append(f"N1  - {' | '.join(notes)}")
        lines.append("ER  -")
        entries.append("\n".join(lines))
    return "\n\n".join(entries) + ("\n" if entries else "")


def zotero_item_type(paper: dict) -> str:
    entry_type = bibtex_entry_type(paper)
    if entry_type == "inproceedings":
        return "conferencePaper"
    if entry_type == "misc":
        return "preprint"
    return "journalArticle"


def zotero_creator(name: str) -> dict:
    parts = name.split()
    if len(parts) <= 1:
        return {"creatorType": "author", "lastName": name}
    return {
        "creatorType": "author",
        "firstName": " ".join(parts[:-1]),
        "lastName": parts[-1],
    }


def zotero_item_from_paper(paper: dict) -> dict:
    url = paper_url(paper)
    item = {
        "itemType": zotero_item_type(paper),
        "title": ris_value(paper.get("title")) or "Untitled",
        "creators": [zotero_creator(author) for author in split_author_names(paper.get("authors"))],
        "abstractNote": ris_value(paper.get("fullAbstract") or paper.get("abstract")),
        "date": ris_value(paper.get("published")) or paper_year_text(paper),
        "url": url,
        "DOI": paper_doi(paper),
        "archive": ris_value(paper.get("sourceLabel") or paper.get("source")),
        "archiveLocation": ris_value(paper.get("paperId") or paper.get("arxivId")),
        "tags": [{"tag": tag} for tag in (paper.get("tags") or []) if isinstance(tag, str) and tag.strip()],
        "notes": [],
    }
    venue = ris_value(paper.get("venue") or "")
    if item["itemType"] == "conferencePaper":
        item["proceedingsTitle"] = venue
    elif item["itemType"] == "journalArticle":
        item["publicationTitle"] = venue
    else:
        item["repository"] = venue or item["archive"]
    category = ris_value(paper.get("category"))
    if category:
        item["tags"].append({"tag": category})
    note = ris_value(paper.get("note"))
    pdf_url = ris_value(paper.get("pdfUrl"))
    note_parts = []
    if note:
        note_parts.append(note)
    if pdf_url:
        note_parts.append(f"Public PDF: {pdf_url}")
    if note_parts:
        item["notes"].append({"note": "<p>" + "<br/>".join(note_parts) + "</p>"})
    return {
        key: value
        for key, value in item.items()
        if value is not None and value != "" and value != []
    }


def zotero_connector_status() -> dict:
    try:
        response = requests.get(
            ZOTERO_CONNECTOR_PING_URL,
            headers={**REQUEST_HEADERS, "Sec-Fetch-Mode": "navigate"},
            timeout=(1, 2),
        )
    except requests.RequestException:
        return {"available": False, "message": "未检测到本机 Zotero。可以导出 RIS 后导入 Zotero 或 EndNote。"}
    if response.status_code == 200:
        return {"available": True, "message": "已检测到本机 Zotero，可直接保存题录。"}
    return {
        "available": False,
        "message": f"本机 Zotero 响应异常（HTTP {response.status_code}）。可以改用 RIS 导入。",
    }


def zotero_bridge_pairing_payload() -> dict:
    return {
        "protocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
        "client": "PaperHunter",
        "pairingToken": zotero_bridge_token(),
    }


def zotero_bridge_pairing_check() -> dict:
    try:
        response = requests.post(
            ZOTERO_BRIDGE_PAIRING_CHECK_URL,
            headers={"Content-Type": "application/json"},
            json=zotero_bridge_pairing_payload(),
            timeout=(1, 3),
        )
    except requests.RequestException as exc:
        return {
            "ok": False,
            "statusCode": None,
            "reason": "pairing_check_unreachable",
            "message": "Bridge 已响应 ping，但配对检查接口不可达。请安装当前页面下载的最新版 Bridge 并重启 Zotero。",
            "error": compact_text(str(exc), 240),
        }
    if response.status_code not in {200, 201}:
        detail = compact_text(response.text, 240)
        return {
            "ok": False,
            "statusCode": response.status_code,
            "reason": "pairing_check_failed",
            "message": "Bridge 配对 token 不匹配或检查失败。请从当前 PaperHunter 页面重新下载 XPI，覆盖安装后重启 Zotero。",
            "error": detail,
        }
    try:
        data = response.json()
    except ValueError:
        data = {}
    if data.get("ok") is False:
        return {
            "ok": False,
            "statusCode": response.status_code,
            "reason": "pairing_check_rejected",
            "message": "Bridge 拒绝了当前 PaperHunter 的配对 token。请重新下载并覆盖安装当前 XPI。",
            "error": compact_text(str(data.get("error") or data), 240),
        }
    return {
        "ok": True,
        "statusCode": response.status_code,
        "reason": "paired",
        "message": "Bridge 配对 token 已确认匹配。",
        "tokenAccepted": bool(data.get("tokenAccepted", True)),
    }


def zotero_bridge_status() -> dict:
    package_status = zotero_bridge_package_status()
    token = zotero_bridge_token()
    base_status = {
        "downloadUrl": ZOTERO_BRIDGE_DOWNLOAD_URL,
        "package": package_status,
        "installSteps": ZOTERO_BRIDGE_INSTALL_STEPS,
        "installHint": "下载 XPI 后，在 Zotero 插件管理器中选择从文件安装，重启 Zotero 后刷新 PaperHunter。",
        "capabilities": ZOTERO_BRIDGE_CAPABILITIES,
        "pairing": {
            "required": True,
            "configured": bool(token),
            "tokenMasked": mask_secret(token),
            "verified": False,
        },
    }
    try:
        response = requests.get(ZOTERO_BRIDGE_PING_URL, headers=REQUEST_HEADERS, timeout=(1, 2))
    except requests.RequestException:
        return {
            **base_status,
            "available": False,
            "compatible": False,
            "reason": "not_running_or_not_installed",
            "nextStep": f"下载当前页面提供的 Bridge {ZOTERO_BRIDGE_VERSION} XPI，在 Zotero 中从文件安装，重启 Zotero 后刷新 PaperHunter。",
            "version": "",
            "expectedVersion": ZOTERO_BRIDGE_VERSION,
            "protocolVersion": None,
            "expectedProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
            "message": "未检测到 PaperHunter Zotero Bridge。同步译文回 Zotero 前，请在 Zotero 中安装并启用 Bridge 插件。",
        }
    if response.status_code != 200:
        return {
            **base_status,
            "available": False,
            "compatible": False,
            "reason": "http_error",
            "nextStep": "重启 Zotero；如果仍然异常，请重新下载当前页面提供的 Bridge XPI 并覆盖安装。",
            "version": "",
            "expectedVersion": ZOTERO_BRIDGE_VERSION,
            "protocolVersion": None,
            "expectedProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
            "message": f"PaperHunter Zotero Bridge 响应异常（HTTP {response.status_code}）。",
        }
    try:
        data = response.json()
    except ValueError:
        data = {}
    version = str(data.get("version") or "")
    protocol_version = data.get("protocolVersion")
    compatible = protocol_version == ZOTERO_BRIDGE_PROTOCOL_VERSION and version == ZOTERO_BRIDGE_VERSION
    capabilities = data.get("capabilities") if isinstance(data.get("capabilities"), dict) else {}
    token_supported = bool(capabilities.get("requiresPairingToken"))
    compatible = compatible and token_supported
    if not compatible:
        reason = "pairing_not_supported" if not token_supported else "version_or_protocol_mismatch"
        return {
            **base_status,
            "available": True,
            "compatible": False,
            "reason": reason,
            "nextStep": f"从当前 PaperHunter 下载 Bridge {ZOTERO_BRIDGE_VERSION}，在 Zotero 中覆盖安装，然后重启 Zotero。",
            "message": (
                f"已检测到 PaperHunter Zotero Bridge {version or '未知版本'}，"
                f"但版本、协议或配对能力不兼容。请重新下载并安装 Bridge {ZOTERO_BRIDGE_VERSION}。"
            ),
            "version": version,
            "expectedVersion": ZOTERO_BRIDGE_VERSION,
            "protocolVersion": protocol_version,
            "expectedProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
        }
    pairing = zotero_bridge_pairing_check()
    if not pairing.get("ok"):
        return {
            **base_status,
            "available": True,
            "compatible": False,
            "reason": pairing.get("reason") or "pairing_check_failed",
            "nextStep": "从当前 PaperHunter 下载最新 Bridge XPI，覆盖安装到 Zotero，重启 Zotero 后刷新状态。",
            "message": pairing.get("message") or "Bridge 配对检查失败，请重新安装当前 XPI。",
            "version": version,
            "expectedVersion": ZOTERO_BRIDGE_VERSION,
            "protocolVersion": protocol_version,
            "expectedProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
            "policy": data.get("policy") if isinstance(data.get("policy"), dict) else {},
            "capabilities": capabilities or ZOTERO_BRIDGE_CAPABILITIES,
            "pairing": {
                **base_status["pairing"],
                "verified": False,
                "check": pairing,
            },
        }
    return {
        **base_status,
        "available": True,
        "compatible": True,
        "reason": "ready",
        "nextStep": "Bridge 已安装并配对；回写前先查看 dry-run 预览，确认只写 PaperHunter 管理内容。",
        "message": "已检测到并配对 PaperHunter Zotero Bridge，可同步摘要/全文译文回 Zotero。",
        "version": version,
        "expectedVersion": ZOTERO_BRIDGE_VERSION,
        "protocolVersion": protocol_version,
        "expectedProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
        "policy": data.get("policy") if isinstance(data.get("policy"), dict) else {},
        "capabilities": capabilities or ZOTERO_BRIDGE_CAPABILITIES,
        "pairing": {
            **base_status["pairing"],
            "verified": True,
            "check": pairing,
        },
    }


def zotero_database_status() -> dict:
    available = ZOTERO_DB_PATH.exists() and ZOTERO_STORAGE_DIR.exists()
    return {
        "available": available,
        "databasePath": str(ZOTERO_DB_PATH) if ZOTERO_DB_PATH.exists() else "",
        "storagePath": str(ZOTERO_STORAGE_DIR) if ZOTERO_STORAGE_DIR.exists() else "",
        "message": "已找到 Zotero 本地资料库，可导入条目和 PDF 附件。" if available else "未找到 Zotero 本地资料库。",
    }


def zotero_status() -> dict:
    connector = zotero_connector_status()
    database = zotero_database_status()
    bridge = zotero_bridge_status()
    return {
        **connector,
        "connector": connector,
        "database": database,
        "bridge": bridge,
        "importAvailable": bool(database.get("available")),
        "syncAvailable": bool(bridge.get("available") and bridge.get("compatible")),
    }


def copy_zotero_database_snapshot() -> Path:
    if not ZOTERO_DB_PATH.exists():
        raise ValueError("未找到 Zotero 本地数据库。请确认 Zotero 已安装并初始化资料库。")
    target_dir = CACHE_DIR / "zotero-import"
    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = target_dir / f"zotero-{int(time.time() * 1000)}.sqlite"
    shutil.copy2(ZOTERO_DB_PATH, snapshot_path)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(ZOTERO_DB_PATH) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(snapshot_path) + suffix))
    return snapshot_path


def zotero_resolved_attachment_path(item_key: str, attachment_path: str) -> Path | None:
    raw_path = str(attachment_path or "")
    if not raw_path:
        return None
    if raw_path.startswith("storage:"):
        filename = raw_path.split(":", 1)[1]
        path = (ZOTERO_STORAGE_DIR / item_key / filename).resolve()
    else:
        path = Path(raw_path).expanduser().resolve()
    return path if path.exists() else None


def zotero_storage_path(item_key: str, attachment_path: str) -> str:
    path = zotero_resolved_attachment_path(item_key, attachment_path)
    if not path:
        return ""
    storage_root = ZOTERO_STORAGE_DIR.resolve()
    if storage_root not in path.parents and path != storage_root:
        return ""
    return str(path) if path.exists() and path.suffix.lower() == ".pdf" else ""


def zotero_attachment_path(item_key: str, attachment_path: str, content_type: str = "") -> str:
    path = zotero_resolved_attachment_path(item_key, attachment_path)
    if not path:
        return ""
    suffix = path.suffix.lower()
    storage_root = ZOTERO_STORAGE_DIR.resolve()
    download_root = DOWNLOAD_DIR.resolve()
    translated_root = TRANSLATED_DIR.resolve()
    in_storage = storage_root in path.parents or path == storage_root
    in_downloads = download_root in path.parents or path == download_root
    in_translated = translated_root in path.parents or path == translated_root
    normalized_type = str(content_type or "").lower()
    if (in_storage or in_downloads) and (normalized_type == "application/pdf" or suffix == ".pdf"):
        return str(path)
    if in_translated and (normalized_type in {"text/markdown", "text/x-markdown"} or suffix in {".md", ".markdown"}):
        return str(path)
    return ""


def clean_zotero_date(value: str) -> tuple[str, str]:
    text = clean_html(str(value or ""))
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return text, match.group(0) if match else ""


def zotero_authors(conn: sqlite3.Connection, item_id: int) -> str:
    rows = conn.execute(
        """
        select c.firstName, c.lastName, c.fieldMode
        from itemCreators ic
        join creators c on c.creatorID = ic.creatorID
        where ic.itemID = ?
        order by ic.orderIndex
        """,
        (item_id,),
    ).fetchall()
    names = []
    for row in rows[:4]:
        if int(row["fieldMode"] or 0) == 1:
            name = str(row["lastName"] or "").strip()
        else:
            name = " ".join(part for part in (str(row["firstName"] or "").strip(), str(row["lastName"] or "").strip()) if part)
        if name:
            names.append(name)
    if len(rows) > 4:
        names.append("et al.")
    return ", ".join(names)


def zotero_item_fields(conn: sqlite3.Connection, item_id: int) -> dict[str, str]:
    rows = conn.execute(
        """
        select f.fieldName, v.value
        from itemData d
        join fields f on f.fieldID = d.fieldID
        join itemDataValues v on v.valueID = d.valueID
        where d.itemID = ?
        """,
        (item_id,),
    ).fetchall()
    return {str(row["fieldName"]): str(row["value"] or "") for row in rows}


def zotero_item_tags(conn: sqlite3.Connection, item_id: int) -> list[str]:
    rows = conn.execute(
        "select t.name from itemTags it join tags t on t.tagID = it.tagID where it.itemID = ? order by t.name",
        (item_id,),
    ).fetchall()
    return [clean_display_text(str(row["name"]), 32) for row in rows if str(row["name"] or "").strip()][:12]


def zotero_item_collections(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        select c.collectionID, c.key, c.collectionName
        from collectionItems ci
        join collections c on c.collectionID = ci.collectionID
        where ci.itemID = ?
        order by c.collectionName
        """,
        (item_id,),
    ).fetchall()
    return [{"collectionID": row["collectionID"], "key": row["key"], "name": row["collectionName"]} for row in rows]


def zotero_item_notes(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        select n.itemID, i.key, n.note, n.title
        from itemNotes n
        join items i on i.itemID = n.itemID
        where n.parentItemID = ?
        order by n.itemID
        """,
        (item_id,),
    ).fetchall()
    notes = []
    for row in rows:
        note_text = clean_html(str(row["note"] or row["title"] or ""))
        if not note_text:
            continue
        notes.append({
            "itemID": row["itemID"],
            "key": row["key"],
            "title": clean_display_text(note_text, 80),
            "preview": clean_display_text(note_text, 240),
            "managedByPaperHunter": ZOTERO_MANAGED_NOTE_MARKER in note_text,
        })
    return notes[:20]


def zotero_attachments(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        select child.itemID, child.key, ia.contentType, ia.path
        from itemAttachments ia
        join items child on child.itemID = ia.itemID
        where ia.parentItemID = ?
        order by child.itemID
        """,
        (item_id,),
    ).fetchall()
    attachments = []
    for row in rows:
        content_type = str(row["contentType"] or "")
        path = zotero_attachment_path(str(row["key"] or ""), str(row["path"] or ""), content_type)
        if path:
            suffix = Path(path).suffix.lower()
            fields = zotero_item_fields(conn, int(row["itemID"]))
            attachments.append({
                "itemID": row["itemID"],
                "key": row["key"],
                "contentType": content_type,
                "path": path,
                "title": clean_display_text(fields.get("title") or Path(path).name, 120),
                "isPdf": content_type == "application/pdf" or suffix == ".pdf",
                "managedByPaperHunter": suffix in {".md", ".markdown"} and (TRANSLATED_DIR.resolve() in Path(path).parents),
            })
    return attachments


def zotero_paper_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict | None:
    item_id = int(row["itemID"])
    item_type = str(row["typeName"] or "")
    if item_type in {"attachment", "note", "annotation"}:
        return None
    fields = zotero_item_fields(conn, item_id)
    title = clean_display_text(fields.get("title") or fields.get("shortTitle") or "", TITLE_TEXT_LIMIT)
    if not title:
        return None
    date_text, year = clean_zotero_date(fields.get("date") or row["dateAdded"])
    attachments = zotero_attachments(conn, item_id)
    pdf_attachments = [attachment for attachment in attachments if attachment.get("isPdf")]
    first_pdf = pdf_attachments[0] if pdf_attachments else {}
    venue = (
        fields.get("publicationTitle")
        or fields.get("proceedingsTitle")
        or fields.get("conferenceName")
        or fields.get("repository")
        or fields.get("archive")
        or "Zotero"
    )
    zotero_meta = {
        "libraryID": row["libraryID"],
        "itemID": item_id,
        "itemKey": row["key"],
        "itemType": item_type,
        "dateAdded": row["dateAdded"],
        "dateModified": row["dateModified"],
        "attachments": attachments,
        "collections": zotero_item_collections(conn, item_id),
        "notes": zotero_item_notes(conn, item_id),
    }
    return make_paper(
        source="zotero",
        title=title,
        authors=zotero_authors(conn, item_id),
        published=date_text,
        year=year,
        venue=venue,
        category=fields.get("archive") or fields.get("repository") or item_type or "Zotero",
        abstract=fields.get("abstractNote") or "",
        pdf_url="",
        page_url=fields.get("url") or "",
        paper_id=fields.get("DOI") or fields.get("archiveLocation") or f"zotero-{row['key']}",
        doi=fields.get("DOI") or "",
        local_pdf_path=str(first_pdf.get("path") or ""),
        access="user_library",
        zotero=zotero_meta,
    ) | {"tags": zotero_item_tags(conn, item_id)}


def read_zotero_candidates(limit: int = 400, attempts: int = 1, delay: float = 0.4) -> list[dict]:
    last_error = None
    for attempt in range(max(1, attempts)):
        try:
            return read_zotero_papers(limit=limit, require_pdf=False)
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(delay)
    if last_error:
        return []
    return []


def zotero_link_review_candidates(paper: dict, candidates: list[dict] | None = None) -> list[dict]:
    snapshot = paper_snapshot(paper)
    candidates = candidates if candidates is not None else read_zotero_candidates()
    link = snapshot.get("zoteroLink") if isinstance(snapshot.get("zoteroLink"), dict) else {}
    sync = snapshot.get("zoteroSync") if isinstance(snapshot.get("zoteroSync"), dict) else {}
    target_keys = {
        clean_zotero_item_key(link.get("itemKey")),
        clean_zotero_item_key(sync.get("itemKey")),
        zotero_meta_item_key(snapshot.get("zotero")),
    }
    for candidate in link.get("candidates") or []:
        if isinstance(candidate, dict):
            target_keys.add(clean_zotero_item_key(candidate.get("itemKey")))
    target_keys.discard("")

    by_key = {}
    for candidate in candidates:
        item_key = zotero_meta_item_key(candidate.get("zotero"))
        if not item_key:
            continue
        score = paper_match_score(snapshot, candidate)
        exact = item_key in target_keys
        if not exact and score < ZOTERO_MATCH_THRESHOLD:
            continue
        summary = zotero_link_candidate(candidate, max(score, 100 if exact else score))
        summary["exactItemKey"] = exact
        existing = by_key.get(item_key)
        if not existing or summary["score"] > existing["score"] or (exact and not existing.get("exactItemKey")):
            by_key[item_key] = summary

    values = list(by_key.values())
    values.sort(key=lambda item: (bool(item.get("exactItemKey")), int(item.get("score") or 0), item.get("dateModified") or ""), reverse=True)
    for item in values:
        item.pop("exactItemKey", None)
    return values[:8]


def merge_zotero_candidate_summaries(*candidate_lists: list[dict]) -> list[dict]:
    by_key = {}
    for candidate_list in candidate_lists:
        if not isinstance(candidate_list, list):
            continue
        for candidate in candidate_list:
            if not isinstance(candidate, dict):
                continue
            item_key = clean_zotero_item_key(candidate.get("itemKey"))
            if not item_key:
                continue
            summary = {
                **candidate,
                "itemKey": item_key,
                "score": clamp_int(candidate.get("score"), default=0, minimum=0, maximum=100),
            }
            existing = by_key.get(item_key)
            if not existing or summary["score"] > int(existing.get("score") or 0):
                by_key[item_key] = summary
    values = list(by_key.values())
    values.sort(key=lambda item: (int(item.get("score") or 0), str(item.get("dateModified") or "")), reverse=True)
    return values[:8]


def persist_zotero_link_review(
    key: str,
    paper: dict,
    *,
    status: str,
    message: str = "",
    candidates: list[dict] | None = None,
) -> dict:
    snapshot = paper_snapshot(paper)
    existing_link = snapshot.get("zoteroLink") if isinstance(snapshot.get("zoteroLink"), dict) else {}
    link = {
        **existing_link,
        "status": status if status in ZOTERO_LINK_STATUSES else str(existing_link.get("status") or "unlinked"),
        "message": message or str(existing_link.get("message") or ""),
        "candidates": merge_zotero_candidate_summaries(candidates or [], existing_link.get("candidates") or []),
        "updatedAt": now_iso(),
    }
    snapshot["zoteroLink"] = link
    snapshot["paperKey"] = key
    with LIBRARY_LOCK:
        library = load_library()
        update_library_paper_snapshot(library, key, snapshot)
        save_library(library)
    return snapshot


def zotero_link_for_match(match: dict, score: int, source: str = "auto-match", status: str = "auto") -> dict:
    candidate = zotero_link_candidate(match, score)
    return {
        "status": status,
        "itemKey": candidate["itemKey"],
        "libraryID": candidate.get("libraryID"),
        "itemID": candidate.get("itemID"),
        "confidence": int(score),
        "source": source,
        "confirmedAt": "",
        "updatedAt": now_iso(),
        "message": "",
        "candidates": [candidate],
    }


def zotero_link_for_ambiguity(candidates: list[dict], message: str = "") -> dict:
    return {
        "status": "ambiguous",
        "itemKey": "",
        "libraryID": None,
        "itemID": None,
        "confidence": candidates[0]["score"] if candidates else 0,
        "source": "auto-match",
        "confirmedAt": "",
        "updatedAt": now_iso(),
        "message": message or "Multiple Zotero items match this PaperHunter paper. Confirm the canonical item before saving or syncing.",
        "candidates": candidates[:8],
    }


def resolve_zotero_match(paper: dict, candidates: list[dict] | None = None) -> dict:
    candidates = candidates if candidates is not None else read_zotero_candidates()
    scored = []
    for candidate in candidates:
        score = paper_match_score(paper, candidate)
        if score >= ZOTERO_MATCH_THRESHOLD:
            scored.append((candidate, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        return {"status": "unmatched", "match": None, "score": 0, "candidates": []}

    top_score = scored[0][1]
    close_matches = [
        (candidate, score)
        for candidate, score in scored
        if score >= top_score - ZOTERO_AMBIGUOUS_SCORE_GAP
    ]
    summaries = [zotero_link_candidate(candidate, score) for candidate, score in close_matches]
    unique_keys = {candidate["itemKey"] for candidate in summaries if candidate.get("itemKey")}
    if len(unique_keys) > 1:
        return {"status": "ambiguous", "match": None, "score": top_score, "candidates": summaries}
    return {"status": "unique", "match": scored[0][0], "score": top_score, "candidates": summaries[:1]}


def find_matching_zotero_paper(paper: dict, candidates: list[dict] | None = None) -> tuple[dict | None, int]:
    result = resolve_zotero_match(paper, candidates)
    return (result.get("match"), int(result.get("score") or 0)) if result.get("status") == "unique" else (None, int(result.get("score") or 0))


def merge_zotero_metadata(paper: dict, zotero_paper: dict) -> dict:
    score = paper_match_score(paper, zotero_paper)
    merged = {
        **paper,
        "zotero": zotero_paper.get("zotero") if isinstance(zotero_paper.get("zotero"), dict) else {},
        "zoteroLink": zotero_link_for_match(zotero_paper, score, source="zotero-match"),
    }
    if zotero_paper.get("localPdfPath") and not merged.get("localPdfPath"):
        merged["localPdfPath"] = zotero_paper.get("localPdfPath")
        merged["localPdfFilename"] = zotero_paper.get("localPdfFilename") or Path(str(zotero_paper.get("localPdfPath"))).name
        merged["access"] = merged.get("access") or "user_library"
        merged["isDownloaded"] = True
        merged["downloadable"] = True
    if not merged.get("doi") and zotero_paper.get("doi"):
        merged["doi"] = zotero_paper.get("doi")
    existing_tags = [tag for tag in (paper.get("tags") or []) if isinstance(tag, str) and tag.strip()]
    zotero_tags = [tag for tag in (zotero_paper.get("tags") or []) if isinstance(tag, str) and tag.strip()]
    if zotero_tags:
        merged["tags"] = sorted(set([*existing_tags, *zotero_tags]))
    return paper_snapshot(merged)


def update_library_paper_snapshot(library: dict, key: str, snapshot: dict, now: str | None = None) -> None:
    now = now or now_iso()
    existing = library.get("papers", {}).get(key)
    library["papers"][key] = {
        "createdAt": (existing or {}).get("createdAt", now),
        "updatedAt": now,
        "paper": snapshot,
    }
    for section in ("favorites", "ignored"):
        item = library.get(section, {}).get(key)
        if isinstance(item, dict):
            item["paper"] = snapshot
            item["updatedAt"] = now
    download = library.get("downloads", {}).get(key)
    if isinstance(download, dict):
        download["paper"] = paper_snapshot({**snapshot, "isDownloaded": True})
        download["updatedAt"] = now
    elif snapshot.get("localPdfPath"):
        library["downloads"][key] = {
            "createdAt": now,
            "updatedAt": now,
            "filename": snapshot.get("localPdfFilename") or Path(str(snapshot.get("localPdfPath"))).name,
            "path": snapshot.get("localPdfPath"),
            "source": "zotero",
            "paper": paper_snapshot({**snapshot, "isDownloaded": True}),
        }


def link_library_paper_to_zotero(key: str, paper: dict, candidates: list[dict] | None = None) -> dict:
    paper = paper_snapshot(paper)
    link = paper.get("zoteroLink") if isinstance(paper.get("zoteroLink"), dict) else {}
    if link.get("status") in ZOTERO_BLOCKED_LINK_STATUSES:
        return {
            "ok": True,
            "linked": False,
            "alreadyLinked": False,
            "ambiguous": link.get("status") == "ambiguous",
            "conflict": link.get("status") == "conflict",
            "paper": paper,
            "itemKey": "",
            "score": link.get("confidence") or 0,
            "candidates": link.get("candidates") or [],
            "message": link.get("message") or "Confirm the canonical Zotero item before linking.",
        }

    existing_zotero = paper.get("zotero") if isinstance(paper.get("zotero"), dict) else {}
    existing_item_key = clean_zotero_item_key(link.get("itemKey") or existing_zotero.get("itemKey"))
    if existing_item_key:
        return {
            "ok": True,
            "linked": False,
            "alreadyLinked": True,
            "paper": paper_snapshot(paper),
            "itemKey": existing_item_key,
            "score": link.get("confidence") or 100,
            "candidates": link.get("candidates") or [],
        }

    match_result = resolve_zotero_match(paper, candidates)
    if match_result.get("status") == "ambiguous":
        snapshot = paper_snapshot({
            **paper,
            "zoteroLink": zotero_link_for_ambiguity(match_result.get("candidates") or []),
        })
        snapshot["paperKey"] = key
        with LIBRARY_LOCK:
            library = load_library()
            update_library_paper_snapshot(library, key, snapshot)
            save_library(library)
        return {
            "ok": True,
            "linked": False,
            "alreadyLinked": False,
            "ambiguous": True,
            "paper": snapshot,
            "itemKey": "",
            "score": match_result.get("score") or 0,
            "candidates": match_result.get("candidates") or [],
            "message": snapshot.get("zoteroLink", {}).get("message") or "",
        }

    match = match_result.get("match") if isinstance(match_result.get("match"), dict) else None
    score = int(match_result.get("score") or 0)
    if not match:
        return {
            "ok": True,
            "linked": False,
            "alreadyLinked": False,
            "paper": paper_snapshot(paper),
            "itemKey": "",
            "score": score,
            "candidates": [],
        }

    snapshot = merge_zotero_metadata(paper, match)
    snapshot["paperKey"] = key
    with LIBRARY_LOCK:
        library = load_library()
        update_library_paper_snapshot(library, key, snapshot)
        save_library(library)
    zotero = snapshot.get("zotero") if isinstance(snapshot.get("zotero"), dict) else {}
    return {
        "ok": True,
        "linked": True,
        "alreadyLinked": False,
        "paper": snapshot,
        "itemKey": str(zotero.get("itemKey") or ""),
        "score": score,
    }


def link_papers_to_zotero(papers: list[dict], attempts: int = 1) -> dict:
    candidates = read_zotero_candidates(attempts=attempts)
    linked = 0
    already_linked = 0
    unmatched = 0
    ambiguous = 0
    conflict = 0
    results = []
    for paper in papers:
        snapshot = paper_snapshot(paper)
        key = str(snapshot.get("paperKey") or paper_key(snapshot))
        result = link_library_paper_to_zotero(key, snapshot, candidates)
        if result.get("alreadyLinked"):
            already_linked += 1
        elif result.get("linked"):
            linked += 1
        elif result.get("ambiguous"):
            ambiguous += 1
        elif result.get("conflict"):
            conflict += 1
        else:
            unmatched += 1
        results.append({
            "paperKey": key,
            "linked": bool(result.get("linked")),
            "alreadyLinked": bool(result.get("alreadyLinked")),
            "ambiguous": bool(result.get("ambiguous")),
            "conflict": bool(result.get("conflict")),
            "itemKey": result.get("itemKey") or "",
            "score": result.get("score") or 0,
            "candidates": result.get("candidates") or [],
            "message": result.get("message") or "",
        })
    return {
        "linked": linked,
        "alreadyLinked": already_linked,
        "unmatched": unmatched,
        "ambiguous": ambiguous,
        "conflict": conflict,
        "results": results,
        "library": compact_library(load_library()),
    }


def find_matching_library_key(library: dict, paper: dict) -> tuple[str, dict | None, int]:
    best_key = ""
    best_entry = None
    best_score = 0
    seen = set()
    for section in ("papers", "favorites", "downloads", "ignored"):
        for key, item in (library.get(section) or {}).items():
            if key in seen or not isinstance(item, dict) or not isinstance(item.get("paper"), dict):
                continue
            seen.add(key)
            score = paper_match_score(item["paper"], paper)
            if score > best_score or (
                score == best_score
                and best_entry
                and str((best_entry.get("paper") or {}).get("source") or "") == "zotero"
                and str(item["paper"].get("source") or "") != "zotero"
            ):
                best_key = str(key)
                best_entry = item
                best_score = score
    return (best_key, best_entry, best_score) if best_score >= 70 else ("", None, best_score)


def read_zotero_papers(limit: int = 100, require_pdf: bool = False) -> list[dict]:
    snapshot_path = copy_zotero_database_snapshot()
    conn = None
    try:
        conn = sqlite3.connect(snapshot_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select i.itemID, i.key, i.libraryID, i.dateAdded, i.dateModified, it.typeName
            from items i
            join itemTypes it on it.itemTypeID = i.itemTypeID
            where i.itemID not in (select itemID from deletedItems)
            order by i.dateModified desc, i.itemID desc
            limit ?
            """,
            (max(1, min(limit * 3, 1000)),),
        ).fetchall()
        papers = []
        for row in rows:
            paper = zotero_paper_from_row(conn, row)
            if not paper:
                continue
            if require_pdf and not paper.get("localPdfPath"):
                continue
            papers.append(paper)
            if len(papers) >= limit:
                break
        return papers
    finally:
        if conn is not None:
            conn.close()
        try:
            snapshot_path.unlink(missing_ok=True)
            for suffix in ("-wal", "-shm"):
                Path(str(snapshot_path) + suffix).unlink(missing_ok=True)
        except OSError:
            pass


def import_zotero_library(payload: dict) -> dict:
    limit = clamp_int(payload.get("limit"), default=50, minimum=1, maximum=200)
    require_pdf = bool(payload.get("requirePdf", False))
    papers = read_zotero_papers(limit=limit, require_pdf=require_pdf)
    imported = 0
    updated = 0
    linked = 0
    with LIBRARY_LOCK:
        library = load_library()
        now = now_iso()
        for paper in papers:
            zotero_snapshot = paper_snapshot({
                **paper,
                "access": "user_library",
                "isDownloaded": bool(paper.get("localPdfPath")),
                "downloadable": bool(paper.get("localPdfPath")),
                "tags": sorted(set([*(paper.get("tags") or []), "zotero"])),
            })
            matched_key, matched_entry, _ = find_matching_library_key(library, zotero_snapshot)
            if matched_key and matched_entry and str((matched_entry.get("paper") or {}).get("source") or "") != "zotero":
                base_paper = matched_entry.get("paper") if isinstance(matched_entry.get("paper"), dict) else {}
                snapshot = merge_zotero_metadata(base_paper, zotero_snapshot)
                snapshot["paperKey"] = matched_key
                key = matched_key
                existed = True
                linked += 1
            else:
                snapshot = zotero_snapshot
                key = matched_key or snapshot["paperKey"]
                snapshot["paperKey"] = key
                existed = key in (library.get("papers") or {}) or key in (library.get("favorites") or {})
            entry = {
                "createdAt": (library.get("papers", {}).get(key) or {}).get("createdAt", now),
                "updatedAt": now,
                "paper": snapshot,
            }
            library["papers"][key] = entry
            library["favorites"][key] = entry
            if snapshot.get("localPdfPath"):
                library["downloads"][key] = {
                    "createdAt": (library.get("downloads", {}).get(key) or {}).get("createdAt", now),
                    "updatedAt": now,
                    "filename": snapshot.get("localPdfFilename") or Path(str(snapshot.get("localPdfPath"))).name,
                    "path": snapshot.get("localPdfPath"),
                    "source": "zotero",
                    "paper": snapshot,
                }
            imported += 0 if existed else 1
            updated += 1 if existed else 0
        save_library(library)
    return {
        "ok": True,
        "imported": imported,
        "updated": updated,
        "linked": linked,
        "count": len(papers),
        "withPdf": sum(1 for paper in papers if paper.get("localPdfPath")),
        "library": compact_library(load_library()),
    }


def abstract_text_from_crossref_message(message: dict) -> str:
    abstract = clean_html(str(message.get("abstract") or ""))
    if abstract:
        return abstract
    return ""


def crossref_abstract_candidate(doi: str) -> dict:
    if not doi:
        return {}
    try:
        response = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers=REQUEST_HEADERS,
            timeout=request_timeout(),
        )
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        message = (response.json().get("message") or {})
    except (requests.RequestException, ValueError):
        return {}
    abstract = abstract_text_from_crossref_message(message)
    if not abstract:
        return {}
    return {
        "text": abstract,
        "source": "crossref",
        "sourceLabel": "Crossref",
        "accessMode": "open-metadata",
        "fetchedAt": now_iso(),
        "completeness": abstract_completeness_for_text(abstract),
    }


def openalex_abstract_from_inverted_index(index: object) -> str:
    if not isinstance(index, dict):
        return ""
    positions = []
    for word, raw_positions in index.items():
        if not isinstance(raw_positions, list):
            continue
        for position in raw_positions:
            try:
                positions.append((int(position), str(word)))
            except (TypeError, ValueError):
                continue
    if not positions:
        return ""
    positions.sort(key=lambda item: item[0])
    return clean_html(" ".join(word for _, word in positions))


def openalex_abstract_candidate(doi: str) -> dict:
    if not doi:
        return {}
    try:
        response = requests.get(
            f"https://api.openalex.org/works/https://doi.org/{doi}",
            headers=REQUEST_HEADERS,
            timeout=request_timeout(),
        )
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return {}
    abstract = openalex_abstract_from_inverted_index(data.get("abstract_inverted_index"))
    if not abstract:
        return {}
    return {
        "text": abstract,
        "source": "openalex",
        "sourceLabel": "OpenAlex",
        "accessMode": "open-metadata",
        "fetchedAt": now_iso(),
        "completeness": abstract_completeness_for_text(abstract),
    }


def semantic_abstract_candidate_by_doi(doi: str) -> dict:
    if not doi:
        return {}
    try:
        response = requests.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "abstract"},
            headers=REQUEST_HEADERS,
            timeout=request_timeout(),
        )
        if response.status_code in {404, 429}:
            return {}
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return {}
    abstract = clean_html(str(data.get("abstract") or ""))
    if not abstract:
        return {}
    return {
        "text": abstract,
        "source": "semantic",
        "sourceLabel": "Semantic Scholar",
        "accessMode": "open-metadata",
        "fetchedAt": now_iso(),
        "completeness": abstract_completeness_for_text(abstract),
    }


def zotero_abstract_candidate(paper: dict, candidates: list[dict] | None = None) -> dict:
    zotero = paper.get("zotero") if isinstance(paper.get("zotero"), dict) else {}
    if str(paper.get("source") or "") == "zotero":
        text = clean_html(str(paper.get("fullAbstract") or paper.get("abstract") or ""))
        if text:
            return {
                "text": text,
                "source": "zotero",
                "sourceLabel": "Zotero",
                "accessMode": "user-library",
                "fetchedAt": now_iso(),
                "completeness": abstract_completeness_for_text(text),
            }
    if candidates is None:
        try:
            candidates = read_zotero_candidates()
        except Exception:
            candidates = []
    if not candidates:
        return {}
    target_key = clean_zotero_item_key(zotero.get("itemKey") or (paper.get("zoteroLink") or {}).get("itemKey"))
    match = None
    if target_key:
        match = next((candidate for candidate in candidates if zotero_meta_item_key(candidate.get("zotero")) == target_key), None)
    if not match:
        match, _score = find_matching_zotero_paper(paper, candidates)
    if not match:
        return {}
    text = clean_html(str(match.get("fullAbstract") or match.get("abstract") or ""))
    if not text:
        return {}
    return {
        "text": text,
        "source": "zotero",
        "sourceLabel": "Zotero",
        "accessMode": "user-library",
        "fetchedAt": now_iso(),
        "completeness": abstract_completeness_for_text(text),
    }


def open_metadata_abstract_candidates(paper: dict) -> list[dict]:
    doi = paper_doi(paper)
    if not doi:
        return []
    candidates = []
    for getter in (semantic_abstract_candidate_by_doi, crossref_abstract_candidate, openalex_abstract_candidate):
        candidate = getter(doi)
        if candidate:
            candidates.append(candidate)
    return candidates


def open_metadata_abstract_candidates_with_diagnostics(paper: dict) -> tuple[list[dict], list[dict]]:
    doi = paper_doi(paper)
    providers = (
        ("semantic", "Semantic Scholar", semantic_abstract_candidate_by_doi),
        ("crossref", "Crossref", crossref_abstract_candidate),
        ("openalex", "OpenAlex", openalex_abstract_candidate),
    )
    if not doi:
        return [], [
            abstract_diagnostic_empty(source, label, "缺少 DOI，无法查询该开放元数据来源。", "skipped")
            for source, label, _getter in providers
        ]

    candidates = []
    diagnostics = []
    for source, label, getter in providers:
        try:
            candidate = getter(doi)
        except Exception as exc:
            candidate = {}
            diagnostics.append(abstract_diagnostic_empty(
                source,
                label,
                f"查询失败：{compact_text(str(exc), 120)}",
                "failed",
            ))
        if candidate:
            candidates.append(candidate)
            diagnostics.append(abstract_diagnostic_from_candidate(candidate, "available", "开放元数据返回了摘要。"))
        elif not any(diagnostic.get("source") == source for diagnostic in diagnostics):
            diagnostics.append(abstract_diagnostic_empty(
                source,
                label,
                "未返回摘要，可能尚未收录、尚未更新或该来源不公开摘要。",
                "empty",
            ))
    return candidates, diagnostics


def collect_abstract_candidates(paper: dict, *, zotero_candidates: list[dict] | None = None,
                                include_source_refresh: bool = True,
                                include_open_metadata: bool = True) -> dict:
    snapshot = paper_snapshot(paper)
    candidates = [abstract_candidate_from_paper(snapshot, snapshot.get("abstractSource") or "existing")]
    diagnostics = []
    current_candidate = candidates[0]
    current_text = clean_html(str(current_candidate.get("text") or ""))
    diagnostics.append(abstract_diagnostic_from_candidate(
        current_candidate,
        "current" if current_text else "empty",
        "当前记录中的摘要。" if current_text else "当前记录没有可用摘要。",
    ))

    zotero_candidate = zotero_abstract_candidate(snapshot, zotero_candidates)
    if zotero_candidate:
        candidates.append(zotero_candidate)
        diagnostics.append(abstract_diagnostic_from_candidate(zotero_candidate, "available", "Zotero 本地资料库返回了摘要。"))
    else:
        zotero_message = "未匹配到 Zotero 摘要，或 Zotero 条目没有 abstractNote。"
        if not zotero_candidates and str(snapshot.get("source") or "") != "zotero":
            zotero_message = "未检测到可用于匹配的 Zotero 本地候选。"
        diagnostics.append(abstract_diagnostic_empty("zotero", "Zotero", zotero_message, "empty"))

    if include_open_metadata:
        open_candidates, open_diagnostics = open_metadata_abstract_candidates_with_diagnostics(snapshot)
        candidates.extend(open_candidates)
        diagnostics.extend(open_diagnostics)
    else:
        diagnostics.extend([
            abstract_diagnostic_empty(source, label, "本次操作未检查开放元数据来源。", "skipped")
            for source, label in (
                ("semantic", "Semantic Scholar"),
                ("crossref", "Crossref"),
                ("openalex", "OpenAlex"),
            )
        ])

    if include_source_refresh and snapshot.get("abstractCompleteness") != "complete":
        try:
            refreshed = find_refreshed_paper(snapshot)
        except Exception as exc:
            refreshed = None
            diagnostics.append(abstract_diagnostic_empty(
                "source-refresh",
                "来源刷新",
                f"来源刷新失败：{compact_text(str(exc), 120)}",
                "failed",
            ))
        if refreshed:
            refreshed_candidate = abstract_candidate_from_paper(
                {
                    **refreshed,
                    "abstractSource": "source-refresh",
                    "abstractSourceLabel": SOURCE_LABELS.get(str(refreshed.get("source") or ""), "来源刷新"),
                },
                "source-refresh",
                SOURCE_LABELS.get(str(refreshed.get("source") or ""), "来源刷新"),
            )
            candidates.append(refreshed_candidate)
            diagnostics.append(abstract_diagnostic_from_candidate(refreshed_candidate, "available", "来源刷新找到了匹配记录。"))
        elif not any(diagnostic.get("source") == "source-refresh" for diagnostic in diagnostics):
            diagnostics.append(abstract_diagnostic_empty("source-refresh", "来源刷新", "来源刷新未找到可匹配的更新记录。", "empty"))
    elif include_source_refresh:
        diagnostics.append(abstract_diagnostic_empty("source-refresh", "来源刷新", "当前摘要已完整，跳过来源刷新。", "skipped"))
    else:
        diagnostics.append(abstract_diagnostic_empty("source-refresh", "来源刷新", "本次导入不执行来源刷新。", "skipped"))

    selected_source = snapshot.get("abstractSource") or ""
    return {
        "paper": snapshot,
        "candidates": normalize_abstract_candidates(candidates),
        "rawCandidates": candidates,
        "diagnostics": selected_abstract_diagnostics(diagnostics, selected_source),
        "conflict": abstract_conflict_from_candidates(candidates, selected_source),
    }


def enrich_paper_abstract(paper: dict, *, zotero_candidates: list[dict] | None = None,
                          include_source_refresh: bool = True,
                          include_open_metadata: bool = True) -> dict:
    collected = collect_abstract_candidates(
        paper,
        zotero_candidates=zotero_candidates,
        include_source_refresh=include_source_refresh,
        include_open_metadata=include_open_metadata,
    )
    snapshot = collected["paper"]
    before_support = json.dumps(
        {
            "diagnostics": snapshot.get("abstractDiagnostics") or [],
            "candidates": snapshot.get("abstractCandidates") or [],
            "conflict": snapshot.get("abstractConflict") or {},
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    candidates = collected["rawCandidates"]
    before_hash = stable_text_hash(snapshot.get("fullAbstract") or snapshot.get("abstract") or "")
    enriched = snapshot
    for candidate in candidates[1:]:
        enriched = merge_paper_abstract(enriched, candidate)
    after_hash = stable_text_hash(enriched.get("fullAbstract") or enriched.get("abstract") or "")
    diagnostics = selected_abstract_diagnostics(collected["diagnostics"], enriched.get("abstractSource") or "")
    conflict = abstract_conflict_from_candidates(candidates, enriched.get("abstractSource") or "")
    enriched = paper_snapshot({
        **enriched,
        "abstractDiagnostics": diagnostics,
        "abstractConflict": conflict,
        "abstractCandidates": collected["candidates"],
    })
    after_support = json.dumps(
        {
            "diagnostics": enriched.get("abstractDiagnostics") or [],
            "candidates": enriched.get("abstractCandidates") or [],
            "conflict": enriched.get("abstractConflict") or {},
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return {
        "paper": enriched,
        "changed": before_hash != after_hash,
        "diagnosticsChanged": before_support != after_support,
        "source": enriched.get("abstractSource") or "",
        "sourceLabel": enriched.get("abstractSourceLabel") or "",
        "candidateCount": max(0, len(candidates) - 1),
    }


def candidate_lookup_key(candidate: dict) -> set[str]:
    keys = set()
    for field in ("id", "textHash"):
        value = str(candidate.get(field) or "").strip()
        if value:
            keys.add(value)
    source = normalize_abstract_source(candidate.get("source"), "")
    text_hash = str(candidate.get("textHash") or "").strip()
    if source:
        keys.add(source)
    if source and text_hash:
        keys.add(f"{source}:{text_hash}")
    return keys


def find_abstract_candidate(candidates: list[dict], selector: object) -> dict:
    selector_text = str(selector or "").strip()
    if not selector_text:
        return {}
    for candidate in normalize_abstract_candidates(candidates):
        if selector_text in candidate_lookup_key(candidate):
            return candidate
    return {}


def abstract_candidates_payload(payload: dict) -> dict:
    key, paper = resolve_library_paper(payload)
    include_source_refresh = bool(payload.get("includeSourceRefresh", True))
    persist = bool(payload.get("persist", True))
    try:
        zotero_candidates = read_zotero_candidates()
    except Exception:
        zotero_candidates = []
    collected = collect_abstract_candidates(
        paper,
        zotero_candidates=zotero_candidates,
        include_source_refresh=include_source_refresh,
    )
    snapshot = paper_snapshot({
        **collected["paper"],
        "abstractCandidates": collected["candidates"],
        "abstractDiagnostics": collected["diagnostics"],
        "abstractConflict": collected["conflict"],
    })
    snapshot["paperKey"] = key

    library_view = None
    if persist and key:
        with LIBRARY_LOCK:
            library = load_library()
            existing_item = library_entry_for_key(library, key)
            if isinstance(existing_item, dict):
                existing = existing_item.get("paper") if isinstance(existing_item.get("paper"), dict) else {}
                safe_snapshot = paper_snapshot(preserve_existing_state(snapshot, existing))
                safe_snapshot["paperKey"] = key
                update_library_entry_with_snapshot(library, key, safe_snapshot)
                save_library(library)
                snapshot = safe_snapshot
                library_view = compact_library(library)

    return {
        "ok": True,
        "paper": snapshot,
        "paperKey": key,
        "candidates": snapshot.get("abstractCandidates") or [],
        "diagnostics": snapshot.get("abstractDiagnostics") or [],
        "conflict": snapshot.get("abstractConflict") or {},
        "locked": bool(snapshot.get("abstractLocked")),
        "library": library_view or compact_library(load_library()),
    }


def abstract_confirm_payload(payload: dict) -> dict:
    key, paper = resolve_library_paper(payload)
    snapshot = paper_snapshot(paper)
    action = str(payload.get("action") or "confirm").strip().lower()
    lock_requested = bool(payload.get("lock", True))

    if action == "unlock":
        updated = paper_snapshot({
            **snapshot,
            "abstractLocked": False,
            "abstractAudit": add_abstract_audit_event(snapshot, "unlock", locked=False, message="用户解除摘要锁定。"),
            "metadataUpdatedAt": now_iso(),
        })
    else:
        if action in {"lock", "lock-current"}:
            selected = normalize_abstract_candidate(
                abstract_candidate_from_paper(snapshot, snapshot.get("abstractSource") or "existing", snapshot.get("abstractSourceLabel") or "")
            )
            if not selected:
                raise ValueError("当前记录没有可锁定的摘要。")
            lock_requested = True
        else:
            provided = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
            selected = normalize_abstract_candidate(provided)
            selector = payload.get("candidateId") or payload.get("textHash") or payload.get("source") or ""
            candidates = normalize_abstract_candidates(snapshot.get("abstractCandidates"))
            if not selected and selector:
                selected = find_abstract_candidate(candidates, selector)
            if not selected and selector:
                try:
                    collected = abstract_candidates_payload({**payload, "paper": snapshot, "paperKey": key, "persist": False})
                    selected = find_abstract_candidate(collected.get("candidates") or [], selector)
                    candidates = normalize_abstract_candidates(collected.get("candidates") or candidates)
                except Exception:
                    selected = {}
            if not selected:
                raise ValueError("没有找到可确认的摘要候选。")

        now = now_iso()
        all_candidates = normalize_abstract_candidates([selected, *(snapshot.get("abstractCandidates") or [])])
        diagnostics = selected_abstract_diagnostics(
            [
                *normalize_abstract_diagnostics(snapshot.get("abstractDiagnostics")),
                abstract_diagnostic_from_candidate(selected, "available", "用户手动确认的摘要候选。"),
            ],
            selected.get("source") or "",
        )
        updated = paper_snapshot({
            **snapshot,
            "fullAbstract": selected["text"],
            "abstract": compact_text(selected["text"], ABSTRACT_TEXT_LIMIT),
            "abstractSource": selected["source"],
            "abstractSourceLabel": selected["sourceLabel"],
            "abstractFetchedAt": selected.get("fetchedAt") or now,
            "abstractCompleteness": selected["completeness"],
            "abstractAccessMode": selected.get("accessMode") or "",
            "abstractDiagnostics": diagnostics,
            "abstractConflict": abstract_conflict_from_candidates(all_candidates, selected.get("source") or ""),
            "abstractCandidates": all_candidates,
            "abstractLocked": lock_requested,
            "abstractConfirmedAt": now,
            "abstractConfirmedBy": "user",
            "abstractAudit": add_abstract_audit_event(
                snapshot,
                "lock-current" if action in {"lock", "lock-current"} else "confirm",
                candidate=selected,
                locked=lock_requested,
                message="用户锁定当前摘要。" if action in {"lock", "lock-current"} else "用户确认摘要来源。",
            ),
            "metadataUpdatedAt": now,
        })

    updated["paperKey"] = key
    with LIBRARY_LOCK:
        library = load_library()
        update_library_entry_with_snapshot(library, key, updated)
        save_library(library)
        library_view = compact_library(library)

    return {
        "ok": True,
        "paper": updated,
        "paperKey": key,
        "locked": bool(updated.get("abstractLocked")),
        "library": library_view,
    }


def update_library_entry_with_snapshot(library: dict, key: str, snapshot: dict, now: str | None = None) -> None:
    update_library_paper_snapshot(library, key, snapshot, now=now)
    if key in (library.get("favorites") or {}):
        library["favorites"][key]["refreshedAt"] = now or now_iso()


def enrich_favorites_abstracts(payload: dict | None = None) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    only_incomplete = bool(payload.get("onlyIncomplete", True))
    limit = clamp_int(payload.get("limit"), default=50, minimum=1, maximum=120)
    library = load_library()
    favorites = [
        (key, item.get("paper"))
        for key, item in (library.get("favorites") or {}).items()
        if isinstance(item, dict) and isinstance(item.get("paper"), dict)
    ]
    if only_incomplete:
        favorites = [
            (key, paper)
            for key, paper in favorites
            if paper_snapshot(paper).get("abstractCompleteness") != "complete"
        ]
    favorites = favorites[:limit]
    if not favorites:
        return {
            "ok": True,
            "library": compact_library(library),
            "checked": 0,
            "enriched": 0,
            "diagnosticsUpdated": 0,
            "errors": {},
        }

    try:
        zotero_candidates = read_zotero_candidates()
    except Exception:
        zotero_candidates = []

    updated = {}
    enriched_count = 0
    diagnostics_updated = 0
    errors = {}
    with ThreadPoolExecutor(max_workers=min(len(favorites), 3)) as executor:
        future_to_key = {
            executor.submit(enrich_paper_abstract, paper, zotero_candidates=zotero_candidates): key
            for key, paper in favorites
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
            except Exception as exc:
                errors[key] = compact_text(str(exc), 180)
                continue
            if result.get("changed"):
                enriched_count += 1
            if result.get("diagnosticsChanged") and not result.get("changed"):
                diagnostics_updated += 1
            if result.get("changed") or result.get("diagnosticsChanged"):
                updated[key] = result["paper"]

    with LIBRARY_LOCK:
        library = load_library()
        now = now_iso()
        for key, snapshot in updated.items():
            item = library.get("favorites", {}).get(key)
            if not isinstance(item, dict):
                continue
            existing = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            safe_snapshot = paper_snapshot(preserve_existing_state(snapshot, existing))
            safe_snapshot["paperKey"] = key
            update_library_entry_with_snapshot(library, key, safe_snapshot, now=now)
        save_library(library)
        library_view = compact_library(library)

    return {
        "ok": True,
        "library": library_view,
        "checked": len(favorites),
        "enriched": enriched_count,
        "diagnosticsUpdated": diagnostics_updated,
        "errors": errors,
    }


def extract_dois(text: str) -> list[str]:
    dois = []
    seen = set()
    for match in re.finditer(r"10\.\d{4,9}/[^\s\"<>]+", text, flags=re.IGNORECASE):
        doi = match.group(0).rstrip(".,;:)］】")
        key = doi.lower()
        if key not in seen:
            seen.add(key)
            dois.append(doi)
    return dois


def extract_first_url(text: str) -> str:
    match = re.search(r"https?://[^\s\"<>]+", text)
    return match.group(0).rstrip(".,;)") if match else ""


ALERT_FIELD_ALIASES = {
    "title": {"title", "标题", "article", "article title", "paper", "name", "ti", "t1"},
    "abstract": {"abstract", "abstract note", "摘要", "summary", "description", "ab"},
    "authors": {"authors", "author", "作者", "creator", "au"},
    "venue": {"journal", "journal title", "venue", "publication", "期刊", "会议", "source", "来源", "jo", "jf", "t2"},
    "year": {"year", "年份", "date", "日期", "published", "publication date", "py", "y1"},
    "doi": {"doi", "do"},
    "url": {"url", "link", "链接", "ur"},
}


def alert_field_key(label: str) -> str:
    raw = str(label or "").strip().lower()
    normalized = normalize_key(raw) or raw
    for key, aliases in ALERT_FIELD_ALIASES.items():
        if raw in aliases or normalized in aliases:
            return key
    return ""


def clean_alert_field_value(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^\s*[\"'{]+", "", text)
    text = re.sub(r"[\"'}]+\s*,?\s*$", "", text)
    return clean_html(text)


def parse_alert_field_line(line: str) -> tuple[str, str]:
    text = str(line or "").strip()
    patterns = (
        r"^\s*([^:：]{2,32})\s*[:：]\s*(.+)$",
        r"^\s*([A-Za-z][A-Za-z0-9_\- ]{1,32})\s*=\s*(.+?)\s*,?\s*$",
        r"^\s*([A-Z0-9]{2})\s+-\s*(.*)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        key = alert_field_key(match.group(1))
        if key:
            return key, clean_alert_field_value(match.group(2))
    return "", ""


def split_alert_text_blocks(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []

    ris_blocks = [
        block.strip()
        for block in re.split(r"(?im)^\s*ER\s+-?\s*$", text)
        if block.strip()
    ]
    if len(ris_blocks) > 1:
        return ris_blocks

    bib_matches = list(re.finditer(r"(?is)@\w+\s*\{.*?(?=\n\s*@\w+\s*\{|\Z)", text))
    if len(bib_matches) > 1:
        return [match.group(0).strip() for match in bib_matches if match.group(0).strip()]

    lines = text.splitlines()
    title_starts = [
        index
        for index, line in enumerate(lines)
        if parse_alert_field_line(line)[0] == "title"
    ]
    if len(title_starts) > 1:
        blocks = []
        for position, start in enumerate(title_starts):
            end = title_starts[position + 1] if position + 1 < len(title_starts) else len(lines)
            block = "\n".join(lines[start:end]).strip()
            if block:
                blocks.append(block)
        if blocks:
            return blocks

    dois = extract_dois(text)
    if len(dois) > 1:
        blocks = []
        lowered = text.lower()
        for doi in dois:
            doi_index = lowered.find(doi.lower())
            before = text[max(0, doi_index - 1400):doi_index]
            after = text[doi_index:min(len(text), doi_index + 2200)]
            blocks.append(f"{before}\n{after}".strip())
        return blocks

    return [text]


def value_after_label(lines: list[str], labels: tuple[str, ...]) -> str:
    wanted = {alert_field_key(label) for label in labels}
    wanted.discard("")
    for line in lines:
        field_key, value = parse_alert_field_line(line)
        if field_key in wanted and value:
            return value
        for label in labels:
            pattern = rf"^\s*{re.escape(label)}\s*[:：]\s*(.+)$"
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                return clean_html(match.group(1))
    return ""


def extract_labeled_abstract(lines: list[str]) -> str:
    stop_labels = {
        "doi", "title", "authors", "year", "venue", "url",
    }
    for index, line in enumerate(lines):
        field_key, value = parse_alert_field_line(line)
        if field_key != "abstract":
            continue
        chunks = [value] if value else []
        for next_line in lines[index + 1:]:
            next_key, _next_value = parse_alert_field_line(next_line)
            if next_key in stop_labels:
                break
            if not next_line.strip() and chunks:
                break
            if next_line.strip():
                chunks.append(next_line.strip())
        return clean_html(" ".join(chunks))
    return ""


def infer_alert_title(lines: list[str], doi: str = "") -> str:
    title = value_after_label(lines, ("Title", "标题", "Article", "Paper"))
    if title:
        return title
    blocked = ("doi", "http", "abstract", "摘要", "authors", "作者", "journal", "期刊", "source", "来源")
    candidates = []
    for line in lines:
        text = clean_html(line)
        if not text:
            continue
        low = text.lower()
        if doi and doi.lower() in low:
            continue
        if any(token in low for token in blocked):
            continue
        if len(text) >= 12:
            candidates.append(text)
    return candidates[0] if candidates else ""


def parse_alert_text(text: str, source_label: str = "") -> list[dict]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("请先粘贴 alert 邮件、页面摘要或 DOI 文本。")
    source_label = clean_display_text(source_label or "Alert 导入", 80)
    blocks = split_alert_text_blocks(raw)

    papers = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        block_dois = extract_dois(block)
        doi = value_after_label(lines, ("DOI", "DO")) or (block_dois[0] if block_dois else "")
        title = infer_alert_title(lines, doi)
        abstract = extract_labeled_abstract(lines)
        authors = value_after_label(lines, ("Authors", "Author", "作者"))
        venue = value_after_label(lines, ("Journal", "Venue", "期刊", "会议", "Source", "来源"))
        year_text = value_after_label(lines, ("Year", "年份", "Date", "日期"))
        year_match = re.search(r"\b(19|20)\d{2}\b", year_text or block)
        url = value_after_label(lines, ("URL", "Link", "链接")) or extract_first_url(block)
        if not title and doi:
            title = doi
        if not title:
            continue
        paper = make_paper(
            source="alert",
            title=title,
            authors=authors,
            published=year_text,
            year=year_match.group(0) if year_match else "",
            venue=venue or source_label,
            category=source_label,
            abstract=abstract,
            page_url=url,
            paper_id=doi or normalize_key(title).replace(" ", "-")[:64],
            doi=doi,
            access="user_visible_metadata",
        )
        paper.update({
            "abstractSource": "alert",
            "abstractSourceLabel": source_label,
            "abstractFetchedAt": now_iso(),
            "abstractAccessMode": "user-visible",
            "abstractCompleteness": abstract_completeness_for_text(abstract),
            "metadataUpdatedAt": now_iso(),
            "downloadable": False,
        })
        papers.append(paper_snapshot(paper))
    if not papers:
        raise ValueError("没有从文本中识别到论文标题或 DOI。")
    return papers


def decode_alert_bytes(value: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def html_alert_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)<\s*(br|/p|/div|/li|/tr|/h[1-6])\s*/?\s*>", "\n", text)
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s+", "\n", text).strip()


def eml_alert_text(raw: bytes) -> str:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception:
        return decode_alert_bytes(raw)
    parts = []
    for preferred_type in ("text/plain", "text/html"):
        for part in message.walk():
            if part.get_content_type() != preferred_type:
                continue
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                content = decode_alert_bytes(payload)
            if content:
                parts.append(html_alert_text(content) if preferred_type == "text/html" else clean_html(str(content)))
        if parts:
            break
    return "\n".join(parts).strip() or decode_alert_bytes(raw)


def csv_alert_text(value: str) -> str:
    try:
        reader = csv.DictReader(io.StringIO(value))
    except csv.Error:
        return value
    if not reader.fieldnames:
        return value
    normalized_fields = {field: alert_field_key(field) for field in reader.fieldnames if field}
    if not any(normalized_fields.values()):
        return value
    blocks = []
    for row in reader:
        lines = []
        for field, field_key in normalized_fields.items():
            if not field_key:
                continue
            raw_value = row.get(field)
            text = clean_html(str(raw_value or ""))
            if not text:
                continue
            label = {
                "title": "Title",
                "authors": "Authors",
                "venue": "Journal",
                "year": "Year",
                "doi": "DOI",
                "url": "URL",
                "abstract": "Abstract",
            }.get(field_key, field)
            lines.append(f"{label}: {text}")
        if lines:
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks).strip() or value


def normalize_alert_document_text(text: str, *, name: str = "", mime_type: str = "") -> str:
    filename = str(name or "").lower()
    mime = str(mime_type or "").lower()
    value = str(text or "").strip()
    if not value:
        return ""
    if filename.endswith(".csv") or "csv" in mime:
        return csv_alert_text(value)
    if filename.endswith((".html", ".htm")) or "html" in mime or re.search(r"(?is)<html|<body|<br|<p\b|<div\b", value):
        return html_alert_text(value)
    return value


def alert_file_text(item: object) -> dict | None:
    if isinstance(item, str):
        text = item
        name = "alert.txt"
        mime_type = "text/plain"
        raw = text.encode("utf-8")
    elif isinstance(item, dict):
        name = clean_display_text(str(item.get("name") or item.get("filename") or "alert.txt"), 120)
        mime_type = clean_display_text(str(item.get("mimeType") or item.get("type") or ""), 80)
        if item.get("contentBase64"):
            try:
                raw = base64.b64decode(str(item.get("contentBase64") or ""), validate=True)
            except ValueError as exc:
                raise ValueError(f"{name} 不是有效的 base64 文件内容。") from exc
            text = decode_alert_bytes(raw)
        else:
            text = str(item.get("content") or item.get("text") or "")
            raw = text.encode("utf-8", errors="replace")
    else:
        return None
    if name.lower().endswith(".eml") or "message/rfc822" in mime_type.lower():
        text = eml_alert_text(raw)
    text = normalize_alert_document_text(text, name=name, mime_type=mime_type)
    if not text:
        return None
    return {"name": name, "mimeType": mime_type, "text": text}


def alert_documents_from_payload(payload: dict) -> list[dict]:
    documents = []
    text = str(payload.get("text") or "").strip()
    if text:
        documents.append({"name": "pasted-alert.txt", "mimeType": "text/plain", "text": normalize_alert_document_text(text)})
    for collection_key in ("items", "files", "documents"):
        raw_items = payload.get(collection_key)
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            document = alert_file_text(item)
            if document:
                documents.append(document)
            if len(documents) >= MAX_ALERT_BATCH_DOCUMENTS:
                break
        if len(documents) >= MAX_ALERT_BATCH_DOCUMENTS:
            break
    if not documents:
        raise ValueError("请先粘贴 Alert 文本，或选择可读取的 Alert 文件。")
    return documents[:MAX_ALERT_BATCH_DOCUMENTS]


def alert_source_health_for_paper(alert_paper: dict, diagnostics: list[dict] | None = None,
                                  *, check_open_metadata: bool = True) -> dict:
    snapshot = paper_snapshot(alert_paper)
    doi = paper_doi(snapshot)
    alert_completeness = str(snapshot.get("abstractCompleteness") or "unknown")
    alert_complete = alert_completeness == "complete" and not looks_truncated_text(snapshot.get("fullAbstract") or snapshot.get("abstract") or "")
    if diagnostics is None and check_open_metadata and doi:
        try:
            _open_candidates, diagnostics = open_metadata_abstract_candidates_with_diagnostics(snapshot)
        except Exception as exc:
            diagnostics = [abstract_diagnostic_empty("open-metadata", "开放元数据", f"查询失败：{compact_text(str(exc), 120)}", "failed")]
    diagnostics = normalize_abstract_diagnostics(diagnostics or [])
    open_sources = [
        diagnostic for diagnostic in diagnostics
        if diagnostic.get("source") in OPEN_METADATA_ABSTRACT_SOURCES
    ]
    active_open_sources = [item for item in open_sources if item.get("status") != "skipped"]
    open_has_abstract = any(
        item.get("status") in {"available", "selected"} and item.get("textLength")
        for item in active_open_sources
    )
    open_failed = any(item.get("status") == "failed" for item in active_open_sources)
    checked_open_metadata = bool(check_open_metadata or active_open_sources)
    open_missing = bool(doi and checked_open_metadata and not open_has_abstract and not open_failed)
    open_lagging = bool(alert_complete and doi and not open_has_abstract and (open_missing or open_failed))
    if open_has_abstract:
        status = "open_has_abstract"
        note = "开放元数据已返回摘要。"
    elif open_lagging:
        status = "open_lagging" if open_missing else "open_failed"
        note = "Alert 中已有完整摘要，但开放元数据暂未返回；可能是新刊、新记录或开放索引更新滞后。"
    elif alert_complete:
        status = "alert_complete"
        note = "Alert 中已有完整摘要。"
    elif alert_completeness == "missing":
        status = "alert_missing"
        note = "Alert 文本未包含摘要。"
    else:
        status = "alert_partial"
        note = "Alert 摘要可能不完整，需要审阅。"
    return normalize_alert_source_health({
        "status": status,
        "alertComplete": alert_complete,
        "alertCompleteness": alert_completeness,
        "openHasAbstract": open_has_abstract,
        "openLagging": open_lagging,
        "openMissing": open_missing,
        "openFailed": open_failed,
        "doi": doi,
        "checkedAt": now_iso(),
        "sourceLabel": snapshot.get("abstractSourceLabel") or "",
        "note": note,
        "openSources": open_sources,
    })


def alert_source_health_summary(papers: list[dict]) -> dict:
    summary = empty_alert_source_health_summary()
    for paper in papers:
        health = normalize_alert_source_health(paper.get("alertSourceHealth"))
        completeness = health.get("alertCompleteness") or str(paper.get("abstractCompleteness") or "unknown")
        if completeness == "complete":
            summary["alertComplete"] += 1
        elif completeness == "missing":
            summary["alertMissing"] += 1
        else:
            summary["alertPartial"] += 1
        if health.get("openHasAbstract"):
            summary["openHasAbstract"] += 1
        if health.get("openLagging"):
            summary["openLagging"] += 1
        if health.get("openMissing"):
            summary["openMissing"] += 1
        if health.get("openFailed"):
            summary["openFailed"] += 1
    return summary


def alert_parse_report(documents: list[dict], papers: list[dict], failures: list[dict]) -> dict:
    report = empty_alert_parse_report()
    report["documents"] = len(documents)
    report["failedDocuments"] = len(failures)
    report["parsed"] = len(papers)
    doi_values = {paper_doi(paper).lower() for paper in papers if paper_doi(paper)}
    report["doiCount"] = len(doi_values)
    for document in documents:
        report["parsedBlocks"] += len(split_alert_text_blocks(str(document.get("text") or "")))
    for paper in papers:
        completeness = str(paper.get("abstractCompleteness") or "unknown")
        if completeness == "complete":
            report["completeAbstracts"] += 1
        elif completeness == "missing":
            report["missingAbstracts"] += 1
        else:
            report["partialAbstracts"] += 1
    report["unrecognizedFragments"] = max(0, report["parsedBlocks"] - report["parsed"]) + report["failedDocuments"]
    return normalize_alert_parse_report(report)


def upsert_imported_paper(library: dict, paper: dict, *, favorite: bool = True,
                          adopt_abstract: bool = True) -> tuple[str, dict, bool, bool]:
    now = now_iso()
    snapshot = paper_snapshot(paper)
    matched_key, matched_entry, _score = find_matching_library_key(library, snapshot)
    key = matched_key or str(snapshot.get("paperKey") or paper_key(snapshot))
    existed = bool(matched_entry)
    existing_paper = matched_entry.get("paper") if isinstance(matched_entry, dict) and isinstance(matched_entry.get("paper"), dict) else {}
    if existing_paper:
        snapshot = merge_library_paper_metadata(existing_paper, snapshot, adopt_abstract=adopt_abstract)
    elif not adopt_abstract:
        snapshot = stage_paper_abstract_for_review(snapshot)
    snapshot["paperKey"] = key
    entry = {
        "createdAt": (matched_entry or {}).get("createdAt", now),
        "updatedAt": now,
        "paper": snapshot,
    }
    library["papers"][key] = entry
    ignored = key in (library.get("ignored") or {})
    if favorite and not ignored:
        library["favorites"][key] = entry
    elif ignored:
        library["ignored"][key] = entry
    return key, snapshot, existed, ignored


def import_alert_payload(payload: dict) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    documents = alert_documents_from_payload(payload)
    combined_text = "\n\n".join(str(document.get("text") or "") for document in documents)
    raw_source_label = str(payload.get("sourceLabel") or "Alert 导入")
    source_id = str(payload.get("sourceId") or "")
    initial_library = load_library()
    detected_source = detect_subscription_source(
        combined_text,
        raw_source_label,
        source_id,
        initial_library.get("subscriptionSources"),
    )
    source_label = str(detected_source.get("sourceLabel") or raw_source_label)

    alert_papers = []
    failures = []
    for document in documents:
        try:
            parsed = parse_alert_text(str(document.get("text") or ""), source_label)
        except ValueError as exc:
            failures.append({
                "name": clean_display_text(str(document.get("name") or "Alert 文档"), 120),
                "error": clean_display_text(str(exc), 180),
            })
            continue
        alert_papers.extend(parsed)
    if not alert_papers:
        message = failures[0]["error"] if failures else "没有从文本中识别到论文标题或 DOI。"
        raise ValueError(message)

    review_only = bool(payload.get("reviewOnly", False))
    check_open_metadata = bool(payload.get("checkOpenMetadata", payload.get("enrich", True)))
    papers = []
    if payload.get("enrich", True):
        try:
            zotero_candidates = read_zotero_candidates()
        except Exception:
            zotero_candidates = []
        for alert_paper in alert_papers:
            try:
                enriched = enrich_paper_abstract(
                    alert_paper,
                    zotero_candidates=zotero_candidates,
                    include_source_refresh=False,
                    include_open_metadata=check_open_metadata,
                )["paper"]
                health = alert_source_health_for_paper(
                    alert_paper,
                    enriched.get("abstractDiagnostics"),
                    check_open_metadata=check_open_metadata,
                )
            except Exception:
                enriched = alert_paper
                health = alert_source_health_for_paper(alert_paper, None, check_open_metadata=check_open_metadata)
            alert_paper = paper_snapshot({**alert_paper, "alertSourceHealth": health})
            enriched = paper_snapshot({**enriched, "alertSourceHealth": health})
            papers.append(alert_paper if review_only else enriched)
    else:
        for alert_paper in alert_papers:
            health = alert_source_health_for_paper(alert_paper, None, check_open_metadata=check_open_metadata)
            papers.append(paper_snapshot({**alert_paper, "alertSourceHealth": health}))

    parse_report = alert_parse_report(documents, alert_papers, failures)
    health_summary = alert_source_health_summary(papers)
    imported = 0
    updated = 0
    ignored_updated = 0
    keys = []
    inbox_events = []
    import_source = normalize_subscription_source(detected_source) or {}
    history_event = {}
    with LIBRARY_LOCK:
        library = load_library()
        timestamp = now_iso()
        import_source = detect_subscription_source(
            combined_text,
            raw_source_label,
            source_id,
            library.get("subscriptionSources"),
        )
        for paper, alert_paper in zip(papers, alert_papers):
            key, snapshot, existed, ignored = upsert_imported_paper(
                library,
                paper,
                favorite=True,
                adopt_abstract=not review_only,
            )
            keys.append(key)
            if ignored:
                ignored_updated += 1
                import_state = "ignored"
            elif existed:
                updated += 1
                import_state = "updated"
            else:
                imported += 1
                import_state = "imported"
            if review_only:
                inbox_event = add_alert_inbox_event(
                    library,
                    import_source,
                    paper_key_value=key,
                    imported_paper=alert_paper,
                    stored_paper=snapshot,
                    import_state=import_state,
                    timestamp=timestamp,
                )
                if inbox_event:
                    inbox_events.append(inbox_event)
        detected = bool(import_source.get("detected"))
        import_source = upsert_subscription_source_import_stats(
            library,
            import_source,
            count=len(papers),
            imported=imported,
            updated=updated,
            ignored_updated=ignored_updated,
            timestamp=timestamp,
        )
        history_event = add_alert_import_history_event(
            library,
            {**import_source, "detected": detected},
            count=len(papers),
            imported=imported,
            updated=updated,
            ignored_updated=ignored_updated,
            timestamp=timestamp,
            report=parse_report,
            source_health=health_summary,
        )
        save_library(library)
        library_view = compact_library(library)
    return {
        "ok": True,
        "library": library_view,
        "papers": papers,
        "keys": keys,
        "source": import_source,
        "historyEvent": history_event,
        "alertInboxEvents": inbox_events,
        "reviewOnly": review_only,
        "checkOpenMetadata": check_open_metadata,
        "parseReport": parse_report,
        "sourceHealth": health_summary,
        "failures": failures,
        "documents": len(documents),
        "imported": imported,
        "updated": updated,
        "ignoredUpdated": ignored_updated,
        "count": len(papers),
    }


def library_entry_for_key(library: dict, key: str) -> dict | None:
    for section in ("papers", "favorites", "ignored", "downloads"):
        item = (library.get(section) or {}).get(key)
        if isinstance(item, dict):
            return item
    return None


def resolve_library_paper(payload: dict) -> tuple[str, dict]:
    paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
    key = str(payload.get("paperKey") or paper.get("paperKey") or "").strip()
    if key:
        library = load_library()
        item = library_entry_for_key(library, key)
        if isinstance(item, dict) and isinstance(item.get("paper"), dict):
            return key, item["paper"]
    if paper:
        return str(paper.get("paperKey") or paper_key(paper)), paper_snapshot(paper)
    raise ValueError("缺少可同步的论文。")


def zotero_item_key_from_paper(paper: dict) -> str:
    snapshot = paper_snapshot(paper)
    link = snapshot.get("zoteroLink") if isinstance(snapshot.get("zoteroLink"), dict) else {}
    status = str(link.get("status") or "")
    if status in ZOTERO_BLOCKED_LINK_STATUSES:
        raise ValueError(link.get("message") or "Zotero itemKey is ambiguous. Confirm the canonical Zotero item before syncing.")
    link_item_key = clean_zotero_item_key(link.get("itemKey"))
    if link_item_key:
        return link_item_key

    sync = paper.get("zoteroSync") if isinstance(paper.get("zoteroSync"), dict) else {}
    synced_item_key = str(sync.get("itemKey") or "").strip() if sync.get("status") == "synced" else ""
    zotero = paper.get("zotero") if isinstance(paper.get("zotero"), dict) else {}
    item_key = clean_zotero_item_key(zotero.get("itemKey") or zotero.get("key"))
    synced_item_key = clean_zotero_item_key(synced_item_key)
    if item_key and synced_item_key and item_key != synced_item_key:
        raise ValueError("PaperHunter has conflicting Zotero itemKeys. Confirm the canonical Zotero item before syncing.")
    if item_key:
        return item_key
    if synced_item_key:
        return synced_item_key
    if not item_key:
        raise ValueError("这篇论文不是从 Zotero 导入的条目，缺少 Zotero itemKey。")
    return item_key


def paper_has_syncable_zotero_key(paper: dict) -> bool:
    try:
        return bool(zotero_item_key_from_paper(paper))
    except ValueError:
        return False


def html_paragraphs(lines: list[str]) -> str:
    return "".join(f"<p>{escape(line)}</p>" for line in lines if str(line or "").strip())


def zotero_note_html_for_paper(paper: dict, include_fulltext: bool = True) -> str:
    title = clean_html(str(paper.get("title") or "Untitled"))
    translation = normalize_translations(paper.get("translations"), paper).get("zh")
    fulltext_items = paper.get("fulltextTranslations") if isinstance(paper.get("fulltextTranslations"), list) else []

    parts = [
        f'<h2 data-paperhunter-role="title">{escape(title)}</h2>',
        (
            f'<p><strong data-paperhunter-marker="sync-result">{ZOTERO_MANAGED_NOTE_MARKER}</strong>'
            f'<br/><span>同步时间：{escape(now_iso())}</span></p>'
        ),
    ]
    abstract = clean_html(str(paper.get("fullAbstract") or paper.get("abstract") or ""))
    if abstract and abstract != "暂无摘要。":
        parts.append("<h3>English Abstract</h3>")
        parts.append(html_paragraphs([abstract]))
    if translation and translation.get("text"):
        parts.append("<h3>中文摘要</h3>")
        parts.append(html_paragraphs([str(translation.get("text") or "")]))
        translated_at = str(translation.get("translatedAt") or "")
        if translated_at:
            parts.append(html_paragraphs([f"摘要翻译时间：{translated_at}"]))

    if include_fulltext and fulltext_items:
        parts.append("<h3>全文翻译</h3>")
        for item in fulltext_items:
            if not isinstance(item, dict):
                continue
            file_value = str(item.get("file") or "")
            created = str(item.get("createdAt") or "")
            if not file_value:
                continue
            line = f"译文文件：{file_value}"
            if created:
                line = f"{line}（{created}）"
            parts.append(html_paragraphs([line]))
    note = clean_html(str(paper.get("note") or ""))
    if note:
        parts.append("<h3>PaperHunter 备注</h3>")
        parts.append(html_paragraphs([note]))
    return "\n".join(parts)


def zotero_sync_tags_for_paper(paper: dict, include_fulltext: bool = True) -> list[str]:
    tags = {"paperhunter", "paperhunter:imported"}
    if normalize_translations(paper.get("translations"), paper).get("zh"):
        tags.add("paperhunter:abstract-translated")
    if include_fulltext and paper.get("fulltextTranslations"):
        tags.add("paperhunter:fulltext-translated")
    return sorted(tags)


def zotero_safe_sync_tags(tags: list[str]) -> list[str]:
    safe = []
    for tag in tags:
        clean_tag = str(tag or "").strip()
        if clean_tag == "paperhunter" or clean_tag.startswith("paperhunter:"):
            safe.append(clean_tag)
    return sorted(set(safe))


def zotero_sync_attachment_paths(paper: dict, include_fulltext: bool = True) -> list[str]:
    if not include_fulltext:
        return []
    paths = []
    seen = set()
    for item in paper.get("fulltextTranslations") or []:
        if not isinstance(item, dict):
            continue
        file_value = str(item.get("file") or "")
        if not file_value:
            continue
        try:
            path = resolve_translated_file(file_value)
        except ValueError:
            continue
        if path.suffix.lower() not in {".md", ".markdown"}:
            continue
        path_text = str(path)
        path_key = path_text.lower() if sys.platform.startswith("win") else path_text
        if path_key in seen:
            continue
        seen.add(path_key)
        paths.append(path_text)
    return paths


def zotero_sync_payload(paper: dict, include_fulltext: bool = True) -> dict:
    tags = zotero_safe_sync_tags(zotero_sync_tags_for_paper(paper, include_fulltext=include_fulltext))
    return {
        "itemKey": zotero_item_key_from_paper(paper),
        "protocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
        "client": "PaperHunter",
        "pairingToken": zotero_bridge_token(),
        "managedNoteMarker": ZOTERO_MANAGED_NOTE_MARKER,
        "allowedAttachmentRoots": [str(TRANSLATED_DIR.resolve())],
        "policy": {
            "tagPrefix": "paperhunter",
            "noteMode": "upsert-managed-note-only",
            "attachmentMode": "link-translated-markdown-only",
            "preserveUserContent": True,
        },
        "capabilities": ZOTERO_BRIDGE_CAPABILITIES,
        "noteHtml": zotero_note_html_for_paper(paper, include_fulltext=include_fulltext),
        "tags": tags,
        "attachments": zotero_sync_attachment_paths(paper, include_fulltext=include_fulltext),
    }


def update_zotero_sync_state(key: str, status: str, *, item_key: str = "", tags: list[str] | None = None,
                             attachments: int = 0, note_id: int | None = None, error: str = "") -> None:
    with LIBRARY_LOCK:
        library = load_library()
        existing = (
            library.get("papers", {}).get(key)
            or library.get("favorites", {}).get(key)
            or library.get("ignored", {}).get(key)
            or library.get("downloads", {}).get(key)
        )
        if not isinstance(existing, dict) or not isinstance(existing.get("paper"), dict):
            return
        existing_paper = existing["paper"]
        existing_link = existing_paper.get("zoteroLink") if isinstance(existing_paper.get("zoteroLink"), dict) else {}
        resolved_item_key = clean_zotero_item_key(
            item_key
            or existing_link.get("itemKey")
            or ((existing_paper.get("zotero") or {}).get("itemKey") if isinstance(existing_paper.get("zotero"), dict) else "")
        )
        link_status = str(existing_link.get("status") or "")
        if resolved_item_key and link_status not in {"confirmed", "conflict", "ambiguous"}:
            link_status = "auto"
        snapshot = paper_snapshot({
            **existing_paper,
            "zoteroLink": {
                **existing_link,
                "status": link_status or ("auto" if resolved_item_key else "unlinked"),
                "itemKey": resolved_item_key,
                "confidence": existing_link.get("confidence") or (100 if resolved_item_key else 0),
                "source": existing_link.get("source") or "sync",
                "updatedAt": now_iso(),
            },
            "zoteroSync": {
                "status": status,
                "itemKey": resolved_item_key,
                "syncedAt": now_iso() if status == "synced" else str((existing["paper"].get("zoteroSync") or {}).get("syncedAt") or ""),
                "noteID": note_id,
                "attachments": attachments,
                "tags": tags or [],
                "error": error,
            },
        })
        update_library_paper_snapshot(library, key, snapshot)
        if status in {"synced", "failed"}:
            add_zotero_audit_event(
                library,
                "sync",
                paper_key=key,
                paper=snapshot,
                item_key=resolved_item_key,
                status=status,
                message=error or ("Synced PaperHunter-managed Zotero content." if status == "synced" else "Zotero sync failed."),
                details={
                    "tags": tags or [],
                    "attachments": attachments,
                    "noteID": note_id,
                    "preserveUserContent": True,
                },
            )
        save_library(library)


def zotero_sync_preview_for_paper(
    key: str,
    paper: dict,
    *,
    include_fulltext: bool = True,
    candidates: list[dict] | None = None,
    persist_review: bool = True,
) -> dict:
    snapshot = paper_snapshot(paper)
    link = snapshot.get("zoteroLink") if isinstance(snapshot.get("zoteroLink"), dict) else {}

    if link.get("status") in ZOTERO_BLOCKED_LINK_STATUSES:
        review_candidates = merge_zotero_candidate_summaries(
            link.get("candidates") or [],
            zotero_link_review_candidates(snapshot, candidates),
        )
        message = link.get("message") or "Confirm the canonical Zotero item before syncing."
        if persist_review:
            snapshot = persist_zotero_link_review(
                key,
                snapshot,
                status=str(link.get("status") or "ambiguous"),
                message=message,
                candidates=review_candidates,
            )
        return {
            "ok": True,
            "ready": False,
            "paperKey": key,
            "title": snapshot.get("title") or "",
            "status": link.get("status"),
            "itemKey": clean_zotero_item_key(link.get("itemKey")),
            "tags": [],
            "attachments": 0,
            "message": message,
            "candidates": review_candidates,
        }

    if not clean_zotero_item_key(link.get("itemKey")):
        match_result = resolve_zotero_match(snapshot, candidates)
        if match_result.get("status") == "ambiguous":
            message = "Multiple Zotero items match this PaperHunter paper. Confirm the canonical item before syncing."
            review_candidates = match_result.get("candidates") or []
            if persist_review:
                snapshot = persist_zotero_link_review(
                    key,
                    snapshot,
                    status="ambiguous",
                    message=message,
                    candidates=review_candidates,
                )
            return {
                "ok": True,
                "ready": False,
                "paperKey": key,
                "title": snapshot.get("title") or "",
                "status": "ambiguous",
                "itemKey": "",
                "tags": [],
                "attachments": 0,
                "message": message,
                "candidates": review_candidates,
            }
        match = match_result.get("match") if isinstance(match_result.get("match"), dict) else None
        if not match:
            return {
                "ok": True,
                "ready": False,
                "paperKey": key,
                "title": snapshot.get("title") or "",
                "status": "unmatched",
                "itemKey": "",
                "tags": [],
                "attachments": 0,
                "message": "No matching Zotero item was found. Save or import the paper into Zotero before syncing.",
                "candidates": [],
            }
        snapshot = merge_zotero_metadata(snapshot, match)

    body = zotero_sync_payload(snapshot, include_fulltext=include_fulltext)
    return {
        "ok": True,
        "ready": True,
        "paperKey": key,
        "itemKey": body["itemKey"],
        "title": snapshot.get("title") or "",
        "tags": body["tags"],
        "attachments": len(body["attachments"]),
        "policy": body["policy"],
        "capabilities": body.get("capabilities") or {},
        "message": "Ready to sync PaperHunter-managed note, tags, and translated Markdown attachments to Zotero.",
    }


def zotero_sync_preview(payload: dict) -> dict:
    key, paper = resolve_library_paper(payload)
    include_fulltext = bool(payload.get("includeFulltext", True))
    persist_review = bool(payload.get("persistReview", True))
    preview = zotero_sync_preview_for_paper(
        key,
        paper,
        include_fulltext=include_fulltext,
        persist_review=persist_review,
    )
    if persist_review:
        preview["library"] = compact_library(load_library())
    return preview


def zotero_favorites_sync_preview(payload: dict) -> dict:
    include_fulltext = bool(payload.get("includeFulltext", True))
    library = load_library()
    favorites = [
        (str(key), item.get("paper"))
        for key, item in (library.get("favorites") or {}).items()
        if isinstance(item, dict) and isinstance(item.get("paper"), dict)
    ]
    candidates = read_zotero_candidates()
    items = []
    counts = {
        "checked": len(favorites),
        "ready": 0,
        "blocked": 0,
        "ambiguous": 0,
        "conflict": 0,
        "missing": 0,
        "unmatched": 0,
        "attachments": 0,
        "tags": 0,
    }
    unique_tags = set()
    for key, paper in favorites:
        preview = zotero_sync_preview_for_paper(
            key,
            paper,
            include_fulltext=include_fulltext,
            candidates=candidates,
            persist_review=True,
        )
        status = str(preview.get("status") or ("ready" if preview.get("ready") else "blocked"))
        item = {
            "paperKey": key,
            "title": preview.get("title") or str((paper or {}).get("title") or ""),
            "ready": bool(preview.get("ready")),
            "status": status,
            "itemKey": clean_zotero_item_key(preview.get("itemKey")),
            "tags": preview.get("tags") or [],
            "attachments": int(preview.get("attachments") or 0),
            "message": preview.get("message") or "",
            "candidates": preview.get("candidates") or [],
        }
        if item["ready"]:
            counts["ready"] += 1
            counts["attachments"] += item["attachments"]
            counts["tags"] += len(item["tags"])
            unique_tags.update(item["tags"])
        else:
            counts["blocked"] += 1
            if status in counts:
                counts[status] += 1
        items.append(item)

    status = "ready" if counts["ready"] and not counts["blocked"] else ("blocked" if counts["blocked"] else "empty")
    message = (
        f"Batch preview checked {counts['checked']} favorites: {counts['ready']} ready, {counts['blocked']} need review."
    )
    with LIBRARY_LOCK:
        library = load_library()
        add_zotero_audit_event(
            library,
            "batch-preview",
            status=status,
            message=message,
            details={**counts, "uniqueTags": sorted(unique_tags)},
        )
        save_library(library)

    return {
        "ok": True,
        **counts,
        "eligible": counts["ready"],
        "uniqueTags": sorted(unique_tags),
        "items": items,
        "policy": {
            "tagPrefix": "paperhunter",
            "noteMode": "upsert-managed-note-only",
            "attachmentMode": "link-translated-markdown-only",
            "preserveUserContent": True,
        },
        "capabilities": ZOTERO_BRIDGE_CAPABILITIES,
        "message": message,
        "library": compact_library(load_library()),
    }


def sync_paper_to_zotero(payload: dict) -> dict:
    key, paper = resolve_library_paper(payload)
    linked_before_sync = False
    if not paper_has_syncable_zotero_key(paper):
        link_result = link_library_paper_to_zotero(key, paper)
        if link_result.get("ambiguous") or link_result.get("conflict"):
            raise RuntimeError(link_result.get("message") or "Confirm the canonical Zotero item before syncing.")
        linked_before_sync = bool(link_result.get("linked"))
        paper = link_result.get("paper") if isinstance(link_result.get("paper"), dict) else paper
    include_fulltext = bool(payload.get("includeFulltext", True))
    body = zotero_sync_payload(paper, include_fulltext=include_fulltext)
    try:
        response = requests.post(
            ZOTERO_BRIDGE_SYNC_URL,
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=(1, ZOTERO_BRIDGE_TIMEOUT_SECONDS),
        )
    except requests.RequestException as exc:
        update_zotero_sync_state(
            key,
            "failed",
            item_key=body["itemKey"],
            tags=body["tags"],
            attachments=len(body["attachments"]),
            error="无法连接 PaperHunter Zotero Bridge。",
        )
        raise RuntimeError("无法连接 PaperHunter Zotero Bridge。请在 Zotero 中安装并启用 Bridge 插件后重试。") from exc
    if response.status_code not in {200, 201}:
        detail = compact_text(response.text, 240)
        update_zotero_sync_state(key, "failed", item_key=body["itemKey"], tags=body["tags"], attachments=len(body["attachments"]), error=detail)
        raise RuntimeError(f"同步到 Zotero 失败（HTTP {response.status_code}）：{detail}")
    try:
        data = response.json()
    except ValueError:
        data = {}
    note_id = data.get("noteID") if isinstance(data.get("noteID"), int) else None
    update_zotero_sync_state(
        key,
        "synced",
        item_key=body["itemKey"],
        tags=body["tags"],
        attachments=len(body["attachments"]),
        note_id=note_id,
    )
    return {
        "ok": True,
        "itemKey": body["itemKey"],
        "tags": body["tags"],
        "attachments": len(body["attachments"]),
        "linked": linked_before_sync,
        "library": compact_library(load_library()),
        "zotero": data,
    }


def sync_favorites_to_zotero(payload: dict) -> dict:
    include_fulltext = bool(payload.get("includeFulltext", True))
    library = load_library()
    favorites = [
        item.get("paper")
        for item in (library.get("favorites") or {}).values()
        if isinstance(item, dict) and isinstance(item.get("paper"), dict)
    ]
    link_result = link_papers_to_zotero(favorites)
    library = load_library()
    candidates = [
        item.get("paper")
        for item in (library.get("favorites") or {}).values()
        if (
            isinstance(item, dict)
            and isinstance(item.get("paper"), dict)
            and paper_has_syncable_zotero_key(item["paper"])
            and not (
                isinstance(item["paper"].get("zoteroLink"), dict)
                and item["paper"].get("zoteroLink", {}).get("status") in ZOTERO_BLOCKED_LINK_STATUSES
            )
        )
    ]
    synced = 0
    errors = {}
    for paper in candidates:
        key = str(paper.get("paperKey") or paper_key(paper))
        try:
            sync_paper_to_zotero({"paper": paper, "paperKey": key, "includeFulltext": include_fulltext})
            synced += 1
        except Exception as exc:
            errors[key] = compact_text(str(exc), 240)
    with LIBRARY_LOCK:
        library = load_library()
        add_zotero_audit_event(
            library,
            "batch-sync",
            status="completed" if not errors else "partial",
            message=f"Batch sync completed: {synced}/{len(candidates)} eligible favorites synced.",
            details={
                "checked": len(favorites),
                "eligible": len(candidates),
                "synced": synced,
                "failed": len(errors),
                "ambiguous": link_result.get("ambiguous", 0),
                "conflict": link_result.get("conflict", 0),
            },
        )
        save_library(library)
    return {
        "ok": True,
        "checked": len(favorites),
        "eligible": len(candidates),
        "synced": synced,
        "failed": len(errors),
        "ambiguous": link_result.get("ambiguous", 0),
        "conflict": link_result.get("conflict", 0),
        "errors": errors,
        "library": compact_library(load_library()),
    }


def save_papers_to_zotero(payload: dict) -> dict:
    papers = papers_from_export_payload(payload)
    if not papers:
        raise ValueError("没有可保存到 Zotero 的论文。")

    preflight = link_papers_to_zotero(papers)
    result_by_key = {str(item.get("paperKey") or ""): item for item in preflight.get("results") or []}
    papers_to_save = []
    for paper in papers:
        snapshot = paper_snapshot(paper)
        key = str(snapshot.get("paperKey") or paper_key(snapshot))
        result = result_by_key.get(key) or {}
        if result.get("linked") or result.get("alreadyLinked") or result.get("ambiguous") or result.get("conflict"):
            continue
        papers_to_save.append(snapshot)

    saved = 0
    post_link_result = {"linked": 0, "alreadyLinked": 0, "unmatched": 0, "ambiguous": 0, "conflict": 0, "results": []}
    if papers_to_save:
        items = [zotero_item_from_paper(paper) for paper in papers_to_save]
        uri = paper_url(papers_to_save[0]) or "http://127.0.0.1:8000/"
        try:
            response = requests.post(
                ZOTERO_CONNECTOR_SAVE_ITEMS_URL,
                headers={"Content-Type": "application/json"},
                json={"items": items, "uri": uri},
                timeout=(1, ZOTERO_CONNECTOR_TIMEOUT_SECONDS),
            )
        except requests.RequestException as exc:
            raise RuntimeError("无法连接本机 Zotero。请先打开 Zotero 桌面端，或改用 RIS 导入。") from exc
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"Zotero 保存失败（HTTP {response.status_code}）。请确认 Zotero Connector 可用，或改用 RIS 导入。")
        saved = len(items)
        post_link_result = link_papers_to_zotero(papers_to_save, attempts=4)

    link_result = {
        "linked": int(preflight.get("linked") or 0) + int(post_link_result.get("linked") or 0),
        "alreadyLinked": int(preflight.get("alreadyLinked") or 0) + int(post_link_result.get("alreadyLinked") or 0),
        "unmatched": int(post_link_result.get("unmatched") or 0),
        "ambiguous": int(preflight.get("ambiguous") or 0) + int(post_link_result.get("ambiguous") or 0),
        "conflict": int(preflight.get("conflict") or 0) + int(post_link_result.get("conflict") or 0),
        "results": [*(preflight.get("results") or []), *(post_link_result.get("results") or [])],
        "library": compact_library(load_library()),
    }
    return {
        "ok": True,
        "saved": saved,
        "linked": link_result["linked"],
        "alreadyLinked": link_result["alreadyLinked"],
        "unmatched": link_result["unmatched"],
        "ambiguous": link_result["ambiguous"],
        "conflict": link_result["conflict"],
        "results": link_result["results"],
        "library": link_result["library"],
    }


def link_zotero_items(payload: dict) -> dict:
    key = str(payload.get("paperKey") or "").strip()
    if key:
        try:
            _, paper = resolve_library_paper(payload)
        except ValueError:
            paper = {}
        if paper:
            result = link_papers_to_zotero([paper])
            return {"ok": True, **result}

    papers = papers_from_export_payload(payload)
    if not papers:
        paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
        if paper:
            papers = [paper_snapshot(paper)]
    if not papers:
        raise ValueError("没有可关联的论文。")
    result = link_papers_to_zotero(papers)
    return {"ok": True, **result}


def confirm_zotero_link(payload: dict) -> dict:
    key, paper = resolve_library_paper(payload)
    item_key = clean_zotero_item_key(payload.get("itemKey"))
    if not item_key:
        raise ValueError("Missing Zotero itemKey to confirm.")

    candidates = read_zotero_candidates()
    match = None
    for candidate in candidates:
        if zotero_meta_item_key(candidate.get("zotero")) == item_key:
            match = candidate
            break
    if not match:
        raise ValueError("The selected Zotero item was not found. Refresh Zotero status and try again.")

    score = paper_match_score(paper, match) or 100
    snapshot = merge_zotero_metadata(paper, match)
    link = zotero_link_for_match(match, score, source="manual-confirm", status="confirmed")
    link["confirmedAt"] = now_iso()
    snapshot["zoteroLink"] = link
    snapshot["paperKey"] = key
    with LIBRARY_LOCK:
        library = load_library()
        update_library_paper_snapshot(library, key, snapshot)
        add_zotero_audit_event(
            library,
            "confirm-link",
            paper_key=key,
            paper=snapshot,
            item_key=item_key,
            status="confirmed",
            message="Confirmed canonical Zotero itemKey for PaperHunter linking.",
            details={"score": score, "source": "manual-confirm"},
        )
        save_library(library)
    return {
        "ok": True,
        "paperKey": key,
        "itemKey": item_key,
        "paper": snapshot,
        "library": compact_library(load_library()),
    }


def export_markdown(papers: list[dict]) -> str:
    lines = ["# PaperHunter 阅读清单", ""]
    for index, paper in enumerate(papers, start=1):
        title = clean_html(str(paper.get("title") or "Untitled"))
        url = paper_url(paper)
        heading = f"{index}. [{title}]({url})" if url else f"{index}. {title}"
        lines.append(heading)
        meta = " · ".join(
            value
            for value in (
                clean_html(str(paper.get("authors") or "")),
                paper_year_text(paper),
                clean_html(str(paper.get("venue") or paper.get("sourceLabel") or "")),
            )
            if value
        )
        if meta:
            lines.append(f"   - {meta}")
        pdf_url = str(paper.get("pdfUrl") or "")
        if pdf_url:
            lines.append(f"   - PDF: {pdf_url}")
        full_abstract = clean_html(str(paper.get("fullAbstract") or ""))
        abstract = full_abstract or clean_html(str(paper.get("abstract") or ""))
        if abstract:
            suffix = " (可能已截断)" if looks_truncated_text(abstract) or not full_abstract else ""
            lines.append(f"   - 摘要: {abstract}{suffix}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def export_bilingual_markdown(papers: list[dict]) -> str:
    lines = ["# PaperHunter 中英文摘要阅读清单", ""]
    for index, paper in enumerate(papers, start=1):
        title = clean_html(str(paper.get("title") or "Untitled"))
        url = paper_url(paper)
        heading = f"## {index}. [{title}]({url})" if url else f"## {index}. {title}"
        lines.append(heading)
        lines.append("")
        meta = " · ".join(
            value
            for value in (
                clean_html(str(paper.get("authors") or "")),
                paper_year_text(paper),
                clean_html(str(paper.get("venue") or paper.get("sourceLabel") or "")),
            )
            if value
        )
        if meta:
            lines.append(f"- 元数据：{meta}")
        pdf_url = str(paper.get("pdfUrl") or "")
        if pdf_url:
            lines.append(f"- PDF: {pdf_url}")
        lines.append(f"- BibTeX Key: `{bibtex_key(paper)}`")
        lines.append("")

        english = clean_html(str(paper.get("fullAbstract") or paper.get("abstract") or ""))
        if english:
            english_warning = "（可能已截断）" if looks_truncated_text(english) else ""
            lines.append(f"### English Abstract{english_warning}")
            lines.append("")
            lines.append(english)
            lines.append("")

        translation = normalize_translations(paper.get("translations"), paper).get("zh")
        if translation:
            translation_text = str(translation.get("text") or "")
            notices = []
            if translation.get("stale"):
                notices.append("可能已过期")
            if looks_truncated_text(english) or looks_truncated_text(translation_text):
                notices.append("可能已截断")
            notice = f"（{'，'.join(notices)}）" if notices else ""
            lines.append(f"### 中文摘要{notice}")
            lines.append("")
            lines.append(translation_text)
            lines.append("")
        else:
            lines.append("### 中文摘要")
            lines.append("")
            lines.append("未翻译。")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def export_papers(payload: dict) -> dict:
    export_format = str(payload.get("format", "bibtex")).lower()
    papers = papers_from_export_payload(payload)
    if not papers:
        raise ValueError("没有可导出的论文。")

    if export_format == "markdown":
        content = export_markdown(papers)
        filename = "paperhunter-reading-list.md"
        mime_type = "text/markdown; charset=utf-8"
    elif export_format == "bilingual_markdown":
        content = export_bilingual_markdown(papers)
        filename = "paperhunter-bilingual-reading-list.md"
        mime_type = "text/markdown; charset=utf-8"
    elif export_format == "bibtex":
        content = export_bibtex(papers)
        filename = "paperhunter-library.bib"
        mime_type = "application/x-bibtex; charset=utf-8"
    elif export_format == "ris":
        content = export_ris(papers)
        filename = "paperhunter-library.ris"
        mime_type = "application/x-research-info-systems; charset=utf-8"
    else:
        raise ValueError("不支持的导出格式。")

    return {
        "ok": True,
        "format": export_format,
        "filename": filename,
        "mimeType": mime_type,
        "content": content,
        "count": len(papers),
    }


def search_arxiv_source(query: str, categories: list[str], max_results: int, sort_by: str) -> list[dict]:
    search_query = build_arxiv_query(query, [str(category) for category in categories])
    if not search_query:
        return []

    criterion = (
        arxiv.SortCriterion.Relevance
        if sort_by == "relevance"
        else arxiv.SortCriterion.SubmittedDate
    )

    search = arxiv.Search(
        query=search_query,
        max_results=max_results,
        sort_by=criterion,
        sort_order=arxiv.SortOrder.Descending,
    )
    client = arxiv.Client(page_size=min(max_results, MAX_RESULTS_LIMIT), delay_seconds=1.0, num_retries=1)

    results = []
    for paper in client.results(search):
        authors = ", ".join(author.name for author in paper.authors[:4])
        if len(paper.authors) > 4:
            authors = f"{authors}, et al."

        results.append(
            make_paper(
                source="arxiv",
                title=paper.title,
                authors=authors,
                published=paper.published.strftime("%Y-%m-%d"),
                year=paper.published.year,
                pdf_url=paper.pdf_url,
                page_url=paper.entry_id,
                paper_id=paper.get_short_id(),
                category=paper.primary_category,
                abstract=paper.summary,
            )
        )
    return results


def semantic_author_names(paper: dict) -> str:
    authors = paper.get("authors") or []
    names = [str(author.get("name", "")).strip() for author in authors[:4] if author.get("name")]
    if len(authors) > 4:
        names.append("et al.")
    return ", ".join(names)


def semantic_search_request(query: str, limit: int) -> requests.Response:
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,venue,url,publicationDate,openAccessPdf,externalIds",
    }
    response = requests.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params=params,
        headers=REQUEST_HEADERS,
        timeout=request_timeout(),
    )
    if response.status_code == 429:
        raise RuntimeError("Semantic Scholar 当前限流，稍后重试或取消该来源。")
    response.raise_for_status()
    return response


def search_semantic_source(query: str, max_results: int) -> list[dict]:
    response = semantic_search_request(query, min(max_results, MAX_RESULTS_LIMIT))

    results = []
    for paper in response.json().get("data", []):
        title = paper.get("title") or "Untitled"
        open_pdf = paper.get("openAccessPdf") or {}
        external_ids = paper.get("externalIds") or {}
        paper_id = (
            external_ids.get("ArXiv")
            or external_ids.get("DOI")
            or external_ids.get("CorpusId")
            or paper.get("paperId")
            or normalize_key(title)
        )
        doi = str(external_ids.get("DOI") or "")
        results.append(
            make_paper(
                source="semantic",
                title=title,
                authors=semantic_author_names(paper),
                published=paper.get("publicationDate") or str(paper.get("year") or ""),
                year=paper.get("year") or "",
                venue=paper.get("venue") or "Semantic Scholar",
                pdf_url=open_pdf.get("url") or "",
                page_url=paper.get("url") or "",
                paper_id=str(paper_id),
                doi=doi,
                abstract=paper.get("abstract") or "",
            )
        )
    return results


def acl_cache_is_fresh() -> bool:
    if not ACL_BIB_CACHE.exists() or ACL_BIB_CACHE.stat().st_size == 0:
        return False
    return time.time() - ACL_BIB_CACHE.stat().st_mtime < ACL_CACHE_MAX_AGE_SECONDS


def ensure_acl_bib_cache() -> None:
    if acl_cache_is_fresh():
        return
    response = requests.get(ACL_BIB_URL, headers=REQUEST_HEADERS, stream=True, timeout=request_timeout(12))
    response.raise_for_status()
    tmp_path = ACL_BIB_CACHE.with_suffix(".tmp")
    with tmp_path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                file.write(chunk)
    tmp_path.replace(ACL_BIB_CACHE)


def iter_bib_entries(text: str) -> list[tuple[str, str]]:
    entries = []
    current = []
    depth = 0
    entry_id = ""
    for line in text.splitlines():
        if line.startswith("@") and not current:
            id_match = re.match(r"@\w+\{([^,]+),", line)
            entry_id = id_match.group(1).strip() if id_match else ""
            current = [line]
            depth = line.count("{") - line.count("}")
            if depth <= 0:
                entries.append((entry_id, "\n".join(current)))
                current = []
            continue

        if current:
            current.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                entries.append((entry_id, "\n".join(current)))
                current = []
                entry_id = ""
    return entries


def extract_bib_field(entry: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}\s*=\s*([{{\"])", entry, re.IGNORECASE)
    if not match:
        return ""

    delimiter = match.group(1)
    index = match.end()
    if delimiter == '"':
        end = entry.find('"', index)
        return clean_bib_value(entry[index:end]) if end != -1 else ""

    depth = 1
    end = index
    while end < len(entry):
        char = entry[end]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return clean_bib_value(entry[index:end])
        end += 1
    return ""


def clean_bib_value(value: str) -> str:
    value = re.sub(r"\\[a-zA-Z]+", "", value)
    value = value.replace("{", "").replace("}", "")
    value = value.replace("\\&", "&").replace("\\_", "_")
    value = value.replace("\\", "")
    return re.sub(r"\s+", " ", value).strip()


def format_acl_authors(value: str) -> str:
    authors = [author.strip() for author in value.split(" and ") if author.strip()]
    visible = authors[:4]
    if len(authors) > 4:
        visible.append("et al.")
    return ", ".join(visible)


def load_acl_entries() -> list[dict]:
    global ACL_ENTRY_CACHE
    if ACL_ENTRY_CACHE is not None:
        return ACL_ENTRY_CACHE

    ensure_acl_bib_cache()
    with gzip.open(ACL_BIB_CACHE, "rt", encoding="utf-8", errors="replace") as file:
        text = file.read()

    entries = []
    for paper_id, entry in iter_bib_entries(text):
        title = extract_bib_field(entry, "title")
        if not title:
            continue
        entries.append(
            {
                "paper_id": paper_id,
                "title": title,
                "authors": format_acl_authors(extract_bib_field(entry, "author")),
                "year": extract_bib_field(entry, "year"),
                "venue": extract_bib_field(entry, "booktitle") or extract_bib_field(entry, "journal") or "ACL Anthology",
                "url": extract_bib_field(entry, "url") or f"https://aclanthology.org/{paper_id}/",
                "abstract": extract_bib_field(entry, "abstract"),
            }
        )

    entries.sort(key=lambda paper: str(paper.get("year", "")), reverse=True)
    ACL_ENTRY_CACHE = entries
    return entries


def search_acl_source(query: str, max_results: int) -> list[dict]:
    results = []
    for paper in load_acl_entries():
        searchable = f"{paper.get('title', '')} {paper.get('authors', '')} {paper.get('venue', '')} {paper.get('abstract', '')}"
        if not query_matches(searchable, query):
            continue

        page_url = paper.get("url") or f"https://aclanthology.org/{paper['paper_id']}/"
        pdf_url = page_url.rstrip("/") + ".pdf"
        results.append(
            make_paper(
                source="acl",
                title=paper.get("title") or "Untitled",
                authors=paper.get("authors") or "",
                published=str(paper.get("year") or ""),
                year=paper.get("year") or "",
                venue=paper.get("venue") or "ACL Anthology",
                pdf_url=pdf_url,
                page_url=page_url,
                paper_id=paper.get("paper_id") or normalize_key(paper.get("title", "")),
                abstract=paper.get("abstract") or "",
            )
        )
        if len(results) >= max_results:
            break
    return results


def parse_cvf_page(html: str, venue: str, base_url: str, query: str, max_results: int) -> list[dict]:
    pattern = re.compile(
        r'<dt class="ptitle">\s*<br>\s*<a href="(?P<page>[^"]+)">(?P<title>.*?)</a></dt>\s*'
        r"<dd>(?P<authors>.*?)</dd>\s*<dd>(?P<links>.*?)</dd>",
        re.IGNORECASE | re.DOTALL,
    )
    results = []
    for match in pattern.finditer(html):
        title = clean_html(match.group("title"))
        authors = ", ".join(
            unescape(author)
            for author in re.findall(r'name="query_author" value="([^"]+)"', match.group("authors"))
        )
        searchable = f"{title} {authors}"
        if not query_matches(searchable, query):
            continue

        links = match.group("links")
        pdf_match = re.search(r'href="([^"]+_paper\.pdf)"', links, re.IGNORECASE)
        page_url = urljoin(base_url, match.group("page"))
        pdf_url = urljoin(base_url, pdf_match.group(1)) if pdf_match else ""
        paper_id = Path(urlparse(pdf_url or page_url).path).stem.replace("_paper", "")
        year_match = re.search(r"\d{4}", venue)
        results.append(
            make_paper(
                source="cvf",
                title=title,
                authors=authors,
                year=year_match.group(0) if year_match else "",
                venue=venue,
                pdf_url=pdf_url,
                page_url=page_url,
                paper_id=paper_id,
                abstract="CVF Open Access 论文。摘要可在论文页面查看。",
            )
        )
        if len(results) >= max_results:
            break
    return results


def search_cvf_source(query: str, max_results: int) -> list[dict]:
    results = []
    for venue, url in CVF_ENDPOINTS:
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=request_timeout())
            if response.status_code != 200:
                continue
            results.extend(parse_cvf_page(response.text, venue, url, query, max_results - len(results)))
        except requests.RequestException:
            continue
        if len(results) >= max_results:
            break
    return results


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def first_child_text(element: ET.Element, names: set[str]) -> str:
    for child in element.iter():
        if child is element:
            continue
        if xml_local_name(child.tag) in names and child.text:
            return clean_html(child.text)
    return ""


def direct_child_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if xml_local_name(child.tag) in names and child.text:
            return clean_html(child.text)
    return ""


def parse_feed_date(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.strftime("%Y-%m-%d"), str(parsed.year)
    except (TypeError, ValueError, IndexError):
        match = re.search(r"\d{4}", value)
        return value[:10], match.group(0) if match else ""


def extract_feed_links(entry: ET.Element) -> tuple[str, str]:
    page_url = ""
    pdf_url = ""
    for child in entry.iter():
        if xml_local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href") or (child.text or "")
        href = href.strip()
        if not href:
            continue
        link_type = child.attrib.get("type", "").lower()
        rel = child.attrib.get("rel", "").lower()
        title = child.attrib.get("title", "").lower()
        if "pdf" in link_type or "pdf" in rel or "pdf" in title or href.lower().endswith(".pdf"):
            pdf_url = href
        elif not page_url:
            page_url = href

    text = ET.tostring(entry, encoding="unicode", method="xml")
    if not pdf_url:
        match = re.search(r"https?://[^\"'<>\s]+\.pdf(?:\?[^\"'<>\s]+)?", text, flags=re.IGNORECASE)
        if match:
            pdf_url = unescape(match.group(0))
    if not page_url:
        guid = direct_child_text(entry, {"guid", "id"})
        if guid.startswith("http"):
            page_url = guid

    return page_url, pdf_url


def chinarxiv_pdf_from_page(page_url: str) -> str:
    if not page_url:
        return ""
    parsed = urlparse(page_url)
    if normalized_host(page_url) not in {"chinarxiv.org", "chinaxiv.org"}:
        return ""
    path = parsed.path
    item_match = re.search(r"/items/([^/?#]+)", path)
    if item_match:
        return f"https://f004.backblazeb2.com/file/chinaxiv/english_pdfs/{item_match.group(1)}.pdf"
    if "/abs/" in path:
        return f"{parsed.scheme}://{parsed.netloc}{path.replace('/abs/', '/pdf/', 1)}"
    if "/html/" in path:
        return f"{parsed.scheme}://{parsed.netloc}{path.replace('/html/', '/pdf/', 1)}"
    return ""


def chinarxiv_authors(entry: ET.Element) -> str:
    names = []
    for child in entry.iter():
        if xml_local_name(child.tag) == "author":
            name = first_child_text(child, {"name"}) or clean_html(child.text or "")
            if name:
                names.append(name)
    if not names:
        creator = first_child_text(entry, {"creator", "author"})
        names = [creator] if creator else []
    visible = names[:4]
    if len(names) > 4:
        visible.append("et al.")
    return ", ".join(visible)


def chinarxiv_page_pdf_url(page_url: str) -> str:
    if not page_url:
        return ""
    try:
        response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=request_timeout(4))
        response.raise_for_status()
    except requests.RequestException:
        return ""
    candidates = re.findall(r'href="([^"]*(?:pdf|download\.htm\?uuid=)[^"]*)"', response.text, flags=re.IGNORECASE)
    candidates += re.findall(r"https?://[^\"'<>\\s]+\.pdf(?:\?[^\"'<>\\s]+)?", response.text, flags=re.IGNORECASE)
    for candidate in candidates:
        url = urljoin(page_url, unescape(candidate).replace("&amp;", "&"))
        if is_trusted_open_pdf_url(url):
            return url
    return ""


def extract_chinarxiv_page_abstract(html: str) -> str:
    patterns = [
        r'<div[^>]+class=["\'][^"\']*\babstract-blockquote\b[^"\']*["\'][^>]*>\s*<p[^>]*>(.*?)</p>',
        r"<h2[^>]*>\s*Abstract\s*</h2>\s*<div[^>]*>(.*?)</div>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        abstract = clean_html(match.group(1))
        if abstract:
            return abstract
    return ""


def chinarxiv_page_abstract(page_url: str) -> str:
    if not page_url or normalized_host(page_url) not in {"chinarxiv.org", "chinaxiv.org"}:
        return ""
    try:
        response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=request_timeout(4))
        response.raise_for_status()
    except requests.RequestException:
        return ""
    return extract_chinarxiv_page_abstract(response.text)


def parse_chinarxiv_feed(text: str, max_results: int, query: str) -> list[dict]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    entries = [
        element
        for element in root.iter()
        if xml_local_name(element.tag) in {"item", "entry"}
    ]
    results = []
    for entry in entries:
        title = direct_child_text(entry, {"title"}) or first_child_text(entry, {"title"})
        if not title:
            continue
        abstract = direct_child_text(entry, {"summary", "description", "abstract"})
        authors = chinarxiv_authors(entry)
        if not query_matches(f"{title} {abstract} {authors}", query):
            continue
        page_url, pdf_url = extract_feed_links(entry)
        page_url = page_url or direct_child_text(entry, {"link"})
        if page_url and (not abstract or looks_truncated_text(abstract)):
            abstract = preferred_abstract_text(abstract, chinarxiv_page_abstract(page_url))
        pdf_url = pdf_url or chinarxiv_pdf_from_page(page_url)
        if pdf_url and not is_trusted_open_pdf_url(pdf_url):
            pdf_url = ""
        published, year = parse_feed_date(
            direct_child_text(entry, {"published", "updated", "pubdate", "date"})
        )
        category = ""
        for child in entry.iter():
            if xml_local_name(child.tag) == "category":
                category = child.attrib.get("term") or child.text or ""
                category = clean_html(category)
                break
        paper_id = normalize_key(Path(urlparse(page_url or pdf_url).path).name or title).replace(" ", "-")
        results.append(
            make_paper(
                source="chinarxiv",
                title=title,
                authors=authors,
                published=published,
                year=year,
                venue="ChinaRxiv / ChinaXiv",
                category=category or "ChinaRxiv / ChinaXiv",
                pdf_url=pdf_url,
                page_url=page_url,
                paper_id=paper_id,
                abstract=abstract,
            )
        )
        if len(results) >= max_results:
            break
    return results


def search_chinarxiv_source(query: str, max_results: int) -> list[dict]:
    last_error = None
    for endpoint in CHINARXIV_FEEDS:
        try:
            response = requests.get(
                endpoint,
                params={"q": query, "has_pdf": "1"},
                headers=REQUEST_HEADERS,
                timeout=request_timeout(),
            )
            response.raise_for_status()
            results = parse_chinarxiv_feed(response.text, max_results, query)
            if results:
                return results
        except requests.RequestException as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def sciopen_pdf_url(doi: str) -> str:
    if not doi:
        return ""
    return f"https://www.sciopen.com/local/article_pdf/{doi}.pdf"


def sciopen_page_url(doi: str) -> str:
    return f"https://www.sciopen.com/article/{doi}" if doi else "https://www.sciopen.com/search/to_search_page"


def sciopen_payload(query: str, max_results: int) -> dict:
    return {
        "keyword": query,
        "startTime": "",
        "endTime": "",
        "keywordDTO": [],
        "pageNo": 1,
        "pageSize": max(1, min(max_results, MAX_RESULTS_LIMIT)),
        "orderBy": 0,
        "journalId": "",
    }


def search_sciopen_source(query: str, max_results: int) -> list[dict]:
    response = requests.post(
        "https://www.sciopen.com/search/search",
        json=sciopen_payload(query, max_results),
        headers={
            **REQUEST_HEADERS,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PaperHunter/1.0",
            "Referer": "https://www.sciopen.com/search/to_search_page",
            "Content-Type": "application/json",
        },
        timeout=request_timeout(),
    )
    response.raise_for_status()
    data = response.json()
    page = (data.get("object") or {}).get("page") or {}

    results = []
    for item in page.get("items") or []:
        doi = str(item.get("doi") or item.get("showDoi") or "").strip()
        title = clean_html(item.get("title") or "")
        if not title:
            continue
        abstract = clean_html(item.get("abstracted") or "")
        authors = clean_html(item.get("author") or "")
        if not query_matches(f"{title} {abstract} {authors}", query):
            continue

        pdf_url = sciopen_pdf_url(doi) if doi and int(item.get("isOa") or 0) > 0 else ""
        published = str(item.get("pubTime") or item.get("pubTimeStr") or "")[:10]
        year_match = re.search(r"\d{4}", published or str(item.get("journalAndVol") or ""))
        venue = clean_html(item.get("journalName") or "SciOpen")
        results.append(
            make_paper(
                source="sciopen",
                title=title,
                authors=authors,
                published=published,
                year=year_match.group(0) if year_match else "",
                venue=venue,
                category=venue,
                pdf_url=pdf_url if is_trusted_open_pdf_url(pdf_url) else "",
                page_url=sciopen_page_url(doi),
                paper_id=doi or str(item.get("id") or normalize_key(title)),
                doi=doi,
                abstract=abstract,
            )
        )
        if len(results) >= max_results:
            break
    return results


def nso_document_url(document: dict) -> str:
    raw_url = str(document.get("url") or "").strip()
    if not raw_url:
        return ""
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    return urljoin(str(document.get("site_url") or NSO_BASE_URL), raw_url)


def nso_document_by_type(item: dict, document_type: str) -> str:
    documents = item.get("documents")
    if isinstance(documents, str):
        return documents if document_type != "pdf" else ""
    if not isinstance(documents, list):
        return ""
    for document in documents:
        if not isinstance(document, dict):
            continue
        if document.get("type") == document_type:
            return nso_document_url(document)
    return ""


def nso_authors(item: dict) -> str:
    authors = item.get("display_authors") or []
    if not isinstance(authors, list):
        return str(authors)
    visible = [str(author) for author in authors[:4] if str(author).strip()]
    if len(authors) > 4:
        visible.append("et al.")
    return ", ".join(visible)


def nso_abstract(item: dict, highlights: dict) -> str:
    highlight = highlights.get(str(item.get("id") or ""), {}) if isinstance(highlights, dict) else {}
    snippets = highlight.get("text_gen") if isinstance(highlight, dict) else []
    if isinstance(snippets, list) and snippets:
        return clean_html(" ".join(str(snippet) for snippet in snippets[:3]))
    return clean_html(item.get("heading") or item.get("idline") or "")


def search_nso_source(query: str, max_results: int) -> list[dict]:
    response = requests.get(
        NSO_SOLR_URL,
        params={
            "option": "com_solr",
            "task": "json",
            "q": query,
            "rows": max(1, min(max_results, MAX_RESULTS_LIMIT)),
            "sort": "score desc",
        },
        headers=REQUEST_HEADERS,
        timeout=request_timeout(),
    )
    response.raise_for_status()
    data = response.json()
    docs = (data.get("response") or {}).get("docs") or []
    highlights = data.get("highlighting") or {}

    results = []
    for item in docs:
        if not isinstance(item, dict):
            continue
        title = clean_html(item.get("display_title") or "")
        if not title:
            continue
        authors = nso_authors(item)
        abstract = nso_abstract(item, highlights)
        if not query_matches(f"{title} {abstract} {authors}", query):
            continue

        pdf_url = nso_document_by_type(item, "pdf")
        if pdf_url and not is_trusted_open_pdf_url(pdf_url):
            pdf_url = ""
        page_url = (
            nso_document_by_type(item, "full_html_noframe")
            or nso_document_by_type(item, "abs_html")
            or str(item.get("url") or "")
        )
        published = clean_html(item.get("idline") or "")
        year_match = re.search(r"\b(19|20)\d{2}\b", published)
        venue = clean_html(item.get("journal_title") or "National Science Open")
        heading = clean_html(item.get("heading") or "")
        results.append(
            make_paper(
                source="nso",
                title=title,
                authors=authors,
                published=published,
                year=year_match.group(0) if year_match else "",
                venue=venue,
                category=heading or venue,
                pdf_url=pdf_url,
                page_url=page_url,
                paper_id=str(item.get("doi") or item.get("dkey") or item.get("id") or normalize_key(title)),
                doi=str(item.get("doi") or ""),
                abstract=abstract,
            )
        )
        if len(results) >= max_results:
            break
    return results


def note_value(content: dict, key: str, default: object = "") -> object:
    value = content.get(key, default)
    if isinstance(value, dict) and "value" in value:
        return value.get("value", default)
    return value


def millis_to_date(value: object) -> str:
    try:
        timestamp = int(value) / 1000
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


def search_openreview_source(search_query: str, max_results: int, base_query: str = "") -> list[dict]:
    response = requests.get(
        "https://api2.openreview.net/notes/search",
        params={"term": search_query, "limit": min(max_results * 4, MAX_RESULTS_LIMIT)},
        headers=REQUEST_HEADERS,
        timeout=request_timeout(),
    )
    response.raise_for_status()

    results = []
    for note in response.json().get("notes", []):
        content = note.get("forumContent") or note.get("content") or {}
        title = str(note_value(content, "title", "")).strip()
        if not title:
            continue

        abstract = str(note_value(content, "abstract", "") or note_value(content, "summary", "") or "")
        venue = str(note_value(content, "venue", "") or note.get("domain") or "OpenReview")
        searchable = f"{title} {abstract} {venue}"
        if base_query and not query_matches(searchable, base_query):
            continue

        authors_value = note_value(content, "authors", [])
        authors = ", ".join(str(author) for author in authors_value[:4]) if isinstance(authors_value, list) else str(authors_value)
        if isinstance(authors_value, list) and len(authors_value) > 4:
            authors = f"{authors}, et al."

        pdf_path = str(note_value(content, "pdf", "") or "")
        page_url = f"https://openreview.net/forum?id={note.get('forum') or note.get('id')}"
        pdf_url = normalize_openreview_pdf_url(pdf_path)
        published = millis_to_date(note.get("pdate") or note.get("cdate"))
        year = published[:4] if published else ""
        results.append(
            make_paper(
                source="openreview",
                title=title,
                authors=authors,
                published=published,
                year=year,
                venue=venue,
                pdf_url=pdf_url,
                page_url=page_url,
                paper_id=str(note.get("forum") or note.get("id") or normalize_key(title)),
                abstract=abstract,
            )
        )
        if len(results) >= max_results:
            break
    return results


def get_selected_sources(payload: dict) -> list[str]:
    sources = payload.get("sources") or ["arxiv"]
    if not isinstance(sources, list):
        sources = ["arxiv"]
    selected = [str(source) for source in sources if str(source) in SOURCE_LABELS]
    return selected or ["arxiv"]


def dedupe_results(results: list[dict], limit: int) -> list[dict]:
    seen = set()
    deduped = []
    for paper in results:
        key = normalize_key(paper.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(paper)
        if len(deduped) >= limit:
            break
    return deduped


def expanded_query(query: str, field_preset: str, intent: str) -> str:
    terms = " ".join(
        value
        for value in (FIELD_QUERY_TERMS.get(field_preset, ""), INTENT_QUERY_TERMS.get(intent, ""))
        if value
    )
    if not terms:
        return query
    return f"{query} {terms}"


def arxiv_query_with_intent(query: str, intent: str) -> str:
    terms = [term for term in INTENT_QUERY_TERMS.get(intent, "").split() if term]
    if not terms:
        return query
    return f"({query}) AND ({' OR '.join(terms)})"


def paper_year(paper: dict) -> int | None:
    for value in (paper.get("year"), paper.get("published")):
        match = re.search(r"\d{4}", str(value or ""))
        if match:
            return int(match.group(0))
    return None


def text_for_scope(paper: dict, scope: str) -> str:
    if scope == "title":
        return str(paper.get("title", ""))
    if scope == "abstract":
        return str(paper.get("abstract", ""))
    if scope == "author":
        return str(paper.get("authors", ""))
    return " ".join(
        str(paper.get(key, ""))
        for key in ("title", "abstract", "authors", "venue", "category", "sourceLabel")
    )


def paper_matches_field(paper: dict, field_preset: str) -> bool:
    if field_preset in {"", "all", "custom"}:
        return True

    source = str(paper.get("source", ""))
    if field_preset in SOURCE_FIELD_HINTS.get(source, set()):
        return True

    category = str(paper.get("category", "")).lower()
    prefixes = FIELD_CATEGORY_PREFIXES.get(field_preset, ())
    if any(category.startswith(prefix.lower()) for prefix in prefixes):
        return True

    return contains_any_term(text_for_scope(paper, "all"), FIELD_QUERY_TERMS.get(field_preset, ""))


def paper_matches_filters(paper: dict, filters: dict) -> bool:
    year = paper_year(paper)
    year_from = filters.get("year_from")
    year_to = filters.get("year_to")
    if year_from is not None and (year is None or year < year_from):
        return False
    if year_to is not None and (year is None or year > year_to):
        return False

    if filters.get("downloadable_only") and not paper.get("downloadable"):
        return False

    if not paper_matches_field(paper, str(filters.get("field_preset", "all"))):
        return False

    author = filters.get("author", "")
    if author and not contains_text(str(paper.get("authors", "")), author):
        return False

    venue = filters.get("venue", "")
    if venue:
        venue_text = " ".join(str(paper.get(key, "")) for key in ("venue", "category", "sourceLabel"))
        if not contains_text(venue_text, venue):
            return False

    scope = filters.get("match_scope", "all")
    if scope != "all" and not query_matches(text_for_scope(paper, scope), filters.get("query", "")):
        return False

    return True


def sort_results(results: list[dict], sort_by: str) -> list[dict]:
    if sort_by != "recent":
        return results
    return sorted(results, key=lambda paper: paper_year(paper) or 0, reverse=True)


def filtered_results(results: list[dict], filters: dict, sort_by: str, limit: int) -> list[dict]:
    filtered = [paper for paper in results if paper_matches_filters(paper, filters)]
    return dedupe_results(sort_results(filtered, sort_by), limit)


def filtered_results_by_source(results: list[dict], filters: dict, sort_by: str, per_source_limit: int) -> list[dict]:
    filtered = [paper for paper in results if paper_matches_filters(paper, filters)]
    seen = set()
    counts: dict[str, int] = {}
    selected = []
    for paper in sort_results(filtered, sort_by):
        source = str(paper.get("source", ""))
        if counts.get(source, 0) >= per_source_limit:
            continue
        key = normalize_key(paper.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        counts[source] = counts.get(source, 0) + 1
        selected.append(paper)
    return selected


def count_results_by_source(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for paper in results:
        source = str(paper.get("source", ""))
        if not source:
            continue
        counts[source] = counts.get(source, 0) + 1
    return counts


def normalized_year_filter(value: object) -> int | None:
    if value in (None, ""):
        return None
    return clamp_int(value, default=0, minimum=0, maximum=9999)


def search_papers(payload: dict) -> dict:
    query = str(payload.get("query", "")).strip()
    if not query:
        raise ValueError("请输入检索关键词。")

    categories = payload.get("categories") or []
    if not isinstance(categories, list):
        categories = []

    per_source_requested = "perSourceLimit" in payload
    max_results = clamp_int(payload.get("maxResults"), default=15, minimum=1, maximum=MAX_RESULTS_LIMIT)
    sort_by = str(payload.get("sortBy", "recent")).lower()
    sources = get_selected_sources(payload)
    per_source_limit = clamp_int(
        payload.get("perSourceLimit"),
        default=5,
        minimum=1,
        maximum=PER_SOURCE_LIMIT_MAX,
    )
    field_preset = str(payload.get("fieldPreset", "all"))
    intent = str(payload.get("intent", "general"))
    if intent == "latest":
        sort_by = "recent"

    expanded_query_text = expanded_query(query, field_preset, intent)
    filters = {
        "query": query,
        "year_from": normalized_year_filter(payload.get("yearFrom")),
        "year_to": normalized_year_filter(payload.get("yearTo")),
        "downloadable_only": bool(payload.get("downloadableOnly", False)),
        "author": str(payload.get("author", "")).strip(),
        "venue": str(payload.get("venue", "")).strip(),
        "match_scope": str(payload.get("matchScope", "all")),
        "field_preset": field_preset,
    }
    if filters["year_from"] is not None and filters["year_to"] is not None and filters["year_from"] > filters["year_to"]:
        filters["year_from"], filters["year_to"] = filters["year_to"], filters["year_from"]

    candidate_limit = max(5, min(MAX_RESULTS_LIMIT, per_source_limit + 3))
    if not per_source_requested:
        candidate_limit = max(5, min(MAX_RESULTS_LIMIT, max_results + 3))
    searchers = {
        "arxiv": lambda: search_arxiv_source(arxiv_query_with_intent(query, intent), categories, candidate_limit, sort_by),
        "semantic": lambda: search_semantic_source(expanded_query_text, candidate_limit),
        "cvf": lambda: search_cvf_source(query, candidate_limit),
        "acl": lambda: search_acl_source(query, candidate_limit),
        "openreview": lambda: search_openreview_source(expanded_query_text, candidate_limit, query),
        "chinarxiv": lambda: search_chinarxiv_source(query, candidate_limit),
        "sciopen": lambda: search_sciopen_source(query, candidate_limit),
        "nso": lambda: search_nso_source(query, candidate_limit),
    }

    results = []
    errors = {}
    executor = ThreadPoolExecutor(max_workers=min(len(sources), 4))
    future_to_source = {executor.submit(searchers[source]): source for source in sources}
    processed_futures = set()
    try:
        for future in as_completed(future_to_source, timeout=SEARCH_TIMEOUT_SECONDS):
            processed_futures.add(future)
            source = future_to_source[future]
            try:
                results.extend(future.result())
            except Exception as exc:
                errors[source] = format_source_error(source, exc)
    except FuturesTimeoutError:
        for future, source in future_to_source.items():
            if future in processed_futures:
                continue
            if future.done():
                try:
                    results.extend(future.result())
                except Exception as exc:
                    errors[source] = format_source_error(source, exc)
            else:
                errors[source] = f"{SOURCE_LABELS.get(source, source)} 搜索超时，已返回其它来源结果。"
                future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    final_results = (
        filtered_results_by_source(results, filters, sort_by, per_source_limit)
        if per_source_requested
        else filtered_results(results, filters, sort_by, max_results)
    )
    with LIBRARY_LOCK:
        library = load_library()
        final_results, hidden_ignored_count = apply_library_state(final_results, library)
        source_counts = count_results_by_source(final_results)
        add_search_history(library, payload, len(final_results), source_counts)
        save_library(library)
        library_view = compact_library(library)

    return {
        "query": query,
        "expandedQuery": expanded_query_text,
        "fieldPreset": field_preset,
        "intent": intent,
        "sources": sources,
        "perSourceLimit": per_source_limit if per_source_requested else None,
        "filters": filters,
        "results": final_results,
        "sourceCounts": source_counts,
        "hiddenIgnoredCount": hidden_ignored_count,
        "errors": errors,
        "downloadedCount": existing_pdf_count(),
        "library": library_view,
    }


def download_pdf(payload: dict) -> dict:
    pdf_url = str(payload.get("pdfUrl", "")).strip()
    title = str(payload.get("title", "")).strip()
    paper_id = str(payload.get("paperId") or payload.get("arxivId") or "").strip()
    source = str(payload.get("source", "")).strip()

    if not pdf_url or not title or not paper_id:
        raise ValueError("下载参数不完整。")

    filename = sanitize_filename(title, paper_id)
    filepath = DOWNLOAD_DIR / filename
    if filepath.exists() and filepath.stat().st_size > 0:
        record_download(payload, filename)
        return {
            "ok": True,
            "filename": filename,
            "message": "本地已存在，已跳过。",
            "downloadedCount": existing_pdf_count(),
        }

    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    try:
        with requests.get(pdf_url, headers=REQUEST_HEADERS, stream=True, timeout=request_timeout(30)) as response:
            if response.status_code != 200:
                raise RuntimeError(f"下载失败：HTTP {response.status_code}")

            content_type = response.headers.get("Content-Type", "").lower()
            first_chunk = b""
            with tmp_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    if not first_chunk:
                        first_chunk = chunk
                        if not first_chunk.lstrip().startswith(b"%PDF"):
                            if source == "openreview":
                                raise RuntimeError("下载失败：这个 OpenReview 结果指向网页，不是可直接下载的 PDF。请打开来源页面查看。")
                            raise RuntimeError(f"下载失败：返回内容不是 PDF（{content_type or 'unknown'}）。")
                    file.write(chunk)

        tmp_path.replace(filepath)
        if filepath.stat().st_size == 0:
            filepath.unlink(missing_ok=True)
            raise RuntimeError("下载失败：文件为空。")
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    record_download(payload, filename)

    return {
        "ok": True,
        "filename": filename,
        "message": "PDF 已保存。",
        "downloadedCount": existing_pdf_count(),
    }


def backup_manifest() -> dict:
    return {
        "app": "PaperHunter",
        "version": 1,
        "createdAt": now_iso(),
        "librarySchemaVersion": LIBRARY_SCHEMA_VERSION,
        "settingsSchemaVersion": SETTINGS_SCHEMA_VERSION,
        "includes": [
            "data/library.json",
            "data/settings.json",
            "data/fulltext_tasks/",
            "downloaded_papers/",
            "translated_papers/",
        ],
        "apiKeyExported": False,
    }


def add_file_to_zip(zip_file: zipfile.ZipFile, path: Path, arcname: str) -> None:
    if path.exists() and path.is_file():
        zip_file.write(path, arcname)


def add_dir_to_zip(zip_file: zipfile.ZipFile, directory: Path, prefix: str) -> None:
    if not directory.exists():
        return
    for path in directory.rglob("*"):
        if path.is_file():
            arcname = f"{prefix}/{path.relative_to(directory).as_posix()}"
            zip_file.write(path, arcname)


def export_workspace_backup() -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("paperhunter-backup.json", json.dumps(backup_manifest(), ensure_ascii=False, indent=2))
        zip_file.writestr("data/library.json", json.dumps(load_library(), ensure_ascii=False, indent=2))
        zip_file.writestr("data/settings.json", json.dumps(settings_without_api_key(load_settings()), ensure_ascii=False, indent=2))
        add_dir_to_zip(zip_file, FULLTEXT_TASK_DIR, "data/fulltext_tasks")
        add_dir_to_zip(zip_file, DOWNLOAD_DIR, "downloaded_papers")
        add_dir_to_zip(zip_file, TRANSLATED_DIR, "translated_papers")
    filename = f"paperhunter-workspace-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return buffer.getvalue(), filename


def zotero_bridge_source_files() -> dict[str, Path]:
    return {
        "manifest.json": ZOTERO_BRIDGE_MANIFEST_PATH,
        "bootstrap.js": ZOTERO_BRIDGE_BOOTSTRAP_PATH,
    }


def read_zotero_bridge_source() -> tuple[dict, str]:
    files = zotero_bridge_source_files()
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise ValueError("缺少 PaperHunter Zotero Bridge 源码文件，请检查 zotero-bridge 目录。")
    try:
        manifest = json.loads(files["manifest.json"].read_text(encoding="utf-8"))
        bootstrap = files["bootstrap.js"].read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("PaperHunter Zotero Bridge 源码文件无法读取或格式不正确。") from exc
    validate_zotero_bridge_source(manifest, bootstrap)
    return manifest, bootstrap


def zotero_bridge_token() -> str:
    settings = load_settings()
    token = str(settings.get("zoteroBridgeToken") or "").strip()
    if token:
        return token
    settings = normalize_settings(settings)
    save_settings(settings)
    return str(settings.get("zoteroBridgeToken") or "")


def zotero_bridge_packaged_source() -> tuple[dict, str]:
    manifest, bootstrap = read_zotero_bridge_source()
    token = zotero_bridge_token()
    if not token:
        raise ValueError("PaperHunter Zotero Bridge 配对 token 不可用。")
    if ZOTERO_BRIDGE_TOKEN_PLACEHOLDER not in bootstrap:
        raise ValueError("PaperHunter Zotero Bridge 源码缺少配对 token 占位符。")
    return manifest, bootstrap.replace(ZOTERO_BRIDGE_TOKEN_PLACEHOLDER, token)


def build_zotero_bridge_xpi() -> bytes:
    manifest, bootstrap = zotero_bridge_packaged_source()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        zip_file.writestr("bootstrap.js", bootstrap)
    content = buffer.getvalue()
    validate_zotero_bridge_xpi(content)
    return content


def zotero_bridge_xpi_matches_source(content: bytes) -> bool:
    try:
        source_manifest, source_bootstrap = zotero_bridge_packaged_source()
        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            bootstrap = zip_file.read("bootstrap.js").decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile, ValueError, json.JSONDecodeError):
        return False
    return manifest == source_manifest and bootstrap == source_bootstrap


def write_zotero_bridge_xpi() -> bytes:
    content = build_zotero_bridge_xpi()
    ZOTERO_BRIDGE_XPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ZOTERO_BRIDGE_XPI_PATH.with_suffix(".tmp")
    tmp_path.write_bytes(content)
    tmp_path.replace(ZOTERO_BRIDGE_XPI_PATH)
    return content


def read_zotero_bridge_xpi() -> tuple[bytes, str]:
    try:
        content = ZOTERO_BRIDGE_XPI_PATH.read_bytes()
        validate_zotero_bridge_xpi(content)
        if not zotero_bridge_xpi_matches_source(content):
            raise ValueError("PaperHunter Zotero Bridge XPI 与源码不一致。")
    except (OSError, ValueError):
        content = write_zotero_bridge_xpi()
    return content, ZOTERO_BRIDGE_XPI_PATH.name


def zotero_bridge_package_status() -> dict:
    built = False
    status = {
        "available": False,
        "valid": False,
        "path": str(ZOTERO_BRIDGE_XPI_PATH),
        "filename": ZOTERO_BRIDGE_XPI_PATH.name,
        "downloadUrl": ZOTERO_BRIDGE_DOWNLOAD_URL,
        "sourcePath": str(ZOTERO_BRIDGE_DIR),
        "builtFromSource": False,
        "version": "",
        "expectedVersion": ZOTERO_BRIDGE_VERSION,
        "protocolVersion": None,
        "expectedProtocolVersion": ZOTERO_BRIDGE_PROTOCOL_VERSION,
        "size": 0,
        "message": "未找到 PaperHunter Zotero Bridge XPI，请重新构建插件包。",
    }
    try:
        content = ZOTERO_BRIDGE_XPI_PATH.read_bytes()
        validate_zotero_bridge_xpi(content)
        if not zotero_bridge_xpi_matches_source(content):
            raise ValueError("PaperHunter Zotero Bridge XPI 与源码不一致。")
    except (OSError, ValueError):
        try:
            content = write_zotero_bridge_xpi()
            built = True
        except ValueError as exc:
            status["message"] = str(exc)
            return status
    status["available"] = True
    status["size"] = len(content)
    status["builtFromSource"] = built
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            bootstrap = zip_file.read("bootstrap.js").decode("utf-8")
        status["version"] = str(manifest.get("version") or "")
        match = re.search(r"protocolVersion:\s*(\d+)", bootstrap)
        if match:
            status["protocolVersion"] = int(match.group(1))
        validate_zotero_bridge_xpi(content)
    except (KeyError, OSError, zipfile.BadZipFile, ValueError, json.JSONDecodeError):
        status["message"] = "PaperHunter Zotero Bridge XPI 不完整或版本不匹配，请重新构建插件包。"
        return status

    status["valid"] = True
    status["message"] = (
        f"Bridge {ZOTERO_BRIDGE_VERSION} 安装包已从源码构建。"
        if built else f"Bridge {ZOTERO_BRIDGE_VERSION} 安装包可用。"
    )
    return status


def validate_zotero_bridge_source(manifest: dict, bootstrap: str) -> None:
    if manifest.get("version") != ZOTERO_BRIDGE_VERSION:
        raise ValueError("PaperHunter Zotero Bridge manifest 版本与后端期望不一致。")
    if f'version: "{ZOTERO_BRIDGE_VERSION}"' not in bootstrap:
        raise ValueError("PaperHunter Zotero Bridge bootstrap 版本与后端期望不一致。")
    if f"protocolVersion: {ZOTERO_BRIDGE_PROTOCOL_VERSION}" not in bootstrap:
        raise ValueError("PaperHunter Zotero Bridge 协议版本与后端期望不一致。")
    required_markers = (
        "preserveUserContent",
        "managedNoteAttribute",
        "isManagedNote",
        "PaperHunter Bridge only links translated Markdown attachments",
        "assertLocalRequest",
        "allowedAttachmentRoots",
        "only links attachments inside PaperHunter translated output",
        "pairingToken",
        "PaperHunter Bridge pairing token is invalid",
        "canVerifyPairingToken",
        "/paperhunter/pairing-check",
        "assertPaired",
    )
    if any(marker not in bootstrap for marker in required_markers):
        raise ValueError("PaperHunter Zotero Bridge 源码缺少必要的安全策略标记。")
    if ZOTERO_BRIDGE_TOKEN_PLACEHOLDER not in bootstrap:
        raise ValueError("PaperHunter Zotero Bridge 源码缺少配对 token 占位符。")


def validate_zotero_bridge_xpi(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
            names = set(zip_file.namelist())
            if not {"manifest.json", "bootstrap.js"}.issubset(names):
                raise ValueError
            manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
            bootstrap = zip_file.read("bootstrap.js").decode("utf-8")
            validate_zotero_bridge_source(manifest, bootstrap.replace(zotero_bridge_token(), ZOTERO_BRIDGE_TOKEN_PLACEHOLDER))
            if ZOTERO_BRIDGE_TOKEN_PLACEHOLDER in bootstrap:
                raise ValueError
    except (OSError, zipfile.BadZipFile, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("PaperHunter Zotero Bridge 插件包不完整，请重新构建 XPI。") from exc


def safe_backup_member(name: str) -> bool:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    allowed_roots = {"paperhunter-backup.json", "data", "downloaded_papers", "translated_papers"}
    return bool(path.parts and path.parts[0] in allowed_roots)


def backup_member_category(name: str) -> str:
    if name == "data/library.json":
        return "library"
    if name == "data/settings.json":
        return "settings"
    if name.startswith("data/fulltext_tasks/") and not name.endswith("/"):
        return "tasks"
    if name.startswith("downloaded_papers/") and not name.endswith("/"):
        return "downloaded"
    if name.startswith("translated_papers/") and not name.endswith("/"):
        return "translated"
    return ""


def analyze_backup_zip(zip_bytes: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zip_file:
            names = zip_file.namelist()
            if "paperhunter-backup.json" not in names:
                raise ValueError("不是 PaperHunter 备份包。")
            if any(not safe_backup_member(name) for name in names):
                raise ValueError("备份包包含不安全路径，已拒绝导入。")
            manifest = json.loads(zip_file.read("paperhunter-backup.json").decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("app") != "PaperHunter":
                raise ValueError("备份包 manifest 不正确。")
            counts = {"tasks": 0, "downloaded": 0, "translated": 0, "other": 0}
            sizes = {"tasks": 0, "downloaded": 0, "translated": 0, "other": 0}
            for info in zip_file.infolist():
                if info.is_dir() or info.filename in {"paperhunter-backup.json", "data/library.json", "data/settings.json"}:
                    continue
                category = backup_member_category(info.filename) or "other"
                counts[category] = counts.get(category, 0) + 1
                sizes[category] = sizes.get(category, 0) + int(info.file_size or 0)
            library_summary = {"present": "data/library.json" in names}
            if library_summary["present"]:
                try:
                    library = migrate_library(json.loads(zip_file.read("data/library.json").decode("utf-8")))
                    library_summary.update({
                        "papers": len(library.get("papers") or {}),
                        "favorites": len(library.get("favorites") or {}),
                        "ignored": len(library.get("ignored") or {}),
                        "downloads": len(library.get("downloads") or {}),
                        "alertInbox": len(library.get("alertInbox") or []),
                        "subscriptionSources": len(library.get("subscriptionSources") or []),
                    })
                except (json.JSONDecodeError, ValueError, TypeError) as exc:
                    raise ValueError("备份包中的 library.json 无法解析。") from exc
            settings_summary = {"present": "data/settings.json" in names}
            if settings_summary["present"]:
                try:
                    raw_settings = json.loads(zip_file.read("data/settings.json").decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise ValueError("备份包中的 settings.json 无法解析。") from exc
                if not isinstance(raw_settings, dict):
                    raise ValueError("备份包中的 settings.json 格式不正确。")
                normalized = normalize_settings({**raw_settings, "apiKey": "", "zoteroBridgeToken": ""})
                settings_summary.update({
                    "provider": normalized.get("provider") or "",
                    "apiType": normalized.get("apiType") or "",
                    "model": normalized.get("model") or "",
                    "baseUrl": normalized.get("baseUrl") or "",
                    "apiKeyRemoved": bool(raw_settings.get("apiKeyRemoved") or raw_settings.get("apiKey")),
                    "zoteroBridgeTokenRemoved": True,
                    "willRotateBridgeToken": True,
                })
    except zipfile.BadZipFile as exc:
        raise ValueError("备份包不是有效的 zip 文件。") from exc
    total_size = sum(sizes.values())
    return {
        "ok": True,
        "manifest": {
            "app": manifest.get("app"),
            "version": manifest.get("version"),
            "createdAt": manifest.get("createdAt", ""),
            "librarySchemaVersion": manifest.get("librarySchemaVersion"),
            "settingsSchemaVersion": manifest.get("settingsSchemaVersion"),
            "apiKeyExported": bool(manifest.get("apiKeyExported")),
        },
        "files": {
            "total": sum(counts.values()),
            "counts": counts,
            "sizes": sizes,
            "totalSize": total_size,
        },
        "library": library_summary,
        "settings": settings_summary,
        "impact": {
            "importsLibrary": library_summary.get("present", False),
            "importsSettings": settings_summary.get("present", False),
            "importsFiles": sum(counts.values()) > 0,
            "apiKeyWillRemainEmpty": bool(settings_summary.get("present")),
            "bridgeReinstallRequired": bool(settings_summary.get("present")),
            "restorePointWillBeCreated": True,
        },
        "strategyOptions": ["merge", "overwrite", "skip"],
        "defaultStrategy": "merge",
        "warnings": [
            "API Key 不会从备份恢复，导入后需要按需重新填写。",
            "导入 settings 会重新生成本机 Bridge 配对 token，需要重新下载并覆盖安装 Bridge XPI。",
            "导入前会创建本机恢复点；如果导入失败，PaperHunter 会自动回滚到恢复点。",
        ],
    }


def create_backup_restore_point() -> dict:
    BACKUP_RESTORE_POINT_DIR.mkdir(parents=True, exist_ok=True)
    restore_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_RESTORE_POINT_DIR / restore_id
    suffix = 1
    while target.exists():
        suffix += 1
        target = BACKUP_RESTORE_POINT_DIR / f"{restore_id}-{suffix}"
    target.mkdir(parents=True)
    files = []

    def copy_file(path: Path, arcname: str) -> None:
        if path.exists() and path.is_file():
            destination = target / arcname
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            files.append(arcname)

    def copy_dir(path: Path, arcname: str) -> None:
        if path.exists() and path.is_dir():
            destination = target / arcname
            shutil.copytree(path, destination)
            files.append(f"{arcname}/")

    copy_file(LIBRARY_PATH, "data/library.json")
    copy_file(SETTINGS_PATH, "data/settings.json")
    copy_dir(FULLTEXT_TASK_DIR, "data/fulltext_tasks")
    copy_dir(DOWNLOAD_DIR, "downloaded_papers")
    copy_dir(TRANSLATED_DIR, "translated_papers")
    metadata = {
        "id": target.name,
        "path": str(target),
        "createdAt": now_iso(),
        "files": files,
    }
    (target / "paperhunter-restore-point.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def restore_backup_restore_point(restore_point: dict) -> None:
    root = Path(str((restore_point or {}).get("path") or ""))
    if not root.exists() or not root.is_dir():
        raise ValueError("恢复点不存在，无法回滚。")

    def restore_file(source: Path, target: Path) -> None:
        if source.exists() and source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        elif target.exists():
            target.unlink()

    def restore_dir(source: Path, target: Path) -> None:
        if target.exists():
            shutil.rmtree(target)
        if source.exists() and source.is_dir():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target)
        else:
            target.mkdir(parents=True, exist_ok=True)

    restore_file(root / "data" / "library.json", LIBRARY_PATH)
    restore_file(root / "data" / "settings.json", SETTINGS_PATH)
    restore_dir(root / "data" / "fulltext_tasks", FULLTEXT_TASK_DIR)
    restore_dir(root / "downloaded_papers", DOWNLOAD_DIR)
    restore_dir(root / "translated_papers", TRANSLATED_DIR)


def backup_preview_payload(payload: dict) -> dict:
    encoded = str(payload.get("contentBase64") or "")
    if not encoded:
        raise ValueError("缺少备份包内容。")
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("备份包不是有效的 base64 内容。") from exc
    return analyze_backup_zip(content)


def extract_backup_zip(zip_bytes: bytes, strategy: str = "merge") -> dict:
    strategy = strategy if strategy in {"merge", "overwrite", "skip"} else "merge"
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zip_file:
        names = zip_file.namelist()
        if "paperhunter-backup.json" not in names:
            raise ValueError("不是 PaperHunter 备份包。")
        if any(not safe_backup_member(name) for name in names):
            raise ValueError("备份包包含不安全路径，已拒绝导入。")
        manifest = json.loads(zip_file.read("paperhunter-backup.json").decode("utf-8"))
        if not isinstance(manifest, dict) or manifest.get("app") != "PaperHunter":
            raise ValueError("备份包 manifest 不正确。")

        imported = {"library": False, "settings": False, "tasks": 0, "downloaded": 0, "translated": 0}
        if "data/library.json" in names and strategy != "skip":
            backup_library = migrate_library(json.loads(zip_file.read("data/library.json").decode("utf-8")))
            if strategy == "overwrite":
                save_library(backup_library)
            else:
                current = load_library()
                for section in ("papers", "favorites", "ignored", "downloads"):
                    current.setdefault(section, {}).update(backup_library.get(section, {}))
                current["history"] = (backup_library.get("history") or []) + (current.get("history") or [])
                current["history"] = current["history"][:MAX_SEARCH_HISTORY]
                current["subscriptionSources"] = normalize_subscription_sources(
                    (backup_library.get("subscriptionSources") or []) + (current.get("subscriptionSources") or [])
                )
                current["alertImportHistory"] = normalize_alert_import_history(
                    (backup_library.get("alertImportHistory") or []) + (current.get("alertImportHistory") or [])
                )
                current["alertInbox"] = normalize_alert_inbox(
                    (backup_library.get("alertInbox") or []) + (current.get("alertInbox") or []),
                    current,
                )
                save_library(current)
            imported["library"] = True

        if "data/settings.json" in names and strategy != "skip":
            raw_backup_settings = json.loads(zip_file.read("data/settings.json").decode("utf-8"))
            if isinstance(raw_backup_settings, dict):
                raw_backup_settings["zoteroBridgeToken"] = ""
            backup_settings = normalize_settings(raw_backup_settings)
            backup_settings["apiKey"] = ""
            save_settings(backup_settings)
            imported["settings"] = True

        for name in names:
            if name.endswith("/") or name in {"paperhunter-backup.json", "data/library.json", "data/settings.json"}:
                continue
            target_root = None
            prefix_offset = 1
            if name.startswith("data/fulltext_tasks/"):
                target_root = FULLTEXT_TASK_DIR
                counter = "tasks"
                prefix_offset = 2
            elif name.startswith("downloaded_papers/"):
                target_root = DOWNLOAD_DIR
                counter = "downloaded"
            elif name.startswith("translated_papers/"):
                target_root = TRANSLATED_DIR
                counter = "translated"
            else:
                continue
            relative = Path(*Path(name).parts[prefix_offset:])
            target = (target_root / relative).resolve()
            if target_root.resolve() not in target.parents and target != target_root.resolve():
                raise ValueError("备份包路径校验失败。")
            if target.exists() and strategy == "skip":
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as file:
                file.write(zip_file.read(name))
            imported[counter] += 1
    return imported


def import_backup_payload(payload: dict) -> dict:
    encoded = str(payload.get("contentBase64") or "")
    if not encoded:
        raise ValueError("缺少备份包内容。")
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("备份包不是有效的 base64 内容。") from exc
    preview = analyze_backup_zip(content)
    restore_point = create_backup_restore_point()
    try:
        imported = extract_backup_zip(content, str(payload.get("strategy") or "merge"))
    except Exception:
        restore_backup_restore_point(restore_point)
        raise
    settings = load_settings()
    return {
        "ok": True,
        "imported": imported,
        "preview": preview,
        "restorePoint": {
            "id": restore_point.get("id"),
            "createdAt": restore_point.get("createdAt"),
            "path": restore_point.get("path"),
        },
        "rollbackAvailable": True,
        "library": compact_library(load_library()),
        "settings": public_settings(settings),
        "bridgeReinstallRequired": bool(imported.get("settings")),
        "bridgeReminder": bridge_reinstall_reminder(bool(imported.get("settings")), settings),
    }


class PaperHunterHandler(SimpleHTTPRequestHandler):
    server_version = "PaperHunter/1.0"

    def translate_path(self, path: str) -> str:
        parsed_path = unquote(urlparse(path).path)
        if parsed_path in {"", "/"}:
            return str(WEB_DIR / "index.html")

        static_path = (WEB_DIR / parsed_path.lstrip("/")).resolve()
        if WEB_DIR.resolve() not in static_path.parents and static_path != WEB_DIR.resolve():
            return str(WEB_DIR / "index.html")
        return str(static_path)

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def do_GET(self) -> None:
        request_path = normalized_request_path(self.path)
        if request_path == "/api/diagnostics":
            self.send_json(diagnostics_payload())
            return

        if request_path == "/api/status":
            library = load_library()
            self.send_json(
                {
                    "ok": True,
                    "downloadedCount": existing_pdf_count(),
                    "downloadDir": str(DOWNLOAD_DIR),
                    "sources": SOURCE_LABELS,
                    "externalGateways": EXTERNAL_GATEWAYS,
                    "library": compact_library(library),
                    "subscription": public_subscription_status(library),
                    "zotero": zotero_status(),
                    "modelSettings": public_settings(load_settings()),
                    "modelProviders": MODEL_PROVIDER_PRESETS,
                    "modelApiTypes": API_TYPE_ENDPOINTS,
                }
            )
            return

        if request_path == "/api/backup/export":
            content, filename = export_workspace_backup()
            self.send_bytes(content, "application/zip", filename)
            return

        if request_path == "/api/zotero/bridge-xpi":
            try:
                content, filename = read_zotero_bridge_xpi()
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=404)
                return
            self.send_bytes(content, "application/x-xpinstall", filename)
            return

        if request_path == "/api/zotero/audit":
            query = parse_qs(urlparse(self.path).query)
            limit = (query.get("limit") or [""])[0]
            self.send_json(zotero_audit_status({"limit": limit}))
            return

        if request_path == "/api/settings":
            self.send_json(model_settings_status())
            return

        if request_path == "/" or not request_path.startswith("/api/"):
            return super().do_GET()

        self.send_json({"ok": False, "error": "接口不存在。"}, status=404)

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            request_path = normalized_request_path(self.path)
            if request_path == "/api/search":
                self.send_json({"ok": True, **search_papers(payload)})
                return
            if request_path == "/api/download":
                self.send_json(download_pdf(payload))
                return
            if request_path == "/api/alert/import":
                self.send_json(import_alert_payload(payload))
                return
            if request_path == "/api/alert/inbox":
                self.send_json(alert_inbox_payload(payload))
                return
            if request_path == "/api/research/radar":
                self.send_json(research_radar_payload(payload))
                return
            if request_path == "/api/diagnostics":
                self.send_json(diagnostics_payload(payload))
                return
            if request_path == "/api/subscription/sources":
                self.send_json(subscription_sources_payload(payload))
                return
            if request_path == "/api/abstract/candidates":
                self.send_json(abstract_candidates_payload(payload))
                return
            if request_path == "/api/abstract/confirm":
                self.send_json(abstract_confirm_payload(payload))
                return
            if request_path == "/api/abstract/enrich":
                self.send_json(enrich_favorites_abstracts(payload))
                return
            if request_path == "/api/library":
                self.send_json(update_library(payload))
                return
            if request_path == "/api/export":
                self.send_json(export_papers(payload))
                return
            if request_path == "/api/zotero/save":
                self.send_json(save_papers_to_zotero(payload))
                return
            if request_path == "/api/zotero/import":
                self.send_json(import_zotero_library(payload))
                return
            if request_path == "/api/zotero/confirm-link":
                self.send_json(confirm_zotero_link(payload))
                return
            if request_path == "/api/zotero/link":
                self.send_json(link_zotero_items(payload))
                return
            if request_path == "/api/zotero/sync-preview":
                self.send_json(zotero_sync_preview(payload))
                return
            if request_path == "/api/zotero/sync-favorites-preview":
                self.send_json(zotero_favorites_sync_preview(payload))
                return
            if request_path == "/api/zotero/sync-favorites":
                self.send_json(sync_favorites_to_zotero(payload))
                return
            if request_path == "/api/zotero/sync":
                self.send_json(sync_paper_to_zotero(payload))
                return
            if request_path == "/api/settings/test":
                self.send_json(test_model_connection(payload))
                return
            if request_path == "/api/settings":
                self.send_json(save_model_settings(payload))
                return
            if request_path == "/api/translate/abstract":
                self.send_json(translate_abstract(payload))
                return
            if request_path == "/api/translate/batch":
                self.send_json(batch_translate_abstracts(payload))
                return
            if request_path == "/api/translate/fulltext/status":
                self.send_json(fulltext_task_status(payload))
                return
            if request_path == "/api/translate/fulltext":
                self.send_json(translate_fulltext(payload))
                return
            if request_path == "/api/open/fulltext-folder":
                self.send_json(open_fulltext_folder(payload))
                return
            if request_path == "/api/backup/preview":
                self.send_json(backup_preview_payload(payload))
                return
            if request_path == "/api/backup/import":
                self.send_json(import_backup_payload(payload))
                return
            self.send_json({"ok": False, "error": "接口不存在。"}, status=404)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def read_json(self) -> dict:
        length = clamp_int(self.headers.get("Content-Length"), default=0, minimum=0, maximum=4 * 1024 * 1024)
        if length == 0:
            return {}

        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("请求 JSON 格式不正确。") from exc

        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 JSON 对象。")
        return payload

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, content_type: str, filename: str = "", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        request_path = normalized_request_path(self.path)
        if request_path == "/" or request_path.endswith((".html", ".js", ".css")):
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
        super().end_headers()

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "application/javascript; charset=utf-8"
        if path.endswith(".css"):
            return "text/css; charset=utf-8"
        if path.endswith(".html"):
            return "text/html; charset=utf-8"
        return mimetypes.guess_type(path)[0] or "application/octet-stream"


def main() -> int:
    if not WEB_DIR.exists():
        print(f"Missing frontend directory: {WEB_DIR}", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer((HOST, PORT), PaperHunterHandler)
    print(f"PaperHunter running at http://{HOST}:{PORT}")
    print(f"PDFs will be saved to {DOWNLOAD_DIR}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PaperHunter.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
