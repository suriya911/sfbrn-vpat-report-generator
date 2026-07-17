# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for the VPAT Reviewer desktop app.

Produces a single, self-contained ``dist/VPAT_Reviewer.exe`` (no Python
install required on the target machine) that anyone on the team can run by
double-clicking. Build it with::

    python -m PyInstaller vpat_reviewer.spec --noconfirm --clean

or just run ``build_exe.bat``, which installs the deps first.

Why a .spec file (and not a one-line ``pyinstaller run_app.py``): two things
need explicit help that command-line flags handle poorly:

1. **The WCAG reference data and the review rubric.**
   ``reference/data/wcag.json`` (see ``reference/loader.py``) and
   ``ai/data/risk_review_prompt.md`` (see ``ai/prompt.py``) are both loaded at
   runtime via ``importlib.resources``. They are *data*, not code, so PyInstaller
   won't pick them up automatically — we bundle them here, preserving their
   package-relative paths so ``importlib.resources`` still finds them inside the
   frozen app. Drop either entry and the exe loses that feature *silently*.
2. **Dynamically-imported third-party code.** reportlab / pdfplumber / pypdf /
   python-docx import many submodules lazily; ``collect_submodules`` pulls them
   all in so nothing is missing at runtime.

If you add a new package data file (e.g. a template or a second JSON), add it
to ``datas`` below the same way. If a new dependency fails at runtime with a
``ModuleNotFoundError``, add ``collect_submodules("<pkg>")`` to ``hiddenimports``.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Bundled data files (source_on_disk, destination_inside_app) ───────────────
# The explicit entries are the reliable ones; collect_data_files is a
# belt-and-suspenders sweep for anything else non-.py under the package.
datas = [
    ("src/vpat_reviewer/reference/data/wcag.json", "vpat_reviewer/reference/data"),
    (
        "src/vpat_reviewer/ai/data/risk_review_prompt.md",
        "vpat_reviewer/ai/data",
    ),
]
datas += collect_data_files("vpat_reviewer")

# ── Dynamically-imported submodules the module graph can't see statically ─────
hiddenimports: list[str] = []
for pkg in ("reportlab", "pdfplumber", "pdfminer", "pypdf", "docx"):
    hiddenimports += collect_submodules(pkg)

# Drag-and-drop: the GUI imports tkinterdnd2 inside a try/except (best-effort
# feature), so name it explicitly rather than trusting the module graph. Once
# it is in the graph, pyinstaller-hooks-contrib's hook-tkinterdnd2 bundles the
# platform-specific tkdnd DLL + .tcl files — the same silent-failure family as
# wcag.json / the rubric; the selftest's dnd_assets_bundled check is the canary.
hiddenimports += ["tkinterdnd2"]

# An icon is optional; drop assets/app.ico next to this spec to brand the exe.
import os  # noqa: E402  (spec files run as plain scripts)

_icon = os.path.join("assets", "app.ico")
icon = _icon if os.path.exists(_icon) else None


a = Analysis(
    ["run_app.py"],  # thin launcher -> vpat_reviewer.ui.gui.app:main
    pathex=["src"],  # src-layout: make the package importable during the build
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "test", "pytest", "mypy", "ruff"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="VPAT_Reviewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI app: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
