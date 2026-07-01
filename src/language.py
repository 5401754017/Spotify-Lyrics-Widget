SUPPORTED_LANGUAGES = ("en", "zh_TW")
DEFAULT_LANGUAGE = "en"

_LANGUAGE_ALIASES = {
    "en": "en",
    "english": "en",
    "zh_TW": "zh_TW",
    "zh-tw": "zh_TW",
    "chinesetraditional": "zh_TW",
}


def normalize_language(value: str | None, default: str | None = DEFAULT_LANGUAGE) -> str | None:
    if value is None:
        return default
    return _LANGUAGE_ALIASES.get(str(value).strip(), default)


def language_from_locale(locale_name: str | None) -> str:
    if (locale_name or "").lower().startswith("zh"):
        return "zh_TW"
    return DEFAULT_LANGUAGE
