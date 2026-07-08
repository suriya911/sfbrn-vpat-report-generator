"""Settings Manager — compatibility shim (Phase 1 strangler).

The canonical settings store is now ``vpat_reviewer.config.settings``, which
holds both organization identity *and* the editable grading policy in one
``settings.json`` (non-destructively — saving identity never clobbers the policy
and vice-versa). This module preserves the v10 public API so ``run_app.py`` keeps
working unchanged.
"""

from vpat_reviewer.config.settings import (
    FIELD_LABELS,
    IDENTITY_DEFAULTS as DEFAULTS,
    is_first_run,
    load_settings,
    save_settings,
    settings_path,
)

__all__ = [
    "DEFAULTS",
    "FIELD_LABELS",
    "settings_path",
    "load_settings",
    "save_settings",
    "is_first_run",
]
