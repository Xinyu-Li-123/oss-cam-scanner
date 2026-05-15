from __future__ import annotations

from importlib import resources
from pathlib import PurePosixPath

from PySide6.QtCore import QLocale

from oss_cam_scanner.i18n import app_translation_locale


def load_localized_markdown(name: str, locale: QLocale | None = None) -> str:
    document_name = _safe_document_name(name)
    locale_name = app_translation_locale(locale)
    for candidate_locale in (locale_name, "en"):
        resource = resources.files("oss_cam_scanner").joinpath(
            "resources",
            "docs",
            candidate_locale,
            document_name,
        )
        if resource.is_file():
            return resource.read_text(encoding="utf-8")
    raise FileNotFoundError(document_name)


def _safe_document_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or path.name != name:
        raise ValueError(f"Invalid localized document name: {name}")
    if path.suffix != ".md":
        raise ValueError(f"Localized document must be Markdown: {name}")
    return name
