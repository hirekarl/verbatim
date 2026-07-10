"""Generate the Saturday demo deck for Verbatim.

Standalone script, not part of the `verbatim` package: run with
`uv run --with python-pptx python presentation/build_deck.py`. Content is
transcribed verbatim from `presentation/PRESENTATION_PLAN.md` Sections A/B;
design language (colors, type, icon geometry) is documented in the plan this
script implements, not repeated here.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.slide import Slide
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).parent
ICON_PATH = HERE.parent / "addon" / "icon.png"
OUTPUT_PATH = HERE / "Verbatim - Saturday Demo.pptx"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

BLUE = RGBColor(0x42, 0x85, 0xF4)
INK = RGBColor(0x20, 0x21, 0x24)
SECONDARY = RGBColor(0x5F, 0x63, 0x68)
BG = RGBColor(0xF8, 0xF9, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DIVIDER = RGBColor(0xDA, 0xDC, 0xE0)

CATEGORY_COLORS = {
    "tone_drift": RGBColor(0x8E, 0x24, 0xAA),
    "information_hierarchy": RGBColor(0x1E, 0x88, 0xE5),
    "cta_cadence": RGBColor(0x00, 0x89, 0x7B),
    "readability": RGBColor(0xF4, 0x51, 0x1E),
    "formatting_and_style": RGBColor(0x6D, 0x4C, 0x41),
    "channel_constraints": RGBColor(0x39, 0x49, 0xAB),
    "banned_words_and_competitors": RGBColor(0xC6, 0x28, 0x28),
}

HEAD_FONT = "Google Sans"
BODY_FONT = "Roboto"


def set_run(run, *, font=BODY_FONT, size=18, color=INK, bold=False, italic=False):
    """Apply consistent font styling to a text run."""
    run.font.name = font
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic


def add_background(slide: Slide, color=WHITE):
    """Fill the slide background."""
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(0), Emu(0), SLIDE_W, SLIDE_H)
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.line.fill.background()
    rect.shadow.inherit = False
    # Push the background behind everything else added to the slide.
    sp_tree = slide.shapes._spTree
    sp_tree.remove(rect._element)
    sp_tree.insert(2, rect._element)
    return rect


def add_footer(slide: Slide, page_num: int):
    """Small rounded-square 'V' watermark + page number, bottom-right."""
    size = Inches(0.35)
    x = SLIDE_W - Inches(0.9)
    y = SLIDE_H - Inches(0.7)
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, size, size)
    box.adjustments[0] = 0.28
    box.fill.solid()
    box.fill.fore_color.rgb = BLUE
    box.line.fill.background()
    box.shadow.inherit = False
    tf = box.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "V"
    set_run(run, font=HEAD_FONT, size=14, color=WHITE, bold=True)

    num_box = slide.shapes.add_textbox(x - Inches(0.5), y, Inches(0.45), size)
    num_tf = num_box.text_frame
    num_tf.word_wrap = False
    p2 = num_tf.paragraphs[0]
    p2.alignment = PP_ALIGN.RIGHT
    run2 = p2.add_run()
    run2.text = str(page_num)
    set_run(run2, size=12, color=SECONDARY)


def add_title(slide: Slide, text: str, *, align=PP_ALIGN.LEFT, top=None, width=None):
    """Slide title in Google Sans Bold."""
    if top is None:
        top = Inches(0.6)
    if width is None:
        width = Inches(12.0)
    box = slide.shapes.add_textbox(Inches(0.7), top, width, Inches(1.2))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    set_run(run, font=HEAD_FONT, size=40, color=INK, bold=True)
    return box


def add_subhead(slide: Slide, text: str, *, top, align=PP_ALIGN.LEFT, size=20):
    """Secondary supporting line under a title."""
    box = slide.shapes.add_textbox(Inches(0.7), top, Inches(12.0), Inches(0.7))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    set_run(run, size=size, color=SECONDARY)
    return box


def add_rounded_container(
    slide: Slide, x, y, w, h, *, fill=BLUE, radius=0.18
) -> object:
    """A rounded-square container echoing addon/icon.png's geometry."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.adjustments[0] = radius
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def add_category_legend(slide: Slide, entries: list[tuple[str, str, str]], *, top):
    """A column of color-swatch + name + plain-language gloss rows.

    `entries` is (CATEGORY_COLORS key, display name, gloss). Reused across
    the deterministic categories (slide 3) and the LLM-judged ones (slide 4)
    so both legends read as one visual system.
    """
    for i, (key, name, gloss) in enumerate(entries):
        row_y = top + Inches(0.95) * i
        swatch = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(1.0),
            row_y,
            Inches(0.5),
            Inches(0.5),
        )
        swatch.adjustments[0] = 0.3
        swatch.fill.solid()
        swatch.fill.fore_color.rgb = CATEGORY_COLORS[key]
        swatch.line.fill.background()
        swatch.shadow.inherit = False

        name_box = slide.shapes.add_textbox(
            Inches(1.8), row_y - Inches(0.05), Inches(4.3), Inches(0.6)
        )
        name_box.text_frame.word_wrap = True
        pn = name_box.text_frame.paragraphs[0]
        rn = pn.add_run()
        rn.text = name
        set_run(rn, font=HEAD_FONT, size=20, color=INK, bold=True)

        gloss_box = slide.shapes.add_textbox(
            Inches(6.2), row_y - Inches(0.02), Inches(6.3), Inches(0.6)
        )
        gloss_box.text_frame.word_wrap = True
        pg = gloss_box.text_frame.paragraphs[0]
        rg = pg.add_run()
        rg.text = gloss
        set_run(rg, size=18, color=SECONDARY, italic=True)


