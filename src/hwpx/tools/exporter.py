"""Export HWPX document content to plain text, HTML, and Markdown formats.

All exporters accept either an :class:`~hwpx.document.HwpxDocument` instance
or raw HWPX file bytes and produce a string in the target format.
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING, Sequence
from xml.etree import ElementTree as ET
from zipfile import ZipFile

if TYPE_CHECKING:
    from ..document import HwpxDocument

__all__ = [
    "export_text",
    "export_html",
    "export_markdown",
    "export_markdown_structured",
]

# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------

_HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HP = f"{{{_HP_NS}}}"

_SECTION_RE = re.compile(r"^Contents/section\d+\.xml$")


# ---------------------------------------------------------------------------
# Internal traversal helpers
# ---------------------------------------------------------------------------


def _section_xmls(source: HwpxDocument | bytes) -> list[ET.Element]:
    """Return a list of section root elements from *source*."""
    if isinstance(source, bytes):
        with ZipFile(io.BytesIO(source)) as zf:
            names = sorted(n for n in zf.namelist() if _SECTION_RE.match(n))
            return [ET.fromstring(zf.read(n)) for n in names]
    else:
        # HwpxDocument – use the in-memory oxml tree
        return [sec.element for sec in source._root.sections]


def _iter_paragraphs(section: ET.Element) -> list[ET.Element]:
    """Yield top-level ``<hp:p>`` elements in document order."""
    return section.findall(f"{_HP}p")


def _paragraph_text(p: ET.Element) -> str:
    """Extract concatenated text from a paragraph's direct runs only.

    Text inside nested objects (tables, shapes, etc.) is excluded to
    prevent duplication.
    """
    parts: list[str] = []
    # Only traverse direct <hp:run> children of the paragraph
    for run in p.findall(f"{_HP}run"):
        for child in run:
            if child.tag == f"{_HP}t":
                if child.text:
                    parts.append(child.text)
    return "".join(parts)


def _is_table(el: ET.Element) -> bool:
    return el.tag == f"{_HP}tbl" or el.tag.endswith("}tbl")


def _table_cells_text(tbl: ET.Element) -> list[list[str]]:
    """Return a row-major 2D list of cell texts from a table element."""
    rows: list[list[str]] = []
    for tr in tbl.findall(f"{_HP}tr"):
        row: list[str] = []
        for tc in tr.findall(f"{_HP}tc"):
            cell_parts: list[str] = []
            for t in tc.findall(f".//{_HP}t"):
                if t.text:
                    cell_parts.append(t.text)
            row.append("".join(cell_parts).strip())
        rows.append(row)
    return rows


def _find_tables(p: ET.Element) -> list[ET.Element]:
    """Find all ``<hp:tbl>`` elements inside a paragraph's runs."""
    return p.findall(f".//{_HP}tbl")


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _text_from_t(t: ET.Element) -> str:
    """Return flattened text content inside a ``<hp:t>`` node."""
    return "".join(t.itertext())


def _section_start_page(section: ET.Element) -> int:
    """Return explicit section start page from ``<hp:startNum page=...>``.

    Falls back to 1 when unavailable or invalid.
    """
    sec_pr = section.find(f".//{_HP}secPr")
    if sec_pr is None:
        return 1
    start_num = sec_pr.find(f"{_HP}startNum")
    if start_num is None:
        return 1
    raw = start_num.get("page")
    if raw is None:
        return 1
    try:
        value = int(raw)
    except ValueError:
        return 1
    return value if value > 0 else 1


# ---------------------------------------------------------------------------
# Plain-text exporter
# ---------------------------------------------------------------------------


def export_text(
    source: HwpxDocument | bytes,
    *,
    paragraph_separator: str = "\n",
    section_separator: str = "\n\n",
    include_tables: bool = True,
) -> str:
    """Export document content as plain text.

    Args:
        source: An :class:`~hwpx.document.HwpxDocument` or HWPX archive
            bytes.
        paragraph_separator: String inserted between paragraphs.
        section_separator: String inserted between sections.
        include_tables: Whether to include table cell text inline.

    Returns:
        The full document text as a single string.
    """
    sections = _section_xmls(source)
    section_texts: list[str] = []

    for section_root in sections:
        paragraphs = _iter_paragraphs(section_root)
        para_texts: list[str] = []
        for p in paragraphs:
            text = _paragraph_text(p)
            if text:
                para_texts.append(text)
            if include_tables:
                for tbl in _find_tables(p):
                    rows = _table_cells_text(tbl)
                    for row in rows:
                        para_texts.append("\t".join(row))
        section_texts.append(paragraph_separator.join(para_texts))

    return section_separator.join(section_texts)


