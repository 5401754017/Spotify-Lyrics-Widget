#!/usr/bin/env python3
"""Render the multilingual launch site.

Reads site/template.html and every site/i18n/<lang>.json, substitutes the
{{placeholders}}, and writes site/<lang>/index.html. Also writes the root
site/index.html language-router.

To add a language: drop a new site/i18n/<lang>.json (copy an existing one and
translate the values), add the code to LANGS below, then run: python site/build.py
"""

import json
import re
from pathlib import Path

# Order controls the language-switcher and the router's fallback preference.
LANGS = ["zh-Hant", "en"]

SITE = Path(__file__).resolve().parent
TEMPLATE = SITE / "template.html"
I18N = SITE / "i18n"

# Single source of truth. Change USER if the GitHub username changes, or
# REPO_NAME / VERSION on a rename or new release — every GitHub link, the
# Pages OG image URL, the version badge, and all download buttons follow.
USER = "AgendaLin"
REPO_NAME = "Spotify-Lyrics-Widget"
VERSION = "v3.2.1"

REPO = f"https://github.com/{USER}/{REPO_NAME}"
PAGES_BASE = f"https://{USER}.github.io/{REPO_NAME}"
DOWNLOAD_URL = f"{REPO}/releases/download/{VERSION}/SpotifyLyricsWidgetSetup.exe"
OG_IMAGE = f"{PAGES_BASE}/assets/og.png"

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render(lang: str) -> None:
    data = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
    lines = data.pop("demo_lines")

    values = dict(data)
    values["LANG"] = data["lang"]
    values["version"] = VERSION
    values["repo"] = REPO
    values["download_url"] = DOWNLOAD_URL
    values["og_image"] = OG_IMAGE
    values["demo_lines_json"] = json.dumps(lines, ensure_ascii=False)
    values["demo_init_line"] = lines[1] if len(lines) > 1 else lines[0]

    template = TEMPLATE.read_text(encoding="utf-8")

    def sub(m: "re.Match[str]") -> str:
        key = m.group(1)
        if key not in values:
            raise KeyError(f"{lang}.json is missing key '{key}' used in template.html")
        return str(values[key])

    html = PLACEHOLDER.sub(sub, template)

    out_dir = SITE / lang
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"  wrote {lang}/index.html")


def write_router() -> None:
    default = LANGS[0]
    langs_js = json.dumps(LANGS)
    html = f"""<!DOCTYPE html>
<!-- GENERATED FILE — do not edit. Edit site/build.py, then run: python site/build.py -->
<html lang="{default}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lyrics Widget</title>
<link rel="icon" href="assets/favicon.ico">
<link rel="alternate" hreflang="zh-Hant" href="zh-Hant/">
<link rel="alternate" hreflang="en" href="en/">
<link rel="alternate" hreflang="x-default" href="zh-Hant/">
<script>
  (function () {{
    var langs = {langs_js};
    var saved = null;
    try {{ saved = localStorage.getItem('lang'); }} catch (e) {{}}
    var target = (saved && langs.indexOf(saved) !== -1) ? saved : null;
    if (!target) {{
      var nav = (navigator.language || navigator.userLanguage || '').toLowerCase();
      if (nav.indexOf('zh') === 0) target = 'zh-Hant';
      else if (nav.indexOf('en') === 0) target = 'en';
      else target = '{default}';
    }}
    location.replace(target + '/index.html');
  }})();
</script>
</head>
<body style="margin:0;background:#0a0a0a;color:#b3b3b3;font-family:sans-serif;">
<noscript style="display:block;padding:40px;text-align:center;">
  Choose a language: <a href="zh-Hant/index.html" style="color:#1ED760;">繁體中文</a> ·
  <a href="en/index.html" style="color:#1ED760;">English</a>
</noscript>
</body>
</html>
"""
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print("  wrote index.html (router)")


def main() -> None:
    print("Building launch site:")
    for lang in LANGS:
        render(lang)
    write_router()
    print("Done.")


if __name__ == "__main__":
    main()
