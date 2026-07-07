# Indices and ranges

Reference: <https://developers.google.com/workspace/docs/api/concepts/structure>

Every structural/paragraph element carries `startIndex`/`endIndex` marking its
position within the enclosing segment (body, header, footer, or footnote).

## The UTF-16 gotcha

**Indexes are measured in UTF-16 code units, not Unicode code points or Python
string indices.** Characters outside the Basic Multilingual Plane — most emoji,
some rare scripts — are encoded as UTF-16 surrogate pairs and consume **two** index
positions, not one.

Practically: if a paragraph's text contains an emoji and you need to slice Python's
(UTF-32-ish, one-index-per-codepoint) string representation using the API's
reported indices, naive slicing will be off by one for every such character after
it. Not an issue for Day 1's read-only text extraction (we never compute or send
indices back), but this is the first thing to get right before Day 2's
`batchUpdate` — any `create_suggestion` targeting a range that follows an emoji or
similar character needs index math that accounts for this.

## `startIndex`/`endIndex` placement

These live on the **parent `StructuralElement`**, not inside the `paragraph`/
`table`/`sectionBreak` object it wraps. When walking `body.content`, read the index
off the outer element, not the inner one.

## Gotcha for future `batchUpdate` work (Day 2)

A `batchUpdate` request can contain multiple update requests in one call. Applying
one request can shift the indices that a later request in the *same batch* needs to
target (e.g. inserting text moves everything after it). Google's own guidance:
sequence batch requests carefully, or issue them in an order (e.g.
last-range-first) that avoids invalidating indices you still need. Not relevant to
Day 1's read-only calls, but load-bearing for `create_suggestion` later — don't
forget it exists by the time that work starts.

**Confirmed, single-contiguous-edit-region case needs no compensation:** the
Editor-role "editor marks" path (`updateTextStyle` strikethrough on `[start,
end)` → `insertText` at `end` → `updateTextStyle` bold on `[end, end +
len(replacement))`) doesn't need any index-shift math, because each request's
range is either unaffected by length changes (the strikethrough, which doesn't
change document length) or is *defined by* the immediately preceding request's
own effect (the replacement's range is exactly "wherever we just inserted it,
for however long it is" — known in advance, not derived by re-reading
post-insert state). This is the easy case the note above warns is *not*
generally true — it only holds because there's one edit region, not multiple
disjoint ones in the same batch.
