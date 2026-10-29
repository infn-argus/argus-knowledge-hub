"""A PDF page's text (app/intake/files.py `_page_text`): read as laid out, so a word processor's justified lines
(a Google Docs export, whose plain reading is a word per line) stay lines; the layout's column padding is folded
to one space and its margin taken off; the plain reading is the fallback."""
from app.intake import files, markdown as md

# A running log's page: the plain reading, then the same page as laid out.
PLAIN = " \n \n SPARC  Running  LOG  \n26.10.2026\n \ninterfaccia\n \npython\n \ncompatibile\n \nsolo\n \ncon\n \npython\n \n11)\n"
LAID = ("                       SPARC Running LOG\n\n\n\n"
        "        26.10.2026\n\n"
        "        interfaccia python   matlab che e       compatibile solo con python 11)\n"
        "            → Waist su targhetta con RFD OFF\n")


class Page:
    def __init__(self, laid, plain=PLAIN, fails=False):
        self.laid, self.plain, self.fails = laid, plain, fails

    def extract_text(self, extraction_mode="plain"):
        if extraction_mode == "layout":
            if self.fails:
                raise ValueError("layout unavailable")
            return self.laid
        return self.plain


def test_a_justified_page_keeps_its_lines_and_its_words_together():
    text = files._page_text(Page(LAID))
    assert text.splitlines()[0] == "SPARC Running LOG"                          # the page's margin is gone
    assert "interfaccia python matlab che e compatibile solo con python 11)" in text   # one line, single spaces
    assert "    → Waist su targhetta" in text                                    # its own indent is kept
    assert "\n\n\n" not in text
    as_markdown = md.text_to_markdown(text, wrapped=True)
    assert "compatibile solo con python" in as_markdown
    assert "26.10.2026" in as_markdown.splitlines()                            # a day's heading stays a line


def test_the_plain_reading_is_the_fallback():
    assert files._page_text(Page("", plain="  plain text  ")) == "plain text"
    assert files._page_text(Page(LAID, plain="the plain one", fails=True)) == "the plain one"
