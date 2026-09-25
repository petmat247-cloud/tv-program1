import gzip
import urllib.request
import urllib.error
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

XMLTV_SOURCES = [
    "https://epg.lat/files/cz.xml.gz",
    "https://raw.githubusercontent.com/kozmali/sk-cz-epg/main/epg.xml.gz"
]

XMLTV_CHANNEL_MAP = {
    "Nova.cz":         "TV Nova",
    "Prima.cz":        "Prima",
    "Seznam.cz.TV.cz": "Televize Seznam",
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for url in XMLTV_SOURCES:
    print(f"\n--- Checking {url} ---")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            raw = r.read()
        
        try:
            xml_bytes = gzip.decompress(raw)
        except Exception:
            xml_bytes = raw
            
        root = ET.fromstring(xml_bytes)
        
        wanted = set(XMLTV_CHANNEL_MAP.keys())
        progs = []
        for prog in root.iter("programme"):
            ch = prog.get("channel")
            if ch in wanted:
                start = prog.get("start", "")
                title = prog.find("title")
                t = title.text if title is not None else ""
                progs.append((ch, start, t))
        
        print(f"Found {len(progs)} total programs for wanted channels.")
        
        # Sort and filter for Sept 26
        for target_ch in wanted:
            ch_progs = sorted([p for p in progs if p[0] == target_ch], key=lambda x: x[1])
            if ch_progs:
                print(f"Last prog for {target_ch}: {ch_progs[-1][1]} - {ch_progs[-1][2]}")
            
    except Exception as e:
        print(f"Failed: {e}")
