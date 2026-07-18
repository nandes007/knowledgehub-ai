from ingestion.chunk import chunk_markdown


def test_splits_by_header_and_prefixes_breadcrumb():
    text = (
        "# Policy\n\n"
        "## Vacation\n\nEmployees get 20 days of PTO per year.\n\n"
        "## Sick Leave\n\nEmployees get 10 sick days per year.\n"
    )
    chunks = chunk_markdown(text)

    assert len(chunks) == 2
    assert chunks[0].h1 == "Policy"
    assert chunks[0].h2 == "Vacation"
    assert "Policy > Vacation" in chunks[0].text
    assert "20 days of PTO" in chunks[0].text
    assert chunks[1].h2 == "Sick Leave"


def test_long_section_splits_into_multiple_chunks():
    long_text = "# Doc\n\n" + ("word " * 500)
    chunks = chunk_markdown(long_text)

    assert len(chunks) > 1
    assert all(c.h1 == "Doc" for c in chunks)


def test_chunks_have_sequential_index():
    text = "# A\n\ntext one\n\n# B\n\ntext two"
    chunks = chunk_markdown(text)

    assert [c.index for c in chunks] == list(range(len(chunks)))
