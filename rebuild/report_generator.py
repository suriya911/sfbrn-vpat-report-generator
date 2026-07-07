"""
SFBRN VPAT Report Generator — v10
==================================
Visual redesign to mirror the SFBRN sample report format (master prompt spec):
  - Running header on every body page: 4pt primary-blue top border, logo block,
    centered report title, date at right, 1px divider below.
  - Three-part footer on every page: copyright | report name | Page X of Y
    (implemented with a two-pass NumberedCanvas so total pages is known).
  - Executive Summary compliance meter: large percentage, threshold language,
    horizontal progress bar.
  - Callout boxes with left accent bars.
  - Barrier cards: italic quoted WCAG criterion text, "What this means"
    plain-language explanation, pill-shaped Level/Status badges, shaded
    Vendor Remarks block.
  - Master-prompt color palette and typography only.

SCORING POLICY (Option A — deliberate, do not regress):
  - v9 scoring preserved: Not Applicable criteria are EXCLUDED from both the
    compliance-score denominator and the barrier count.
  - NA criteria ARE displayed in Section 2 as transparently documented
    "known gaps" per SFBRN policy, but they do not affect the score.
  - Regression anchors: CCPS 57%, Minitab 91%.

Identity fields (reviewer, organization, contact, threshold, logo) come from
the `settings` dict so any organization can use the app. Defaults are SFBRN /
Jonathan Hale so the master-prompt requirements are met out of the box.
"""

import os
import logging
from datetime import date, datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Image as RLImage
)
from reportlab.graphics.shapes import Drawing, Rect
try:
    import wcag_reference  # bundled WCAG 2.1 Quick Reference dataset
    _ref_result = wcag_reference.has_all_required()
    _WCAG_REF_OK = _ref_result[0] if isinstance(_ref_result, tuple) else bool(_ref_result)
except Exception:
    wcag_reference = None
    _WCAG_REF_OK = False

logger = logging.getLogger(__name__)

# ── Master-prompt color palette (only these colors appear in the report) ──────
C_PRIMARY  = colors.HexColor("#1a4f8a")   # primary blue
C_ACCENT   = colors.HexColor("#2e6db5")   # accent blue
C_BG       = colors.HexColor("#e8f0fb")   # light background
C_WHITE    = colors.white                  # #ffffff
C_BORDER   = colors.HexColor("#b5d4f4")   # border
C_BODY     = colors.HexColor("#1a1a2e")   # body text
C_CAPTION  = colors.HexColor("#555555")   # caption text
C_QUOTE    = colors.HexColor("#333333")   # quoted criterion text

C_SUPPORTS = colors.HexColor("#1a7a4a")
C_PARTIAL  = colors.HexColor("#b36b00")
C_DOES_NOT = colors.HexColor("#a32d2d")
C_NA       = colors.HexColor("#5f5e5a")
C_NOT_EVAL = colors.HexColor("#888780")

STATUS_COLORS = {
    "Supports":           C_SUPPORTS,
    "Partially Supports": C_PARTIAL,
    "Does Not Support":   C_DOES_NOT,
    "Not Applicable":     C_NA,
    "Not Evaluated":      C_NOT_EVAL,
}
# Impact box colors reuse palette colors only
IMPACT_COLORS = {"High": C_DOES_NOT, "Medium": C_PARTIAL, "Low": C_SUPPORTS}

# ── Default identity settings (overridable via settings.json / Settings UI) ───
DEFAULT_SETTINGS = {
    "org_name":       "San Francisco Bay Region Network (SFBRN)",
    "org_short":      "SFBRN",
    "reviewer_name":  "Jonathan Hale",
    "reviewer_title": "Accessibility Compliance Reviewer",
    "org_contact":    "",
    "threshold":      90,
    "report_title":   "VPAT Accessibility Compliance \u2014 Summary Report",
}

def _merged_settings(settings):
    s = dict(DEFAULT_SETTINGS)
    if settings:
        for k, v in settings.items():
            if v not in (None, ""):
                s[k] = v
    try:
        s["threshold"] = int(s["threshold"])
    except (TypeError, ValueError):
        s["threshold"] = 90
    return s


# ── WCAG reference (v9 canonical — includes 1.2.3 full title, do not edit) ────
WCAG_DATA = {
    "1.1.1":  ("Non-text Content",                          "A",  "Perceivable"),
    "1.2.1":  ("Audio-only and Video-only (Prerecorded)",   "A",  "Perceivable"),
    "1.2.2":  ("Captions (Prerecorded)",                    "A",  "Perceivable"),
    "1.2.3":  ("Audio Description or Media Alternative (Prerecorded)", "A", "Perceivable"),
    "1.2.4":  ("Captions (Live)",                           "AA", "Perceivable"),
    "1.2.5":  ("Audio Description (Prerecorded)",           "AA", "Perceivable"),
    "1.3.1":  ("Info and Relationships",                    "A",  "Perceivable"),
    "1.3.2":  ("Meaningful Sequence",                       "A",  "Perceivable"),
    "1.3.3":  ("Sensory Characteristics",                   "A",  "Perceivable"),
    "1.3.4":  ("Orientation",                               "AA", "Perceivable"),
    "1.3.5":  ("Identify Input Purpose",                    "AA", "Perceivable"),
    "1.4.1":  ("Use of Color",                              "A",  "Perceivable"),
    "1.4.2":  ("Audio Control",                             "A",  "Perceivable"),
    "1.4.3":  ("Contrast (Minimum)",                        "AA", "Perceivable"),
    "1.4.4":  ("Resize Text",                               "AA", "Perceivable"),
    "1.4.5":  ("Images of Text",                            "AA", "Perceivable"),
    "1.4.10": ("Reflow",                                    "AA", "Perceivable"),
    "1.4.11": ("Non-text Contrast",                         "AA", "Perceivable"),
    "1.4.12": ("Text Spacing",                              "AA", "Perceivable"),
    "1.4.13": ("Content on Hover or Focus",                 "AA", "Perceivable"),
    "2.1.1":  ("Keyboard",                                  "A",  "Operable"),
    "2.1.2":  ("No Keyboard Trap",                          "A",  "Operable"),
    "2.1.4":  ("Character Key Shortcuts",                   "A",  "Operable"),
    "2.2.1":  ("Timing Adjustable",                         "A",  "Operable"),
    "2.2.2":  ("Pause, Stop, Hide",                         "A",  "Operable"),
    "2.3.1":  ("Three Flashes or Below Threshold",          "A",  "Operable"),
    "2.4.1":  ("Bypass Blocks",                             "A",  "Operable"),
    "2.4.2":  ("Page Titled",                               "A",  "Operable"),
    "2.4.3":  ("Focus Order",                               "A",  "Operable"),
    "2.4.4":  ("Link Purpose (In Context)",                 "A",  "Operable"),
    "2.4.5":  ("Multiple Ways",                             "AA", "Operable"),
    "2.4.6":  ("Headings and Labels",                       "AA", "Operable"),
    "2.4.7":  ("Focus Visible",                             "AA", "Operable"),
    "2.4.11": ("Focus Not Obscured (Minimum)",              "AA", "Operable"),
    "2.5.1":  ("Pointer Gestures",                          "A",  "Operable"),
    "2.5.2":  ("Pointer Cancellation",                      "A",  "Operable"),
    "2.5.3":  ("Label in Name",                             "A",  "Operable"),
    "2.5.4":  ("Motion Actuation",                          "A",  "Operable"),
    "2.5.7":  ("Dragging Movements",                        "AA", "Operable"),
    "2.5.8":  ("Target Size (Minimum)",                     "AA", "Operable"),
    "3.1.1":  ("Language of Page",                          "A",  "Understandable"),
    "3.1.2":  ("Language of Parts",                         "AA", "Understandable"),
    "3.2.1":  ("On Focus",                                  "A",  "Understandable"),
    "3.2.2":  ("On Input",                                  "A",  "Understandable"),
    "3.2.3":  ("Consistent Navigation",                     "AA", "Understandable"),
    "3.2.4":  ("Consistent Identification",                 "AA", "Understandable"),
    "3.3.1":  ("Error Identification",                      "A",  "Understandable"),
    "3.3.2":  ("Labels or Instructions",                    "A",  "Understandable"),
    "3.3.3":  ("Error Suggestion",                          "AA", "Understandable"),
    "3.3.4":  ("Error Prevention (Legal, Financial, Data)", "AA", "Understandable"),
    "3.3.8":  ("Accessible Authentication (Minimum)",       "AA", "Understandable"),
    "4.1.1":  ("Parsing",                                   "A",  "Robust"),
    "4.1.2":  ("Name, Role, Value",                         "A",  "Robust"),
    "4.1.3":  ("Status Messages",                           "AA", "Robust"),
}

PRINCIPLES = ["Perceivable", "Operable", "Understandable", "Robust"]


PRINCIPLES = ["Perceivable", "Operable", "Understandable", "Robust"]


# ── v9 canned workaround library (all 24 AA criteria covered — do not regress) ─

