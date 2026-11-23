import pytest

from atti.arabic import parse_articles, parse_ordinal


@pytest.mark.parametrize("heading,expected", [
    ("المادة الأولى :", (1, False)),
    ("المادة العاشرة :", (10, False)),
    ("المادة الحادية عشرة :", (11, False)),
    ("المادة الثانية والثلاثون :", (32, False)),
    ("المادة الثانية والستون:", (62, False)),
    ("المادة المائة :", (100, False)),
    ("المادة الأولى بعد المائة :", (101, False)),
    ("المادة العشرون بعد المائة :", (120, False)),
    ("المادة المئتان :", (200, False)),
    ("المادة الخامسة والأربعون بعد المائتين :", (245, False)),
    ("( التاسعة والسبعين مكرر )", (79, True)),
    ("( التاسعة والعشرين بعد المائتين مكرر )", (229, True)),
])
def test_parse_ordinal(heading, expected):
    assert parse_ordinal(heading) == expected


@pytest.mark.parametrize("heading", [
    "الفصل الأول : التعريفات",
    "الباب الثاني: تنظيم عمليات التوظيف",
    "(المادة الحادية والثلاثون بعد المائتين حالياً) (المادة الأربعون بعد المائتين سابقاً) :",
])
def test_non_article_headings(heading):
    assert parse_ordinal(heading) is None


HTML = """
<div class="article_item no_alternate ">
  <h3 class="center">الفصل الأول : التعريفات</h3>
  <h3 class="center">المادة الأولى :</h3>
  <p><div class="HTMLContainer">نص   تجريبي<br />للمادة&nbsp;الأولى.</div></p>
</div>
<div class="article_item no_alternate changed-article">
  <h3 class="center">المادة الثانية</h3>
  <div class="HTMLContainer"><p>تعديل منبثق لا يدخل في النص</p></div>
  <p><div class="HTMLContainer"><strong>نص</strong> أصلي &quot;مقتبس&quot;</div></p>
</div>
"""


def test_parse_articles():
    arts = parse_articles(HTML)
    assert [(a.number, a.amended) for a in arts] == [(1, False), (2, True)]
    assert arts[0].text == "نص تجريبي للمادة الأولى."
    assert arts[1].text == 'نص أصلي "مقتبس"'
