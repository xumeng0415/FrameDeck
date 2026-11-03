"""Lightweight JSON-backed internationalization for FrameDeck.

Design:
    - Translation keys are the ORIGINAL ENGLISH SOURCE STRINGS. This keeps the
      codebase readable (``tr("Import Media...")``) and means the English UI is
      the zero-configuration fallback: ``resources/i18n/en_US.json`` can stay
      empty.
    - Language files live in ``resources/i18n/<code>.json`` as flat
      ``{"English source": "translated text"}`` maps. Keys starting with ``$``
      are metadata and ignored by :func:`tr`.
    - ``init()`` must be called BEFORE any module that evaluates translated
      strings at import time (``constants`` builds its enum labels with
      ``tr(...)``). Language changes take effect on application restart, which
      the language menu performs automatically.
    - ``zh_TW`` falls back to ``zh_CN`` for keys it does not provide yet, so the
      traditional-Chinese file can be filled in incrementally.

This module deliberately depends only on the standard library plus the tiny
``resources`` package (for its path), so ``constants`` can import it without
creating a cycle.
"""

from __future__ import absolute_import

import json
import os

AVAILABLE = {
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "en_US": "English",
    "ja": "日本語",
    "ko": "한국어",
    "ru": "Русский",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
}
DEFAULT_LANGUAGE = "zh_CN"
FALLBACK_LANGUAGE = "zh_CN"
SETTINGS_KEY = "i18n/language"

_CURRENT = DEFAULT_LANGUAGE
_TRANSLATIONS = {}
_FALLBACK = {}


def _lang_dir():
    """Return the directory holding <code>.json language files."""
    import resources

    return os.path.join(resources.CURRENT_PATH, "i18n")


def _read(code):
    """Load one language file; return {} when absent or malformed."""
    path = os.path.join(_lang_dir(), f"{code}.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return {}
    return {key: value for key, value in data.items() if not key.startswith("$")}


def init(language=None):
    """Select the active language. Call once at startup, before importing
    ``constants``. Unknown codes fall back to :data:`DEFAULT_LANGUAGE`."""
    global _CURRENT, _TRANSLATIONS, _FALLBACK
    if language not in AVAILABLE:
        language = DEFAULT_LANGUAGE
    _CURRENT = language
    _TRANSLATIONS = _read(language)
    if language in (DEFAULT_LANGUAGE, "en_US"):
        _FALLBACK = {}
    else:
        _FALLBACK = _read(FALLBACK_LANGUAGE)


def current_language():
    """Return the active language code."""
    return _CURRENT


def tr(text):
    """Translate *text* (the English source string) into the active language.

    Unknown keys and the ``en_US`` language return the key unchanged, so new
    code is always renderable before its translation exists.
    """
    if _CURRENT == "en_US":
        return text
    return _TRANSLATIONS.get(text) or _FALLBACK.get(text, text)
