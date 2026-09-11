#!/usr/bin/env python3
"""
fetch_epg.py — Stahuje TV program z epg.lat/cz.xml.gz (XMLTV/gzip).
Tato verze stahuje všechny stanice (včetně ČT) z jednoho zdroje,
aby se obešlo blokování GitHub Actions ze strany oficiálního API ČT.
"""

import gzip
import json
import sys
import argparse
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET
import urllib.request as urllib_request
import urllib.error

# ──────────────────────────────────────────────────────────────────────────────
# Konfigurace
# ──────────────────────────────────────────────────────────────────────────────

XMLTV_URL = "https://epg.lat/files/cz.xml.gz"

# XMLTV mapování pro všechny kanály
XMLTV_CHANNEL_MAP = {
    "Nova.cz":         "TV Nova",
    "Prima.cz":        "Prima",
    "Seznam.cz.TV.cz": "Televize Seznam",
    "ČT1.cz":          "ČT1",
    "ČT2.cz":          "ČT2",
    "ČT.sport.cz":     "ČT sport",
}

XMLTV_LOGOS_FALLBACK = {
    "TV Nova":         "https://www.sms.cz/kategorie/televize/bmp/loga/velka/nova.png",
    "Prima":           "https://www.sms.cz/kategorie/televize/bmp/loga/velka/prima.png",
    "Televize Seznam": "https://www.sms.cz/kategorie/televize/bmp/loga/velka/seznamcztv.png",
    "ČT1":             "https://www.sms.cz/kategorie/televize/bmp/loga/velka/ct1.png",
    "ČT2":             "https://www.sms.cz/kategorie/televize/bmp/loga/velka/ct2.png",
    "ČT sport":        "https://www.sms.cz/kategorie/televize/bmp/loga/velka/ct4.png",
}

CHANNEL_ORDER = ["TV Nova", "Prima", "Televize Seznam", "ČT1", "ČT2", "ČT sport"]
CHANNEL_SLUGS = {
    "TV Nova":         "tv-nova",
    "Prima":           "prima",
    "Televize Seznam": "seznam-tv",
    "ČT1":             "ct1",
    "ČT2":             "ct2",
    "ČT sport":        "ct-sport",
}

# ──────────────────────────────────────────────────────────────────────────────
# Sdílené utility
# ──────────────────────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib_request.Request(
        url,
        headers={"User-Agent": "TVProgramCZ/2.0 (rodinny-web; personal-use)"}
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} při stahování {url}: {exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"Chyba při stahování {url}: {exc}") from exc

def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ──────────────────────────────────────────────────────────────────────────────
# Zpracování XMLTV
# ──────────────────────────────────────────────────────────────────────────────

def parse_xmltv_time(time_str: str) -> datetime:
    time_str = time_str.strip()
    if " " in time_str:
        dt_part, tz_part = time_str.split(" ", 1)
        sign = 1 if tz_part.startswith("+") else -1
        tz_h = int(tz_part[1:3])
        tz_m = int(tz_part[3:5])
        tz = timezone(timedelta(hours=tz_h, minutes=tz_m) * sign)
    else:
        dt_part, tz = time_str, timezone.utc
    return datetime.strptime(dt_part, "%Y%m%d%H%M%S").replace(tzinfo=tz)


def fetch_xmltv(days_ahead: int) -> tuple:
    wanted = set(XMLTV_CHANNEL_MAP.keys())

    print(f"[INFO] Stahuji XMLTV z: {XMLTV_URL}", file=sys.stderr)
    raw  = http_get(XMLTV_URL)
    print(f"[INFO] Staženo {len(raw):,} bajtů, dekomprimuji...", file=sys.stderr)

    xml_bytes = gzip.decompress(raw)
    root = ET.fromstring(xml_bytes)

    # Loga kanálů
    icons = {}
    for ch_el in root.iter("channel"):
        ch_id = ch_el.get("id", "")
        if ch_id in wanted and ch_id not in icons:
            icon_el = ch_el.find("icon")
            if icon_el is not None:
                src = icon_el.get("src", "").strip()
                if src:
                    icons[ch_id] = src

    # Pořady
    now_utc = datetime.now(timezone.utc)
    cutoff  = now_utc + timedelta(days=days_ahead)
    progs   = {cid: [] for cid in wanted}

    for prog in root.iter("programme"):
        ch_id = prog.get("channel", "")
        if ch_id not in wanted:
            continue
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop", ""))
        except ValueError:
            continue

        if stop < now_utc - timedelta(hours=2) or start > cutoff:
            continue

        title_el = prog.find("title")
        desc_el  = prog.find("desc")
        cat_el   = prog.find("category")

        progs[ch_id].append({
            "title":       (title_el.text or "").strip() if title_el is not None else "",
            "start":       utc_iso(start.astimezone(timezone.utc)),
            "stop":        utc_iso(stop.astimezone(timezone.utc)),
            "description": (desc_el.text or "").strip() or None if desc_el is not None else None,
            "category":    (cat_el.text  or "").strip() or None if cat_el  is not None else None,
        })

    for ch_id in progs:
        progs[ch_id].sort(key=lambda p: p["start"])
        print(
            f"[INFO] XMLTV – {XMLTV_CHANNEL_MAP[ch_id]} ({ch_id}): "
            f"{len(progs[ch_id])} pořadů",
            file=sys.stderr
        )

    return progs, icons


# ──────────────────────────────────────────────────────────────────────────────
# Sestavení výsledného JSON
# ──────────────────────────────────────────────────────────────────────────────

def build_output(xmltv_progs: dict, xmltv_icons: dict) -> dict:
    channels = []
    
    for canon_name in CHANNEL_ORDER:
        ch_progs = []
        ch_logo = None
        ch_slug = CHANNEL_SLUGS[canon_name]
        
        # Najdeme všechny XMLTV IDs, které patří tomuto kanálu
        for ch_id, c_name in XMLTV_CHANNEL_MAP.items():
            if c_name == canon_name:
                ch_progs.extend(xmltv_progs.get(ch_id, []))
                if ch_logo is None:
                    ch_logo = xmltv_icons.get(ch_id) or XMLTV_LOGOS_FALLBACK.get(canon_name)
                    
        # Deduplikace
        seen = set()
        unique_progs = []
        for p in sorted(ch_progs, key=lambda x: x["start"]):
            k = (p["start"], p["title"])
            if k not in seen:
                seen.add(k)
                unique_progs.append(p)
                
        channels.append({
            "id":         ch_slug,
            "name":       canon_name,
            "logo":       ch_logo,
            "source":     "epg.lat",
            "programmes": unique_progs,
        })

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "xmltv": XMLTV_URL,
        },
        "channels": channels,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Hlavní funkce
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Stahuje TV program pro všechny stanice z epg.lat XMLTV → JSON."
    )
    parser.add_argument("--output", "-o", default="epg_data.json")
    parser.add_argument("--days", "-d", type=int, default=7)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args()

    try:
        xmltv_progs, xmltv_icons = fetch_xmltv(args.days)
    except RuntimeError as exc:
        print(f"[CHYBA] XMLTV selhalo: {exc}", file=sys.stderr)
        sys.exit(1)

    output = build_output(xmltv_progs, xmltv_icons)
    indent = args.indent if args.indent > 0 else None

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=indent)

    total = sum(len(ch["programmes"]) for ch in output["channels"])
    print(f"\n[OK] Uloženo {total} pořadů → '{args.output}'", file=sys.stderr)


if __name__ == "__main__":
    main()
