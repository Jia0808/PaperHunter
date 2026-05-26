import gzip
import hashlib
import json
import mimetypes
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from urllib.parse import unquote, urljoin, urlparse

import arxiv
import requests


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
DOWNLOAD_DIR = ROOT_DIR / "downloaded_papers"
CACHE_DIR = ROOT_DIR / ".cache"
DATA_DIR = ROOT_DIR / "data"
DOWNLOAD_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

HOST = "127.0.0.1"
PORT = 8000
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
SOURCE_LABELS = {
    "arxiv": "arXiv",
    "semantic": "Semantic Scholar",
    "cvf": "CVF Open Access",
    "acl": "ACL Anthology",
    "openreview": "OpenReview",
    "chinarxiv": "ChinaRxiv / ChinaXiv",
    "sciopen": "SciOpen",
    "nso": "National Science Open",
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
LIBRARY_PATH = DATA_DIR / "library.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
LIBRARY_LOCK = RLock()
LIBRARY_SCHEMA_VERSION = 3
SETTINGS_SCHEMA_VERSION = 1
TRANSLATION_PROMPT_VERSION = "abstract-zh-v1"
MAX_SEARCH_HISTORY = 30
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
    "entryUrl",
    "pageUrl",
    "arxivId",
    "paperId",
    "source",
    "sourceLabel",
    "venue",
    "category",
    "abstract",
    "fullAbstract",
    "downloadable",
    "isDownloaded",
    "readingStatus",
    "note",
    "tags",
    "translations",
)


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


def paper_snapshot(paper: dict) -> dict:
    snapshot = {field: paper.get(field, "") for field in PAPER_SNAPSHOT_FIELDS}
    snapshot["paperKey"] = paper_key(paper)
    snapshot["title"] = clean_display_text(str(snapshot.get("title") or "Untitled"), TITLE_TEXT_LIMIT)
    snapshot["authors"] = clean_display_text(str(snapshot.get("authors") or "Unknown authors"), AUTHOR_TEXT_LIMIT)
    snapshot["abstract"] = clean_display_text(str(snapshot.get("abstract") or "暂无摘要。"), ABSTRACT_TEXT_LIMIT)
    snapshot["fullAbstract"] = clean_html(str(snapshot.get("fullAbstract") or ""))
    snapshot["downloadable"] = bool(snapshot.get("pdfUrl"))
    snapshot["isDownloaded"] = bool(snapshot.get("isDownloaded"))
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


def join_url(base_url: str, endpoint: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    path = str(endpoint or "").strip()
    if not path:
        path = API_TYPE_ENDPOINTS["chat_completions"]
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}" if base else path


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
) -> dict:
    source_label = SOURCE_LABELS.get(source, source)
    resolved_id = paper_id or normalize_key(title).replace(" ", "-")[:48] or "unknown"
    full_abstract = clean_html(str(abstract or "暂无摘要。"))
    return {
        "title": clean_display_text(title, TITLE_TEXT_LIMIT) or "Untitled",
        "authors": clean_display_text(authors, AUTHOR_TEXT_LIMIT) or "Unknown authors",
        "published": published or str(year or ""),
        "year": year,
        "pdfUrl": pdf_url,
        "entryUrl": page_url,
        "pageUrl": page_url,
        "arxivId": resolved_id,
        "paperId": resolved_id,
        "source": source,
        "sourceLabel": source_label,
        "venue": clean_display_text(venue, 120),
        "category": clean_display_text(category or venue or source_label, 120),
        "abstract": compact_text(full_abstract, ABSTRACT_TEXT_LIMIT),
        "fullAbstract": full_abstract,
        "downloadable": bool(pdf_url),
        "isDownloaded": bool(pdf_url) and (DOWNLOAD_DIR / sanitize_filename(title, resolved_id)).exists(),
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
    return {
        "createdAt": str(value.get("createdAt") or now_iso()),
        "filename": str(value.get("filename") or ""),
        "paper": snapshot,
    }


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
        tmp_path = LIBRARY_PATH.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(library, file, ensure_ascii=False, indent=2)
            file.write("\n")
        tmp_path.replace(LIBRARY_PATH)


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

    settings = {
        "version": SETTINGS_SCHEMA_VERSION,
        "provider": provider,
        "apiType": api_type,
        "baseUrl": str(raw.get("baseUrl") if raw.get("baseUrl") is not None else base.get("baseUrl") or preset["baseUrl"]).strip().rstrip("/"),
        "endpoint": endpoint if endpoint.startswith("/") else f"/{endpoint}",
        "model": str(raw.get("model") if raw.get("model") is not None else base.get("model") or preset["defaultModel"]).strip(),
        "apiKey": str(api_key or "").strip(),
        "updatedAt": str(raw.get("updatedAt") or base.get("updatedAt") or ""),
    }
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
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)
        file.write("\n")
    tmp_path.replace(SETTINGS_PATH)


def public_settings(settings: dict) -> dict:
    endpoint = settings.get("endpoint") or API_TYPE_ENDPOINTS[normalize_api_type(settings.get("apiType"))]
    return {
        "version": SETTINGS_SCHEMA_VERSION,
        "provider": settings.get("provider", "custom"),
        "apiType": normalize_api_type(settings.get("apiType")),
        "baseUrl": settings.get("baseUrl", ""),
        "endpoint": endpoint,
        "model": settings.get("model", ""),
        "hasApiKey": bool(settings.get("apiKey")),
        "apiKeyMasked": mask_secret(str(settings.get("apiKey", ""))),
        "finalUrl": join_url(str(settings.get("baseUrl", "")), str(endpoint)),
        "updatedAt": settings.get("updatedAt", ""),
    }


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


