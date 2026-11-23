from atti.english import appendix_refs, pages_to_text, parse_text

PAGES = [
    "Labor Law \n\nPart 1: General\n\nChapter 1: Definitions\n\nArticle 1 \n\nThis law shall be\ncalled the Labor  Law.\n\n1 \n\n \n",
    "Labor Law \n\nArticle 2 \n\nSecond: Duties\n\nThe worker shall:\n1. work;\n2. rest.\n\nThird: Disciplinary Rules\n\n2 \n",
    "Labor Law \n\nAppendix\n\nAmending Articles 12, 13, and 14.\nAmending paragraph (1) of Article 48.\nAdding Article 79 bis.\n",
]


def test_parse_text_strips_layout_and_headings():
    doc = parse_text(pages_to_text(PAGES))
    assert doc.articles == {
        1: "This law shall be called the Labor Law.",
        2: "The worker shall: 1. work; 2. rest.",
    }
    assert doc.appendix_article_refs == {12, 13, 14, 48, 79}


def test_appendix_refs_ignores_paragraph_numbers():
    assert appendix_refs("Amending paragraph (3.3) of Article 22") == {22}