def add_notes(slide: Slide, lines: list[tuple[str | None, str, str | None]]):
    """Populate speaker notes verbatim from PRESENTATION_PLAN.md Section B.

    Each entry is (speaker, quoted_line, stage_direction) — stage_direction
    (a parenthetical) renders italic on its own trailing run, never spoken.
    """
    notes_tf = slide.notes_slide.notes_text_frame
    notes_tf.clear()
    for i, (speaker, quote, stage) in enumerate(lines):
        p = notes_tf.paragraphs[0] if i == 0 else notes_tf.add_paragraph()
        if speaker:
            r = p.add_run()
            r.text = f"{speaker}: "
            set_run(r, size=14, color=INK, bold=True)
        r2 = p.add_run()
        r2.text = quote
        set_run(r2, size=14, color=INK)
        if stage:
            r3 = p.add_run()
            r3.text = f"  {stage}"
            set_run(r3, size=14, color=SECONDARY, italic=True)


def new_slide() -> Slide:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide)
    return slide


# --------------------------------------------------------------------------
# Slide 1 — Title
# --------------------------------------------------------------------------


def build_slide_1():
    slide = new_slide()
    if ICON_PATH.exists():
        slide.shapes.add_picture(
            str(ICON_PATH), Inches(5.867), Inches(1.6), Inches(1.6), Inches(1.6)
        )
    add_title(slide, "Verbatim", align=PP_ALIGN.CENTER, top=Inches(3.4))
    add_subhead(
        slide,
        "for copywriters",
        top=Inches(4.15),
        align=PP_ALIGN.CENTER,
        size=22,
    )
    add_subhead(
        slide,
        "20–30% of editing time → policing mechanical fixes",
        top=Inches(5.6),
        align=PP_ALIGN.CENTER,
        size=16,
    )
    add_footer(slide, 1)
    add_notes(
        slide,
        [
            ("KARL", '"I\'m Karl."', None),
            (
                "CHRISTINA",
                "\"I'm Christina. We built Verbatim for copywriters — the "
                "people who write a company's marketing emails, social posts, "
                'and web copy."',
                None,
            ),
            (
                "KARL",
                '"On a lot of marketing teams, the lead editor spends twenty '
                "to thirty percent of their editing time just policing "
                "mechanical stuff — voice, tone, formatting — instead of "
                "the actual writing and strategy. Right before a piece goes "
                "out, it needs that check. Verbatim automates it, so editors "
                'get their time back."',
                None,
            ),
        ],
    )


