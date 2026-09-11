# TV Program – Webová aplikace

Jednoduchá, moderní a plně automatizovaná webová aplikace pro TV program stanic:
**TV Nova, Prima, Televize Seznam, ČT1, ČT2 a ČT sport**.

- **Živý web:** [https://tv-program1.netlify.app](https://tv-program1.netlify.app) (případně GitHub Pages, doporučeno kvůli kreditům)
- **GitHub repozitář:** `petmat247-cloud/tv-program`
- **Hosting:** Netlify / GitHub Pages

---

## 📡 Architektura a zdroje dat

1. **Česká televize (ČT1, ČT2, ČT sport):**
   - Oficiální bezplatné JSON API České televize (`ceskatelevize.cz`)
   - Délka pořadu (stopaz) se z API parsuje jako `MM:SS` (minuty:sekundy).
2. **TV Nova, Prima a Televize Seznam:**
   - EPG zdroj `https://epg.lat/files/cz.xml.gz` (XMLTV formát).
   - Loga se stahují staticky z `sms.cz` kvůli spolehlivosti.
3. **Automatizace:**
   - GitHub Actions (`.github/workflows/update-epg.yml`) spouští každý den ráno skript `scripts/fetch_epg.py`.
   - Výsledný `public/epg_data.json` se automaticky uloží do repozitáře. *Doporučuje se hostovat přes GitHub Pages kvůli úspoře Netlify kreditů (každý commit přes Actions jinak vyčerpává Netlify).*

---

## 📂 Struktura projektu

```text
TV-Web/
├── .github/
│   └── workflows/
│       └── update-epg.yml      ← Denní GitHub Actions cron (stahování + commit)
├── public/
│   ├── index.html              ← Kompletní frontend (CSS, JS, Dark/Light mód, filtry)
│   ├── epg_data.json           ← Aktuální vygenerovaná data programu
│   └── epg_sample.json         ← Referenční ukázka
├── scripts/
│   └── fetch_epg.py            ← Python skript stahující ČT API + epg.lat
├── Spustit-nahled.command      ← Dvojklik pro lokální testování (spustí server http://localhost:8080)
├── netlify.toml                ← Konfigurace Netlify (CORS, cache hlavičky)
├── .gitignore
└── README.md
```

---

## 📝 Historie a vývoj (Září 2026 - Změny a fixy)
Při pokračování ve vývoji s AI sdílejte tyto body, aby věděla, na co navázat:
- **Televize Seznam:** Byla přidána (CSS `#991b1b`, ID `seznam-tv`, stahuje se z `epg.lat` z kanálu `Seznam.cz.TV.cz`).
- **Opravy layoutu:** Problém s překrýváním dlouhých názvů (např. Cestománie) se štítkem "PRÁVĚ BĚŽÍ" je opraven přes CSS `grid` pro `.p-row`. Filtry a navigace dnů jsou v CSS vycentrované.
- **Logika Právě Běží:** Každý kanál může mít ve stejnou dobu "PRÁVĚ BĚŽÍ" vždy **maximálně jeden pořad**.
- **Barvy stanic:**
  - ČT1 je laděna do `indigo` (modro-červená, odlišená od Novy).
  - ČT2 je laděna do zlatavě žluté, zbytek stanic ponechán v brand barvách.
- **Zdroje log:** Přešlo se jednotně na loga ze `sms.cz`, aby nedocházelo k chybám 404 z původního zdroje ČT.
- **Bugfixes:**
  - Opravena stopáž ČT pořadů (původní kód četl minuty jako hodiny).
  - Ze zdroje `epg.lat` byl vyřazen kanál `Nova.TV.cz` (což je chorvatská Nova), načítá se pouze česká `Nova.cz`.

---

## 🚀 Jak nahrávat změny (workflow)
1. Úprava souborů lokálně v této složce.
2. Před uploadem lokálně zkontrolovat otevřením `index.html` (nebo `Spustit-nahled.command`).
3. Dát git commit celého projektu na GitHub najednou (např. z VS Code nebo terminálu), nikoliv editací jednoho souboru po druhém z webového rozhraní GitHubu, aby nedocházelo k plýtvání deploy limitů (pokud využíváte Netlify).
