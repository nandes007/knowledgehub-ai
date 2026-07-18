from dataclasses import dataclass

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

_HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2")]
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 120


@dataclass
class Chunk:
    text: str
    index: int
    h1: str | None
    h2: str | None


def chunk_markdown(text: str) -> list[Chunk]:
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS_TO_SPLIT_ON, strip_headers=False)
    sections = header_splitter.split_text(text)

    char_splitter = RecursiveCharacterTextSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)

    chunks: list[Chunk] = []
    for section in sections:
        h1 = section.metadata.get("h1")
        h2 = section.metadata.get("h2")
        breadcrumb = " > ".join(part for part in (h1, h2) if part)
        for piece in char_splitter.split_text(section.page_content):
            prefixed = f"{breadcrumb}\n\n{piece}" if breadcrumb else piece
            chunks.append(Chunk(text=prefixed, index=len(chunks), h1=h1, h2=h2))
    return chunks
