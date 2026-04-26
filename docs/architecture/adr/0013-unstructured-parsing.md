# ADR-0013: `unstructured` library for document parsing

- **Status:** Accepted
- **Date:** 2026-04-26
- **Tags:** ingestion, parsing, ml-libraries

## Context

`Enterprise_RAG_Folder_Structure.md` shows hand-rolled per-format parsers (`pdf_parser.py`, `docx_parser.py`, `html_parser.py`, `markdown_parser.py`, `csv_parser.py`). Writing these from scratch:

- PDF — must handle text extraction, OCR fallback, table extraction, layout preservation. Real PDFs in the wild are nightmares.
- DOCX — XML-zip format; styles, tracked changes, embedded objects.
- HTML — boilerplate stripping, semantic structure.

`unstructured` (open-source by Unstructured.io) handles all of this with a unified `partition()` interface. It returns structured `Element` objects (Title, NarrativeText, Table, ListItem, etc.) which feed naturally into structure-aware chunking.

## Decision

- Default parser: **`unstructured`** library.
- Wrapper interface in `apps/ingestion-service/app/parsers/parser.py`:

```python
class Parser(Protocol):
    def parse(self, blob: BinaryIO, mime_type: str) -> list[ParsedElement]: ...
```

- Single `UnstructuredParser` implementation handles PDF, DOCX, HTML, MD, TXT, CSV, EML, EPUB, PPTX, XLSX (via dispatching `partition_*` from unstructured).
- `ParsedElement` is our shared model with `text`, `element_type`, `metadata` (page_number, section, table_html, etc.). Decouples downstream chunking from unstructured's API.
- For each parsed element we keep `element_type` so structure-aware chunkers can respect headings/tables.
- We pin `unstructured[all-docs]` and bump deliberately. Image OCR (`tesseract`) is included.

For specialized cases (a customer requires a custom XML format, etc.), additional `Parser` adapters are added behind the same interface. v1 ships with only `UnstructuredParser`.

## Consequences

### Positive

- Days of parser-engineering work avoided.
- Format coverage is broader than we'd build ourselves.
- Layout-aware extraction (table HTML, page numbers) feeds rich `chunk_metadata` for citations.
- Active community; maintained by a real company.

### Negative

- Heavy install: `unstructured[all-docs]` brings in `pdfminer`, `tesseract`, `pillow`, `lxml`, `pikepdf`, `python-docx`, ~500MB of deps. Mitigation: ingestion-worker images are large; we accept this and don't put `unstructured` in the API image.
- For very large PDFs (>100MB), unstructured's strategies need tuning (`hi_res` is slow; `fast` misses tables). We expose a per-job `parsing_strategy` config.
- Some failure modes are opaque ("element extraction failed for chunk 42"). We log the raw extraction error and persist a `parse_error` on the document version.

### Neutral

- The `Parser` interface lets us replace `unstructured` later if it becomes a problem.

## Alternatives considered

### Option A — Hand-rolled parsers per format
- **Pros:** Total control.
- **Cons:** Weeks of work; less tested on adversarial inputs.
- **Rejected because:** Time we don't have, for quality we won't match.

### Option B — Per-format libraries directly (`pypdf`, `python-docx`, `BeautifulSoup`)
- **Pros:** Smaller dep footprint.
- **Cons:** N adapters to write; uneven API; we re-implement what unstructured did.
- **Rejected because:** Same reasons as A but with more code.

### Option C — LlamaParse / Reducto API
- **Pros:** Best-in-class quality on complex PDFs.
- **Cons:** Per-doc cost; cloud dependency; conflicts with self-hosted narrative.
- **Possible add-on:** Plug behind `Parser` interface for "premium" tenants in a later phase.

## Trade-off summary

| Dimension | unstructured | Per-format libs | LlamaParse |
|---|---|---|---|
| Eng cost (initial) | Low | Medium-High | Lowest |
| Image footprint | Large (~500MB) | Small (~50MB per format) | Tiny (API call) |
| Format coverage | Broad | Per-library | Best |
| Ongoing cost | $0 | $0 | $$$ per doc |
| Self-hostable | Yes | Yes | No |

## References

- [unstructured](https://github.com/Unstructured-IO/unstructured)