def extract_responses_text(data: dict) -> str:
    if data.get("output_text"):
        return str(data.get("output_text"))
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("text"):
                return str(content.get("text"))
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


def post_model_json(url: str, headers: dict, body: dict) -> dict:
    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=request_timeout(30),
    )
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("模型接口没有返回 JSON。") from exc
    if not isinstance(data, dict):
        raise RuntimeError("模型接口返回格式不是 JSON 对象。")
    return data


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
            "input": "Reply with exactly OK.",
            "max_output_tokens": 8,
        },
    )
    return extract_responses_text(data), data.get("usage") if isinstance(data.get("usage"), dict) else {}


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


def invoke_model_text(settings: dict, prompt: str, max_tokens: int = 900) -> tuple[str, dict]:
    api_type = normalize_api_type(settings.get("apiType"))
    url = join_url(settings["baseUrl"], settings["endpoint"])
    if api_type == "responses":
        data = post_model_json(
            url,
            model_headers(settings),
            {
                "model": settings["model"],
                "input": prompt,
                "max_output_tokens": max_tokens,
            },
        )
        text = extract_responses_text(data)
    elif api_type == "anthropic_messages":
        data = post_model_json(
            url,
            model_headers(settings),
            {
                "model": settings["model"],
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
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
        raise RuntimeError(normalize_model_error(exc)) from exc

    return {
        "ok": True,
        "message": "测试连接成功。",
        "provider": settings.get("provider"),
        "apiType": api_type,
        "finalUrl": join_url(settings["baseUrl"], settings["endpoint"]),
        "model": settings.get("model"),
        "sample": compact_text(text or "OK", 120),
        "usage": usage,
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
            })

    ignored = []
    for key, item in (library.get("ignored") or {}).items():
        if isinstance(item, dict):
            paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            ignored.append({**paper, "paperKey": key, "ignoredAt": item.get("createdAt", "")})

    favorites.sort(key=lambda paper: str(paper.get("favoritedAt", "")), reverse=True)
    ignored.sort(key=lambda paper: str(paper.get("ignoredAt", "")), reverse=True)
    return {
        "version": LIBRARY_SCHEMA_VERSION,
        "favorites": favorites,
        "ignored": ignored,
        "history": (library.get("history") or [])[:MAX_SEARCH_HISTORY],
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
            note = stored_paper.get("note")
            tags = stored_paper.get("tags")
            reading_status = stored_paper.get("readingStatus")
            if translations:
                paper["translations"] = translations
            if note:
                paper["note"] = note
            if tags:
                paper["tags"] = tags
            if reading_status:
                paper["readingStatus"] = reading_status
        paper["paperKey"] = key
        paper["isFavorite"] = key in favorites
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
    for field in ("paperId", "arxivId", "pageUrl", "entryUrl", "pdfUrl", "title"):
        value = normalize_key(str(paper.get(field, "")))
        if value:
            values.add(value)
    return values


def same_paper(left: dict, right: dict) -> bool:
    left_ids = paper_identity_values(left)
    right_ids = paper_identity_values(right)
    if left_ids & right_ids:
        return True

    left_title = normalize_key(str(left.get("title", "")))
    right_title = normalize_key(str(right.get("title", "")))
    return bool(left_title and right_title and left_title == right_title)


def refresh_queries_for_paper(paper: dict) -> list[str]:
    candidates = [
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

    snapshot = paper_snapshot({**refreshed, "isDownloaded": bool(paper.get("isDownloaded")) or bool(refreshed.get("isDownloaded"))})
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
            item["paper"] = snapshot
            item["refreshedAt"] = now_iso()
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
            suffix = "" if full_abstract else " (可能已截断)"
            lines.append(f"   - 摘要: {abstract}{suffix}")
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
    elif export_format == "bibtex":
        content = export_bibtex(papers)
        filename = "paperhunter-library.bib"
        mime_type = "application/x-bibtex; charset=utf-8"
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
        if self.path.startswith("/api/status"):
            library = load_library()
            self.send_json(
                {
                    "ok": True,
                    "downloadedCount": existing_pdf_count(),
                    "downloadDir": str(DOWNLOAD_DIR),
                    "sources": SOURCE_LABELS,
                    "externalGateways": EXTERNAL_GATEWAYS,
                    "library": compact_library(library),
                    "modelSettings": public_settings(load_settings()),
                    "modelProviders": MODEL_PROVIDER_PRESETS,
                    "modelApiTypes": API_TYPE_ENDPOINTS,
                }
            )
            return

        if self.path.startswith("/api/settings"):
            self.send_json(model_settings_status())
            return

        if self.path == "/" or not self.path.startswith("/api/"):
            return super().do_GET()

        self.send_json({"ok": False, "error": "接口不存在。"}, status=404)

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path.startswith("/api/search"):
                self.send_json({"ok": True, **search_papers(payload)})
                return
            if self.path.startswith("/api/download"):
                self.send_json(download_pdf(payload))
                return
            if self.path.startswith("/api/library"):
                self.send_json(update_library(payload))
                return
            if self.path.startswith("/api/export"):
                self.send_json(export_papers(payload))
                return
            if self.path.startswith("/api/settings/test"):
                self.send_json(test_model_connection(payload))
                return
            if self.path.startswith("/api/settings"):
                self.send_json(save_model_settings(payload))
                return
            if self.path.startswith("/api/translate/abstract"):
                self.send_json(translate_abstract(payload))
                return
            self.send_json({"ok": False, "error": "接口不存在。"}, status=404)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def read_json(self) -> dict:
        length = clamp_int(self.headers.get("Content-Length"), default=0, minimum=0, maximum=1024 * 1024)
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