# --------------------------------------------------------------------------
# Slide 2 — Why two documents
# --------------------------------------------------------------------------


def add_document_glyph(slide: Slide, cx, cy):
    """Three thin white bars on a blue card, suggesting a document."""
    for i in range(3):
        bar = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Emu(int(cx - Inches(0.5))),
            Emu(int(cy + Inches(0.28) * i)),
            Inches(1.0),
            Inches(0.1),
        )
        bar.adjustments[0] = 0.5
        bar.fill.solid()
        bar.fill.fore_color.rgb = WHITE
        bar.line.fill.background()
        bar.shadow.inherit = False


def build_slide_2():
    slide = new_slide()
    add_title(slide, "Why two documents")

    card_w, card_h = Inches(4.6), Inches(2.6)
    top = Inches(3.0)
    left1 = Inches(1.2)
    left2 = Inches(7.5)

    add_rounded_container(slide, left1, top, card_w, card_h)
    add_rounded_container(slide, left2, top, card_w, card_h)

    add_document_glyph(slide, int(left1 + card_w / 2), int(top + Inches(0.5)))
    add_document_glyph(slide, int(left2 + card_w / 2), int(top + Inches(0.5)))

    for card_left, label, gloss in (
        (left1, "Brand Style Guide", "permanent voice & rules"),
        (left2, "Campaign Brief", "specific to this one piece"),
    ):
        label_box = slide.shapes.add_textbox(
            card_left, top + Inches(1.5), card_w, Inches(0.5)
        )
        p = label_box.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = label
        set_run(r, font=HEAD_FONT, size=22, color=WHITE, bold=True)

        gloss_box = slide.shapes.add_textbox(
            card_left, top + Inches(2.0), card_w, Inches(0.5)
        )
        pg = gloss_box.text_frame.paragraphs[0]
        pg.alignment = PP_ALIGN.CENTER
        rg = pg.add_run()
        rg.text = gloss
        set_run(rg, size=14, color=WHITE)

    plus_box = slide.shapes.add_textbox(
        Inches(6.1), top + Inches(0.9), Inches(1.1), Inches(0.8)
    )
    pp = plus_box.text_frame.paragraphs[0]
    pp.alignment = PP_ALIGN.CENTER
    rp = pp.add_run()
    rp.text = "+"
    set_run(rp, font=HEAD_FONT, size=44, color=BLUE, bold=True)

    add_footer(slide, 2)
    add_notes(
        slide,
        [
            (
                "CHRISTINA",
                '"Every piece of copy gets checked against two different '
                "things. First, a brand style guide — a company's "
                "permanent voice and rules. Always sounds like this, never "
                "says that. The one we're demoing with today is built from "
                "Mailchimp's publicly published content style guide.\"",
                None,
            ),
            (
                "KARL",
                "\"Second, the campaign brief — what's specific to just "
                "this one piece? Who it's going to, what we want the reader "
                'to do, and by when."',
                None,
            ),
            (
                "CHRISTINA",
                "\"You need both. Copy that's perfectly on-brand but ignores "
                "what this campaign needs is useless. Copy that nails the "
                "ask but doesn't sound anything like the company is going "
                'to confuse people."',
                None,
            ),
            (
                "KARL",
                '"Checking both by hand means one person holding a style '
                "guide in one hand and a brief in the other, line by line. "
                "Two reviewers won't always catch the same things, and it's "
                "slow. That's the gap Verbatim closes.\"",
                None,
            ),
        ],
    )


# --------------------------------------------------------------------------
# Loop icon helpers (Observe / Decide / Act / Checkpoint)
# --------------------------------------------------------------------------