WORKAROUNDS = {
    "1.1.1": [
        "Use a screen reader (NVDA, JAWS, or VoiceOver) to check whether images are announced with a meaningful description.",
        "If an image button has no accessible name, right-click the element and use your browser's accessibility inspector to check for an aria-label.",
        "Request the vendor add alt text to all informative images and mark decorative images as presentation role.",
        "As an interim measure, faculty can provide a text-based version of any visual content embedded in the tool.",
    ],
    "1.2.1": [
        "Request a written transcript from the content creator for any audio-only files.",
        "For video-only content, request a text description of what occurs visually.",
        "Faculty should provide alternative text-based materials alongside audio or silent video content.",
    ],
    "1.2.2": [
        "Request caption files (.vtt or .srt) from the vendor or content creator.",
        "Use YouTube's auto-caption feature as a starting point, then review for accuracy.",
        "Google Live Transcribe (Android) or Microsoft Translator can provide real-time speech-to-text.",
        "Students needing captions should contact Disability Services for accommodation support.",
    ],
    "1.2.3": [
        "Request an audio description track or a text transcript that describes both audio and visual content.",
        "Faculty can record a secondary narration track describing visual elements for students who are blind.",
    ],
    "1.2.4": [
        "Use Google Live Transcribe (free, Android) or Otter.ai (free tier available) for real-time transcription of live sessions.",
        "Microsoft Teams, Zoom, and Google Meet all offer built-in live captions that can be used alongside this product.",
        "Request that the vendor enable WebVTT caption support for any live video features.",
        "Students needing live captioning should contact Disability Services for a CART (Communication Access Realtime Translation) provider.",
    ],
    "1.2.5": [
        "Request an audio description track from the vendor or content creator.",
        "Faculty can provide a written narration document that describes the visual content of any prerecorded video.",
        "Use Described and Captioned Media Program (DCMP) guidelines to create audio descriptions for critical course videos.",
    ],
    "1.3.1": [
        "Use NVDA (free) or JAWS with the browser to navigate by headings (H key) and landmarks (D key for main content).",
        "Install the Accessibility Insights for Web browser extension (free, Microsoft) to quickly view the heading structure and landmark regions.",
        "If the page lacks a main landmark, use Ctrl+F (Find) in the browser to search for key terms and navigate directly.",
        "Report missing heading structure and landmark regions to the vendor — these are high-priority fixes.",
    ],
    "1.3.2": [
        "Use a screen reader's Reading View (NVDA: Insert+Space) to hear content in linear reading order.",
        "Use the browser Reader Mode (F9 in Firefox, or Reader View in Safari) to strip layout and reveal content in logical order.",
        "If content order is confusing, navigate by paragraph (Ctrl+Down in NVDA) rather than by layout.",
    ],
    "1.3.3": [
        "When instructions reference shape, color, or position, ask the vendor to also include a text label.",
        "As a workaround, faculty should supplement any position-based instructions ('click the button on the right') with explicit step-by-step text instructions.",
    ],
    "1.3.4": [
        "If the application forces portrait orientation, users who mount devices in landscape can use a physical rotation lock override on their device.",
        "On Windows tablets, disable auto-rotate in Action Center and manually set orientation.",
        "Contact the vendor to request that orientation restrictions be removed in a future update.",
        "As an interim measure, use the desktop web version of the product which is not subject to orientation restrictions.",
    ],
    "1.3.5": [
        "Use your browser's autofill or password manager to fill personal information fields automatically.",
        "If fields are not auto-filling, use your screen reader's Forms Mode to manually identify and fill each field.",
    ],
    "1.4.1": [
        "Enable High Contrast Mode in Windows (Settings > Ease of Access > High Contrast) to override color-only indicators.",
        "On macOS, enable Increase Contrast (System Settings > Accessibility > Display).",
        "Install the Colorblindly or Color Enhancer browser extension to remap color-based indicators.",
        "Request the vendor add a text label or icon alongside any color-only status indicators.",
    ],
    "1.4.3": [
        "Increase browser zoom to 150% or 200% (Ctrl++ or Cmd++) to make low-contrast text easier to read.",
        "Enable High Contrast Mode in Windows (Win+Ctrl+C or Settings > Ease of Access > High Contrast).",
        "On macOS, enable Increase Contrast under System Settings > Accessibility > Display.",
        "Install the Dark Reader browser extension to apply a high-contrast dark mode overlay to any web application.",
        "Use the Chrome DevTools Accessibility panel to check exact contrast ratios and report specific failures to the vendor.",
        "Students with low vision or color perception differences should contact Disability Services for accommodation support.",
    ],
    "1.4.4": [
        "Use browser zoom (Ctrl++ repeatedly) up to 200%. If content truncates at high zoom, try a wider browser window or a larger physical monitor.",
        "In Chrome or Edge, go to Settings > Appearance > Page Zoom and set a persistent default zoom level.",
        "Use Windows Magnifier (Win+Plus) to zoom into specific screen regions without triggering browser reflow.",
        "Use ZoomText or SuperNova (commercial low-vision tools) for advanced magnification without layout disruption.",
        "Report the specific page and zoom level where content truncates to the vendor with a screenshot.",
    ],
    "1.4.5": [
        "Use your operating system's accessibility zoom (Windows Magnifier or macOS Zoom) to enlarge images of text.",
        "Request the vendor replace image-based text with live, selectable HTML text.",
    ],
    "1.4.10": [
        "If the page does not reflow at 400% zoom, set zoom to 200% and use a larger physical display.",
        "Use Windows Magnifier (Win+Plus) to zoom into specific screen regions without triggering browser reflow.",
        "Switch to the vendor's mobile app if available, as mobile-first designs typically handle narrow viewports better.",
        "Use the browser's Reader Mode (Firefox: F9) which strips layout and reformats content into a single readable column.",
        "Report non-reflowing pages to the vendor with the specific URL and zoom level — reflow is a legal requirement under Section 508.",
    ],
    "1.4.11": [
        "Enable High Contrast Mode (Windows: Win+Ctrl+C) to boost the contrast of all UI controls and focus indicators.",
        "Install the Dark Reader browser extension to apply uniform high-contrast styling to the entire application.",
        "Use NVDA's Object Navigation (NumPad 2/8) to interact with controls that are visually hard to distinguish.",
        "Report specific pages with low-contrast controls to the vendor, including screenshots with identified elements.",
    ],
    "1.4.12": [
        "Use browser DevTools (F12 > Elements) to manually add line-height and letter-spacing CSS overrides for readability.",
        "Install the Stylus browser extension to apply a persistent custom stylesheet that increases text spacing.",
        "Use the browser's built-in Reading Mode for a reformatted, better-spaced reading experience.",
    ],
    "1.4.13": [
        "Use the Tab key to trigger hover-activated content via keyboard focus, which keeps it visible longer.",
        "Use NVDA or JAWS with the arrow keys to read tooltip and popup content once it appears.",
        "Press Escape to dismiss stuck tooltips or popovers — report any that cannot be dismissed to the vendor.",
        "Use the Accessibility Insights browser extension to inspect tooltip content in the accessibility tree.",
    ],
    "2.1.1": [
        "Use Tab and Shift+Tab to navigate forward and backward between interactive elements.",
        "Use Enter or Space to activate buttons, and arrow keys to navigate within components like dropdowns or menus.",
        "If a control is not keyboard-reachable, use NVDA's Object Navigator (Insert+Numpad arrows) to access it.",
        "Use the browser's Find (Ctrl+F) to locate and navigate to specific on-page elements.",
        "Report all inaccessible interactive elements to the vendor — keyboard access is a fundamental legal requirement.",
        "As a workaround, some actions blocked from keyboard can be accessed via the browser's right-click context menu.",
    ],
    "2.1.2": [
        "If keyboard focus becomes trapped, press Escape to attempt to exit the component.",
        "As a last resort, press F5 to refresh the page and restart navigation.",
        "Report keyboard traps to the vendor immediately with the specific page and the key combination that triggers the trap.",
        "Use Tab+Shift+Tab rapidly to try to break out of a trapped focus loop.",
    ],
    "2.4.1": [
        "Use the browser address bar (Ctrl+L / Cmd+L) to navigate directly to specific pages, bypassing repeated navigation menus.",
        "Use NVDA's Landmark Navigation (D key) to jump directly to the main content region, skipping navigation.",
        "Install the SkipTo browser extension which adds a visible Skip Navigation control to all web pages.",
        "Create browser bookmarks for frequently used pages deep within the application to bypass the navigation structure.",
    ],
    "2.4.3": [
        "When focus jumps unexpectedly after opening a dialog, press Shift+Tab to move focus backward to the dialog content.",
        "Use NVDA's Focus Mode (Insert+Space) to track and follow focus as it moves through the page.",
        "After closing a dialog, if focus is lost, press Tab once to reorient to the nearest focusable element.",
        "Use the browser's accessibility tree inspector (F12 > Accessibility tab) to locate where focus is currently positioned.",
    ],
    "2.4.4": [
        "Use NVDA's Links List (Insert+F7) to view all links on the page and their full accessible names.",
        "Use JAWS Links List (Insert+F7) to navigate links with context shown.",
        "When a link text is ambiguous, hover over it to see if a tooltip provides additional context.",
        "Report identical or ambiguous link labels to the vendor with specific examples.",
    ],
    "2.4.5": [
        "Use the browser's built-in search (Ctrl+F) to locate content within the application.",
        "Use browser bookmarks to create direct navigation shortcuts to frequently used sections.",
        "Request the vendor add a site-wide search feature or sitemap to enable multiple navigation pathways.",
    ],
    "2.4.6": [
        "Use NVDA's Headings List (Insert+F7 > Headings tab) to review all heading labels and identify ambiguous ones.",
        "Use JAWS's Headings List (Insert+F6) for the same purpose.",
        "When buttons are identically labeled, use NVDA's Object Properties (Insert+Tab) to read the full accessible name.",
        "Request the vendor add unique, descriptive labels to all repeated buttons and form fields.",
    ],
    "2.4.7": [
        "Enable High Contrast Mode (Windows: Win+Ctrl+C) which typically makes focus indicators more visible.",
        "Install the Focus Indicator browser extension (Chrome Web Store) to add a visible yellow outline to all focused elements.",
        "In Firefox, go to about:config and enable accessibility.browsewithcaret to see a text cursor on all pages.",
        "Use keyboard navigation in combination with NVDA's speech output to confirm focus position even when the indicator is not visible.",
        "Report pages where focus is invisible with specific interactive elements noted — this is a legal requirement.",
    ],
    "2.5.3": [
        "Use speech recognition software (Dragon NaturallySpeaking or Windows Speech Recognition) and say the visible button text — if the accessible name differs, the voice command may not work.",
        "Report mismatched accessible names to the vendor: specify the visible label and the announced name from a screen reader.",
        "As a workaround, use Tab to navigate to the control by position rather than by name.",
    ],
    "2.5.7": [
        "Look for a menu or settings option to perform the same action that is available via drag — many applications offer alternative UI for drag operations.",
        "Use NVDA's Object Navigator to interact with drag targets using the keyboard.",
        "On Windows, some drag operations can be performed via the keyboard using the application's context menu (Shift+F10 or the Menu key).",
        "Request the vendor add a keyboard-accessible alternative for all drag-and-drop interactions — this is required by WCAG 2.2.",
        "Contact the vendor specifically about this barrier as it is a WCAG 2.2 Level AA requirement added in 2023.",
    ],
    "2.5.8": [
        "Increase display scaling (Windows: Settings > Display > Scale) to make small targets larger on-screen.",
        "Use mouse pointer size settings (Windows: Settings > Ease of Access > Mouse Pointer) to make clicking more precise.",
        "Consider using a stylus or trackball for more controlled pointer input on small targets.",
    ],
    "3.1.1": [
        "Set your screen reader's language manually to match the content language in screen reader settings.",
        "In NVDA, go to NVDA Menu > Preferences > Speech > Language to set the synthesizer language.",
        "In JAWS, use the Language Selection dialog to set a preferred language.",
        "Report the missing lang attribute to the vendor — this is typically a one-line code fix.",
    ],
    "3.1.2": [
        "Set your screen reader to auto-detect language changes: in NVDA, enable 'Automatic language switching' under Preferences > Speech.",
        "If pronunciation is incorrect for a foreign phrase, manually switch your screen reader's language while reading that section.",
        "Request the vendor add lang attributes to all content in languages other than the primary page language.",
    ],
    "3.2.3": [
        "Use browser bookmarks to navigate directly to frequently used sections, bypassing inconsistent navigation.",
        "Use the browser's back button and history to retrace navigation paths when menus appear in unexpected positions.",
    ],
    "3.2.4": [
        "When a control appears to have changed its label, use NVDA's Object Properties (Insert+Tab) to verify its accessible name.",
        "Report inconsistently labeled controls to the vendor with screenshots of both instances.",
    ],
    "3.3.1": [
        "After submitting a form, use NVDA's Browse Mode to read the page from the top — error messages are usually announced near the form fields.",
        "Use JAWS's Forms Mode and navigate field by field after submission to hear any error messages.",
        "Request the vendor use aria-describedby or aria-live to ensure error messages are announced automatically.",
    ],
    "3.3.2": [
        "Before filling a form, read all surrounding text carefully for instructions that may not be programmatically associated.",
        "Use NVDA's Forms Mode (Enter key) then Tab to each field — some instructions may be adjacent but not associated.",
        "Request the vendor use aria-label or aria-labelledby to explicitly associate all form labels with their fields.",
    ],
    "3.3.3": [
        "If the application does not suggest a correction, look for inline help text or tooltips near the error field.",
        "Use the browser's built-in spell-check and form validation to catch errors before submitting.",
        "Request the vendor add specific error suggestions using aria-describedby on error messages.",
    ],
    "3.3.4": [
        "Before submitting any important form, take a screenshot or copy your input so you can reconstruct it if needed.",
        "Check whether the application sends a confirmation email — that serves as a record of submission.",
        "If the form has a review step, use it even if it appears optional.",
        "Faculty should document submission steps for students in case data is lost.",
    ],
    "3.3.8": [
        "If a CAPTCHA blocks login, look for an audio CAPTCHA alternative (usually a speaker icon on the CAPTCHA widget).",
        "Request the vendor implement WCAG 2.2 compliant authentication that does not require cognitive function tests.",
        "Use password manager autofill (Bitwarden, 1Password, browser built-in) to bypass typing-based authentication challenges.",
        "Students unable to complete authentication challenges should contact Disability Services for an alternative login method.",
    ],
    "4.1.1": [
        "This criterion is considered always satisfied under the WCAG 2.1 September 2023 errata update for modern browsers.",
        "No specific workaround is required — modern browsers handle malformed HTML gracefully.",
    ],
    "4.1.2": [
        "Use NVDA's Object Navigation (Insert+Numpad arrows) to interact with controls that are missing accessible names.",
        "Use JAWS's Virtual Cursor to read element properties for unlabeled controls.",
        "Install Accessibility Insights for Web (browser extension) to identify all controls missing name/role/value.",
        "Report specific controls with missing ARIA attributes to the vendor — include the page URL and control description.",
        "As a workaround, look for alternative ways to achieve the same action using keyboard-accessible standard controls.",
    ],
    "2.4.11": [
        "Enable High Contrast Mode in Windows (Win+Ctrl+C) to enhance visibility of all focused elements.",
        "Install the Focus Indicator browser extension (Chrome Web Store) to add a bright outline around the focused element.",
        "Use keyboard navigation alongside NVDA speech output — NVDA announces the focused element even when visually obscured.",
        "In Firefox, enable accessibility.browsewithcaret in about:config to show a text cursor that indicates focus position.",
        "Report specific pages where the focused element is obscured by a sticky header or fixed element to the vendor.",
    ],
    "4.1.3": [
        "After performing an action, manually navigate to the top of the page with Ctrl+Home and read downward to catch status messages.",
        "Use NVDA's Browse Mode and read from the current position with the Down arrow to catch announcements.",
        "Enable NVDA's 'Report changes to progress bars' in Preferences > Object Presentation to catch progress updates.",
        "Refresh the page after an action to confirm whether the action was successful.",
        "Request the vendor add aria-live='polite' regions to all status and notification areas.",
    ],
}

