from __future__ import annotations

from contextlib import ExitStack
from enum import StrEnum
from importlib import resources

from PySide6.QtCore import QCoreApplication, QLocale, QSettings, QTranslator
from PySide6.QtWidgets import QApplication

APP_ORGANIZATION = "oss-cam-scanner"
APP_NAME = "oss-cam-scanner"
LANGUAGE_SETTING_KEY = "ui/language"


class Language(StrEnum):
    SYSTEM = "system"
    EN = "en"
    ZH_CN = "zh_CN"


class TranslationManager:
    def __init__(
        self,
        app: QApplication,
        locale: QLocale | None = None,
        language_preference: Language | str = Language.SYSTEM,
    ) -> None:
        self._app = app
        self._locale = locale or QLocale.system()
        self._language_preference = normalize_language_preference(language_preference)
        self._locale_name = app_translation_locale(
            self._locale,
            self._language_preference,
        )
        self._resource_stack = ExitStack()
        self._translators: list[QTranslator] = []

    def install(self) -> None:
        match self._locale_name:
            case Language.EN:
                return
            case Language.ZH_CN:
                self._install_qm(f"oss_cam_scanner_{self._locale_name.value}.qm")
            case Language.SYSTEM:
                return

    def locale_name(self) -> Language:
        return self._locale_name

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
    language_preference: Language | str = Language.SYSTEM,
) -> Language:
    preference = normalize_language_preference(language_preference)
    match preference:
        case Language.EN:
            return Language.EN
        case Language.ZH_CN:
            return Language.ZH_CN
        case Language.SYSTEM:
            active_locale = locale or QLocale.system()
            if active_locale.language() == QLocale.Language.Chinese:
                return Language.ZH_CN
            return Language.EN


def system_language_preference_label(locale: QLocale | None = None) -> str:
    match app_translation_locale(locale):
        case Language.EN:
            return "Use System Language"
        case Language.ZH_CN:
            return "使用系统语言"
        case Language.SYSTEM:
            return "Use System Language"


def native_language_label(language: Language) -> str:
    match language:
        case Language.EN:
            return "English"
        case Language.ZH_CN:
            return "简体中文"
        case Language.SYSTEM:
            return system_language_preference_label()


def normalize_language_preference(value: object) -> Language:
    if isinstance(value, Language):
        return value
    if isinstance(value, str):
        try:
            return Language(value)
        except ValueError:
            return Language.SYSTEM
    return Language.SYSTEM


def language_preference_from_settings(settings: QSettings) -> Language:
    return normalize_language_preference(
        settings.value(
            LANGUAGE_SETTING_KEY,
            Language.SYSTEM.value,
            type=str,
        )
    )


def active_translation_locale() -> Language:
    app = QCoreApplication.instance()
    manager = getattr(app, "_oss_cam_scanner_translation_manager", None)
    if isinstance(manager, TranslationManager):
        return manager.locale_name()
    return app_translation_locale()


def install_translations(
    app: QApplication,
    locale: QLocale | None = None,
    language_preference: Language | str = Language.SYSTEM,
) -> TranslationManager:
    manager = TranslationManager(app, locale, language_preference)
    manager.install()
    app._oss_cam_scanner_translation_manager = manager  # type: ignore[attr-defined]
    return manager