# ---------------------------------------------------------------------------
# HTML exporter
# ---------------------------------------------------------------------------


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def export_html(
    source: HwpxDocument | bytes,
    *,
    include_tables: bool = True,
    full_document: bool = True,
    title: str = "HWPX Document",
) -> str:
    """Export document content as HTML.

    Args:
        source: An :class:`~hwpx.document.HwpxDocument` or HWPX archive bytes.
        include_tables: Whether to render tables as ``<table>`` elements.
        full_document: Wrap output in a complete HTML5 document structure.
        title: Title for the ``<title>`` element when *full_document* is True.

    Returns:
        An HTML string.
    """
    sections = _section_xmls(source)
    body_parts: list[str] = []

    for sec_idx, section_root in enumerate(sections):
        if sec_idx > 0:
            body_parts.append("<hr />")
        paragraphs = _iter_paragraphs(section_root)
        for p in paragraphs:
            text = _paragraph_text(p)
            if text:
                body_parts.append(f"<p>{_escape_html(text)}</p>")

            if include_tables:
                for tbl in _find_tables(p):
                    rows = _table_cells_text(tbl)
                    if rows:
                        body_parts.append("<table border=\"1\">")
                        for row in rows:
                            body_parts.append("  <tr>")
                            for cell in row:
                                body_parts.append(
                                    f"    <td>{_escape_html(cell)}</td>"
                                )
                            body_parts.append("  </tr>")
                        body_parts.append("</table>")

    body = "\n".join(body_parts)

    if full_document:
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"ko\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            f"  <title>{_escape_html(title)}</title>\n"
            "</head>\n"
            "<body>\n"
            f"{body}\n"
            "</body>\n"
            "</html>"
        )
    return body


# ---------------------------------------------------------------------------
# Markdown exporter
# ---------------------------------------------------------------------------


def export_markdown(
    source: HwpxDocument | bytes,
    *,
    include_tables: bool = True,
    section_separator: str = "\n---\n\n",
) -> str:
    """Export document content as Markdown.

    Args:
        source: An :class:`~hwpx.document.HwpxDocument` or HWPX archive bytes.
        include_tables: Whether to render tables as Markdown tables.
        section_separator: String inserted between sections.

    Returns:
        A Markdown formatted string.
    """
    sections = _section_xmls(source)
    section_parts: list[str] = []

    for section_root in sections:
        paragraphs = _iter_paragraphs(section_root)
        lines: list[str] = []
        for p in paragraphs:
            text = _paragraph_text(p)
            if text:
                lines.append(text)
                lines.append("")  # blank line between paragraphs

            if include_tables:
                for tbl in _find_tables(p):
                    rows = _table_cells_text(tbl)
                    if rows:
                        # Header row
                        header = rows[0]
                        lines.append(
                            "| " + " | ".join(header) + " |"
                        )
                        lines.append(
                            "| " + " | ".join("---" for _ in header) + " |"
                        )
                        # Data rows
                        for row in rows[1:]:
                            # Pad if row is shorter than header
                            padded = row + [""] * max(0, len(header) - len(row))
                            lines.append(
                                "| " + " | ".join(padded[: len(header)]) + " |"
                            )
                        lines.append("")

        section_parts.append("\n".join(lines).rstrip())

    return section_separator.join(section_parts)