def add_icon_container(slide: Slide, cx, cy, size=None):
    if size is None:
        size = Inches(1.8)
    x = Emu(int(cx - size / 2))
    y = Emu(int(cy - size / 2))
    return add_rounded_container(slide, x, y, size, size, radius=0.22)


def _icon_scale(size) -> float:
    """Glyph offsets below are tuned for a 1.8in container; scale for others."""
    return size / Inches(1.8)


def add_observe_icon(slide: Slide, cx, cy, size=None):
    if size is None:
        size = Inches(1.8)
    add_icon_container(slide, cx, cy, size=size)
    k = _icon_scale(size)
    lens_d = int(Inches(0.7) * k)
    lens = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Emu(int(cx - Inches(0.5) * k)),
        Emu(int(cy - Inches(0.5) * k)),
        lens_d,
        lens_d,
    )
    lens.fill.background()
    lens.line.color.rgb = WHITE
    lens.line.width = Pt(5)
    lens.shadow.inherit = False

    handle = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Emu(int(cx + Inches(0.15) * k)),
        Emu(int(cy + Inches(0.15) * k)),
        int(Inches(0.55) * k),
        int(Inches(0.14) * k),
    )
    handle.rotation = 45
    handle.adjustments[0] = 0.5
    handle.fill.solid()
    handle.fill.fore_color.rgb = WHITE
    handle.line.fill.background()
    handle.shadow.inherit = False


def add_decide_icon(slide: Slide, cx, cy, size=None):
    if size is None:
        size = Inches(1.8)
    add_icon_container(slide, cx, cy, size=size)
    k = _icon_scale(size)
    fb = slide.shapes.build_freeform(
        Emu(int(cx - Inches(0.45) * k)), Emu(int(cy + Inches(0.05) * k))
    )
    fb.add_line_segments(
        [
            (Emu(int(cx - Inches(0.1) * k)), Emu(int(cy + Inches(0.4) * k))),
            (Emu(int(cx + Inches(0.5) * k)), Emu(int(cy - Inches(0.35) * k))),
        ],
        close=False,
    )
    shape = fb.convert_to_shape()
    shape.line.color.rgb = WHITE
    shape.line.width = Pt(max(3, 6 * k))
    shape.fill.background()
    shape.shadow.inherit = False


def add_act_icon(slide: Slide, cx, cy, size=None):
    if size is None:
        size = Inches(1.8)
    add_icon_container(slide, cx, cy, size=size)
    k = _icon_scale(size)
    body = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Emu(int(cx - Inches(0.55) * k)),
        Emu(int(cy - Inches(0.12) * k)),
        int(Inches(0.9) * k),
        int(Inches(0.22) * k),
    )
    body.rotation = -30
    body.adjustments[0] = 0.5
    body.fill.solid()
    body.fill.fore_color.rgb = WHITE
    body.line.fill.background()
    body.shadow.inherit = False

    tip = slide.shapes.add_shape(
        MSO_SHAPE.ISOSCELES_TRIANGLE,
        Emu(int(cx + Inches(0.3) * k)),
        Emu(int(cy - Inches(0.35) * k)),
        int(Inches(0.22) * k),
        int(Inches(0.22) * k),
    )
    tip.rotation = 60
    tip.fill.solid()
    tip.fill.fore_color.rgb = WHITE
    tip.line.fill.background()
    tip.shadow.inherit = False


def add_checkpoint_icon(slide: Slide, cx, cy, size=None):
    if size is None:
        size = Inches(1.8)
    add_icon_container(slide, cx, cy, size=size)
    k = _icon_scale(size)
    for dx in (-Inches(0.18) * k, Inches(0.05) * k):
        bar = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Emu(int(cx + dx)),
            Emu(int(cy - Inches(0.35) * k)),
            int(Inches(0.16) * k),
            int(Inches(0.7) * k),
        )
        bar.adjustments[0] = 0.5
        bar.fill.solid()
        bar.fill.fore_color.rgb = WHITE
        bar.line.fill.background()
        bar.shadow.inherit = False