_GENERIC_WORKAROUND = [
    "Use a screen reader (NVDA for Windows, VoiceOver for macOS/iOS, TalkBack for Android) to navigate this feature.",
    "Try the keyboard-only navigation path: Tab to reach the element, Enter or Space to activate it.",
    "Contact the vendor's accessibility support team to request a remediation timeline for this barrier.",
    "Contact SFBRN for accommodation support if this barrier prevents completion of required work.",
]


def _generate_workaround(criterion) -> list:
    """Return the canned workaround bullet list for the given criterion."""
    return WORKAROUNDS.get(criterion.criterion_id, _GENERIC_WORKAROUND)


# WCAG 2.2-only criteria (kept in dataset for parsing, but the printed
# "WCAG 2.1 Success Criteria" reference tables include the 2.1 set plus any
# 2.2 rows actually found in the vendor VPAT — nothing parsed is dropped).
WCAG22_ONLY = {"2.4.11", "2.5.7", "2.5.8", "3.3.8"}


# ── Style helpers ──────────────────────────────────────────────────────────────

_style_counter = [0]

def _ps(name, **kw):
    """Create a ParagraphStyle with a guaranteed-unique name (v9 canonical rule:
    never reuse ParagraphStyle names across _ps() calls)."""
    _style_counter[0] += 1
    return ParagraphStyle(f"{name}_{_style_counter[0]}", **kw)

# Typography (master prompt, px treated as pt for print):
#   cover H1 26 / H2 18 / H3 15 / body 14 lh 1.75 / table 13 / caption 12
# Those sizes are scaled ~0.72 for a letter page with 1.25in margins so the
# report matches the visual density of the approved sample PDF.
FS_COVER = 19; FS_H2 = 13.5; FS_H3 = 11; FS_BODY = 10
FS_TABLE = 9;  FS_CAP = 8.5; FS_QUOTE = 9; FS_BADGE = 8; FS_LVL = 7.5

def _styles():
    return {
        "cover_title": _ps("CoverTitle", fontName="Helvetica-Bold",
            fontSize=FS_COVER, leading=FS_COVER * 1.25, textColor=C_PRIMARY,
            alignment=TA_CENTER, spaceAfter=6),
        "cover_sub": _ps("CoverSub", fontName="Helvetica", fontSize=11,
            leading=15, textColor=C_ACCENT, alignment=TA_CENTER, spaceAfter=4),
        "h2": _ps("H2Head", fontName="Helvetica-Bold", fontSize=FS_H2,
            textColor=C_PRIMARY, spaceBefore=20, spaceAfter=2),
        "h3": _ps("H3Head", fontName="Helvetica", fontSize=FS_H3,
            textColor=C_ACCENT, spaceBefore=12, spaceAfter=6),
        "body": _ps("BodyTxt", fontName="Helvetica", fontSize=FS_BODY,
            textColor=C_BODY, leading=FS_BODY * 1.75, spaceAfter=6),
        "small": _ps("SmallTxt", fontName="Helvetica", fontSize=FS_CAP,
            textColor=C_CAPTION, leading=12),
        "quote": _ps("QuoteTxt", fontName="Helvetica-Oblique", fontSize=FS_QUOTE,
            textColor=C_QUOTE, leading=14, spaceAfter=4),
        "bullet": _ps("BulletTxt", fontName="Helvetica", fontSize=FS_TABLE,
            textColor=C_BODY, leading=14, leftIndent=12, spaceAfter=3),
    }

