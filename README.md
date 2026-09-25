# TV Program – Webová aplikace

Jednoduchá, moderní a plně automatizovaná webová aplikace pro TV program stanic:
**TV Nova, Prima, Televize Seznam, ČT1, ČT2 a ČT sport**.

- **Živý web:** [https://petmat247-cloud.github.io/tv-program1/](https://petmat247-cloud.github.io/tv-program1/)
- **GitHub repozitář:** `petmat247-cloud/tv-program1`
- **Hosting:** GitHub Pages (Zcela zdarma, Netlify bylo zrušeno kvůli kreditům)

---

## 📡 Architektura a zdroje dat

1. **Česká televize (ČT1, ČT2, ČT sport):**
   - Oficiální bezplatné JSON API České televize (`ceskatelevize.cz`)
   - Délka pořadu (stopaz) se z API parsuje jako `MM:SS` (minuty:sekundy).
2. **TV Nova, Prima a Televize Seznam (Komunitní XMLTV s přepínáním):**
   - Hledá se nejčerstvější program z více nezávislých zdrojů.
   - **Záloha 1:** EPG zdroj `https://epg.lat/files/cz.xml.gz`
   - **Záloha 2:** Komunitní `sk-cz-epg` GitHub (pokud `epg.lat` zaostane).
   - Loga se stahují staticky z `sms.cz` kvůli spolehlivosti.
3. **Automatizace (GitHub Actions):**
   - Skript `.github/workflows/update-epg.yml` se spouští každý den ráno (nebo při změně kódu).
   - Spustí `scripts/fetch_epg.py`, který vygeneruje `public/epg_data.json`.
   - Následně GitHub Action automaticky vezme celou složku `public` a nasadí ji jako web na GitHub Pages.

---

## 📂 Struktura projektu

```text
TV-Web/
├── .github/
│   └── workflows/
│       └── update-epg.yml      ← Automatizace: Stažení dat + Deploy na GitHub Pages
├── public/
│   ├── index.html              ← Kompletní frontend (CSS, JS, Dark/Light mód, filtry, tlačítko na refresh)
│   ├── epg_data.json           ← Aktuální vygenerovaná data programu
│   └── epg_sample.json         ← Referenční ukázka
├── scripts/
│   └── fetch_epg.py            ← Python skript stahující ČT API + chytře vybírá z XMLTV zdrojů
├── Spustit-nahled.command      ← Dvojklik pro lokální testování (spustí server http://localhost:8080)
├── .gitignore
└── README.md
```

---

## 📝 Historie a vývoj (Změny a fixy)
Při pokračování ve vývoji s AI sdílejte tyto body, aby věděla, na co navázat:

- **Září 2026 (Fix EPG výpadků):** Aplikace trpěla na prázdná data pro komerční stanice, když primární zdroj `epg.lat` přestal aktualizovat soubor. Řešením bylo nasazení **"inteligentního fallbacku"** ve `fetch_epg.py` – skript stáhne více XMLTV zdrojů, porovná aktuálnost a vybere ten nejčerstvější. Zároveň bylo pro ČT kanály pevně navráceno **ČT API**, aby byly nezávislé na XMLTV komunitě.
- **Září 2026 (UI Vylepšení):** Bylo přidáno tlačítko Refresh (🔄) vedle změny vzhledu, které tiše stáhne na pozadí nejnovější `epg_data.json` ze serveru (cache-busting) bez reloadování celé stránky, užitečné po proběhnutí GitHub Action.
- **Září 2026 (Migrace):** Kompletní přesun z Netlify na GitHub Pages. Přepracován `update-epg.yml`, aby stahoval EPG a rovnou nasazoval web (složku `public`). Smazán `netlify.toml` a fallbacky v `index.html`. Repozitář přejmenován na `tv-program1` a nastavena oprávnění Read/Write.
- **Televize Seznam:** Byla přidána (CSS `#991b1b`, ID `seznam-tv`, stahuje se z `epg.lat` z kanálu `Seznam.cz.TV.cz`).
- **Opravy layoutu:** Problém s překrýváním dlouhých názvů se štítkem "PRÁVĚ BĚŽÍ" je opraven přes CSS `grid` pro `.p-row`.
- **Logika Právě Běží:** Každý kanál může mít ve stejnou dobu "PRÁVĚ BĚŽÍ" vždy **maximálně jeden pořad**.
- **Barvy stanic:** ČT1 je laděna do `indigo`, ČT2 do zlatavě žluté.
- **Zdroje log:** Přešlo se jednotně na loga ze `sms.cz`, aby nedocházelo k chybám 404 z původního zdroje ČT.

---

## 🚀 Jak nahrávat změny a aktualizovat web

Pokud chceš cokoliv upravit (přidat kanál, změnit barvu, upravit text):

1. **Úprava na počítači:** Otevři projekt ve **VS Code** a proveď změny v kódu (např. v `public/index.html`).
2. **Lokální kontrola:** Otevři si `index.html` v prohlížeči nebo dvakrát klikni na `Spustit-nahled.command` a podívej se, jestli to vypadá tak, jak chceš.
3. **Nahrání na GitHub (VS Code):**
   - V levém menu VS Code klikni na třetí ikonku shora (**Source Control**).
   - Napiš krátkou zprávu (např. "Přidán nový kanál") do políčka *Message* a klikni na modré tlačítko **Commit**.
   - Pak klikni na modré tlačítko **Sync Changes** (nebo ikonu `0↓ 1↑` dole v liště).
4. **Hotovo:** Jakmile to VS Code nahraje na GitHub, automaticky se spustí akce a do minuty se změny objeví na živém webu! (Na nic dalšího neklikej, vše se zkompiluje samo).
