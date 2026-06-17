# Design: Split Report Writing and DOCX Conversion Rules

## Context

The current `docs/report-writing-rules.md` defines broad writing rules for reports: no bold formatting, manual heading numbering, paragraph-based prose, and academic tone. The recent work on `docs/TabPFN3_DKA_AKI.md` and `docs/TabPFN3_DKA_AKI.docx` exposed additional recurring rules that are more specific to tables, Pandoc conversion, and DOCX post-processing.

Those rules should not all live in the same section because they serve different readers. Authors need concise Markdown writing rules. The conversion/post-processing step needs technical rules about Word table rendering, line breaks, table widths, captions, and verification.

## Goal

Split the guidance into two linked documents:

1. `docs/report-writing-rules.md` remains the source-authoring standard for Markdown reports.
2. `docs/docx-conversion-rules.md` becomes the technical standard for Pandoc-to-DOCX conversion and DOCX post-processing.

This keeps writing guidance readable while preserving the implementation details needed to produce stable Word output.

## Proposed Changes

### `docs/report-writing-rules.md`

Add source-writing rules for report authors and AI agents:

- Use Pandoc table captions in the form `Table: Bảng N. ...`.
- Place a stable anchor such as `<a id="bang-1"></a>` immediately before each table that appears in the table list.
- Keep table text unbolded, including header cells, to match the existing no-bold rule.
- For multi-level categorical variables, put the overall p-value only on the parent variable row. Child category rows should leave the p-value cell blank or use a single agreed placeholder. Do not repeat the same p-value on each child row.
- When an intended Word table cell needs multiple visual lines, write the Markdown cell with explicit `<br>` separators and document that conversion must preserve them as real Word line breaks.
- For model-configuration tables, write one parameter per visual line in the final output. Avoid dense `key: value;key: value` rendering in the Word result.
- Keep table, figure, caption, and list-of-tables/list-of-figures naming consistent.

### `docs/docx-conversion-rules.md`

Create a new technical conversion guide covering:

- The conversion pipeline from Markdown to DOCX and the required post-processing step.
- DOCX tables should use fixed layout and explicit DXA widths when stable rendering is required.
- All report tables should render at 12 pt unless the user explicitly requests otherwise.
- Markdown `<br>` inside a table cell must be verified as real Word line breaks (`w:br`) after conversion.
- Table widths should be chosen by content type rather than divided equally by default.
- Multi-column metric tables should preserve readable headers without shrinking the font.
- Captions should be converted to proper Word sequence fields for table and figure lists.
- Final verification should include DOCX ZIP integrity, XML spot checks for table widths and line breaks, LibreOffice PDF conversion, and rendered-page inspection for the key table pages.

## Non-Goals

This design does not change the research content, table values, p-values, references, figures, or existing DOCX output. It only defines where the documentation rules should live and what topics they should cover.

## Validation

After implementation, validate by checking that:

- `docs/report-writing-rules.md` remains focused on author-facing Markdown rules.
- `docs/docx-conversion-rules.md` contains the technical Word/Pandoc rules.
- The two documents cross-reference each other where needed.
- No rule contradicts the existing no-bold, manual-heading, and paragraph-prose standards.