def _h2(text, S):
    """H2 with the master-prompt 2px bottom border in primary blue."""
    return [
        Paragraph(text, S["h2"]),
        HRFlowable(width="100%", thickness=2, color=C_PRIMARY,
                   spaceBefore=2, spaceAfter=10),
    ]

def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=C_BORDER,
                      spaceBefore=12, spaceAfter=12)

CONTENT_W = 6.0 * inch   # letter width minus 1.25in left/right margins


def _pill(text, bg, font_size=FS_BADGE, width=None):
    """Pill-shaped badge (border-radius look) as a small nested table."""
    p = Paragraph(text, _ps("Pill", fontName="Helvetica-Bold",
        fontSize=font_size, textColor=C_WHITE, alignment=TA_CENTER, leading=font_size + 2))
    w = width or (0.14 * inch + 0.062 * inch * len(text))
    t = Table([[p]], colWidths=[w], rowHeights=[font_size + 9])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), bg),
        ("ROUNDEDCORNERS", [7, 7, 7, 7]),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t

def _status_pill(status):
    return _pill(status, STATUS_COLORS.get(status, C_NOT_EVAL))

def _level_pill(level):
    color = C_PRIMARY if level == "A" else C_ACCENT
    return _pill(f"Level {level}", color, font_size=FS_LVL)


def _callout(paragraphs, accent=True):
    """Light-blue callout box; optional 3pt left accent bar (sample style)."""
    rows = [[p] for p in paragraphs]
    inner = Table(rows, colWidths=[CONTENT_W - (5 if accent else 0)])
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    if not accent:
        return inner
    outer = Table([["", inner]], colWidths=[5, CONTENT_W - 5])
    outer.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), C_ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return outer


def _info_table(rows):
    """Two-column info table: 1.9in bold primary label column, striped rows."""
    data = []
    for lbl, val in rows:
        data.append([
            Paragraph(str(lbl), _ps("InfoK", fontName="Helvetica-Bold",
                fontSize=FS_TABLE, textColor=C_PRIMARY, leading=13)),
            Paragraph(str(val) if val else "", _ps("InfoV",
                fontName="Helvetica", fontSize=FS_TABLE,
                textColor=C_BODY, leading=13)),
        ])
    t = Table(data, colWidths=[1.9 * inch, CONTENT_W - 1.9 * inch])
    ts = TableStyle([
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ])
    for i in range(len(data)):
        ts.add("BACKGROUND", (0, i), (-1, i), C_BG if i % 2 == 0 else C_WHITE)
    t.setStyle(ts)
    return t


def _grid_table(header_cells, rows, col_widths):
    """Generic striped table: primary-blue header, alternating rows."""
    hdr = [Paragraph(f"<b>{h}</b>", _ps("GridH", fontName="Helvetica-Bold",
           fontSize=FS_TABLE, textColor=C_WHITE, leading=13)) for h in header_cells]
    data = [hdr] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_PRIMARY),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 9),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 9),
    ])
    for i in range(1, len(data)):
        ts.add("BACKGROUND", (0, i), (-1, i), C_BG if i % 2 == 1 else C_WHITE)
    t.setStyle(ts)
    return t


def _compliance_meter(score, threshold, org_short):
    """Executive Summary meter: big %, threshold label, progress bar, caption."""
    pct_style = _ps("MeterPct", fontName="Helvetica-Bold", fontSize=22,
                    textColor=C_PRIMARY, leading=24)
    lbl_style = _ps("MeterLbl", fontName="Helvetica", fontSize=FS_TABLE,
                    textColor=C_BODY, leading=13)
    cap_style = _ps("MeterCap", fontName="Helvetica", fontSize=FS_CAP,
                    textColor=C_CAPTION, leading=12)

    bar_w = CONTENT_W - 0.5 * inch
    d = Drawing(bar_w, 14)
    track = Rect(0, 2, bar_w, 10, fillColor=C_WHITE, strokeColor=C_BORDER,
                 strokeWidth=0.6)
    track.rx = track.ry = 5
    d.add(track)
    if score:
        fill = Rect(0, 2, max(10, bar_w * min(score, 100) / 100.0), 10,
                    fillColor=C_ACCENT, strokeColor=None)
        fill.rx = fill.ry = 5
        d.add(fill)

    if score is None:
        caption = ("Compliance score could not be calculated because no "
                   "reviewable WCAG Level AA criteria were found.")
        head = [[Paragraph("N/A", pct_style),
                 Paragraph(f"WCAG 2.1 Level AA compliance "
                           f"({org_short} threshold: {threshold}%)", lbl_style)]]
    else:
        verdict = ("meets or exceeds" if score >= threshold else "falls below")
        caption = f"Score {verdict} the {threshold}% {org_short} threshold."
        head = [[Paragraph(f"{score}%", pct_style),
                 Paragraph(f"WCAG 2.1 Level AA compliance "
                           f"({org_short} threshold: {threshold}%)", lbl_style)]]

    ht = Table(head, colWidths=[0.95 * inch, bar_w - 0.95 * inch])
    ht.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    box = Table([[ht], [d], [Paragraph(caption, cap_style)]],
                colWidths=[bar_w])
    box.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BG),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return box


def _wcag_lookup(cid):
    """Official description + plain-language text from the bundled WCAG 2.1
    Quick Reference dataset. Never invents descriptions (master prompt rule)."""
    if wcag_reference is not None:
        entry = wcag_reference.lookup(cid)
        if entry:
            return entry.get("description", ""), entry.get("plain", "")
    return "", ""


# ── Two-pass canvas: header/footer with "Page X of Y" ──────────────────────────

def _make_numbered_canvas(settings, product_name, report_date, logo_path):
    """Canvas subclass that buffers pages, then draws the running header
    (pages 2+) and three-part footer with 'Page X of Y' on save()."""

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_states = []

        def showPage(self):
            self._saved_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_states)
            for i, state in enumerate(self._saved_states):
                self.__dict__.update(state)
                self._draw_chrome(i + 1, total)
                super().showPage()
            super().save()

        # ---- header + footer -------------------------------------------------
        def _draw_chrome(self, page_num, total):
            w, h = letter
            self.saveState()
            if page_num > 1:
                self._draw_header(w, h)
            self._draw_footer(w, page_num, total)
            self.restoreState()

        def _draw_header(self, w, h):
            # 4pt solid top border, full width, primary blue
            self.setFillColor(C_PRIMARY)
            self.rect(0, h - 4, w, 4, fill=1, stroke=0)
            band_top = h - 0.18 * inch
            # Logo block: primary-blue rectangle with white inner logo panel
            blk_w, blk_h = 1.45 * inch, 0.62 * inch
            blk_x, blk_y = 0.55 * inch, band_top - blk_h
            self.setFillColor(C_PRIMARY)
            self.rect(blk_x, blk_y, blk_w, blk_h, fill=1, stroke=0)
            pad = 4
            self.setFillColor(C_WHITE)
            self.rect(blk_x + pad, blk_y + pad, blk_w - 2 * pad,
                      blk_h - 2 * pad, fill=1, stroke=0)
            drawn = False
            if logo_path and os.path.exists(logo_path):
                try:
                    self.drawImage(logo_path, blk_x + pad + 2, blk_y + pad + 2,
                                   width=blk_w - 2 * pad - 4,
                                   height=blk_h - 2 * pad - 4,
                                   preserveAspectRatio=True, mask="auto")
                    drawn = True
                except Exception:
                    drawn = False
            if not drawn:
                self.setFillColor(C_PRIMARY)
                self.setFont("Helvetica-Bold", 12)
                self.drawCentredString(blk_x + blk_w / 2,
                                       blk_y + blk_h / 2 - 4,
                                       settings["org_short"])
            # Centered-left title in primary blue + date at right in gray
            self.setFillColor(C_PRIMARY)
            self.setFont("Helvetica-Bold", 9.5)
            ty = blk_y + blk_h / 2 - 3
            self.drawString(blk_x + blk_w + 0.14 * inch, ty,
                            settings["report_title"])
            self.setFillColor(C_CAPTION)
            self.setFont("Helvetica", 8.5)
            self.drawRightString(w - 0.55 * inch, ty, report_date)
            # 1px divider below header
            self.setStrokeColor(C_BORDER)
            self.setLineWidth(0.8)
            self.line(0.55 * inch, blk_y - 0.12 * inch,
                      w - 0.55 * inch, blk_y - 0.12 * inch)

        def _draw_footer(self, w, page_num, total):
            self.setStrokeColor(C_BORDER)
            self.setLineWidth(0.6)
            self.line(0.55 * inch, 0.72 * inch, w - 0.55 * inch, 0.72 * inch)
            self.setFillColor(C_CAPTION)
            self.setFont("Helvetica", 7.5)
            year = datetime.now().year
            self.drawString(0.55 * inch, 0.55 * inch,
                f"\u00a9{year} {settings['org_name']}.")
            self.drawCentredString(w / 2, 0.55 * inch,
                f"{settings['report_title']}.")
            self.drawRightString(w - 0.55 * inch, 0.55 * inch,
                f"Page {page_num} of {total}")

    return NumberedCanvas


# ── Barrier / gap card ─────────────────────────────────────────────────────────

