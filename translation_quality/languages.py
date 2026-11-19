"""Language codes: finding them in file names and form fields, and naming them."""
import os
import re

LANGUAGE_NAMES = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "az": "Azerbaijani", "bg": "Bulgarian",
    "bn": "Bengali", "bs": "Bosnian", "ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish",
    "de": "German", "el": "Greek", "en": "English", "es": "Spanish", "et": "Estonian", "eu": "Basque",
    "fa": "Persian", "fi": "Finnish", "fil": "Filipino", "fr": "French", "ga": "Irish", "gl": "Galician",
    "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi", "hr": "Croatian", "ht": "Haitian Creole",
    "hu": "Hungarian", "hy": "Armenian", "id": "Indonesian", "is": "Icelandic", "it": "Italian",
    "ja": "Japanese", "ka": "Georgian", "kk": "Kazakh", "km": "Khmer", "kn": "Kannada", "ko": "Korean",
    "lo": "Lao", "lt": "Lithuanian", "lv": "Latvian", "mk": "Macedonian", "ml": "Malayalam",
    "mr": "Marathi", "ms": "Malay", "mt": "Maltese", "my": "Burmese", "nb": "Norwegian Bokmål",
    "ne": "Nepali", "nl": "Dutch", "no": "Norwegian", "pa": "Punjabi", "pl": "Polish", "ps": "Pashto",
    "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "si": "Sinhala", "sk": "Slovak",
    "sl": "Slovenian", "so": "Somali", "sq": "Albanian", "sr": "Serbian", "sv": "Swedish",
    "sw": "Swahili", "ta": "Tamil", "te": "Telugu", "th": "Thai", "tl": "Tagalog", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese", "yue": "Cantonese", "zh": "Chinese",
    "zu": "Zulu",
}

REGION_NAMES = {
    "US": "US", "GB": "UK", "UK": "UK", "IE": "Ireland", "CA": "Canada", "AU": "Australia",
    "NZ": "New Zealand", "MX": "Mexico", "ES": "Spain", "419": "Latin America", "AR": "Argentina",
    "CO": "Colombia", "CL": "Chile", "PE": "Peru", "FR": "France", "BE": "Belgium", "CH": "Switzerland",
    "LU": "Luxembourg", "DE": "Germany", "AT": "Austria", "IT": "Italy", "PT": "Portugal", "BR": "Brazil",
    "AO": "Angola", "MZ": "Mozambique", "NL": "Netherlands", "SE": "Sweden", "NO": "Norway",
    "DK": "Denmark", "FI": "Finland", "PL": "Poland", "RO": "Romania", "MD": "Moldova", "GR": "Greece",
    "TR": "Turkey", "RU": "Russia", "UA": "Ukraine", "IL": "Israel", "SA": "Saudi Arabia",
    "AE": "UAE", "EG": "Egypt", "MA": "Morocco", "IN": "India", "PK": "Pakistan", "BD": "Bangladesh",
    "JP": "Japan", "KR": "Korea", "VN": "Vietnam", "TH": "Thailand", "PH": "Philippines",
    "ID": "Indonesia", "MY": "Malaysia", "SG": "Singapore", "NG": "Nigeria", "KE": "Kenya",
    "ZA": "South Africa", "GT": "Guatemala", "SV": "El Salvador", "HN": "Honduras",
    "DO": "Dominican Republic", "EC": "Ecuador",
}

# Chinese is named by script rather than by country.
CHINESE_VARIANTS = {
    "CN": "Simplified", "SG": "Simplified", "HANS": "Simplified",
    "TW": "Traditional", "HANT": "Traditional", "HK": "Traditional, Hong Kong", "MO": "Traditional, Macau",
}

# Languages spoken mainly in one country: "ko-KR" is shown as "Korean", not "Korean (Korea)".
SINGLE_COUNTRY = {"bg": "BG", "cs": "CZ", "da": "DK", "el": "GR", "et": "EE", "fi": "FI", "he": "IL",
                  "hr": "HR", "hu": "HU", "id": "ID", "ja": "JP", "ko": "KR", "lt": "LT", "lv": "LV",
                  "pl": "PL", "sk": "SK", "sl": "SI", "th": "TH", "tr": "TR", "uk": "UA", "vi": "VN"}

