"""System font enumeration for fingerprint ``font_list``.

Ports ``front-electron/src/main/system-fonts.ts``:
Windows uses PowerShell + PresentationCore ``SystemFontFamilies``;
other platforms fall back to the protected set.
"""

from __future__ import annotations

import platform
import random
import subprocess
from typing import List, Optional

PROTECTED_FONT_FAMILIES: List[str] = [
    "Arial",
    "Times New Roman",
    "Courier New",
    "Segoe UI",
    "Calibri",
    "Tahoma",
    "Verdana",
    "Georgia",
    "Trebuchet MS",
    "Comic Sans MS",
    "Impact",
    "Consolas",
    "Lucida Console",
    "Microsoft YaHei",
    "SimSun",
    "Microsoft Sans Serif",
]

_cached_families: Optional[List[str]] = None


def _normalize_family(name: str) -> str:
    return name.strip().strip("\"'")


def _list_fonts_win32() -> List[str]:
    ps = (
        "chcp 65001 | Out-Null; "
        "Add-Type -AssemblyName PresentationCore; "
        "$families = [Windows.Media.Fonts]::SystemFontFamilies; "
        "foreach ($family in $families) { "
        "  $name = ''; "
        "  if (!$family.FamilyNames.TryGetValue("
        "[Windows.Markup.XmlLanguage]::GetLanguage('zh-cn'), [ref]$name)) { "
        "    $name = $family.FamilyNames[[Windows.Markup.XmlLanguage]::GetLanguage('en-us')] "
        "  }; "
        "  if ($name) { Write-Output $name } "
        "}"
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"powershell exit {result.returncode}")
    return [
        _normalize_family(line)
        for line in (result.stdout or "").splitlines()
        if _normalize_family(line)
    ]


def get_system_font_families(force_refresh: bool = False) -> List[str]:
    """Enumerate unique system font family names (sorted). Cached for process life."""
    global _cached_families
    if not force_refresh and _cached_families is not None:
        return list(_cached_families)

    try:
        if platform.system() == "Windows":
            raw = _list_fonts_win32()
        else:
            raw = list(PROTECTED_FONT_FAMILIES)
        families = set(raw)
        for p in PROTECTED_FONT_FAMILIES:
            families.add(p)
        _cached_families = sorted(families, key=lambda s: s.casefold())
    except Exception:
        _cached_families = list(PROTECTED_FONT_FAMILIES)

    return list(_cached_families)


def randomize_font_list(all_families: Optional[List[str]] = None) -> List[str]:
    """Keep protected fonts; randomly drop 1~5 non-critical ones."""
    families = all_families if all_families is not None else get_system_font_families()
    protected_set = {f.lower() for f in PROTECTED_FONT_FAMILIES}
    protected_list: List[str] = []
    removable: List[str] = []

    for family in families:
        if family.lower() in protected_set:
            protected_list.append(family)
        else:
            removable.append(family)

    for p in PROTECTED_FONT_FAMILIES:
        if not any(f.lower() == p.lower() for f in protected_list):
            protected_list.append(p)

    drop_count = min(len(removable), random.randint(1, 5)) if removable else 0
    if drop_count:
        dropped = set(random.sample(removable, drop_count))
        kept_removable = [f for f in removable if f not in dropped]
    else:
        kept_removable = list(removable)

    result = protected_list + kept_removable
    result.sort(key=lambda s: s.casefold())
    return result


def generate_random_font_list() -> List[str]:
    return randomize_font_list(get_system_font_families())
