# TSV Lindau Handball – Herren

Statistik-App der TSV Lindau Herren (Bezirksoberliga Oberschwaben-Ostalb):
Tabelle, Spielplan mit Hallen und Route, Ergebnisse, Links zu den Spielberichten
und Spielerstatistik.

**Als App aufs Handy:** Seite öffnen → iPhone: Teilen → „Zum Home-Bildschirm“ ·
Android: Menü ⋮ → „App installieren“ bzw. „Zum Startbildschirm hinzufügen“.

## So funktioniert es
- `site/` – die Seite (wird über GitHub Pages veröffentlicht)
- `site/data/liga.json` – Tabelle und Spiele, **automatisch jeden Sonntag 21:30 Uhr**
  von handball4all geholt (`scripts/liga_update.py`, `.github/workflows/update.yml`).
  GitHub startet geplante Abläufe teils verspätet.
- `site/data/spieler.json` – Spielerstatistik aus den Spielberichten (PDF).
  Die PDFs werden **nicht** automatisch geladen, sondern im Claude-Chat hochgeladen
  und mit `scripts/bericht_auswerten.py` ausgewertet (Prüfung: Torsumme = Endstand,
  Spielertore = Mannschaftsliste; „N.N.“ über `site/data/trikotliste.json`).
- Manuelles Update: Aktionen → „Update & Veröffentlichen“ → „Run workflow“.

Quelle der Daten: handball4all / Spielbetrieb BWHV.