def export_markdown_structured(
    source: HwpxDocument | bytes,
    *,
    include_tables: bool = True,
    skip_empty: bool = True,
    include_page_index: bool = False,
    paragraph_level_only: bool = False,
) -> dict[str, str]:
    """Export document text fragments as Markdown keyed by structural IDs.

    ID format:
        - default: ``s{section}.p{paragraph}.r{run}``
        - with page index: ``s{section}.pg{page}.p{paragraph}.r{run}``
        - table text: ``...tbl{table}.tr{row}.tc{cell}.p{paragraph}.r{run}``
        - paragraph-level mode: ``s{section}.p{paragraph}``

    Notes:
        - Indices are 1-based.
        - Paragraphs are top-level ``<hp:p>`` children of each section.
        - Table cell content is represented with additional nested coordinates.
        - ``pg`` is an explicit-break index derived from section ``startNum.page``
          and paragraph ``pageBreak`` flags. It is not rendered pagination.
        - Text-node granularity is flattened; each run value combines all of its
          ``<hp:t>`` descendants.
        - ``paragraph_level_only=True`` flattens each paragraph's direct run text
          into one value. Table content remains structured when
          ``include_tables=True``.
    """
    sections = _section_xmls(source)
    mapping: dict[str, str] = {}

    for s_idx, section_root in enumerate(sections, start=1):
        paragraphs = _iter_paragraphs(section_root)
        page_idx = _section_start_page(section_root)
        for p_idx, paragraph in enumerate(paragraphs, start=1):
            if p_idx > 1 and paragraph.get("pageBreak") == "1":
                page_idx += 1

            if include_page_index:
                base = f"s{s_idx}.pg{page_idx}.p{p_idx}"
            else:
                base = f"s{s_idx}.p{p_idx}"

            if paragraph_level_only:
                parts: list[str] = []
                for run in paragraph.findall(f"{_HP}run"):
                    for child in run:
                        if _local_name(child.tag) == "t":
                            parts.append(_text_from_t(child))
                paragraph_text = "".join(parts)
                if not (skip_empty and paragraph_text == ""):
                    mapping[base] = paragraph_text

                if include_tables:
                    for r_idx, run in enumerate(paragraph.findall(f"{_HP}run"), start=1):
                        tbl_idx = 0
                        for child in run:
                            if _local_name(child.tag) != "tbl":
                                continue
                            tbl_idx += 1
                            for tr_idx, tr in enumerate(child.findall(f"{_HP}tr"), start=1):
                                for tc_idx, tc in enumerate(tr.findall(f"{_HP}tc"), start=1):
                                    cell_paragraphs = tc.findall(f".//{_HP}p")
                                    for cp_idx, cp in enumerate(cell_paragraphs, start=1):
                                        paragraph_parts: list[str] = []
                                        for cr in cp.findall(f"{_HP}run"):
                                            paragraph_parts.extend(
                                                _text_from_t(ct) for ct in cr.findall(f"{_HP}t")
                                            )
                                        cell_paragraph_text = "".join(paragraph_parts)
                                        if skip_empty and cell_paragraph_text == "":
                                            continue
                                        key = (
                                            f"{base}.r{r_idx}"
                                            f".tbl{tbl_idx}.tr{tr_idx}.tc{tc_idx}"
                                            f".p{cp_idx}"
                                        )
                                        mapping[key] = cell_paragraph_text
                continue

            for r_idx, run in enumerate(paragraph.findall(f"{_HP}run"), start=1):
                run_text_parts: list[str] = []
                tbl_idx = 0
                for child in run:
                    tag = _local_name(child.tag)
                    if tag == "t":
                        run_text_parts.append(_text_from_t(child))
                        continue

                    if include_tables and tag == "tbl":
                        tbl_idx += 1
                        for tr_idx, tr in enumerate(child.findall(f"{_HP}tr"), start=1):
                            for tc_idx, tc in enumerate(tr.findall(f"{_HP}tc"), start=1):
                                cell_paragraphs = tc.findall(f".//{_HP}p")
                                for cp_idx, cp in enumerate(cell_paragraphs, start=1):
                                    runs = cp.findall(f"{_HP}run")
                                    for cr_idx, cr in enumerate(runs, start=1):
                                        cell_parts = [_text_from_t(ct) for ct in cr.findall(f"{_HP}t")]
                                        cell_text = "".join(cell_parts)
                                        if skip_empty and cell_text == "":
                                            continue
                                        key = (
                                            f"{base}.r{r_idx}"
                                            f".tbl{tbl_idx}.tr{tr_idx}.tc{tc_idx}"
                                            f".p{cp_idx}.r{cr_idx}"
                                        )
                                        mapping[key] = cell_text

                run_text = "".join(run_text_parts)
                if skip_empty and run_text == "":
                    continue
                mapping[f"{base}.r{r_idx}"] = run_text

    return mapping
