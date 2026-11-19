from __future__ import annotations

import csv
import io
import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import digest_text


@dataclass
class ParsedMaterial:
    text: str
    page_count: int | None
    mime_type: str
    title: str | None = None
    final_url: str | None = None


def normalize_filename_extension(file_name: str) -> str:
    return Path(file_name).suffix.lower()


def parse_file(file_name: str, data: bytes) -> ParsedMaterial:
    settings = get_settings()
    suffix = normalize_filename_extension(file_name)
    if len(data) > settings.upload_max_bytes:
        raise AppError("validation", "error.validation.file_too_large")
    try:
        if suffix == ".txt":
            return ParsedMaterial(text=_limit(data.decode("utf-8", errors="replace")), page_count=None, mime_type="text/plain")
        if suffix == ".md":
            from markdown_it import MarkdownIt

            html = MarkdownIt().render(data.decode("utf-8", errors="replace"))
            text = _strip_html(html)
            return ParsedMaterial(text=_limit(text), page_count=None, mime_type="text/markdown")
        if suffix == ".csv":
            text = data.decode("utf-8", errors="replace")
            rows = list(csv.reader(io.StringIO(text)))
            flattened = "\n".join(" | ".join(row) for row in rows)
            return ParsedMaterial(text=_limit(flattened), page_count=None, mime_type="text/csv")
        if suffix == ".pdf":
            import pdfplumber

            chunks: list[str] = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            return ParsedMaterial(
                text=_limit("\n\n".join(chunks)),
                page_count=len(chunks),
                mime_type="application/pdf",
            )
        if suffix == ".docx":
            import docx

            document = docx.Document(io.BytesIO(data))
            chunks = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    chunks.append(" | ".join(cell.text for cell in row.cells))
            return ParsedMaterial(
                text=_limit("\n".join(chunks)),
                page_count=None,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        if suffix == ".xlsx":
            import openpyxl

            workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
            chunks = []
            for sheet in workbook.worksheets:
                chunks.append(f"# Sheet: {sheet.title}")
                for row in sheet.iter_rows(values_only=True):
                    values = [str(v) for v in row if v is not None]
                    if values:
                        chunks.append(" | ".join(values))
            return ParsedMaterial(
                text=_limit("\n".join(chunks)),
                page_count=len(workbook.worksheets),
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        if suffix == ".pptx":
            from pptx import Presentation

            presentation = Presentation(io.BytesIO(data))
            chunks = []
            for i, slide in enumerate(presentation.slides, start=1):
                chunks.append(f"# Slide {i}")
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        chunks.append(shape.text)
            return ParsedMaterial(
                text=_limit("\n".join(chunks)),
                page_count=len(presentation.slides),
                mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AppError("parse_failure", "error.parse.failed", details={"reason": "parser_error"}) from exc
    raise AppError("validation", "error.validation.unsupported_type")


def _limit(text: str) -> str:
    settings = get_settings()
    clean = text.replace("\x00", "").strip()
    return clean[: settings.ingest_max_chars]


def _strip_html(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n")


def normalize_url(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise AppError("validation", "error.validation.invalid_url")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AppError("validation", "error.validation.invalid_url")
    if parsed.username or parsed.password:
        raise AppError("validation", "error.validation.invalid_url")
    try:
        host = parsed.hostname.encode("idna").decode("ascii")
    except Exception as exc:  # noqa: BLE001
        raise AppError("validation", "error.validation.invalid_url") from exc
    if "." not in host and host != "localhost":
        raise AppError("validation", "error.validation.invalid_url")
    netloc = host + (f":{parsed.port}" if parsed.port else "")
    return urlunparse((parsed.scheme, netloc, parsed.path or "/", "", parsed.query, ""))


def _assert_public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise AppError("parse_failure", "error.parse.url_unreachable") from exc
    for info in infos:
        addr = info[4][0]
        ip = ipaddress.ip_address(addr)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or str(ip) == "169.254.169.254"
        ):
            raise AppError("validation", "error.validation.invalid_url", details={"reason": "private_host"})


async def fetch_url(raw_url: str) -> ParsedMaterial:
    url = normalize_url(raw_url)
    current = url
    for _ in range(5):
        parsed = urlparse(current)
        _assert_public_host(parsed.hostname or "")
        try:
            async with httpx.AsyncClient(
                timeout=15, follow_redirects=False, headers={"User-Agent": "BoundPPT/0.1 (+pilot)"}
            ) as client:
                async with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise AppError("parse_failure", "error.parse.url_unreachable")
                        current = normalize_url(str(location))
                        continue
                    if response.status_code == 404 or response.status_code >= 400:
                        raise AppError("parse_failure", "error.parse.url_unreachable")
                    content_type = response.headers.get("content-type", "")
                    if not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml")):
                        raise AppError("parse_failure", "error.parse.url_unreachable")
                    data = b""
                    async for chunk in response.aiter_bytes():
                        data += chunk
                        if len(data) > 5 * 1024 * 1024:
                            break
                    final_url = str(response.url)
                    title = parsed.hostname or ""
                    if "html" in content_type:
                        from bs4 import BeautifulSoup

                        soup = BeautifulSoup(data, "lxml")
                        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
                            tag.decompose()
                        if soup.title and soup.title.string:
                            title = soup.title.string.strip()[:200]
                        text = soup.get_text("\n")
                    else:
                        text = data.decode("utf-8", errors="replace")
                    clean = _limit(text)
                    if len(clean) < 40:
                        raise AppError("parse_failure", "error.parse.url_unreachable")
                    return ParsedMaterial(
                        text=clean,
                        page_count=None,
                        mime_type="text/html",
                        title=title,
                        final_url=final_url,
                    )
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AppError("parse_failure", "error.parse.url_unreachable") from exc
    raise AppError("parse_failure", "error.parse.url_unreachable")


def material_content_key(project_id: str, material_id: str) -> str:
    return f"projects/{project_id}/materials/{material_id}/content.txt"


def material_raw_key(project_id: str, material_id: str, file_name: str) -> str:
    suffix = Path(file_name).suffix.lower() or ".bin"
    return f"projects/{project_id}/materials/{material_id}/raw{suffix}"


def url_hash(url: str) -> str:
    return digest_text(url)
