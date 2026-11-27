"""Official source definitions and a cached downloader (stdlib only).

The legal texts are fetched into a local, git-ignored cache (``data/raw``) and
never committed to the repository. A cached file is never overwritten:
the cache is the pinned baseline that ``atti pilot`` reproduces from.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import http.client
import json
import os
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

BOE_LAW_ID = "08381293-6388-48e2-8ad2-a9a700f2aa94"


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    filename: str
    description: str


ARABIC = Source(
    key="ar",
    url=f"https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/{BOE_LAW_ID}/1",
    filename="boe_labor_law_ar.html",
    description="Bureau of Experts at the Council of Ministers - Labor Law, Arabic (governing text)",
)
ENGLISH = Source(
    key="en",
    url="https://laws.boe.gov.sa/Files/Download/?attId=704cf56e-eb7a-4ddb-8c28-adbb01244dc6",
    filename="boe_labor_law_en.pdf",
    description="Bureau of Experts, Official Translation Department - Labor Law, English (PDF)",
)
SOURCES = (ARABIC, ENGLISH)

USER_AGENT = "atti-benchmark/0.1 (research; tokenizer measurement)"

Downloader = Callable[[str], bytes]


class NetworkError(RuntimeError):
    """The source could not be retrieved (DNS, TLS, timeout, HTTP error status)."""


class UntrustedURLError(NetworkError):
    """A request or redirect would leave the official HTTPS host; nothing is fetched from it."""


BOE_HOST = "laws.boe.gov.sa"


def require_https_host(url: str, host: str) -> str:
    """Return ``url`` if it is plain HTTPS on exactly ``host`` (default port, no credentials)."""
    from urllib.parse import urlsplit

    try:
        p = urlsplit(url)
        port = p.port
    except ValueError as exc:
        raise UntrustedURLError(f"refusing malformed URL {url!r}") from exc
    if p.scheme != "https" or p.hostname != host or port not in (None, 443) or p.username or p.password:
        raise UntrustedURLError(f"refusing {url!r}: only https://{host}/ is allowed")
    return url


class _OfficialHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if its target is on the official BOE host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require_https_host(newurl, BOE_HOST)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def download(url: str) -> bytes:
    """GET ``url``; every transport-level failure is raised as NetworkError."""
    import truststore  # verify TLS against the OS trust store (the BOE server needs it)

    require_https_host(url, BOE_HOST)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _OfficialHostRedirects())
    try:
        with opener.open(req, timeout=120) as resp:
            require_https_host(resp.geturl(), BOE_HOST)
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise NetworkError(f"{url}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        raise NetworkError(f"{url}: {exc}") from exc


def write_atomic(path: Path, data: bytes) -> None:
    """Write via a temporary sibling and rename, so readers never see a partial file."""
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def fetch(source: Source, cache_dir: Path, downloader: Downloader = download) -> Path:
    """Download ``source`` into ``cache_dir`` only if it is not cached yet."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / source.filename
    if path.exists():
        return path
    data = downloader(source.url)
    write_atomic(path, data)
    log_path = cache_dir / "fetch_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    log[source.key] = {
        "url": source.url,
        "file": source.filename,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    write_atomic(log_path, (json.dumps(log, indent=2, ensure_ascii=False) + "\n").encode())
    return path


def fetch_all(cache_dir: Path, downloader: Downloader = download) -> dict[str, Path]:
    return {s.key: fetch(s, cache_dir, downloader) for s in SOURCES}


def fetch_fresh(dest_dir: Path, downloader: Downloader = download) -> dict[str, Path]:
    """Always download every source into ``dest_dir`` (a temporary directory)."""
    out = {}
    for s in SOURCES:
        path = dest_dir / s.filename
        path.write_bytes(downloader(s.url))
        out[s.key] = path
    return out
