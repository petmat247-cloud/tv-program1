#!/usr/bin/env python3
"""
fetch_epg.py — Stahuje TV program z více zdrojů:
  - ČT1, ČT2, ČT sport → oficiální API České televize
  - TV Nova, Prima, Televize Seznam → epg.lat XMLTV (Záloha 1) nebo komunitní GitHub (Záloha 2)

Zkontroluje, který ze zdrojů (epg.lat nebo sk-cz-epg) má novější data a ten použije,
čímž se řeší výpadky aktualizací na serverech.
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

XMLTV_SOURCES = [
    "https://epg.lat/files/cz.xml.gz",
    "https://raw.githubusercontent.com/kozmali/sk-cz-epg/main/epg.xml.gz"
]

CT_API_URL = (
    "https://www.ceskatelevize.cz/services-old/programme/xml/schedule.php"
    "?user=test&date={date}&channel={channel}&json=1"
)
CT_CHANNELS = {
    "ct1":  {"name": "ČT1",      "id": "ct1",
             "logo": "https://www.sms.cz/kategorie/televize/bmp/loga/velka/ct1.png"},
    "ct2":  {"name": "ČT2",      "id": "ct2",
             "logo": "https://www.sms.cz/kategorie/televize/bmp/loga/velka/ct2.png"},
    "ct4":  {"name": "ČT sport", "id": "ct4",
             "logo": "https://www.sms.cz/kategorie/televize/bmp/loga/velka/ct4.png"},
}

XMLTV_CHANNEL_MAP = {
    "Nova.cz":         "TV Nova",
    "Prima.cz":        "Prima",
    "Seznam.cz.TV.cz": "Televize Seznam",
}
XMLTV_LOGOS_FALLBACK = {
    "TV Nova":         "https://www.sms.cz/kategorie/televize/bmp/loga/velka/nova.png",
    "Prima":           "https://www.sms.cz/kategorie/televize/bmp/loga/velka/prima.png",
    "Televize Seznam": "https://www.sms.cz/kategorie/televize/bmp/loga/velka/seznamcztv.png",
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


def get_czech_tz(dt_utc: datetime) -> timezone:
    import calendar
    year = dt_utc.year
    def last_sunday(y, month):
        last = calendar.monthrange(y, month)[1]
        d = datetime(y, month, last, 1, 0, 0, tzinfo=timezone.utc)
        return d - timedelta(days=(d.weekday() + 1) % 7)

    if last_sunday(year, 3) <= dt_utc < last_sunday(year, 10):
        return timezone(timedelta(hours=2))
    return timezone(timedelta(hours=1))


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ──────────────────────────────────────────────────────────────────────────────
# Zdroj 1: Česká televize – Oficiální API
# ──────────────────────────────────────────────────────────────────────────────

def fetch_ct_day(channel_id: str, date: datetime) -> list:
    date_str = date.strftime("%d.%m.%Y")
    url = CT_API_URL.format(date=date_str, channel=channel_id)
    try:
        raw = http_get(url)
        data = json.loads(raw)
    except Exception:
        return []

    porad_list = data.get("porad", [])
    if not isinstance(porad_list, list):
        return []

    programmes = []
    for p in porad_list:
        cas   = p.get("cas", "")
        nazev = (p.get("nazvy") or {}).get("nazev", "").strip()
        datum = p.get("datum", "")
        stopaz = p.get("stopaz", "")
        popis = p.get("noticka", "") or ""
        zanr  = p.get("zanr", "") or ""

        if not (cas and nazev and datum): continue
        try:
            start_local_naive = datetime.strptime(f"{datum} {cas}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue

        approx_utc = start_local_naive.replace(tzinfo=timezone.utc)
        tz = get_czech_tz(approx_utc)
        start_dt = start_local_naive.replace(tzinfo=tz)
        start_utc = start_dt.astimezone(timezone.utc)

        stop_utc = start_utc + timedelta(minutes=30)
        if stopaz:
            try:
                parts = stopaz.split(":")
                dur_min = int(parts[0]) + round(int(parts[1]) / 60)
                if dur_min > 0:
                    stop_utc = start_utc + timedelta(minutes=dur_min)
            except (ValueError, IndexError):
                pass

        programmes.append({
            "title":       nazev,
            "start":       utc_iso(start_utc),
            "stop":        utc_iso(stop_utc),
            "description": popis.strip() or None,
            "category":    zanr.strip() or None,
        })
    return programmes


def fetch_ct_all(days_ahead: int) -> dict:
    now_local = datetime.now(get_czech_tz(datetime.now(timezone.utc)))
    results = {info["name"]: [] for info in CT_CHANNELS.values()}

    for ch_id, info in CT_CHANNELS.items():
        all_progs = []
        for day_offset in range(days_ahead + 1):
            day = now_local + timedelta(days=day_offset)
            progs = fetch_ct_day(ch_id, day)
            all_progs.extend(progs)

        seen = set()
        unique = []
        for p in sorted(all_progs, key=lambda x: x["start"]):
            key = (p["start"], p["title"])
            if key not in seen:
                seen.add(key)
                unique.append(p)
        results[info["name"]] = unique
        print(f"[INFO] ČT API – {info['name']}: {len(unique)} pořadů", file=sys.stderr)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Zdroj 2: XMLTV — TV Nova, Prima, Televize Seznam (Vybírá nejlepší zdroj)
# ──────────────────────────────────────────────────────────────────────────────

def parse_xmltv_time(time_str: str) -> datetime:
    time_str = time_str.strip()
    if " " in time_str:
        dt_part, tz_part = time_str.split(" ", 1)
        sign = 1 if tz_part.startswith("+") else -1
        tz = timezone(timedelta(hours=int(tz_part[1:3]), minutes=int(tz_part[3:5])) * sign)
    else:
        dt_part, tz = time_str, timezone.utc
    return datetime.strptime(dt_part, "%Y%m%d%H%M%S").replace(tzinfo=tz)


def fetch_xmltv_from_url(url: str, days_ahead: int) -> tuple:
    wanted = set(XMLTV_CHANNEL_MAP.keys())
    print(f"[INFO] Zkouším XMLTV zdroj: {url}", file=sys.stderr)
    raw = http_get(url)
    xml_bytes = gzip.decompress(raw)
    root = ET.fromstring(xml_bytes)

    icons = {}
    for ch_el in root.iter("channel"):
        ch_id = ch_el.get("id", "")
        if ch_id in wanted and ch_id not in icons:
            icon_el = ch_el.find("icon")
            if icon_el is not None and icon_el.get("src"):
                icons[ch_id] = icon_el.get("src").strip()

    latest_date = None
    progs = {cid: [] for cid in wanted}

    for prog in root.iter("programme"):
        ch_id = prog.get("channel", "")
        if ch_id not in wanted:
            continue
        try:
            start = parse_xmltv_time(prog.get("start", ""))
            stop  = parse_xmltv_time(prog.get("stop", ""))
            
            if latest_date is None or start > latest_date:
                latest_date = start
                
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
        except ValueError:
            continue
            
    for ch_id in progs:
        progs[ch_id].sort(key=lambda p: p["start"])

    return progs, icons, latest_date


def get_best_xmltv(days_ahead: int):
    best_progs = None
    best_icons = None
    best_date = None
    best_url = None

    for url in XMLTV_SOURCES:
        try:
            progs, icons, latest = fetch_xmltv_from_url(url, days_ahead)
            if latest is None:
                continue
            
            print(f"  -> Nejnovější data v tomto zdroji: {latest.strftime('%Y-%m-%d')}", file=sys.stderr)
            
            if best_date is None or latest > best_date:
                best_date = latest
                best_progs = progs
                best_icons = icons
                best_url = url
                
            # Pokud už máme data pro zítřek nebo pozítří, je to dost dobré a nemusíme zkoušet další
            if (latest.date() - datetime.now(timezone.utc).date()).days >= 1:
                break
                
        except Exception as exc:
            print(f"  -> Selhalo: {exc}", file=sys.stderr)

    if best_progs is None:
        raise RuntimeError("Všechny XMLTV zdroje selhaly!")
        
    print(f"[OK] Zvolen XMLTV zdroj: {best_url} s daty do {best_date.strftime('%Y-%m-%d')}", file=sys.stderr)
    return best_progs, best_icons, best_url


# ──────────────────────────────────────────────────────────────────────────────
# Sestavení výsledného JSON
# ──────────────────────────────────────────────────────────────────────────────

def deduplicate(progs):
    seen = set()
    unique = []
    for p in sorted(progs, key=lambda x: x["start"]):
        k = (p["start"], p["title"])
        if k not in seen:
            seen.add(k)
            unique.append(p)
    return unique

def build_output(ct_progs: dict, xmltv_progs: dict, xmltv_icons: dict, xmltv_source_url: str) -> dict:
    nova_ch = [c for c, name in XMLTV_CHANNEL_MAP.items() if name == "TV Nova"][0]
    prima_ch = [c for c, name in XMLTV_CHANNEL_MAP.items() if name == "Prima"][0]
    seznam_ch = [c for c, name in XMLTV_CHANNEL_MAP.items() if name == "Televize Seznam"][0]

    channels = [
        {
            "id": "tv-nova", "name": "TV Nova",
            "logo": xmltv_icons.get(nova_ch) or XMLTV_LOGOS_FALLBACK["TV Nova"],
            "source": xmltv_source_url,
            "programmes": deduplicate(xmltv_progs.get(nova_ch, [])),
        },
        {
            "id": "prima", "name": "Prima",
            "logo": xmltv_icons.get(prima_ch) or XMLTV_LOGOS_FALLBACK["Prima"],
            "source": xmltv_source_url,
            "programmes": deduplicate(xmltv_progs.get(prima_ch, [])),
        },
        {
            "id": "seznam-tv", "name": "Televize Seznam",
            "logo": xmltv_icons.get(seznam_ch) or XMLTV_LOGOS_FALLBACK["Televize Seznam"],
            "source": xmltv_source_url,
            "programmes": deduplicate(xmltv_progs.get(seznam_ch, [])),
        },
        {
            "id": "ct1", "name": "ČT1",
            "logo": CT_CHANNELS["ct1"]["logo"],
            "source": "Česká televize (API)",
            "programmes": ct_progs.get("ČT1", []),
        },
        {
            "id": "ct2", "name": "ČT2",
            "logo": CT_CHANNELS["ct2"]["logo"],
            "source": "Česká televize (API)",
            "programmes": ct_progs.get("ČT2", []),
        },
        {
            "id": "ct-sport", "name": "ČT sport",
            "logo": CT_CHANNELS["ct4"]["logo"],
            "source": "Česká televize (API)",
            "programmes": ct_progs.get("ČT sport", []),
        },
    ]

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {"ct": CT_API_URL, "xmltv": xmltv_source_url},
        "channels": channels,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default="epg_data.json")
    parser.add_argument("--days", "-d", type=int, default=7)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args()

    try:
        print("\n=== Česká televize (oficiální API) ===", file=sys.stderr)
        ct_progs = fetch_ct_all(args.days)
    except RuntimeError as exc:
        ct_progs = {"ČT1": [], "ČT2": [], "ČT sport": []}
        print(f"[CHYBA] ČT API selhalo: {exc}", file=sys.stderr)

    try:
        print("\n=== Nova + Prima + Seznam (XMLTV) ===", file=sys.stderr)
        xmltv_progs, xmltv_icons, best_url = get_best_xmltv(args.days)
    except RuntimeError as exc:
        xmltv_progs = {ch: [] for ch in XMLTV_CHANNEL_MAP}
        xmltv_icons, best_url = {}, "none"
        print(f"[CHYBA] Všechny XMLTV zdroje selhaly: {exc}", file=sys.stderr)

    output = build_output(ct_progs, xmltv_progs, xmltv_icons, best_url)
    indent = args.indent if args.indent > 0 else None

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=indent)

    total = sum(len(ch["programmes"]) for ch in output["channels"])
    print(f"\n[OK] Uloženo {total} pořadů → '{args.output}'", file=sys.stderr)

if __name__ == "__main__":
    main()
