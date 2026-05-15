from __future__ import annotations

from importlib import resources
from pathlib import PurePosixPath

from PySide6.QtCore import QLocale

from oss_cam_scanner.i18n import (
    Language,
    active_translation_locale,
    app_translation_locale,
)


def load_localized_markdown(
    name: str,
    locale: QLocale | str | Language | None = None,
) -> str:
    document_name = _safe_document_name(name)
    if isinstance(locale, Language):
        locale_name = locale.value
    elif isinstance(locale, str):
        locale_name = locale
    elif locale is not None:
        locale_name = app_translation_locale(locale).value
    else:
        locale_name = active_translation_locale().value
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
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.name
        or path.name in {".", ".."}
    ):
        raise ValueError(f"Invalid localized document name: {name}")
    if path.suffix != ".md":
        raise ValueError(f"Localized document must be Markdown: {name}")
    return path.as_posix()