# Country codes often used by mistake in place of language codes (e.g. "JP_US" for Japanese).
COUNTRY_AS_LANGUAGE = {"jp": "ja", "cn": "zh", "kr": "ko", "vn": "vi", "gr": "el", "cz": "cs",
                       "dk": "da", "ua": "uk"}

_NAME_TO_CODE = {name.lower(): code for code, name in LANGUAGE_NAMES.items()}
_NAME_TO_CODE.update({"chinese (simplified)": "zh-CN", "chinese (traditional)": "zh-TW",
                      "simplified chinese": "zh-CN", "traditional chinese": "zh-TW"})


def _base(code):
    code = (code or "").lower()
    return COUNTRY_AS_LANGUAGE.get(code, code)


def is_language(code):
    return _base(code) in LANGUAGE_NAMES


def normalise(language, region=None):
    """'JP', 'US' -> 'ja-US'; 'zh', 'cn' -> 'zh-CN'; 'de' -> 'de'."""
    lang = _base(language)
    if not region:
        return lang
    region = region.upper() if len(region) != 4 else region.title()
    return f"{lang}-{region}"


def display_name(code):
    """'es-US' -> 'Spanish (US)', 'zh-CN' -> 'Chinese (Simplified)'. Unknown codes come back as given."""
    if not code:
        return ""
    parts = re.split(r"[-_]", code)
    lang = _base(parts[0])
    name = LANGUAGE_NAMES.get(lang)
    if not name:
        return code
    if len(parts) == 1:
        return name
    region = parts[1].upper()
    if lang == "zh" and region in CHINESE_VARIANTS:
        return f"{name} ({CHINESE_VARIANTS[region]})"
    if SINGLE_COUNTRY.get(lang) == region:
        return name
    return f"{name} ({REGION_NAMES.get(region, parts[1])})"


_PAIR = re.compile(r"(?<![A-Za-z])([A-Za-z]{2,3})[-_]([A-Za-z]{2}|\d{3}|[A-Za-z]{4})(?![A-Za-z])")


def code_from_text(text):
    """Find a language code in free text such as 'fr-FR', 'Vietnamese (vi-VN)', 'Korean', 'zh_CN'."""
    if not text:
        return None
    text = str(text).strip()
    for m in _PAIR.finditer(text):
        if is_language(m.group(1)):
            return normalise(m.group(1), m.group(2))
    low = text.lower()
    if low in _NAME_TO_CODE:
        return _NAME_TO_CODE[low]
    first = re.split(r"[\s(,]", low)[0]
    if first in _NAME_TO_CODE:
        return _NAME_TO_CODE[first]
    if re.fullmatch(r"[A-Za-z]{2,3}", text) and is_language(text):
        return normalise(text)
    return None


def code_from_filename(path):
    """Language code at the end of a file name, e.g. '..._es_US.xlsm' -> 'es-US',
    '..._th_TH (Campaign page).xlsm' -> 'th-TH', '..._ro_RO_2.xlsm' -> 'ro-RO', '..._DE.xlsm' -> 'de'."""
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"\([^)]*\)", " ", stem)
    tokens = [t for t in re.split(r"[_\s]+", stem) if t]
    while tokens and tokens[-1].isdigit():
        tokens.pop()
    if not tokens:
        return None
    last = tokens[-1]
    m = re.fullmatch(r"([A-Za-z]{2,3})-([A-Za-z]{2}|\d{3}|[A-Za-z]{4})", last)
    if m:
        return normalise(m.group(1), m.group(2)) if is_language(m.group(1)) else None
    if (len(tokens) >= 2 and re.fullmatch(r"[A-Za-z]{2,3}", tokens[-2]) and is_language(tokens[-2])
            and re.fullmatch(r"[A-Za-z]{2}|\d{3}", last)):
        return normalise(tokens[-2], last)
    if re.fullmatch(r"[A-Za-z]{2,3}", last) and is_language(last):
        return normalise(last)
    return None