def _criterion_card(crit, S, is_na_gap=False):
    """Sample-style card: blue title, italic quoted criterion text,
    'What this means', pill badges, shaded Vendor Remarks block."""
    wcag_info = WCAG_DATA.get(crit.criterion_id)
    crit_title = wcag_info[0] if wcag_info else (crit.title or "")
    description, plain = _wcag_lookup(crit.criterion_id)

    items = []
    items.append(Paragraph(f"{crit.criterion_id} {crit_title}",
        _ps("CardTitle", fontName="Helvetica", fontSize=11.5,
            textColor=C_ACCENT, spaceBefore=2, spaceAfter=6)))

    if description:
        items.append(Paragraph(
            f"\u201c{description}\u201d "
            f'<font size="{FS_CAP}" color="#555555">\u2014 WCAG 2.1 Quick Reference</font>',
            S["quote"]))
    else:
        items.append(Paragraph(
            "[Official WCAG criterion text unavailable \u2014 WCAG reference "
            "dataset missing]", S["quote"]))
        logger.error("WCAG reference lookup failed for %s", crit.criterion_id)

    wtm = plain or ""
    if is_na_gap:
        wtm += (" The vendor reports this criterion as Not Applicable; per "
                "SFBRN policy it is documented transparently as a known gap "
                "and is excluded from the compliance score.")
    if wtm.strip():
        items.append(Paragraph(
            f'<font color="#2e6db5"><b>What this means:</b></font> {wtm.strip()}',
            _ps("Wtm", fontName="Helvetica", fontSize=FS_TABLE,
                textColor=C_BODY, leading=15, spaceBefore=2, spaceAfter=6)))

    badge_row = Table(
        [[_level_pill("AA"), _status_pill(crit.normalized_status), ""]],
        colWidths=[0.75 * inch, 1.45 * inch, CONTENT_W - 2.6 * inch])
    badge_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    items.append(badge_row)

    remarks_text = crit.remarks or "[No vendor remarks provided]"
    remarks_p = Paragraph(
        f'<font color="#1a4f8a"><b>Vendor Remarks:</b></font> {remarks_text}',
        _ps("VRemark", fontName="Helvetica", fontSize=FS_TABLE,
            textColor=C_BODY, leading=14))
    rt = Table([[remarks_p]], colWidths=[CONTENT_W - 0.55 * inch])
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BG),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROUNDEDCORNERS", [5, 5, 5, 5]),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    items.append(rt)

    card = Table([[it] for it in items], colWidths=[CONTENT_W - 0.3 * inch])
    card.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.75, C_BORDER),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("BACKGROUND",    (0, 0), (-1, -1), C_WHITE),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    card.hAlign = "CENTER"
    return card


def _sort_key(cid):
    try:
        return [int(n) for n in cid.split(".")]
    except ValueError:
        return [99, 99, 99]


# ── Third-party AT tool table (master prompt canonical 15-tool list) ──────────

AT_TOOLS = [
    ("NVDA (NonVisual Desktop Access)",
     "Free, open-source screen reader for Windows that reads screen content aloud and supports braille displays.",
     "https://www.nvaccess.org"),
    ("VoiceOver",
     "Built-in screen reader for macOS and iOS devices that provides speech and braille output.",
     "https://www.apple.com/accessibility/vision"),
    ("Narrator",
     "Free screen reader included in Windows that reads text and UI elements aloud.",
     "https://support.microsoft.com/windows/narrator-guide"),
    ("TalkBack",
     "Android's built-in screen reader that enables spoken feedback and gesture navigation.",
     "https://support.google.com/accessibility/android"),
    ("Orca",
     "Free, open-source screen reader for Linux systems using speech and braille output.",
     "https://orca.gnome.org"),
    ("ChromeVox",
     "Screen reader built into Chrome OS for Chromebook users.",
     "https://support.google.com/chromebook"),
    ("NaturalReader",
     "Text-to-speech software that converts documents, PDFs, and web pages into spoken audio (free tier available).",
     "https://www.naturalreaders.com"),
    ("Voice Dream Reader",
     "Mobile app that reads ebooks and documents aloud with customizable voices and accessibility features.",
     "https://www.voicedream.com/reader"),
    ("Read&Write",
     "Literacy support tool with text-to-speech, word prediction, and comprehension aids (free version available).",
     "https://www.texthelp.com/products/read-and-write"),
    ("Balabolka",
     "Free Windows text-to-speech program with customizable voices and file export options.",
     "http://www.cross-plus-a.com/balabolka.htm"),
    ("WordTalk",
     "Free Microsoft Word plugin that reads documents aloud and supports speech customization.",
     "https://www.wordtalk.org.uk"),
    ("Google Live Transcribe",
     "Real-time speech-to-text app for Android that provides captions for conversations.",
     "https://play.google.com/store/apps/details?id=com.google.audio.hearing.visualization.accessibility.scribe"),
    ("Otter.ai",
     "Speech-to-text transcription tool for meetings and lectures (free plan available).",
     "https://otter.ai"),
    ("Microsoft Dictate",
     "Free speech-to-text add-in for Microsoft Office that converts spoken words into text.",
     "https://dictate.ms"),
    ("Seeing AI",
     "AI-powered app that narrates the world (text, people, objects) for visually impaired users.",
     "https://www.microsoft.com/ai/seeing-ai"),
]


# ── Main report builder ────────────────────────────────────────────────────────

