"""HRSD source handling: fetcher, HTML and PDF segmentation, numbering integrity (offline)."""

import json

import httpx
import pytest

from atti import hrsd
from atti.sources import NetworkError

# ---------------------------------------------------------------- fetcher


class FakeResponse:
    def __init__(self, status, content=b"ok", url="https://x/final"):
        self.status_code, self.content, self.url = status, content, url
        self.headers = {"content-type": "text/html", "last-modified": "Sun, 22 Nov 2026 15:02:02 GMT"}


class FakeClient:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def get(self, url):
        self.calls.append(url)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def fetcher(tmp_path, script):
    sleeps = []
    f = hrsd.Fetcher(tmp_path, client=FakeClient(script), sleep=sleeps.append, clock=lambda: 0.0)
    return f, sleeps


def test_retries_with_backoff_then_caches_with_provenance(tmp_path):
    f, sleeps = fetcher(tmp_path, [FakeResponse(503), httpx.ConnectError("reset"), FakeResponse(200, b"page")])
    path = f.fetch("en/index.html", "https://x/index")
    assert path.read_bytes() == b"page"
    assert 1 in sleeps and 2 in sleeps  # exponential backoff 2**0, 2**1
    assert any(s == hrsd.MIN_INTERVAL_S for s in sleeps)  # rate limiting between requests
    prov = json.loads((tmp_path / "provenance.json").read_text())["en/index.html"]
    assert prov["final_url"] == "https://x/final" and prov["status"] == 200 and len(prov["sha256"]) == 64
    assert prov["last_modified_header"]  # recorded as a header, not as a legislative date


def test_gives_up_after_retries(tmp_path):
    f, _ = fetcher(tmp_path, [FakeResponse(503)] * (hrsd.RETRIES + 1))
    with pytest.raises(NetworkError, match="after"):
        f.fetch("a", "https://x/a")
    assert not (tmp_path / "a").exists()


def test_client_error_not_retried(tmp_path):
    f, _ = fetcher(tmp_path, [FakeResponse(404)])
    with pytest.raises(NetworkError, match="HTTP 404"):
        f.fetch("a", "https://x/a")
    assert len(f._client.calls) == 1


def test_cache_is_never_overwritten(tmp_path):
    (tmp_path / "a").write_bytes(b"baseline")
    f, _ = fetcher(tmp_path, [FakeResponse(200, b"new")])
    assert f.fetch("a", "https://x/a").read_bytes() == b"baseline"
    assert f._client.calls == []


# ---------------------------------------------------------------- HTML

def card(label, href, title):
    return (f'<div class="card"><h2 class="text-lg">{label}</h2>'
            f'<h4><a href="{href}"><strong>{title}</strong></a></h4></div>')


def test_discover_parts_from_index_cards():
    words = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
             "Twelve", "Thirteen", "fourteenth", "Fifteen", "Sixteen"]
    html = "<main>" + "".join(card(f"Part {w}", f"/en/node/{i}", f"T{i}") for i, w in enumerate(words, 1)) + "</main>"
    parts = hrsd.discover_parts(html)
    assert [p.part for p in parts] == list(range(1, 17))
    assert parts[13].url == "https://www.hrsd.gov.sa/en/node/14"


def test_discover_parts_rejects_malformed_index():
    with pytest.raises(ValueError, match="Parts 1..16"):
        hrsd.discover_parts("<main>" + card("Part One", "/en/node/1", "x") + "</main>")


EN_PAGE = """<html><nav><h4>Article 999: navigation noise</h4></nav><main><div class="body">
<h4 class="text-align-center">Section 1</h4>
<h4>Article 1:&nbsp;</h4><p>Synthetic article one text.</p>
<h4>Article 2:</h4><p>The following apply:</p>
<ol><li><p>first item</p></li><li><p>second item</p><ol type="a"><li>sub a</li><li>sub b</li></ol></li></ol>
<p>Second: Duties of Workers</p>
<h4>Article 11 Bis:</h4><p>Bis text.</p>
<h4>Article 131 (Bis):</h4><p>Other bis.</p>
<h4>Article 3:</h4><ol start="7"><li>seventh</li></ol>
<h4>Article 3:</h4><p>(Repealed)</p>
</div><div class="rating">Was this content useful?</div></main><footer>Article 5: footer</footer></html>"""