# --------------------------------------------------------------------------
# Slide 3 — Loop: Observe
# --------------------------------------------------------------------------


def build_slide_3():
    slide = new_slide()
    add_title(slide, "Loop — Observe", width=Inches(9.5))
    # Small badge beside the title, matching slide 4's fix — a full-size
    # icon stacked above the legend collided with the title text.
    add_observe_icon(slide, int(Inches(11.9)), int(Inches(1.2)), size=Inches(1.0))

    caption = slide.shapes.add_textbox(
        Inches(0.7), Inches(1.9), Inches(11.0), Inches(0.5)
    )
    p = caption.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = "Docs/Drive API pull, then Christina's evaluator — regex, no model call"
    set_run(r, size=18, color=SECONDARY)

    add_category_legend(
        slide,
        [
            (
                "banned_words_and_competitors",
                "Banned words & competitors",
                "off-brand terms, no-go phrases",
            ),
            (
                "formatting_and_style",
                "Formatting & style",
                "commas, quotes, mechanical rules",
            ),
            (
                "channel_constraints",
                "Channel constraints",
                "character caps & rules per channel",
            ),
        ],
        top=Inches(2.6),
    )

    add_footer(slide, 3)
    add_notes(
        slide,
        [
            (
                "KARL",
                '"My half of the work involved getting the actual content '
                "onto the page. When a copywriter clicks ‘Run Verbatim "
                "Audit’ in the sidebar, with the brief and channel already "
                "filled in, Verbatim pulls the draft and the brief straight "
                "out of Google Docs — no copying and pasting into another "
                'tool."',
                None,
            ),
            (
                "CHRISTINA",
                "\"While that's happening, my evaluator runs over the text "
                "— a rules engine I built and tested against real sample "
                "copy. It checks what's black-and-white: banned words, "
                "formatting details like commas and quotation marks, and "
                "channel limits — things like Twitter's character cap, or "
                "an email subject line that's too long or too generic. None "
                "of that touches the model, it's just pattern matching.\"",
                None,
            ),
        ],
    )


# --------------------------------------------------------------------------
# Slide 4 — Loop: Decide (+ 4-category legend)
# --------------------------------------------------------------------------


def build_slide_4():
    slide = new_slide()
    add_title(slide, "Loop — Decide", width=Inches(9.5))
    # Small badge beside the title, not stacked above the legend — a
    # full-size icon there collided with the title text (see
    # loop_decide_layout_problem.png).
    add_decide_icon(slide, int(Inches(11.9)), int(Inches(1.2)), size=Inches(1.0))

    add_category_legend(
        slide,
        [
            ("tone_drift", "Tone drift", "still sound like the brand?"),
            (
                "information_hierarchy",
                "Information hierarchy",
                "important stuff said first?",
            ),
            (
                "cta_cadence",
                "CTA cadence",
                "clear ask, shown at the right moment?",
            ),
            ("readability", "Readability", "actually easy to read?"),
        ],
        top=Inches(2.3),
    )

    add_footer(slide, 4)
    add_notes(
        slide,
        [
            (
                "CHRISTINA",
                '"Whatever my evaluator flags gets fed straight into the '
                "agent's system prompt — the instructions that shape "
                "everything it does — as evidence it can point to, instead "
                'of guessing at the same rules a second time."',
                None,
            ),
            (
                "KARL",
                '"That same system prompt is what makes the agent judge the '
                "four things that actually need judgment, not pattern "
                "matching. Does the writing still sound like the brand, or "
                "has the tone drifted? Is the important information said "
                "first, or is it buried three paragraphs down? Is there a "
                "clear CTA, and does it show up at the right moment and not "
                "too often? CTA means ‘call to action’ — the part of the "
                "copy that tells someone what to actually do next, like "
                "‘sign up’ or ‘buy now.’ And is it actually easy to read? "
                "Christina's findings, the brand guidelines, the document, "
                "and the brief all go into that one system prompt, and the "
                'agent decides what to flag."',
                None,
            ),
        ],
    )


