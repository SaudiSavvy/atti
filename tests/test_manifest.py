import re

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_manifest_shape(manifest):
    arts = manifest["articles"]
    assert len(arts) == 10
    assert len({a["article"] for a in arts}) == 10
    for a in arts:
        assert HEX64.match(a["ar_sha256"]) and HEX64.match(a["en_sha256"])
        assert a["ar_chars"] > 0 and a["en_chars"] > 0
        v = a["verification"]
        assert v["ar_page_marks_amended"] is False
        assert v["en_appendix_references_article"] is False
        assert v["content_review"]
    assert HEX64.match(manifest["sources"]["en"]["pdf_sha256"])


def test_no_selected_article_is_disputed_or_amended(manifest):
    audit = manifest["audit"]
    excluded = set(audit["ar_articles_marked_amended"]) | set(audit["en_appendix_article_refs"])
    assert not excluded & {a["article"] for a in manifest["articles"]}


def test_lengths_vary(manifest):
    chars = sorted(a["ar_chars"] for a in manifest["articles"])
    assert chars[-1] >= 10 * chars[0]
