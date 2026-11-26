#!/usr/bin/env python3
"""Holt Tabelle und Spielplan von handball4all und schreibt site/data/liga.json.
Läuft automatisch per GitHub Actions (sonntags 21:30 Uhr). Bei Fehlern wird die
alte Datei NICHT überschrieben und das Skript endet mit Fehler (rote Aktion).

Aufruf: python3 scripts/liga_update.py [datei.json]   (Datei = Test ohne Internet)
"""
import json, sys, pathlib, datetime, urllib.request

LIGA, ORG, TEAM = 166226, 216, 'TSV Lindau'
URL = f'https://spo.handball4all.de/service/if_g_json.php?ca=1&cl={LIGA}&cmd=ps&og={ORG}'
BERICHT = 'https://spo.handball4all.de/misc/sboPublicReports.php?sGID='
OUT = pathlib.Path(__file__).resolve().parent.parent / 'site/data/liga.json'


def zahl(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def laden(quelle):
    if quelle:
        return json.loads(pathlib.Path(quelle).read_text())
    req = urllib.request.Request(URL, headers={'User-Agent': 'tsv-lindau-statistik (privat, 1x pro Woche)'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def umwandeln(raw):
    d = raw[0] if isinstance(raw, list) else raw
    head, c = d.get('head') or {}, d.get('content') or {}
    tabelle = [dict(pl=zahl(s.get('tabScore')), team=str(s.get('tabTeamname', '')).strip(),
                    sp=zahl(s.get('numPlayedGames')), s=zahl(s.get('numWonGames')), u=zahl(s.get('numEqualGames')),
                    n=zahl(s.get('numLostGames')), tf=zahl(s.get('numGoalsShot')), ta=zahl(s.get('numGoalsGot')),
                    pp=zahl(s.get('pointsPlus')), pm=zahl(s.get('pointsMinus'))) for s in c.get('score') or []]
    spiele, gesehen = [], set()
    quellen = list(c.get('games') or []) + list((c.get('futureGames') or {}).get('games') or [])
    for g in quellen:
        h, gu = str(g.get('gHomeTeam', '')).strip(), str(g.get('gGuestTeam', '')).strip()
        if TEAM not in (h, gu) or g.get('gID') in gesehen:
            continue
        gesehen.add(g.get('gID'))
        datum = str(g.get('gDate', '')).strip()
        try:
            iso = datetime.datetime.strptime(datum, '%d.%m.%y').date().isoformat()
        except ValueError:
            iso = ''
        sgid = zahl(g.get('sGID')) or 0
        spiele.append(dict(datum=datum, iso=iso, tag=str(g.get('gWDay', '')).strip(), zeit=str(g.get('gTime', '')).strip(),
                           heim=h, gast=gu, th=zahl(g.get('gHomeGoals')), tg=zahl(g.get('gGuestGoals')),
                           hzh=zahl(g.get('gHomeGoals_1')), hzg=zahl(g.get('gGuestGoals_1')),
                           halle=str(g.get('gGymnasiumName', '')).strip(), ort=str(g.get('gGymnasiumTown', '')).strip(),
                           strasse=str(g.get('gGymnasiumStreet', '')).strip(), plz=str(g.get('gGymnasiumPostal', '')).strip(),
                           kommentar=str(g.get('gComment', '') or '').strip(),
                           bericht=(BERICHT + str(sgid)) if sgid else ''))
    spiele.sort(key=lambda s: (s['iso'], s['zeit']))
    for s in spiele:  # ohne Ergebnis -> beide None
        if s['th'] is None or s['tg'] is None:
            s['th'] = s['tg'] = s['hzh'] = s['hzg'] = None
    return dict(liga=str(head.get('name', '')).strip(), staffel=str(head.get('headline2', '') or head.get('headline1', '')).strip(),
                stand_quelle=str(head.get('actualized', '')).strip(),
                abgerufen=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'),
                tabelle=tabelle, spiele=spiele)


def main():
    neu = umwandeln(laden(sys.argv[1] if len(sys.argv) > 1 else None))
    if len(neu['tabelle']) < 2 or not any(r['team'] == TEAM for r in neu['tabelle']) or len(neu['spiele']) < 2:
        sys.exit(f"Abbruch: unplausible Daten (Tabelle {len(neu['tabelle'])} Zeilen, {len(neu['spiele'])} Spiele). Alte Datei bleibt.")
    OUT.write_text(json.dumps(neu, ensure_ascii=False, indent=1))
    gesp = sum(s['th'] is not None for s in neu['spiele'])
    print(f"OK: {len(neu['tabelle'])} Mannschaften, {len(neu['spiele'])} Spiele ({gesp} gespielt), Stand Quelle: {neu['stand_quelle']}")


if __name__ == '__main__':
    main()
