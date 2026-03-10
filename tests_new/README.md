# `tests_new` Structured ID Documentation

This folder uses `export_markdown_structured()` to produce JSON snapshots:

- input: `tests_new/input/*.hwpx`
- output: `tests_new/output/*.structured.json`
- runner: `tests_new/test.py`

Each JSON entry is:

- key: structural ID (canonical location)
- value: extracted text (markdown-editable string unit)

## ID Format

There are two main ID shapes.

1. Normal paragraph/run text

`s{section}.p{paragraph}.r{run}`

2. Text inside table cells (nested in a run)

`s{section}.p{paragraph}.r{run}.tbl{table}.tr{row}.tc{cell}.p{cell_paragraph}.r{cell_run}`

Optional page-index form (explicit-break based):

`s{section}.pg{page}.p{paragraph}.r{run}`

Optional paragraph-level-only form:

`s{section}.p{paragraph}`

## Segment Meaning

- `sN`: section index
- `pN`: paragraph index (top-level paragraph under section)
- `rN`: run index inside that paragraph
- `tblN`: table index inside the parent run
- `trN`: table row index
- `tcN`: table cell index in the row
- `pN` (after `tcN`): paragraph index inside the cell
- `rN` (after cell paragraph): run index inside the cell paragraph
- `pgN` (optional): explicit page index derived from section/page-break metadata

All indices are **1-based**.

## Examples

From generated snapshots:

- `s1.p2.r1`
  - section 1, paragraph 2, run 1
- `s1.p3.r1.tbl1.tr1.tc2.p1.r1`
  - section 1, paragraph 3, run 1
  - first table in that run
  - row 1, cell 2
  - first paragraph/run inside that cell

## Practical Notes

- IDs are designed for round-trip edit mapping.
- Multiple IDs can belong to what looks like one visible sentence (because HWPX splits content across runs/text nodes).
- A new blank paragraph may already exist in a fresh document, so visible content can start at `p2`.
- Empty text fragments may be skipped depending on exporter options (`skip_empty=True` by default).
- Run values flatten all text nodes (`<hp:t>`) inside the run into one string.
- `pgN` is **not** renderer-accurate pagination. It is a deterministic index based on:
  - section `startNum.page` (if present, else 1)
  - paragraph `pageBreak="1"` transitions
- `paragraph_level_only=True` flattens direct run text into paragraph keys.
- Table entries are still emitted in structured form unless `include_tables=False`.
  In this mode, table keys are flattened to cell-paragraph level: `...tcN.pN`.

## Snapshot Commands

Generate/update snapshots:

```bash
uv run python tests_new/test.py
```

Check snapshots without writing:

```bash
uv run python tests_new/test.py --check
```

Paragraph-level keys + structured table entries:

```bash
uv run python tests_new/test.py --paragraph-level-only
```
