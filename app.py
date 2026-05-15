import gzip
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
from urllib.parse import unquote, urljoin, urlparse

import arxiv
import requests


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
DOWNLOAD_DIR = ROOT_DIR / "downloaded_papers"
CACHE_DIR = ROOT_DIR / ".cache"
DOWNLOAD_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

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


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


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
        "abstract": clean_display_text(abstract or "暂无摘要。", ABSTRACT_TEXT_LIMIT),
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

    return {
        "query": query,
        "expandedQuery": expanded_query_text,
        "fieldPreset": field_preset,
        "intent": intent,
        "sources": sources,
        "perSourceLimit": per_source_limit if per_source_requested else None,
        "filters": filters,
        "results": final_results,
        "sourceCounts": count_results_by_source(final_results),
        "errors": errors,
        "downloadedCount": existing_pdf_count(),
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
            self.send_json(
                {
                    "ok": True,
                    "downloadedCount": existing_pdf_count(),
                    "downloadDir": str(DOWNLOAD_DIR),
                    "sources": SOURCE_LABELS,
                    "externalGateways": EXTERNAL_GATEWAYS,
                }
            )
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
