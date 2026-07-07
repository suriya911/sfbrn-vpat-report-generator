"""
WCAG 2.1 / 2.2 Quick Reference dataset — the "dictionary" module.

RECONSTRUCTED FILE.  The original wcag_reference.py was lost in the file-name
shuffle that damaged this project (its slot on disk had been overwritten with
the INSTALL_INSTRUCTIONS text).  report_generator.py consumes this module
through two functions only:

    lookup(criterion_id) -> {"description": str, "plain": str} | None
    has_all_required()   -> (bool, list_of_missing_ids)

`description` is the official Success Criterion text (quoted in the report as
"… — WCAG 2.1 Quick Reference").  `plain` is the plain-language "What this
means" explanation.  Descriptions are the normative W3C Success Criterion
statements (public standard); they are not invented.  The criterion set matches
the WCAG_DATA table embedded in report_generator.py exactly.
"""

# ── Official criterion text + plain-language explanation ──────────────────────
# Keyed by WCAG Success Criterion number. Descriptions are condensed from the
# normative W3C WCAG 2.1/2.2 text; plain-language lines summarise the intent.

WCAG_REFERENCE = {
    # ── 1. Perceivable ──────────────────────────────────────────────────────
    "1.1.1": {
        "description": "All non-text content that is presented to the user has a text alternative that serves the equivalent purpose, except for controls, time-based media, tests, sensory experiences, CAPTCHA, and decoration.",
        "plain": "Every meaningful image, icon, chart, or control needs a text description so people who cannot see it — including screen-reader users — get the same information. Purely decorative graphics should be hidden from assistive technology.",
    },
    "1.2.1": {
        "description": "For prerecorded audio-only and prerecorded video-only media, an alternative is provided that presents equivalent information.",
        "plain": "Audio-only files need a transcript, and silent video needs either a transcript or an audio track, so the content is available to people who cannot hear or cannot see it.",
    },
    "1.2.2": {
        "description": "Captions are provided for all prerecorded audio content in synchronized media, except when the media is a media alternative for text and is clearly labeled as such.",
        "plain": "Recorded videos with sound must have accurate synchronized captions so people who are deaf or hard of hearing can follow the spoken content.",
    },
    "1.2.3": {
        "description": "An alternative for time-based media or audio description of the prerecorded video content is provided for synchronized media, except when the media is a media alternative for text and is clearly labeled as such.",
        "plain": "Prerecorded video needs either a full text alternative or audio description so that people who are blind understand the important visual action.",
    },
    "1.2.4": {
        "description": "Captions are provided for all live audio content in synchronized media.",
        "plain": "Live video with sound (webinars, live streams) must have real-time captions so people who are deaf or hard of hearing can participate as it happens.",
    },
    "1.2.5": {
        "description": "Audio description is provided for all prerecorded video content in synchronized media.",
        "plain": "Prerecorded video should include an audio-description track that narrates key visual details for viewers who are blind or have low vision.",
    },
    "1.3.1": {
        "description": "Information, structure, and relationships conveyed through presentation can be programmatically determined or are available in text.",
        "plain": "Headings, lists, tables, and form labels must be marked up with real structure — not just visual styling — so assistive technology can convey the same relationships a sighted user sees.",
    },
    "1.3.2": {
        "description": "When the sequence in which content is presented affects its meaning, a correct reading sequence can be programmatically determined.",
        "plain": "Content must be coded in a logical reading order so a screen reader announces it in a sequence that still makes sense.",
    },
    "1.3.3": {
        "description": "Instructions provided for understanding and operating content do not rely solely on sensory characteristics of components such as shape, color, size, visual location, orientation, or sound.",
        "plain": "Directions should not depend only on things like \"click the round button on the right\" — they must also work for people who cannot perceive shape, color, or position.",
    },
    "1.3.4": {
        "description": "Content does not restrict its view and operation to a single display orientation, such as portrait or landscape, unless a specific orientation is essential.",
        "plain": "The interface must work in both portrait and landscape so people who have their device mounted in a fixed orientation are not locked out.",
    },
    "1.3.5": {
        "description": "The purpose of each input field collecting information about the user can be programmatically determined when the field serves a common purpose and the technology supports identifying it.",
        "plain": "Common form fields (name, email, address) should declare their purpose in code so browsers and assistive tools can autofill and adapt them.",
    },
    "1.4.1": {
        "description": "Color is not used as the only visual means of conveying information, indicating an action, prompting a response, or distinguishing a visual element.",
        "plain": "Information shown with color (like a red \"error\" field) must also be shown another way — text, an icon, or a pattern — for people who cannot distinguish colors.",
    },
    "1.4.2": {
        "description": "If any audio plays automatically for more than 3 seconds, a mechanism is available to pause or stop it, or to control its volume independently of the overall system volume.",
        "plain": "Sound that starts on its own must be easy to stop or mute so it does not interfere with a screen reader or startle the user.",
    },
    "1.4.3": {
        "description": "The visual presentation of text and images of text has a contrast ratio of at least 4.5:1, except for large text (3:1), incidental text, and logotypes.",
        "plain": "Text must stand out clearly from its background (at least 4.5:1 contrast) so people with low vision can read it.",
    },
    "1.4.4": {
        "description": "Except for captions and images of text, text can be resized without assistive technology up to 200 percent without loss of content or functionality.",
        "plain": "Users must be able to enlarge text to 200% (using browser zoom) without content overlapping, being cut off, or breaking.",
    },
    "1.4.5": {
        "description": "If the technologies being used can achieve the visual presentation, text is used to convey information rather than images of text, except for customizable images and where a particular presentation is essential.",
        "plain": "Use real text instead of pictures of text so it can be resized, recolored, and read by assistive technology.",
    },
    "1.4.10": {
        "description": "Content can be presented without loss of information or functionality, and without requiring scrolling in two dimensions, at a width equivalent to 320 CSS pixels or a height equivalent to 256 CSS pixels.",
        "plain": "Content should reflow into a single column on a narrow screen or at high zoom, so users don't have to scroll both horizontally and vertically to read it.",
    },
    "1.4.11": {
        "description": "The visual presentation of user-interface components and graphical objects has a contrast ratio of at least 3:1 against adjacent colors.",
        "plain": "Buttons, form borders, icons, and meaningful graphics need at least 3:1 contrast so people with low vision can see and operate them.",
    },
    "1.4.12": {
        "description": "No loss of content or functionality occurs when users override line height to 1.5 times the font size, paragraph spacing to 2 times, letter spacing to 0.12 times, and word spacing to 0.16 times the font size.",
        "plain": "When users adjust spacing to make text easier to read, the layout must adapt without clipping or hiding content.",
    },
    "1.4.13": {
        "description": "Where receiving and then removing pointer hover or keyboard focus triggers additional content, that content is dismissable, hoverable, and persistent.",
        "plain": "Tooltips and pop-ups that appear on hover or focus must be dismissible, must stay open long enough to read, and must not disappear when the pointer moves onto them.",
    },
    # ── 2. Operable ─────────────────────────────────────────────────────────
    "2.1.1": {
        "description": "All functionality of the content is operable through a keyboard interface without requiring specific timings for individual keystrokes.",
        "plain": "Everything you can do with a mouse must also be doable with a keyboard alone, for people who cannot use a pointing device.",
    },
    "2.1.2": {
        "description": "If keyboard focus can be moved to a component using a keyboard interface, then focus can be moved away from that component using only a keyboard interface.",
        "plain": "Keyboard users must never get \"trapped\" in a widget — they must always be able to tab back out.",
    },
    "2.1.4": {
        "description": "If a keyboard shortcut is implemented using only letter, punctuation, number, or symbol characters, then it can be turned off, remapped, or is active only on focus.",
        "plain": "Single-key shortcuts must be avoidable or remappable so speech-input users don't trigger them by accident.",
    },
    "2.2.1": {
        "description": "For each time limit set by the content, the user can turn it off, adjust it, or extend it, with limited exceptions.",
        "plain": "If a task has a time limit, users must be able to turn it off, lengthen it, or extend it, so people who need more time are not cut off.",
    },
    "2.2.2": {
        "description": "For moving, blinking, scrolling, or auto-updating information, users can pause, stop, or hide it, subject to defined exceptions.",
        "plain": "Anything that moves, blinks, or auto-updates must have a way to pause or stop it, so it does not distract or block people from reading.",
    },
    "2.3.1": {
        "description": "Web pages do not contain anything that flashes more than three times in any one-second period, or the flash is below the general flash and red flash thresholds.",
        "plain": "Nothing should flash more than three times per second, because rapid flashing can trigger seizures.",
    },
    "2.4.1": {
        "description": "A mechanism is available to bypass blocks of content that are repeated on multiple web pages.",
        "plain": "A \"skip to main content\" link or landmark lets keyboard and screen-reader users jump past repeated menus instead of tabbing through them every time.",
    },
    "2.4.2": {
        "description": "Web pages have titles that describe topic or purpose.",
        "plain": "Every page needs a clear, descriptive title so users know where they are and can tell tabs and windows apart.",
    },
    "2.4.3": {
        "description": "If a web page can be navigated sequentially and the navigation sequences affect meaning or operation, focusable components receive focus in an order that preserves meaning and operability.",
        "plain": "As you tab through a page, focus should move in a logical order that matches the visual and reading flow.",
    },
    "2.4.4": {
        "description": "The purpose of each link can be determined from the link text alone, or from the link text together with its programmatically determined context, except where the purpose would be ambiguous to users in general.",
        "plain": "Link text should make its destination clear — avoid vague links like \"click here\" that make no sense out of context.",
    },
    "2.4.5": {
        "description": "More than one way is available to locate a web page within a set of web pages, except where the page is the result of, or a step in, a process.",
        "plain": "Users should have more than one way to find a page — such as a menu, search, and a site map — to suit different needs.",
    },
    "2.4.6": {
        "description": "Headings and labels describe topic or purpose.",
        "plain": "Headings and form labels must be clear and descriptive so users can understand and navigate the content quickly.",
    },
    "2.4.7": {
        "description": "Any keyboard-operable user interface has a mode of operation where the keyboard focus indicator is visible.",
        "plain": "The element that currently has keyboard focus must be visibly highlighted so keyboard users can see where they are.",
    },
    "2.4.11": {
        "description": "When a user-interface component receives keyboard focus, the component is not entirely hidden due to author-created content.",
        "plain": "When you tab to a control, it must not be completely covered by sticky headers, footers, or pop-ups.",
    },
    "2.5.1": {
        "description": "All functionality that uses multipoint or path-based gestures can be operated with a single pointer without a path-based gesture, unless such a gesture is essential.",
        "plain": "Actions that need complex gestures (pinch, swipe paths) must also work with a simple single tap or click.",
    },
    "2.5.2": {
        "description": "For functionality operated using a single pointer, the down-event is not used to complete the action, or completion can be aborted or undone.",
        "plain": "An action should complete on release, not on press, so users can slide off a control to cancel a mistaken tap.",
    },
    "2.5.3": {
        "description": "For user-interface components with labels that include text or images of text, the accessible name contains the text that is presented visually.",
        "plain": "A control's programmatic name must include its visible label text, so speech-input users can activate it by saying what they see.",
    },
    "2.5.4": {
        "description": "Functionality that can be operated by device motion or user motion can also be operated by user-interface components, and responding to the motion can be disabled, unless the motion is essential.",
        "plain": "Features triggered by shaking or tilting the device must also have a normal control and be able to be turned off, for people who cannot move the device precisely.",
    },
    "2.5.7": {
        "description": "All functionality that uses a dragging movement for operation can be achieved by a single pointer without dragging, unless dragging is essential.",
        "plain": "Anything that requires dragging must also offer a simple tap/click alternative for people who cannot perform a sustained drag.",
    },
    "2.5.8": {
        "description": "The size of the target for pointer inputs is at least 24 by 24 CSS pixels, except where spacing, an equivalent control, inline placement, essential presentation, or user-agent control applies.",
        "plain": "Clickable targets should be at least 24×24 pixels (or adequately spaced) so people with limited dexterity can hit them accurately.",
    },
    # ── 3. Understandable ───────────────────────────────────────────────────
    "3.1.1": {
        "description": "The default human language of each web page can be programmatically determined.",
        "plain": "The page must declare its language in code so screen readers pronounce the content with the correct accent and rules.",
    },
    "3.1.2": {
        "description": "The human language of each passage or phrase in the content can be programmatically determined, except for proper names, technical terms, words of indeterminate language, and words that are part of the vernacular.",
        "plain": "Words or passages in a different language should be marked as such so a screen reader switches pronunciation correctly.",
    },
    "3.2.1": {
        "description": "When any user-interface component receives focus, it does not initiate a change of context.",
        "plain": "Simply moving focus onto a field or control must not unexpectedly open a new window, submit a form, or jump the user elsewhere.",
    },
    "3.2.2": {
        "description": "Changing the setting of any user-interface component does not automatically cause a change of context unless the user has been advised of the behavior beforehand.",
        "plain": "Selecting an option or typing in a field must not trigger a surprising context change unless the user was warned first.",
    },
    "3.2.3": {
        "description": "Navigational mechanisms that are repeated on multiple web pages occur in the same relative order each time they are repeated, unless a change is initiated by the user.",
        "plain": "Menus and navigation should stay in the same place and order across pages so users can rely on them.",
    },
    "3.2.4": {
        "description": "Components that have the same functionality within a set of web pages are identified consistently.",
        "plain": "The same control (like a search button) should be labeled and named the same way everywhere, so users recognize it.",
    },
    "3.3.1": {
        "description": "If an input error is automatically detected, the item in error is identified and the error is described to the user in text.",
        "plain": "When a form entry is wrong, the specific field and the problem must be clearly described in text, not just shown with color.",
    },
    "3.3.2": {
        "description": "Labels or instructions are provided when content requires user input.",
        "plain": "Every form field needs a clear visible label or instructions so users know what to enter.",
    },
    "3.3.3": {
        "description": "If an input error is automatically detected and suggestions for correction are known, the suggestions are provided to the user, unless it would jeopardize the security or purpose of the content.",
        "plain": "When the system knows how to fix an input error, it should suggest the correction (for example, a valid date format).",
    },
    "3.3.4": {
        "description": "For pages that cause legal commitments or financial transactions, that modify or delete user-controllable data, or that submit test responses, submissions are reversible, checked, or confirmed.",
        "plain": "Before finalizing something important (a purchase, a legal form, deleting data), users must be able to review, correct, or undo it.",
    },
    "3.3.8": {
        "description": "A cognitive function test (such as remembering a password) is not required for any step in an authentication process unless an alternative, a mechanism, object recognition, or personal-content recognition is available.",
        "plain": "Sign-in should not force people to memorize or transcribe codes — it must allow methods like password managers, copy-paste, or biometrics.",
    },
    # ── 4. Robust ───────────────────────────────────────────────────────────
    "4.1.1": {
        "description": "In content implemented using markup languages, elements have complete start and end tags, are nested according to specification, do not contain duplicate attributes, and any IDs are unique, except where the specifications allow these features. (Note: 4.1.1 is deprecated in WCAG 2.2 and is considered always satisfied for modern HTML.)",
        "plain": "The underlying code should be well-formed — no broken tags or duplicate IDs — so browsers and assistive technology interpret it reliably.",
    },
    "4.1.2": {
        "description": "For all user-interface components, the name and role can be programmatically determined; states, properties, and values that can be set by the user can be programmatically set; and notification of changes to these items is available to user agents, including assistive technologies.",
        "plain": "Every control must expose its name, role, and state in code (often via ARIA) so screen readers can announce what it is and how it's set.",
    },
    "4.1.3": {
        "description": "In content implemented using markup languages, status messages can be programmatically determined through role or properties such that they can be presented to the user by assistive technologies without receiving focus.",
        "plain": "Status updates (like \"item added to cart\" or \"5 results found\") must be announced by a screen reader without moving focus away from the user's task.",
    },
}


