"""Launch the VPAT Reviewer desktop GUI (development entry point).

The GUI itself now lives in the package at ``vpat_reviewer.ui.gui.app``. This
thin launcher keeps ``python run_app.py`` working during development; the
packaged app uses the same ``main()`` via the ``vpat-review-gui`` entry point.
"""

from vpat_reviewer.ui.gui.app import main

if __name__ == "__main__":
    main()