# --------------------------------------------------------------------------
# Slide 5 — Loop: Act
# --------------------------------------------------------------------------


def build_slide_5():
    slide = new_slide()
    add_title(slide, "Loop — Act")
    add_act_icon(slide, int(Inches(3.0)), int(Inches(3.9)))

    box = slide.shapes.add_textbox(Inches(5.2), Inches(3.3), Inches(7.0), Inches(1.2))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "create_suggestion (rewrite) or create_inline_comment (structural)"
    set_run(r, size=20, color=SECONDARY)

    add_footer(slide, 5)
    add_notes(
        slide,
        [
            (
                "KARL",
                '"From there the agent has two moves: propose a suggested '
                "edit for a rewrite, or leave a comment for anything more "
                "structural than a simple text swap. It keeps going until "
                "it's out of things to flag or hits a round limit, then "
                'prints a summary of what it posted."',
                None,
            ),
        ],
    )


# --------------------------------------------------------------------------
# Slide 6 — Checkpoint
# --------------------------------------------------------------------------


def build_slide_6():
    slide = new_slide()
    add_title(slide, "Checkpoint")
    add_checkpoint_icon(slide, int(Inches(3.0)), int(Inches(3.9)))

    box = slide.shapes.add_textbox(Inches(5.2), Inches(3.5), Inches(7.0), Inches(0.8))
    p = box.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = "Reviewable. Never silent."
    set_run(r, font=HEAD_FONT, size=26, color=INK, bold=True)

    add_footer(slide, 6)
    add_notes(
        slide,
        [
            (
                "KARL",
                '"Nothing Verbatim does gets applied outright. Everything '
                "shows up as something reviewable — a suggested edit or a "
                'comment — never a silent change to the doc."',
                None,
            ),
            (
                "CHRISTINA",
                "\"That's because this copy is headed for a final sign-off "
                "— nobody wants their draft rewritten out from under them. "
                "The copywriter goes through every suggestion and comment "
                "one at a time and accepts or rejects each. Only what they "
                'accept moves forward."',
                None,
            ),
        ],
    )


# --------------------------------------------------------------------------
# Slide 7 — Live demo
# --------------------------------------------------------------------------


def build_slide_7():
    slide = new_slide()
    add_title(slide, "Live demo", align=PP_ALIGN.CENTER, top=Inches(3.1))
    add_subhead(
        slide,
        "via the Verbatim Add-on sidebar",
        top=Inches(4.0),
        align=PP_ALIGN.CENTER,
    )
    add_footer(slide, 7)
    add_notes(
        slide,
        [
            (
                "KARL",
                '"Let\'s see it in a doc."',
                "(open the Verbatim sidebar on the draft; the campaign "
                "brief link is already filled in)",
            ),
            (
                "CHRISTINA",
                '"We\'ll run it against Email."',
                '(pick Email from the channel dropdown, click "Run Verbatim Audit")',
            ),
            (
                "CHRISTINA",
                '"The evaluator and the model both run behind the scenes, '
                "so we'll click ‘Check Status’ until it's done thinking.\"",
                '(click "Check Status" once or twice until the results card appears)',
            ),
            (
                "KARL",
                '"Here\'s what came back."',
                "(read off the sidebar's category breakdown and counts — "
                "call out whatever actually shows up, not a fixed number)",
            ),
            (
                "CHRISTINA",
                '"And here in the doc—"',
                "(point at 2-3 of the actual suggestions or comments that "
                "landed, whatever they turn out to be)",
            ),
        ],
    )


# --------------------------------------------------------------------------
# Slide 8 — Close
# --------------------------------------------------------------------------


