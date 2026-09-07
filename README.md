# TV Program – Webová aplikace

Jednoduchá webová aplikace zobrazující TV program pro **TV Nova, ČT1, ČT2 a Prima**.

## Architektura (bezplatná, automatická)

```
epg.lat/cz.xml.gz
        │
        │ stahování (XMLTV/gzip)
        ▼
GitHub Actions (cron 4×/den)
  └── scripts/fetch_epg.py
        │
        │ git commit + push
        ▼
GitHub repozitář
  └── public/epg_data.json
        │
        │ automatický deploy při každém push
        ▼
Netlify CDN
  └── https://vas-web.netlify.app/epg_data.json
        │
        │ fetch() z prohlížeče
        ▼
Frontend (index.html)
```

**Vše probíhá automaticky. Nevyžaduje zapnutý počítač ani placené služby.**

---

## Struktura projektu

```
TV-Web/
├── .github/
│   └── workflows/
│       └── update-epg.yml    ← GitHub Actions cron job (automatická aktualizace)
├── public/
│   ├── epg_data.json         ← Aktuální TV program (generovaný automaticky)
│   ├── epg_sample.json       ← Ukázkový JSON pro referenci
│   └── index.html            ← Frontend (TODO: fáze 3)
├── scripts/
│   └── fetch_epg.py          ← Python skript pro stahování EPG
├── netlify.toml              ← Konfigurace Netlify
├── .gitignore
└── README.md
```

---

## Nasazení (jednorázové nastavení)

### Krok 1: GitHub repozitář

1. Vytvoř nový GitHub repozitář (může být i privátní).
2. Nahraj celý obsah složky `TV-Web/` do repozitáře:
   ```bash
   git init
   git add .
   git commit -m "první commit"
   git remote add origin https://github.com/TVUJ-NICK/tv-program.git
   git push -u origin main
   ```

### Krok 2: Netlify – propojení s GitHub

1. Přihlas se na [netlify.com](https://netlify.com) a klikni **Add new site → Import an existing project**.
2. Zvol **GitHub** a vyber svůj repozitář.
3. Netlify automaticky přečte `netlify.toml` a nastaví:
   - **Publish directory:** `public`
   - **Build command:** *(prázdné – nic se nebuilí)*
4. Klikni **Deploy site**.

> Po nasazení bude `epg_data.json` dostupný na:
> `https://tvuj-web.netlify.app/epg_data.json`

### Krok 3: GitHub Actions – oprávnění pro push

GitHub Actions potřebuje oprávnění zapisovat do repozitáře.

**Nastavení v GitHub:**
1. Jdi do **Settings → Actions → General** tvého repozitáře.
2. V sekci **Workflow permissions** vyber **Read and write permissions**.
3. Klikni **Save**.

To je vše. Workflow soubor `.github/workflows/update-epg.yml` je již připraven.

---

## Jak to funguje automaticky

| Čas (UTC) | Čas (CEST) | Co se děje |
|-----------|------------|------------|
| 06:00     | 08:00      | GitHub Actions spustí `fetch_epg.py` |
| 12:00     | 14:00      | GitHub Actions spustí `fetch_epg.py` |
| 18:00     | 20:00      | GitHub Actions spustí `fetch_epg.py` |
| 22:00     | 00:00      | GitHub Actions spustí `fetch_epg.py` |

**Co přesně se při každém spuštění stane:**
1. GitHub Actions stáhne kód z repozitáře.
2. Spustí `python scripts/fetch_epg.py --output public/epg_data.json --days 7`.
3. Skript stáhne XMLTV data z `epg.lat`, vyfiltruje 4 kanály, uloží JSON.
4. Pokud se JSON změnil → provede `git commit` + `git push`.
5. Netlify detekuje nový commit → automaticky nasadí novou verzi webu.
6. Nová data jsou dostupná na CDN typicky do 30–60 sekund.

**Pokud se JSON nezměnil** (epg.lat ještě neaktualizoval data), commit se neprovede a Netlify se zbytečně nerestartuje.

---

## Limity zdarma

| Služba | Free limit | Naše využití |
|--------|-----------|--------------|
| GitHub Actions | 2 000 min/měsíc (public repo: neomezeno) | ~4 min/měsíc |
| Netlify deploy | 300 kreditů/měsíc (každý deploy = 15 kreditů) | max 120 kreditů (8×/den × 15 dní, když se JSON mění) |
| Netlify bandwidth | 100 GB/měsíc | minimální (statické soubory) |
| epg.lat | zdarma, bez limitu | 4 dotazy/den |

> **Tip:** Pro veřejný GitHub repozitář jsou GitHub Actions zcela zdarma bez minutového omezení.

---

## Manuální spuštění aktualizace

Jdi na GitHub → záložka **Actions** → vyber workflow **Aktualizace TV programu** → klikni **Run workflow**.

---

## EPG zdroj

- **URL:** `https://epg.lat/files/cz.xml.gz`
- **Formát:** XMLTV (gzip)
- **Podmínky:** Volně dostupná data, bez API klíče
- **Aktualizace zdroje:** 1× denně

## Formát výstupního JSON

```json
{
  "generated_at": "2026-09-07T15:29:11Z",
  "source": "https://epg.lat/files/cz.xml.gz",
  "channels": [
    {
      "id": "tv-nova",
      "name": "TV Nova",
      "programmes": [
        {
          "title": "Ulice",
          "start": "2026-09-07T17:30:00Z",
          "stop":  "2026-09-07T18:30:00Z",
          "start_local": "2026-09-07T19:30:00+0200",
          "stop_local":  "2026-09-07T20:30:00+0200",
          "description": "...",
          "category": null
        }
      ]
    }
  ]
}
```
