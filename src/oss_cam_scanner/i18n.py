from __future__ import annotations

from contextlib import ExitStack
from importlib import resources

from PySide6.QtCore import QLocale, QSettings, QTranslator
from PySide6.QtWidgets import QApplication

APP_ORGANIZATION = "oss-cam-scanner"
APP_NAME = "oss-cam-scanner"
LANGUAGE_SYSTEM = "system"
LANGUAGE_ENGLISH = "en"
LANGUAGE_SIMPLIFIED_CHINESE = "zh_CN"
LANGUAGE_SETTING_KEY = "ui/language"
SUPPORTED_LANGUAGE_PREFERENCES = (
    LANGUAGE_SYSTEM,
    LANGUAGE_ENGLISH,
    LANGUAGE_SIMPLIFIED_CHINESE,
)


class TranslationManager:
    def __init__(
        self,
        app: QApplication,
        locale: QLocale | None = None,
        language_preference: str = LANGUAGE_SYSTEM,
    ) -> None:
        self._app = app
        self._locale = locale or QLocale.system()
        self._language_preference = normalize_language_preference(language_preference)
        self._resource_stack = ExitStack()
        self._translators: list[QTranslator] = []

    def install(self) -> None:
        locale_name = app_translation_locale(
            self._locale,
            self._language_preference,
        )
        if locale_name == LANGUAGE_ENGLISH:
            return
        self._install_qm(f"oss_cam_scanner_{locale_name}.qm")

    def close(self) -> None:
        for translator in self._translators:
            self._app.removeTranslator(translator)
        self._translators.clear()
        self._resource_stack.close()

    def _install_qm(self, filename: str) -> None:
        resource = resources.files("oss_cam_scanner").joinpath(
            "translations",
            filename,
        )
        if not resource.is_file():
            return
        translator = QTranslator(self._app)
        path = self._resource_stack.enter_context(resources.as_file(resource))
        if not translator.load(str(path)):
            return
        self._app.installTranslator(translator)
        self._translators.append(translator)


def app_translation_locale(
    locale: QLocale | None = None,
    language_preference: str = LANGUAGE_SYSTEM,
) -> str:
    preference = normalize_language_preference(language_preference)
    if preference != LANGUAGE_SYSTEM:
        return preference
    active_locale = locale or QLocale.system()
    if active_locale.language() == QLocale.Language.Chinese:
        return LANGUAGE_SIMPLIFIED_CHINESE
    return LANGUAGE_ENGLISH


def normalize_language_preference(value: object) -> str:
    if isinstance(value, str) and value in SUPPORTED_LANGUAGE_PREFERENCES:
        return value
    return LANGUAGE_SYSTEM


def language_preference_from_settings(settings: QSettings) -> str:
    return normalize_language_preference(
        settings.value(
            LANGUAGE_SETTING_KEY,
            LANGUAGE_SYSTEM,
            type=str,
        )
    )


def install_translations(
    app: QApplication,
    locale: QLocale | None = None,
    language_preference: str = LANGUAGE_SYSTEM,
) -> TranslationManager:
    manager = TranslationManager(app, locale, language_preference)
    manager.install()
    app._oss_cam_scanner_translation_manager = manager  # type: ignore[attr-defined]
    return manager