def generate_report(vpat_data, score_info, impact_info, reviewer_answers,
                    output_path, logo_path="", settings=None):
    cfg = _merged_settings(settings)
    S = _styles()
    today_str = date.today().strftime("%B %d, %Y")
    org       = cfg["org_name"]
    org_short = cfg["org_short"]
    reviewer  = cfg["reviewer_name"]
    rev_title = cfg["reviewer_title"]
    threshold = cfg["threshold"]
    rpt_title = cfg["report_title"]

    product   = vpat_data.product_name or "[PRODUCT NAME NOT FOUND]"
    version   = vpat_data.product_version or "[VERSION NOT SPECIFIED IN VPAT]"
    vendor    = vpat_data.vendor_name or "[VENDOR NOT FOUND]"
    vpat_date = vpat_data.vendor_report_date_raw or "[VENDOR REPORT DATE NOT FOUND]"
    edition   = vpat_data.vpat_edition or "[VPAT EDITION NOT FOUND]"
    v_contact = vpat_data.vendor_contact or "[VENDOR CONTACT NOT FOUND]"

    score     = score_info.get("score")
    score_str = f"{score}%" if score is not None else "N/A"

    # v9 canonical exec-summary arithmetic
    supported      = score_info.get("supported", 0)
    total_aa       = score_info.get("total_aa_found", score_info.get("total", 0))
    total_reviewed = score_info.get("total", 0)
    na_excl        = score_info.get("na_excluded", 0)

    # Option A: barriers (scored) vs NA documented gaps (displayed only)
    aa_criteria = [c for c in vpat_data.criteria if c.level == "AA"]
    barriers = sorted(
        [c for c in aa_criteria
         if c.normalized_status not in ("Supports", "Not Applicable")],
        key=lambda c: _sort_key(c.criterion_id))
    na_gaps = sorted(
        [c for c in aa_criteria if c.normalized_status == "Not Applicable"],
        key=lambda c: _sort_key(c.criterion_id))
    section2_items = sorted(barriers + na_gaps,
                            key=lambda c: _sort_key(c.criterion_id))

    impact_level = impact_info.get("final_level",
                       impact_info.get("suggested_level", "Medium"))

    NumberedCanvas = _make_numbered_canvas(cfg, product, today_str, logo_path)
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=1.2 * inch, bottomMargin=1.0 * inch,
        leftMargin=1.25 * inch, rightMargin=1.25 * inch,
        title=rpt_title, author=f"{reviewer}, {org_short}",
    )
    story = []

    # ══ 1. COVER PAGE ══════════════════════════════════════════════════════════
    story.append(Spacer(1, 0.35 * inch))
    logo_ok = False
    if logo_path and os.path.exists(logo_path):
        try:
            logo = RLImage(logo_path, height=0.95 * inch, width=2.6 * inch,
                           kind="proportional")
            logo.hAlign = "CENTER"
            story.append(logo)
            logo_ok = True
        except Exception as e:
            logger.warning("Cover logo failed: %s", e)
    if not logo_ok:
        badge = Table([[Paragraph(
            f'<font color="white"><b>{org_short}</b></font>',
            _ps("CoverBadge", fontName="Helvetica-Bold", fontSize=16,
                textColor=C_WHITE, alignment=TA_CENTER))]],
            colWidths=[1.6 * inch], rowHeights=[0.55 * inch])
        badge.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_PRIMARY),
            ("ROUNDEDCORNERS", [8, 8, 8, 8]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        badge.hAlign = "CENTER"
        story.append(badge)
        story.append(Spacer(1, 0.06 * inch))
        story.append(Paragraph(
            f"Logo file not found \u2014 text badge used as fallback.",
            _ps("LogoWarn", fontName="Helvetica", fontSize=7.5,
                textColor=C_CAPTION, alignment=TA_CENTER)))
    story.append(Spacer(1, 0.28 * inch))
    story.append(Paragraph(rpt_title, S["cover_title"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        f"{product}&nbsp;&nbsp;|&nbsp;&nbsp;Version: {version}"
        f"&nbsp;&nbsp;|&nbsp;&nbsp;Evaluation Date: {today_str}",
        S["cover_sub"]))
    story.append(Spacer(1, 0.2 * inch))

    stds_str = ", ".join(vpat_data.standards_reviewed) \
               if vpat_data.standards_reviewed else "[STANDARDS NOT FOUND]"
    meta_rows = [
        ("Product", product), ("Version", version), ("Vendor", vendor),
        ("Vendor Report Date", vpat_date), ("VPAT Edition", edition),
        ("Standards Reviewed", stds_str),
        ("Prepared By", reviewer),
        ("Organization", org),
        ("Vendor Contact", v_contact),
        (f"{org_short} Contact", cfg["org_contact"] or
             vpat_data.sfbrn_contact or ""),
    ]
    story.append(_info_table(meta_rows))
    story.append(Spacer(1, 0.14 * inch))
    story.append(Paragraph(
        f"This summary report was prepared by {org} from the "
        f"vendor-submitted Voluntary Product Accessibility Template (VPAT) for "
        f"{product}. It restates vendor conformance claims, identifies "
        f"accessibility barriers at WCAG 2.1 Level AA, and provides "
        f"plain-language explanations and practical workarounds for faculty, "
        f"staff, auditors, and procurement reviewers. It is not an independent "
        f"audit of the product.", S["small"]))
    story.append(_hr())
    story.append(PageBreak())

    # ══ 2. EXECUTIVE SUMMARY ═══════════════════════════════════════════════════
    story.extend(_h2("Executive Summary", S))

    exec_text = ""
    if vpat_data.product_description:
        exec_text += (f"{product} \u2014 {vpat_data.product_description[:280]} ")
    exec_text += (
        f"{org_short} reviewed the vendor-submitted VPAT against the WCAG 2.1 "
        f"Level AA success criteria. ")
    if total_aa > 0 and score is not None:
        if na_excl > 0:
            exec_text += (
                f"The review evaluated {total_aa} Level AA criteria, of which "
                f"{na_excl} were reported Not Applicable and excluded from "
                f"scoring per {org_short} policy; of the {total_reviewed} "
                f"reviewable criteria, {supported} were fully supported, "
                f"producing an {org_short} compliance score of <b>{score_str}</b> "
                f"\u2014 {'meeting' if score >= threshold else 'below'} the "
                f"{org_short} {threshold}% threshold. ")
        else:
            exec_text += (
                f"Of the {total_reviewed} reviewable Level AA criteria, "
                f"{supported} were fully supported, producing an {org_short} "
                f"compliance score of <b>{score_str}</b> \u2014 "
                f"{'meeting' if score >= threshold else 'below'} the "
                f"{org_short} {threshold}% threshold. ")
    if barriers:
        bnames = ", ".join(
            (WCAG_DATA.get(b.criterion_id, (b.title,))[0] or "").lower()
            for b in barriers[:5])
        exec_text += (
            f"A total of <b>{len(barriers)} Level AA barrier(s)</b> were "
            f"identified, centering on {bnames}; documented workarounds "
            f"appear in Section 3 of this report. ")
    if na_gaps:
        exec_text += (
            f"{len(na_gaps)} additional criteria were reported Not Applicable "
            f"and are documented transparently in Section 2 as known gaps. ")
    if vpat_data.is_outdated:
        exec_text += (
            f"Reviewers should also note that the vendor report date "
            f"({vpat_date}) is more than 12 months older than this review "
            f"date, so the claims may not reflect the current product; "
            f"{org_short} recommends requesting an updated VPAT from the vendor.")
    story.append(Paragraph(exec_text, S["body"]))
    story.append(Spacer(1, 0.12 * inch))

    story.append(_compliance_meter(score, threshold, org_short))
    story.append(Spacer(1, 0.14 * inch))

    if vpat_data.is_outdated:
        story.append(_callout([Paragraph(
            f'<font color="#1a4f8a"><b>Outdated VPAT notice:</b></font> '
            f"The vendor report date ({vpat_date}) is more than 12 months "
            f"older than the {org_short} review date ({today_str}), exceeding "
            f"the {org_short} VPAT currency window. An updated vendor VPAT "
            f"should be requested, and unverified claims should be treated "
            f"with caution.",
            _ps("OutdatedTxt", fontName="Helvetica", fontSize=FS_TABLE,
                textColor=C_BODY, leading=14))]))
    story.append(_hr())

    # ── Impact Assessment (SFBRN review-context feature, retained from v9) ─────
    story.extend(_h2("Impact Assessment", S))
    audience_labels = {"individual": "1 user (individual)",
                       "small_team": "2\u201320 users (small team)",
                       "campus_wide": "21+ users (campus-wide)"}
    access_labels = {"no_limit": "Does not limit access",
                     "limits_some": "Limits some access",
                     "denies_access": "Denies access"}
    legal_labels = {"low": "Low", "medium": "Medium", "high": "High"}
    deploy_labels = {"individual": "Individual", "department": "Department",
                     "campus_wide": "Campus-wide"}
    story.append(_info_table([
        ("Audience / Users",
         audience_labels.get(reviewer_answers.get("audience", ""), "")),
        ("Access for Users with Disabilities",
         access_labels.get(reviewer_answers.get("access_impact", ""), "")),
        ("Legal Exposure",
         legal_labels.get(reviewer_answers.get("legal_exposure", ""), "")),
        ("Deployment Scope",
         deploy_labels.get(reviewer_answers.get("deployment", ""), "")),
        ("Suggested Impact Level", impact_info.get("suggested_level", "")),
        ("Final Impact Level", impact_level),
    ]))
    story.append(Spacer(1, 0.1 * inch))
    rationale = impact_info.get("rationale", [])
    if rationale:
        story.append(Paragraph("<b>Basis for Impact Determination:</b>",
                               S["body"]))
        for r in rationale:
            story.append(Paragraph(f"\u2022  {r}", S["small"]))
        story.append(Spacer(1, 0.08 * inch))
    impact_msgs = {
        "High": ("<b>High Impact \u2014 Alternative Access Plan Required.</b> "
                 "One or more core accessibility barriers may prevent users "
                 "with disabilities from completing required tasks. An "
                 "Alternative Access Plan must be developed and attached to "
                 "this report before campus-wide deployment approval."),
        "Medium": ("<b>Medium Impact \u2014 Department Review Recommended.</b> "
                   "Identified barriers may affect some users in meaningful "
                   f"ways. {org_short} recommends a departmental accessibility "
                   "review before final procurement approval. Standard "
                   "workarounds are documented in Section 3."),
        "Low": ("<b>Low Impact \u2014 Standard Workarounds Sufficient.</b> "
                "Barriers affect a limited number of users and the standard "
                "workarounds in Section 3 are expected to provide adequate "
                "accommodation."),
    }
    story.append(_callout([Paragraph(
        impact_msgs.get(impact_level, impact_msgs["Medium"]),
        _ps("ImpactTxt", fontName="Helvetica", fontSize=FS_TABLE,
            textColor=C_BODY, leading=14))]))
    story.append(_hr())

    # ══ 3. SECTION 1 — PRODUCT AND DESCRIPTION ═════════════════════════════════
    story.extend(_h2("Section 1 \u2014 Product and Description", S))
    story.append(_info_table([
        ("Product Name", product), ("Version", version), ("Vendor", vendor),
        ("Description", vpat_data.product_description
             or "[PRODUCT DESCRIPTION NOT FOUND]"),
        ("Product Type", vpat_data.product_type or ""),
        ("VPAT Date", vpat_date +
            (" \u2014 flagged as outside the 12-month currency window"
             if vpat_data.is_outdated else "")),
        ("VPAT Edition", edition),
        ("Evaluation Date", today_str),
        ("Evaluated By", f"{reviewer}, {rev_title}, {org_short}"),
        ("Vendor Contact", v_contact),
    ]))
    story.append(Paragraph("Vendor Evaluation Methods", S["h3"]))
    story.append(Paragraph(
        (vpat_data.evaluation_methods.replace("\n", "<br/>")
         if vpat_data.evaluation_methods
         else "[VENDOR EVALUATION METHODS NOT FOUND]"), S["body"]))
    story.append(_hr())

    # ══ 4. APPLICABLE STANDARDS ════════════════════════════════════════════════
    story.extend(_h2("Applicable Standards / Guidelines", S))
    std_list = ["WCAG 2.0 Level A", "WCAG 2.0 Level AA", "WCAG 2.0 Level AAA",
                "WCAG 2.1 Level A", "WCAG 2.1 Level AA", "WCAG 2.1 Level AAA",
                "Section 508 (Revised 2017)"]
    cell_std = lambda txt: Paragraph(txt, _ps("StdCell",
        fontName="Helvetica", fontSize=FS_TABLE, textColor=C_BODY, leading=13))
    std_rows = []
    detected = vpat_data.standards_reviewed or []
    for name in std_list:
        base = name.replace(" (Revised 2017)", "")
        inc = any(base.lower() in d.lower() or d.lower() in name.lower()
                  for d in detected)
        std_rows.append([cell_std(name), cell_std("Yes" if inc else "No")])
    story.append(_grid_table(["Standard / Guideline", "Included in Report"],
                             std_rows, [4.2 * inch, CONTENT_W - 4.2 * inch]))
    story.append(_hr())

    # ══ 5. TERMS AND STATUS DEFINITIONS ════════════════════════════════════════
    story.extend(_h2("Terms and Status Definitions", S))
    defs = [
        ("Supports", "The functionality of the product has at least one method "
         "that meets the criterion without known defects or meets with "
         "equivalent facilitation."),
        ("Partially Supports",
         "Some functionality of the product does not meet the criterion."),
        ("Does Not Support", "The majority of product functionality does not "
         "meet the criterion."),
        ("Not Applicable", "The criterion is not relevant to the product."),
        ("Not Evaluated", "The product has not been evaluated against the "
         "criterion."),
    ]
    def_rows = []
    for status, definition in defs:
        def_rows.append([
            _status_pill(status),
            Paragraph(definition, _ps("DefTxt", fontName="Helvetica",
                fontSize=FS_TABLE, textColor=C_BODY, leading=14)),
        ])
    story.append(_grid_table(["Status", "Definition"], def_rows,
                             [1.7 * inch, CONTENT_W - 1.7 * inch]))
    story.append(_hr())

    # ══ 6. SECTION 2 — IDENTIFIED BARRIERS (LEVEL AA) ══════════════════════════
    story.extend(_h2("Section 2 \u2014 Identified Barriers (Level AA)", S))
    story.append(_callout([Paragraph(
        "This section lists every WCAG 2.1 <b>Level AA</b> criterion that the "
        "vendor reported as anything other than \u201cSupports\u201d \u2014 "
        "including \u201cPartially Supports,\u201d \u201cDoes Not Support,\u201d "
        "\u201cNot Evaluated,\u201d and \u201cNot Applicable.\u201d "
        f"Not Applicable items are documented transparently as known gaps per "
        f"{org_short} policy but are <b>excluded from the compliance score</b>, "
        "since the underlying feature is not present in the product. Fully "
        "supported criteria are excluded; no workarounds are needed for them. "
        "Vendor remarks are reproduced verbatim and unaltered; "
        f"{org_short} adds only the quoted criterion text and a plain-language "
        f"explanation. {len(section2_items)} of {total_aa} Level AA criteria "
        "appear below.",
        _ps("ScopeTxt", fontName="Helvetica", fontSize=FS_TABLE,
            textColor=C_BODY, leading=14))]))
    story.append(Spacer(1, 0.12 * inch))

    if not section2_items:
        story.append(_callout([Paragraph(
            "No Level AA barriers were identified in the submitted VPAT.",
            _ps("NoBarTxt", fontName="Helvetica", fontSize=FS_TABLE,
                textColor=C_BODY, leading=14))]))
    else:
        for crit in section2_items:
            story.append(KeepTogether(_criterion_card(
                crit, S, is_na_gap=(crit.normalized_status == "Not Applicable"))))
            story.append(Spacer(1, 0.12 * inch))
    story.append(_hr())

    # ══ 7. SECTION 3 — WORKAROUNDS ═════════════════════════════════════════════
    story.extend(_h2("Section 3 \u2014 Workarounds", S))
    story.append(_callout([Paragraph(
        f"The workarounds below let {org_short} faculty, staff, and students "
        "complete tasks despite the barriers identified in Section 2. They "
        "rely on standard assistive technologies (AT), browser and operating "
        "system accessibility settings, and free or low-cost third-party "
        "tools. Workarounds are interim measures \u2014 they do not replace "
        "vendor remediation of the underlying barriers. Fully supported "
        "criteria do not require workarounds.",
        _ps("WkScope", fontName="Helvetica", fontSize=FS_TABLE,
            textColor=C_BODY, leading=14))]))

    story.append(Paragraph("General Assistive Technology Compatibility",
                           S["h3"]))
    story.append(Paragraph(
        "Users should keep assistive technology current. Mainstream screen "
        "readers \u2014 JAWS and NVDA on Windows, VoiceOver on macOS/iOS, "
        "TalkBack on Android, Orca on Linux, and ChromeVox on Chrome OS \u2014 "
        "generally operate standards-based web and desktop products, subject "
        "to the partial-support caveats described in Section 2. Browser zoom, "
        "reflow, and high-contrast settings can compensate for many contrast "
        "and focus-visibility issues.", S["body"]))

    if section2_items:
        story.append(Paragraph("Workarounds by Criterion", S["h3"]))
        for crit in section2_items:
            wcag_info = WCAG_DATA.get(crit.criterion_id)
            crit_title = wcag_info[0] if wcag_info else (crit.title or "")
            witems = [Paragraph(f"{crit.criterion_id} {crit_title}",
                _ps("WkHead", fontName="Helvetica", fontSize=10.5,
                    textColor=C_ACCENT, spaceAfter=4))]
            for w in _generate_workaround(crit):
                witems.append(Paragraph(f"\u2022  {w}", S["bullet"]))
            wt = Table([[it] for it in witems],
                       colWidths=[CONTENT_W - 0.3 * inch])
            wt.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), C_WHITE),
                ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
                ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            wt.hAlign = "CENTER"
            story.append(KeepTogether(wt))
            story.append(Spacer(1, 0.09 * inch))

    story.append(Paragraph("Operating-System Accessibility Settings", S["h3"]))
    os_rows_src = [
        ("Windows", "Settings \u25b8 Accessibility offers Narrator (built-in "
         "screen reader), Magnifier (Win + Plus), high-contrast themes, text "
         "scaling, and Voice Typing (Win + H) \u2014 useful for enlarging "
         "vague labels and dictating form input."),
        ("macOS", "System Settings \u25b8 Accessibility provides VoiceOver "
         "(Cmd + F5), Zoom, Increase Contrast, Reduce Motion, and per-language "
         "VoiceOver voices."),
        ("Linux", "GNOME Settings \u25b8 Accessibility includes the Orca "
         "screen reader, full-screen magnifier, high-contrast mode, and "
         "large-text settings."),
    ]
    os_rows = [[Paragraph(f"<b>{o}</b>", _ps("OsName",
                   fontName="Helvetica-Bold", fontSize=FS_TABLE,
                   textColor=C_PRIMARY, leading=13)),
                Paragraph(d, _ps("OsDesc", fontName="Helvetica",
                   fontSize=FS_TABLE, textColor=C_BODY, leading=14))]
               for o, d in os_rows_src]
    story.append(_grid_table(["Operating System", "Key Accessibility Settings"],
                             os_rows, [1.5 * inch, CONTENT_W - 1.5 * inch]))

    story.append(Paragraph("Third-Party Assistive Applications", S["h3"]))
    at_rows = []
    for name, desc, url in AT_TOOLS:
        at_rows.append([
            Paragraph(name, _ps("AtName", fontName="Helvetica",
                fontSize=FS_TABLE, textColor=C_BODY, leading=13)),
            Paragraph(desc, _ps("AtDesc", fontName="Helvetica",
                fontSize=FS_CAP, textColor=C_BODY, leading=12)),
            Paragraph(f'<link href="{url}"><font color="#2e6db5">{url}'
                      f'</font></link>',
                _ps("AtUrl", fontName="Helvetica", fontSize=FS_CAP,
                    textColor=C_ACCENT, leading=12)),
        ])
    story.append(_grid_table(["Tool Name", "Description", "URL"], at_rows,
                             [1.5 * inch, 2.1 * inch, CONTENT_W - 3.6 * inch]))
    story.append(_hr())

    # ══ 8. SECTION 4 — SUMMARY REPORT ══════════════════════════════════════════
    story.extend(_h2("Section 4 \u2014 Summary Report", S))
    s4 = f"{product} "
    if vpat_data.product_description:
        s4 += f"is {vpat_data.product_description[:200].rstrip('.')}, and the "
    else:
        s4 += "was reviewed by " + org_short + ", and the "
    s4 += (f"vendor's VPAT reports that {supported} of the {total_reviewed} "
           f"reviewable WCAG 2.1 Level AA criteria are fully met, for an "
           f"{org_short} compliance score of <b>{score_str}</b>, "
           f"{'meeting' if score is not None and score >= threshold else 'below'} "
           f"the {org_short} {threshold}% threshold. ")
    if barriers:
        s4 += (f"People who rely on assistive technology may run into "
               f"{len(barriers)} partially or unsupported area(s); practical "
               f"workarounds exist for every identified barrier, including "
               f"navigating by headings or landmarks, using persistent search, "
               f"and pairing the product with free tools such as NVDA, "
               f"VoiceOver, Otter.ai, or Read&amp;Write. ")
    if na_gaps:
        s4 += (f"{len(na_gaps)} criteria the vendor marks as Not Applicable "
               f"are recorded transparently as known gaps. ")
    s4 += (f"The product has been assigned an impact level of "
           f"<b>{impact_level}</b>. ")
    if vpat_data.is_outdated:
        s4 += (f"Because the vendor's VPAT is outside the {org_short} "
               f"12-month currency window, {org_short} recommends requesting "
               f"a current VPAT and independent third-party testing of the "
               f"criteria the vendor did not evaluate before final "
               f"procurement approval.")
    story.append(Paragraph(s4, S["body"]))
    story.append(_hr())

    # ══ 9–12. WCAG 2.1 SUCCESS CRITERIA — A/B/C/D BY PRINCIPLE ════════════════
    parsed_map = {c.criterion_id: c for c in vpat_data.criteria}
    section_letter = {"Perceivable": "A", "Operable": "B",
                      "Understandable": "C", "Robust": "D"}
    for principle in PRINCIPLES:
        story.extend(_h2(
            f"WCAG 2.1 Success Criteria Section "
            f"{section_letter[principle]} \u2014 {principle}", S))
        rows = []
        for cid, (ctitle, clevel, cprinciple) in sorted(
                WCAG_DATA.items(), key=lambda x: _sort_key(x[0])):
            if cprinciple != principle or clevel not in ("A", "AA"):
                continue
            parsed = parsed_map.get(cid)
            if cid in WCAG22_ONLY and parsed is None:
                continue  # 2.2-only rows appear only if the VPAT included them
            status = parsed.normalized_status if parsed else "Not Evaluated"
            remarks = (parsed.remarks if parsed and parsed.remarks else "\u2014")
            rows.append([
                Paragraph(f"<b>{cid}</b> {ctitle}", _ps("WrCrit",
                    fontName="Helvetica", fontSize=FS_CAP,
                    textColor=C_BODY, leading=12)),
                _level_pill(clevel),
                _status_pill(status),
                Paragraph(remarks, _ps("WrRem", fontName="Helvetica",
                    fontSize=FS_CAP, textColor=C_CAPTION, leading=12)),
            ])
        story.append(_grid_table(
            ["Criterion", "Level", "Status", "Remarks and Explanations"],
            rows, [1.65 * inch, 0.8 * inch, 1.5 * inch, CONTENT_W - 3.95 * inch]))
        story.append(_hr())

    # ══ 13. SECTION 508 FUNCTIONAL PERFORMANCE CRITERIA ════════════════════════
    def _508_note(parsed):
        if parsed and parsed.remarks:
            return parsed.remarks
        return (f"Not covered by the vendor's VPAT; flagged for independent "
                f"third-party testing.")

    def _508_rows(defs, parsed_508, level_label):
        rows = []
        for cid, ctitle in defs:
            p = parsed_508.get(cid)
            status = p.normalized_status if p else "Not Evaluated"
            rows.append([
                Paragraph(f"<b>{cid}</b> {ctitle}", _ps("FpCrit",
                    fontName="Helvetica", fontSize=FS_CAP,
                    textColor=C_BODY, leading=12)),
                Paragraph(level_label, _ps("FpLvl", fontName="Helvetica",
                    fontSize=FS_CAP, textColor=C_BODY, leading=12)),
                _status_pill(status),
                Paragraph(_508_note(p), _ps("FpNote", fontName="Helvetica",
                    fontSize=FS_CAP, textColor=C_CAPTION, leading=12)),
            ])
        return rows

    story.extend(_h2("Section 508 \u2014 Functional Performance Criteria "
                     "(Chapter 3)", S))
    fpc_defs = [
        ("302.1", "Without Vision"), ("302.2", "With Limited Vision"),
        ("302.3", "Without Perception of Color"), ("302.4", "Without Hearing"),
        ("302.5", "With Limited Hearing"), ("302.6", "Without Speech"),
        ("302.7", "With Limited Manipulation"),
        ("302.8", "With Limited Reach and Strength"),
        ("302.9", "With Limited Language, Cognitive, and Learning Abilities"),
    ]
    fpc_parsed = {c.criterion_id: c for c in vpat_data.criteria
                  if c.section == "508_fpc"}
    story.append(_grid_table(
        ["Criterion", "Level", "Conformance Status", "SFBRN Note"
             if org_short == "SFBRN" else f"{org_short} Note"],
        _508_rows(fpc_defs, fpc_parsed, "FPC"),
        [1.7 * inch, 0.55 * inch, 1.45 * inch, CONTENT_W - 3.7 * inch]))
    story.append(_hr())

    # ══ 14. SECTION 508 HARDWARE (CHAPTER 4) ═══════════════════════════════════
    story.extend(_h2("Section 508 \u2014 Chapter 4: Hardware", S))
    story.append(_callout([Paragraph(
        f"Not Applicable. {product} is a software-only application. "
        "Chapter 4 Hardware criteria do not apply.",
        _ps("HwTxt", fontName="Helvetica", fontSize=FS_TABLE,
            textColor=C_BODY, leading=14))]))
    story.append(_hr())

    # ══ 15. SECTION 508 SOFTWARE (CHAPTER 5) ═══════════════════════════════════
    story.extend(_h2("Section 508 \u2014 Chapter 5: Software", S))
    ch5_defs = [
        ("501.1", "Scope \u2013 Incorporation of WCAG 2.0 AA"),
        ("502.2.1", "User Control of Accessibility Features"),
        ("502.2.2", "No Disruption of Accessibility Features"),
        ("502.3", "Interoperability with Assistive Technology"),
        ("502.4", "Platform Accessibility Features"),
        ("503.2", "User Preferences"),
        ("503.3", "Alternative User Interfaces"),
        ("503.4.1", "Caption Controls"),
        ("503.4.2", "Audio Description Controls"),
        ("504.2", "Content Creation or Editing"),
        ("504.2.1", "Preservation of Information Provided for Accessibility "
                    "in Format Conversion"),
        ("504.2.2", "PDF Export"),
        ("504.3", "Prompts"),
        ("504.4", "Templates"),
    ]
    ch5_parsed = {c.criterion_id: c for c in vpat_data.criteria
                  if c.section == "508_ch5"}
    story.append(_grid_table(
        ["Criterion", "Level", "Conformance Status",
         f"{org_short} Note"],
        _508_rows(ch5_defs, ch5_parsed, "Ch. 5"),
        [1.7 * inch, 0.55 * inch, 1.45 * inch, CONTENT_W - 3.7 * inch]))
    story.append(_hr())

    # ══ 16. SECTION 508 SUPPORT DOCUMENTATION AND SERVICES (CHAPTER 6) ═════════
    story.extend(_h2("Section 508 \u2014 Chapter 6: Support Documentation "
                     "and Services", S))
    ch6_defs = [
        ("602.2", "Accessibility and Compatibility Features"),
        ("602.3", "Electronic Support Documentation"),
        ("602.4", "Alternate Formats for Non-Electronic Support Documentation"),
        ("603.2", "Information on Accessibility and Compatibility Features"),
        ("603.3", "Accommodation of Communication Needs"),
    ]
    ch6_parsed = {}
    for c in vpat_data.criteria:
        if c.section == "508_ch6" or c.criterion_id in (
                "602.2", "602.3", "602.4", "603.2", "603.3"):
            ch6_parsed[c.criterion_id] = c
    story.append(_grid_table(
        ["Criterion", "Level", "Conformance Status", f"{org_short} Note"],
        _508_rows(ch6_defs, ch6_parsed, "Ch. 6"),
        [1.7 * inch, 0.55 * inch, 1.45 * inch, CONTENT_W - 3.7 * inch]))
    story.append(Paragraph(
        f"Reference tables are {org_short} scorecard summaries, not mirrors "
        "of the vendor VPAT; full vendor remarks appear only in Section 2 "
        "barrier cards. Criteria not covered by the vendor's VPAT are marked "
        f"Not Evaluated per {org_short} policy.", S["small"]))
    story.append(_hr())

    # ══ 17. REVIEWER SIGNATURE ═════════════════════════════════════════════════
    story.extend(_h2("Reviewer Signature", S))
    story.append(_info_table([
        ("Reviewer", reviewer),
        ("Title", rev_title),
        ("Organization", org),
        ("Report Date", today_str),
    ]))
    story.append(Spacer(1, 0.45 * inch))
    sig_line = _ps("SigLine", fontName="Helvetica", fontSize=FS_CAP,
                   textColor=C_CAPTION, leading=12)
    story.append(HRFlowable(width=3.2 * inch, thickness=0.75, color=C_BODY,
                            hAlign="LEFT", spaceAfter=3))
    story.append(Paragraph(f"Signature \u2014 {reviewer}", sig_line))
    story.append(Spacer(1, 0.4 * inch))
    story.append(HRFlowable(width=3.2 * inch, thickness=0.75, color=C_BODY,
                            hAlign="LEFT", spaceAfter=3))
    story.append(Paragraph("Date", sig_line))
    story.append(Spacer(1, 0.35 * inch))

    # ══ 18. VISIBLE FINAL FOOTER ═══════════════════════════════════════════════
    year = datetime.now().year
    ff = Table([[
        Paragraph(f"\u00a9 {year} {org}",
            _ps("FfL", fontName="Helvetica", fontSize=FS_CAP,
                textColor=C_CAPTION)),
        Paragraph(rpt_title,
            _ps("FfC", fontName="Helvetica", fontSize=FS_CAP,
                textColor=C_CAPTION, alignment=TA_CENTER)),
        Paragraph("End of Report",
            _ps("FfR", fontName="Helvetica", fontSize=FS_CAP,
                textColor=C_CAPTION, alignment=TA_RIGHT)),
    ]], colWidths=[2.4 * inch, 2.2 * inch, CONTENT_W - 4.6 * inch])
    ff.setStyle(TableStyle([
        ("LINEABOVE",  (0, 0), (-1, 0), 0.5, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",(0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(ff)

    doc.build(story, canvasmaker=NumberedCanvas)
    logger.info("Report saved: %s", output_path)
    return output_path


# ── Post-generation PDF validation (master prompt requirement) ────────────────

def validate_report(pdf_path) -> tuple:
    """Validate the generated PDF: exists, non-empty, opens, and contains all
    required sections. Returns (ok: bool, problems: list[str])."""
    problems = []
    p = Path(pdf_path)
    if not p.exists():
        return False, [f"File does not exist: {pdf_path}"]
    if p.stat().st_size == 0:
        return False, ["File size is zero."]
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(p))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        return False, [f"PDF could not be opened/read: {e}"]
    required = [
        "Executive Summary",
        "Section 1", "Section 2", "Section 3", "Section 4",
        "Perceivable", "Operable", "Understandable", "Robust",
        "Functional Performance", "Chapter 5", "Chapter 6",
        "Reviewer Signature", "End of Report",
    ]
    for marker in required:
        if marker not in text:
            problems.append(f"Missing required section marker: {marker}")
    if "%" not in text and "N/A" not in text:
        problems.append("Compliance score not found in report text.")
    return (len(problems) == 0), problems
