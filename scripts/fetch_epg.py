#!/usr/bin/env python3
"""
fetch_epg.py — Stahuje TV program z OFICIÁLNÍHO API České televize (ČT1, ČT2)
               a z epg.lat/cz.xml.gz (TV Nova, Prima).

Zdroje:
  ČT1, ČT2 → https://www.ceskatelevize.cz/services-old/programme/xml/schedule.php
              Oficiální, bezplatné, bez API klíče (user=test stačí).
  Nova, Prima → https://epg.lat/files/cz.xml.gz  (XMLTV/gzip)
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

# Officiální API ČT — jeden dotaz na kanál × den
# user=test je veřejně zdokumentovaný testovací přístup
CT_API_URL = (
    "https://www.ceskatelevize.cz/services-old/programme/xml/schedule.php"
    "?user=test&date={date}&channel={channel}&json=1"
)
CT_CHANNELS = {
    "ct1": {"name": "ČT1",  "id": "ct1",
            "logo": "https://img.ceskatelevize.cz/program/user/16/bnr/ct1.png"},
    "ct2": {"name": "ČT2",  "id": "ct2",
            "logo": "https://img.ceskatelevize.cz/program/user/16/bnr/ct2.png"},
}

# XMLTV mapování pro Novu a Primu (ČT voláme přes vlastní API)
XMLTV_CHANNEL_MAP = {
    "Nova.cz":    "TV Nova",
    "Nova.TV.cz": "TV Nova",
    "Prima.cz":   "Prima",
}
XMLTV_LOGOS_FALLBACK = {
    "TV Nova": "https://www.sms.cz/kategorie/televize/bmp/loga/velka/nova.png",
    "Prima":   None,
}

CHANNEL_ORDER = ["TV Nova", "ČT1", "ČT2", "Prima"]
CHANNEL_SLUGS = {
    "TV Nova": "tv-nova",
    "ČT1":     "ct1",
    "ČT2":     "ct2",
    "Prima":   "prima",
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
    """CET (UTC+1) nebo CEST (UTC+2) podle DST."""
    import calendar
    year = dt_utc.year

    def last_sunday(y, month):
        last = calendar.monthrange(y, month)[1]
        d = datetime(y, month, last, 1, 0, 0, tzinfo=timezone.utc)
        return d - timedelta(days=(d.weekday() + 1) % 7)

    if last_sunday(year, 3) <= dt_utc < last_sunday(year, 10):
        return timezone(timedelta(hours=2))   # CEST
    return timezone(timedelta(hours=1))        # CET


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ──────────────────────────────────────────────────────────────────────────────
# Zdroj 1: Česká televize – Oficiální API
# ──────────────────────────────────────────────────────────────────────────────

def fetch_ct_day(channel_id: str, date: datetime) -> list:
    """
    Stáhne program jednoho ČT kanálu pro jeden den.
    Vrací list pořadů ve společném formátu.
    """
    date_str = date.strftime("%d.%m.%Y")   # formát API: "07.09.2026"
    url = CT_API_URL.format(date=date_str, channel=channel_id)

    try:
        raw = http_get(url)
        data = json.loads(raw)
    except RuntimeError as exc:
        print(f"[WARN] ČT API – {channel_id} {date_str}: {exc}", file=sys.stderr)
        return []
    except json.JSONDecodeError as exc:
        print(f"[WARN] ČT API – neplatný JSON pro {channel_id} {date_str}: {exc}", file=sys.stderr)
        return []

    porad_list = data.get("porad", [])
    if not isinstance(porad_list, list):
        return []

    programmes = []
    for p in porad_list:
        cas   = p.get("cas", "")          # "20:10"
        nazev = (p.get("nazvy") or {}).get("nazev", "").strip()
        datum = p.get("datum", "")        # "2026-09-07"
        stopaz = p.get("stopaz", "")      # "054:24"
        popis = p.get("noticka", "") or ""
        zanr  = p.get("zanr", "") or ""

        if not (cas and nazev and datum):
            continue

        try:
            # Sestavíme start datetime v lokálním čase
            start_local_naive = datetime.strptime(f"{datum} {cas}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue

        # Konvertujeme na UTC
        # Přibližně zjistíme offset pro tento den
        approx_utc = start_local_naive.replace(tzinfo=timezone.utc)
        tz = get_czech_tz(approx_utc)
        start_dt = start_local_naive.replace(tzinfo=tz)
        start_utc = start_dt.astimezone(timezone.utc)

        # Délka pořadu ze stopáže "HH:MM" nebo "HHH:MM"
        stop_utc = start_utc + timedelta(minutes=30)  # fallback
        if stopaz:
            try:
                parts = stopaz.split(":")
                dur_min = int(parts[0]) * 60 + int(parts[1])
                stop_utc = start_utc + timedelta(minutes=dur_min)
            except (ValueError, IndexError):
                pass

        if not nazev:
            continue

        programmes.append({
            "title":       nazev,
            "start":       utc_iso(start_utc),
            "stop":        utc_iso(stop_utc),
            "description": popis.strip() or None,
            "category":    zanr.strip() or None,
        })

    return programmes


def fetch_ct_all(days_ahead: int) -> dict:
    """
    Stáhne data ČT pro všechny dny (dnes + days_ahead) a oba kanály.
    Vrací {canon_name: [programmes...]}
    """
    now_local = datetime.now(get_czech_tz(datetime.now(timezone.utc)))
    results = {info["name"]: [] for info in CT_CHANNELS.values()}

    for ch_id, info in CT_CHANNELS.items():
        all_progs = []
        for day_offset in range(days_ahead + 1):
            day = now_local + timedelta(days=day_offset)
            progs = fetch_ct_day(ch_id, day)
            all_progs.extend(progs)
            print(
                f"[INFO] ČT API – {info['name']} "
                f"{day.strftime('%d.%m.')}: {len(progs)} pořadů",
                file=sys.stderr
            )

        # Deduplikace a seřazení
        seen = set()
        unique = []
        for p in sorted(all_progs, key=lambda x: x["start"]):
            key = (p["start"], p["title"])
            if key not in seen:
                seen.add(key)
                unique.append(p)

        results[info["name"]] = unique

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Zdroj 2: epg.lat XMLTV — TV Nova a Prima
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
    """
    Stáhne a zparsuje XMLTV soubor z epg.lat.
    Vrací (programmes_dict, icons_dict) jen pro Nova a Prima.
    """
    wanted = set(XMLTV_CHANNEL_MAP.keys())

    print(f"[INFO] Stahuji XMLTV z: {XMLTV_URL}", file=sys.stderr)
    raw  = http_get(XMLTV_URL)
    print(f"[INFO] Staženo {len(raw):,} bajtů, dekomprimuji...", file=sys.stderr)

    try:
        xml_bytes = gzip.decompress(raw)
    except Exception as exc:
        raise RuntimeError(f"Dekomprese XMLTV selhala: {exc}") from exc

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise RuntimeError(f"Parsování XML selhalo: {exc}") from exc

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

def build_output(ct_progs: dict, xmltv_progs: dict, xmltv_icons: dict) -> dict:
    """
    Sloučí data z obou zdrojů do jednotného výstupního JSON.
    """
    # Sloučení Nova aliasů
    nova_progs = []
    nova_logo  = None
    for ch_id, canon in XMLTV_CHANNEL_MAP.items():
        if canon == "TV Nova":
            nova_progs.extend(xmltv_progs.get(ch_id, []))
            if nova_logo is None:
                nova_logo = xmltv_icons.get(ch_id) or XMLTV_LOGOS_FALLBACK.get("TV Nova")

    # Deduplikace Nova
    seen = set()
    nova_unique = []
    for p in sorted(nova_progs, key=lambda x: x["start"]):
        k = (p["start"], p["title"])
        if k not in seen:
            seen.add(k)
            nova_unique.append(p)

    # Prima
    prima_progs = []
    prima_logo  = None
    for ch_id, canon in XMLTV_CHANNEL_MAP.items():
        if canon == "Prima":
            prima_progs.extend(xmltv_progs.get(ch_id, []))
            if prima_logo is None:
                prima_logo = xmltv_icons.get(ch_id) or XMLTV_LOGOS_FALLBACK.get("Prima")

    # Sestavení kanálů v pořadí
    channels = [
        {
            "id":         "tv-nova",
            "name":       "TV Nova",
            "logo":       nova_logo,
            "source":     "epg.lat",
            "programmes": nova_unique,
        },
        {
            "id":         "ct1",
            "name":       "ČT1",
            "logo":       CT_CHANNELS["ct1"]["logo"],
            "source":     "ceskatelevize.cz (oficiální API)",
            "programmes": ct_progs.get("ČT1", []),
        },
        {
            "id":         "ct2",
            "name":       "ČT2",
            "logo":       CT_CHANNELS["ct2"]["logo"],
            "source":     "ceskatelevize.cz (oficiální API)",
            "programmes": ct_progs.get("ČT2", []),
        },
        {
            "id":         "prima",
            "name":       "Prima",
            "logo":       prima_logo,
            "source":     "epg.lat",
            "programmes": prima_progs,
        },
    ]

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "ct": "https://www.ceskatelevize.cz/services-old/programme/xml/schedule.php",
            "xmltv": XMLTV_URL,
        },
        "channels": channels,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Hlavní funkce
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Stahuje TV program (ČT z ofic. API, Nova/Prima z XMLTV) → JSON."
    )
    parser.add_argument("--output", "-o", default="epg_data.json")
    parser.add_argument("--days", "-d", type=int, default=7)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args()

    errors = []

    # ── ČT (oficiální API) ──
    try:
        print("\n=== Česká televize (oficiální API) ===", file=sys.stderr)
        ct_progs = fetch_ct_all(args.days)
    except RuntimeError as exc:
        print(f"[CHYBA] ČT API selhalo: {exc}", file=sys.stderr)
        ct_progs = {"ČT1": [], "ČT2": []}
        errors.append(f"ČT API: {exc}")

    # ── Nova + Prima (XMLTV) ──
    try:
        print("\n=== Nova + Prima (epg.lat XMLTV) ===", file=sys.stderr)
        xmltv_progs, xmltv_icons = fetch_xmltv(args.days)
    except RuntimeError as exc:
        print(f"[CHYBA] XMLTV selhalo: {exc}", file=sys.stderr)
        xmltv_progs = {ch: [] for ch in XMLTV_CHANNEL_MAP}
        xmltv_icons = {}
        errors.append(f"XMLTV: {exc}")

    # ── Sestavení výstupu ──
    output = build_output(ct_progs, xmltv_progs, xmltv_icons)
    indent = args.indent if args.indent > 0 else None

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=indent)

    total = sum(len(ch["programmes"]) for ch in output["channels"])
    print(f"\n[OK] Uloženo {total} pořadů → '{args.output}'", file=sys.stderr)

    if errors:
        print(f"[POZOR] Některé zdroje selhaly: {'; '.join(errors)}", file=sys.stderr)
        # Nekončíme chybou — částečná data jsou lepší než nic


if __name__ == "__main__":
    main()