# ── Required-coverage self-check ──────────────────────────────────────────────
# The full set of WCAG 2.1 Level A & AA criteria the report may render, plus the
# WCAG 2.2 additions carried in report_generator's WCAG_DATA table.
REQUIRED_IDS = [
    "1.1.1", "1.2.1", "1.2.2", "1.2.3", "1.2.4", "1.2.5",
    "1.3.1", "1.3.2", "1.3.3", "1.3.4", "1.3.5",
    "1.4.1", "1.4.2", "1.4.3", "1.4.4", "1.4.5",
    "1.4.10", "1.4.11", "1.4.12", "1.4.13",
    "2.1.1", "2.1.2", "2.1.4", "2.2.1", "2.2.2", "2.3.1",
    "2.4.1", "2.4.2", "2.4.3", "2.4.4", "2.4.5", "2.4.6", "2.4.7", "2.4.11",
    "2.5.1", "2.5.2", "2.5.3", "2.5.4", "2.5.7", "2.5.8",
    "3.1.1", "3.1.2", "3.2.1", "3.2.2", "3.2.3", "3.2.4",
    "3.3.1", "3.3.2", "3.3.3", "3.3.4", "3.3.8",
    "4.1.1", "4.1.2", "4.1.3",
]


def lookup(criterion_id):
    """Return {'description': str, 'plain': str} for a WCAG criterion, or None."""
    if not criterion_id:
        return None
    return WCAG_REFERENCE.get(str(criterion_id).strip())


def has_all_required():
    """(all_present, missing_ids) — used by report_generator to decide whether
    the bundled reference dataset is complete before relying on it."""
    missing = [cid for cid in REQUIRED_IDS if cid not in WCAG_REFERENCE]
    return (len(missing) == 0, missing)


if __name__ == "__main__":
    ok, missing = has_all_required()
    print(f"WCAG reference entries: {len(WCAG_REFERENCE)}")
    print(f"Required present: {ok}" + ("" if ok else f" — missing {missing}"))
