"""Downloader behaviour with the network mocked (offline)."""

import io
import socket
import urllib.error

import pytest

from atti import sources


@pytest.mark.parametrize("exc", [
    urllib.error.URLError("nodename nor servname provided"),
    urllib.error.HTTPError("https://x", 503, "Service Unavailable", {}, io.BytesIO()),
    socket.timeout("timed out"),
    ConnectionResetError("reset"),
])
def test_transport_failures_become_network_error(monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(sources.NetworkError):
        sources.download("https://laws.boe.gov.sa/x")


def test_fetch_never_overwrites_cached_baseline(tmp_path):
    cached = tmp_path / sources.ARABIC.filename
    cached.write_bytes(b"baseline")
    calls = []
    sources.fetch(sources.ARABIC, tmp_path, downloader=lambda url: calls.append(url) or b"new")
    assert cached.read_bytes() == b"baseline" and calls == []


def test_fetch_bootstraps_missing_file_and_logs(tmp_path):
    path = sources.fetch(sources.ENGLISH, tmp_path, downloader=lambda url: b"%PDF-1.5 x")
    assert path.read_bytes() == b"%PDF-1.5 x"
    assert sources.sha256_bytes(b"%PDF-1.5 x") in (tmp_path / "fetch_log.json").read_text()
    assert not list(tmp_path.glob("*.part"))


def test_failed_bootstrap_leaves_no_partial_file(tmp_path):
    def fail(url):
        raise sources.NetworkError("down")
    with pytest.raises(sources.NetworkError):
        sources.fetch(sources.ENGLISH, tmp_path, downloader=fail)
    assert list(tmp_path.iterdir()) == []