def test_english_parsing_boundaries_lists_and_bis():
    arts = hrsd.parse_html_articles(EN_PAGE, "en")
    got = [(a.number, a.bis, a.text) for a in arts]
    assert got[0] == (1, False, "Synthetic article one text.")
    assert got[1] == (2, False, "The following apply: 1. first item 2. second item a. sub a b. sub b")
    assert (11, True, "Bis text.") in got and (131, True, "Other bis.") in got
    assert got[4] == (3, False, "7. seventh")  # <ol start> respected, never renumbered
    assert all("navigation" not in a.text and "useful" not in a.text and "footer" not in a.text for a in arts)
    assert all("Second: Duties" not in a.text for a in arts)  # section title ends the article


def test_numbering_report_flags_duplicates_missing_and_order_without_repair():
    arts = hrsd.parse_html_articles(EN_PAGE, "en")
    r = hrsd.numbering_report(arts)
    assert r["duplicates"] == [3] and 4 in r["missing"] and r["bis"] == [11, 131]
    assert [a.number for a in arts].count(3) == 2  # nothing renumbered


AR_PAGE = """<main><div><h4>المادة الأولى:&nbsp;</h4><p>نص تجريبي للمادة الأولى.</p>
<h4>المادة التاسعة والسبعون مكرر:</h4><p>نص مكرر.</p>
<p>ثانياً - واجبات العمال</p>
<h4>المادة الثانية بعد المائتين:</h4><p>نص.</p></div></main>"""


def test_arabic_html_headings_and_bis():
    arts = hrsd.parse_html_articles(AR_PAGE, "ar")
    assert [(a.number, a.bis) for a in arts] == [(1, False), (79, True), (202, False)]
    assert "واجبات" not in arts[1].text


# ---------------------------------------------------------------- PDF segmentation

def L(page, y, size, text, marker=""):
    return hrsd.PdfLine(page, y, size, text, marker)


def test_pdf_segmentation_from_classified_lines():
    lines = [
        L(1, 100, 16.1, "الباب الأول: فهرس"),           # table of contents: ignored (before Part divider)
        L(1, 120, 13.9, "المادة الأولى:"),                # ignored: before first Part divider
        L(2, 300, 36.0, "الباب الأول"),
        L(3, 64, 24.0, "نظام العمل:"),                    # running title: not article text
        L(3, 120, 13.9, "المادة الأولى:", marker="1"),
        L(3, 140, 12.0, "نص تجريبي )بين قوسين(."),  # mirrored parentheses
        L(3, 769, 7.9, "1 - عدلت هذه المادة بناءً على المرسوم الملكي"),  # footnote: excluded
        L(3, 795, 12.0, "3"),                             # page number
        L(4, 30, 12.0, "تتمــــة النص"),                   # continues on next page; kashida removed
        L(4, 60, 25.9, "الفصل الثاني"),                    # chapter title ends the article
        L(4, 80, 12.0, "نص بين الفصول"),                    # orphan text: not attached to any article
        L(4, 100, 13.9, "المادة الثانية:"),
        L(4, 120, 10.6, "(ملغاة)"),
        L(5, 300, 36.0, "الباب الثاني"),
        L(5, 320, 13.9, ") التاسعة والسبعين مكرر (:"),  # PDF stores parentheses mirrored
        L(5, 340, 12.0, "ﻻ نص"),                     # presentation-form lam-alef
    ]
    arts, notes = hrsd.articles_from_lines(lines)
    assert [(a.number, a.bis, a.part) for a in arts] == [(1, False, 1), (2, False, 1), (79, True, 2)]
    assert arts[0].text == "نص تجريبي (بين قوسين). تتمة النص"
    assert arts[0].pages == [3, 4] and arts[0].footnote_refs == ["1"]
    assert arts[1].repealed_marker
    assert arts[2].text == "لا نص"
    assert "عدلت" not in " ".join(a.text for a in arts)


def test_cleanup_only_touches_layout_characters():
    assert hrsd.cleanup_arabic_pdf_text("علــــى )م/51( ﻻ") == "على (م/51) لا"
    assert hrsd.cleanup_arabic_pdf_text("أجرًا إضافيًّا، 10%") == "أجرًا إضافيًّا، 10%"
