"""Launch the VPAT Reviewer desktop GUI (and the packaged-app entry point).

The GUI itself lives in the package at ``vpat_reviewer.ui.gui.app``. This thin
launcher is what PyInstaller freezes (see ``vpat_reviewer.spec``) and what
``python run_app.py`` runs during development.

``--selftest`` runs headless build checks (does the bundled WCAG data load,
etc.) and writes the result to JSON instead of opening the GUI — use it to
verify a freshly built ``VPAT_Reviewer.exe``.
"""

import sys


def main() -> None:
    if "--selftest" in sys.argv:
        from vpat_reviewer.diagnostics import run_selftest

        raise SystemExit(run_selftest(sys.argv))

    from vpat_reviewer.ui.gui.app import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
