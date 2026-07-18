from ingestion.convert import convert_to_markdown


def test_converts_markdown_file_to_text(tmp_path):
    file_path = tmp_path / "sample.md"
    file_path.write_text("# Hello\n\nWorld")

    result = convert_to_markdown(file_path)

    assert "Hello" in result
    assert "World" in result
