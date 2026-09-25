import gzip
import xml.etree.ElementTree as ET

FILES = [
    "cz_epg_lat.xml.gz",
    "cz_epg_git.xml.gz"
]

XMLTV_CHANNEL_MAP = {
    "Nova.cz":         "TV Nova",
    "Prima.cz":        "Prima",
    "Seznam.cz.TV.cz": "Televize Seznam",
}
wanted = set(XMLTV_CHANNEL_MAP.keys())

for file_name in FILES:
    print(f"\n--- Checking {file_name} ---")
    try:
        with gzip.open(file_name, 'rb') as f:
            xml_bytes = f.read()
            
        root = ET.fromstring(xml_bytes)
        
        progs = []
        for prog in root.iter("programme"):
            ch = prog.get("channel")
            if ch in wanted:
                start = prog.get("start", "")
                title = prog.find("title")
                t = title.text if title is not None else ""
                progs.append((ch, start, t))
        
        print(f"Found {len(progs)} total programs for wanted channels.")
        
        for target_ch in wanted:
            ch_progs = sorted([p for p in progs if p[0] == target_ch], key=lambda x: x[1])
            count_25 = 0
            count_26 = 0
            for _, st, title in ch_progs:
                if st.startswith("20260925"):
                    count_25 += 1
                if st.startswith("20260926"):
                    count_26 += 1
                    if count_26 == 1:
                        print(f"First on Sept 26 for {target_ch}: {st} - {title}")
            print(f"{target_ch} -> Sept 25: {count_25}, Sept 26: {count_26}")
            if ch_progs:
                print(f"  Last prog: {ch_progs[-1][1]} - {ch_progs[-1][2]}")
            
    except Exception as e:
        print(f"Failed: {e}")