def build_slide_8():
    slide = new_slide()
    if ICON_PATH.exists():
        slide.shapes.add_picture(
            str(ICON_PATH), Inches(5.867), Inches(2.2), Inches(1.6), Inches(1.6)
        )
    add_title(slide, "Verbatim", align=PP_ALIGN.CENTER, top=Inches(4.2))
    add_subhead(slide, "Thank you.", top=Inches(4.95), align=PP_ALIGN.CENTER)
    add_footer(slide, 8)
    add_notes(
        slide,
        [
            (
                "KARL",
                '"What you just saw is running for real — the same '
                "backend, the same Add-on, live in this doc. Not a "
                'mockup."',
                None,
            ),
            ("CHRISTINA", '"That\'s Verbatim. Thank you."', None),
        ],
    )


def add_flow_step(slide: Slide, top, text, sub, *, width=None, height=None):
    """One box in the slide-9 pipeline diagram: bold title + a dim subline."""
    if width is None:
        width = Inches(8.0)
    if height is None:
        height = Inches(0.6)
    left = Emu(int((SLIDE_W - width) / 2))
    box = add_rounded_container(slide, left, top, width, height, radius=0.2)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_top = tf.margin_bottom = Pt(2)
    p1 = tf.paragraphs[0]
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = text
    set_run(r1, font=HEAD_FONT, size=16, color=WHITE, bold=True)
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run()
    r2.text = sub
    set_run(r2, size=11, color=WHITE)
    return box


def add_flow_chevron(slide: Slide, center_y):
    """A small downward-pointing triangle marking flow direction."""
    w, h = Inches(0.26), Inches(0.1)
    tri = slide.shapes.add_shape(
        MSO_SHAPE.ISOSCELES_TRIANGLE,
        Emu(int((SLIDE_W - w) / 2)),
        Emu(int(center_y - h / 2)),
        w,
        h,
    )
    tri.rotation = 180
    tri.fill.solid()
    tri.fill.fore_color.rgb = BLUE
    tri.line.fill.background()
    tri.shadow.inherit = False


def build_slide_9():
    """Appendix: full pipeline, not part of the timed 5:00 script.

    Adapted from README.md's Mermaid flowchart, updated to the Add-on/Cloud
    Run path this deck actually demos (the README diagram documents the CLI
    entrypoint) and restyled in Verbatim's own palette/type rather than
    Mermaid's default theme, so it reads as one system with the rest of the
    deck.
    """
    slide = new_slide()
    add_title(slide, "Under the hood")
    add_subhead(
        slide, "the full pipeline, for anyone curious", top=Inches(1.4), size=16
    )

    steps = [
        ("Run Verbatim Audit", "Add-on sidebar — brief & channel already set"),
        ("Fetch draft + brief", "Google Docs / Drive API"),
        ("Evaluator runs", "regex — banned words, formatting, channel limits"),
        ("LLM tool-calling loop", "create_suggestion / create_inline_comment"),
        ("Check Status", "Cloud Run backend — submit/poll, no 60s timeout"),
        ("Review in Google Docs", "accept / reject inline → sign-off"),
    ]
    box_h = Inches(0.55)
    gap = Inches(0.15)
    top0 = Inches(2.3)
    for i, (text, sub) in enumerate(steps):
        row_top = top0 + (box_h + gap) * i
        add_flow_step(slide, row_top, text, sub, height=box_h)
        if i > 0:
            prev_bottom = top0 + (box_h + gap) * (i - 1) + box_h
            add_flow_chevron(slide, Emu(int((prev_bottom + row_top) / 2)))

    add_footer(slide, 9)
    add_notes(
        slide,
        [
            (
                None,
                "Appendix — not part of the timed 5:00 script. Full "
                "technical pipeline for reference or Q&A; mirrors "
                "README.md's architecture diagram, updated to the live "
                "Add-on/Cloud Run path this deck actually demos.",
                None,
            ),
        ],
    )


prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H

for builder in (
    build_slide_1,
    build_slide_2,
    build_slide_3,
    build_slide_4,
    build_slide_5,
    build_slide_6,
    build_slide_7,
    build_slide_8,
    build_slide_9,
):
    builder()

prs.save(str(OUTPUT_PATH))
print(f"Wrote {OUTPUT_PATH} ({len(prs.slides)} slides)")
