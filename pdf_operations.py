"""Pure PDF page-operation helpers used by SlicePDF."""
import os
import re
from collections.abc import Iterable


def parse_page_expression(expression: str, total_pages: int) -> list[int]:
    """Return unique zero-based page indexes from a 1-based expression."""
    if total_pages < 1:
        raise ValueError("The PDF has no pages.")
    if not expression.strip():
        raise ValueError("Enter at least one page number or range.")

    pages: list[int] = []
    for item in expression.split(","):
        item = item.strip()
        if not item:
            raise ValueError("Page expressions cannot contain empty items.")
        parts = item.split("-")
        if len(parts) > 2 or any(not part.strip().isdigit() for part in parts):
            raise ValueError(f"Invalid page range: '{item}'.")
        start = int(parts[0])
        end = int(parts[-1])
        if not (1 <= start <= end <= total_pages):
            raise ValueError(f"Pages must be between 1 and {total_pages}.")
        for page in range(start - 1, end):
            if page not in pages:
                pages.append(page)
    return pages


def trim_pages(total_pages: int, from_start: int, from_end: int) -> list[int]:
    """Return pages remaining after removing counts from each end."""
    if from_start < 0 or from_end < 0 or from_start + from_end >= total_pages:
        raise ValueError("Pages removed from the start and end must leave at least one page.")
    return list(range(from_start, total_pages - from_end))


def split_by_count(total_pages: int, page_count: int) -> list[list[int]]:
    """Return zero-based page batches of at most page_count pages."""
    if page_count < 1:
        raise ValueError("Page count must be a positive whole number.")
    return [list(range(start, min(start + page_count, total_pages)))
            for start in range(0, total_pages, page_count)]


def safe_filename(name: str, fallback: str = "output") -> str:
    """Sanitize a user-provided Windows filename while preserving its extension."""
    name = os.path.basename(name.strip())
    stem, extension = os.path.splitext(name)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", stem).strip(" .")
    extension = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", extension).strip()
    stem = stem or fallback
    if not extension:
        extension = ".pdf"
    if extension.lower() != ".pdf":
        extension += ".pdf"
    return f"{stem}{extension}"


def unique_filename(filename: str, destination: str, used: set[str]) -> str:
    """Return filename with a numeric suffix if it already exists or was used."""
    stem, extension = os.path.splitext(filename)
    candidate = filename
    count = 1
    while candidate.casefold() in {item.casefold() for item in used} or os.path.exists(
        os.path.join(destination, candidate)
    ):
        count += 1
        candidate = f"{stem}-{count}{extension}"
    used.add(candidate)
    return candidate


def flatten_pages(groups: Iterable[Iterable[int]]) -> list[int]:
    """Flatten page groups while retaining their requested order."""
    return [page for group in groups for page in group]
