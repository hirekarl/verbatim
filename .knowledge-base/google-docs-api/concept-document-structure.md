# Document body structure

Reference: <https://developers.google.com/workspace/docs/api/concepts/structure>

A document's `body` is a sequence of `StructuralElement` objects. Each `StructuralElement` is "filled in" by exactly one of a few content types:

- **`paragraph`** — a text block terminated by a newline. The common case for ordinary prose.
- **`table`** — tabular data.
- **`sectionBreak`** — section divisions.
- **`tableOfContents`** — an auto-generated table of contents.

## Paragraphs

A `paragraph` has:

- `elements` — a list of `ParagraphElement`s, the actual content (see below).
- `paragraphStyle` (optional) — formatting, including `namedStyleType` (`NORMAL_TEXT`, `HEADING_1`..`HEADING_6`, `TITLE`, `SUBTITLE`, etc.). **This is where heading level lives** — there's no separate "heading" element type.
- `bullet` (optional) — present for list items.

## Paragraph elements

- **`textRun`** — a contiguous string of text sharing one text style. Its `content` field is the actual text (includes the trailing `\n` for the paragraph's line break). Most of a document's text lives here.
- `autoText` — dynamic content like page numbers.
- `columnBreak`, `equation`, `pageBreak`, `footnoteReference`, etc. — not relevant to extracting plain body text/headings.

## What this means for `_extract_title_body_and_headings`

To get plain body text: walk `body.content`, and for every element that has a `paragraph`, concatenate every `paragraph.elements[].textRun.content`. To get headings: same walk, but check `paragraph.paragraphStyle.namedStyleType` — if it starts with `"HEADING"`, record `(level, text)` where `level` is parsed from the suffix digit (`HEADING_1` → level 1, etc.) and `text` is that paragraph's concatenated `textRun.content`.

### Gotchas

- Not every `StructuralElement` has a `paragraph` key — `table` and `sectionBreak` elements don't, so any walk must check which key is present rather than assuming `paragraph` always exists.
- `startIndex`/`endIndex` live on the parent `StructuralElement`, not inside `paragraph`/`table`/`sectionBreak` themselves. See [`concept-indices-and-ranges.md`](concept-indices-and-ranges.md).
- A single logical sentence can be split across multiple `textRun`s if its formatting changes mid-sentence (e.g. part bold, part not) — don't assume one `textRun` per paragraph.
