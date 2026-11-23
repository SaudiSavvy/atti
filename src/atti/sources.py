"""Official source definitions and a cached downloader (stdlib only).

The legal texts are fetched into a local, git-ignored cache (``data/raw``) and
never committed to the repository.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import ssl
import urllib.request
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def fetch(source: Source, cache_dir: Path, refresh: bool = False) -> Path:
    """Download ``source`` into ``cache_dir`` unless already cached."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / source.filename
    if path.exists() and not refresh:
        return path
    req = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    # Verify TLS against the OS trust store (the BOE server relies on it).
    import truststore

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        data = resp.read()
    path.write_bytes(data)
    log_path = cache_dir / "fetch_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    log[source.key] = {
        "url": source.url,
        "file": source.filename,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n")
    return path


def fetch_all(cache_dir: Path, refresh: bool = False) -> dict[str, Path]:
    return {s.key: fetch(s, cache_dir, refresh) for s in SOURCES}
