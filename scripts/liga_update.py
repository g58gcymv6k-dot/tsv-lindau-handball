#!/usr/bin/env python3
"""Holt Tabelle und Spielplan von handball4all und schreibt site/data/liga.json.
Läuft automatisch per GitHub Actions (sonntags 23:00 Uhr). Bei Fehlern wird die
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


def _tok(name):
    n = str(name).lower()
    for z in './-':
        n = n.replace(z, ' ')
    return [t for t in n.split() if t]


def _passt(k, l):
    """Kurz-Token k passt zu Lang-Token l: Präfix ("handb"/"handball") oder Abkürzung mit
    gleichem Anfangsbuchstaben und Buchstaben in Reihenfolge ("fn"/"friedrichshafen")."""
    if l.startswith(k):
        return True
    if k.isdigit() or l.isdigit() or k[0] != l[0]:
        return False
    it = iter(l)
    return all(ch in it for ch in k)


def _kurzform(kurz, lang):
    k, l = _tok(kurz), _tok(lang)
    if not k or not l or (l[-1].isdigit() and len(l[-1]) == 1 and k[-1] != l[-1]):
        return False  # Mannschaftsnummer (z. B. "2") muss übereinstimmen
    i = 0
    for t in l:  # Lang-Tokens dürfen übersprungen werden ("1847", "Handball")
        if i < len(k) and _passt(k[i], t):
            i += 1
    return i == len(k)


def zuordnen(name, tabellen_namen):
    """Spielplan nutzt Kurzformen ("HSG FN-Fisch" statt "HSG Friedrichshafen-Fischbach").
    Ordnet einen Namen eindeutig einem Tabellennamen zu; sonst bleibt der Originalname
    (die Gegenprobe pruefen_alle meldet das dann)."""
    if name in tabellen_namen:
        return name
    treffer = [t for t in tabellen_namen if _kurzform(name, t)]
    return treffer[0] if len(treffer) == 1 else name


def umwandeln(raw):
    d = raw[0] if isinstance(raw, list) else raw
    head, c = d.get('head') or {}, d.get('content') or {}
    tabelle = [dict(pl=zahl(s.get('tabScore')), team=str(s.get('tabTeamname', '')).strip(),
                    sp=zahl(s.get('numPlayedGames')), s=zahl(s.get('numWonGames')), u=zahl(s.get('numEqualGames')),
                    n=zahl(s.get('numLostGames')), tf=zahl(s.get('numGoalsShot')), ta=zahl(s.get('numGoalsGot')),
                    pp=zahl(s.get('pointsPlus')), pm=zahl(s.get('pointsMinus'))) for s in c.get('score') or []]
    namen = [r['team'] for r in tabelle]
    spiele, alle, gesehen = [], [], set()
    quellen = list(c.get('games') or []) + list((c.get('futureGames') or {}).get('games') or [])
    for g in quellen:
        h, gu = str(g.get('gHomeTeam', '')).strip(), str(g.get('gGuestTeam', '')).strip()
        if g.get('gID') in gesehen or not h or not gu:
            continue
        gesehen.add(g.get('gID'))
        datum = str(g.get('gDate', '')).strip()
        try:
            iso = datetime.datetime.strptime(datum, '%d.%m.%y').date().isoformat()
        except ValueError:
            iso = ''
        th, tg = zahl(g.get('gHomeGoals')), zahl(g.get('gGuestGoals'))
        gespielt = th is not None and tg is not None
        # Liga-weite Spiele (nur Ergebnisse/Termine, keine Personen)
        alle.append(dict(datum=datum, iso=iso, tag=str(g.get('gWDay', '')).strip(), zeit=str(g.get('gTime', '')).strip(),
                         heim=zuordnen(h, namen), gast=zuordnen(gu, namen),
                         th=th if gespielt else None, tg=tg if gespielt else None,
                         hzh=zahl(g.get('gHomeGoals_1')) if gespielt else None,
                         hzg=zahl(g.get('gGuestGoals_1')) if gespielt else None,
                         ort=str(g.get('gGymnasiumTown', '')).strip(),
                         kommentar=str(g.get('gComment', '') or '').strip()))
        if TEAM not in (h, gu):
            continue
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
    alle.sort(key=lambda s: (s['iso'], s['zeit'], s['heim']))
    return dict(liga=str(head.get('name', '')).strip(), staffel=str(head.get('headline2', '') or head.get('headline1', '')).strip(),
                stand_quelle=str(head.get('actualized', '')).strip(),
                abgerufen=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'),
                tabelle=tabelle, spiele=spiele, alle=alle)


def pruefen_alle(d):
    """Gegenprobe: Spiele/Tore je Mannschaft aus 'alle' müssen zur Tabelle passen. Gibt Warnungen zurück."""
    w = []
    namen = {r['team'] for r in d['tabelle']}
    fremd = sorted({n for s in d['alle'] for n in (s['heim'], s['gast'])} - namen)
    if fremd:
        w.append('Nicht zugeordnete Namen: ' + ', '.join(fremd))
    for r in d['tabelle']:
        gs = [s for s in d['alle'] if s['th'] is not None and r['team'] in (s['heim'], s['gast'])]
        tf = sum(s['th'] if s['heim'] == r['team'] else s['tg'] for s in gs)
        ta = sum(s['tg'] if s['heim'] == r['team'] else s['th'] for s in gs)
        if (len(gs), tf, ta) != (r['sp'], r['tf'], r['ta']):
            w.append(f"{r['team']}: Spiele/Tore aus Spielplan {len(gs)} / {tf}:{ta}, Tabelle {r['sp']} / {r['tf']}:{r['ta']}")
    return w


def main():
    neu = umwandeln(laden(sys.argv[1] if len(sys.argv) > 1 else None))
    if len(neu['tabelle']) < 2 or not any(r['team'] == TEAM for r in neu['tabelle']) or len(neu['spiele']) < 2:
        sys.exit(f"Abbruch: unplausible Daten (Tabelle {len(neu['tabelle'])} Zeilen, {len(neu['spiele'])} Spiele). Alte Datei bleibt.")
    # Abweichungen (z. B. Wertungen am grünen Tisch) nur melden, die Seite weist selbst darauf hin
    neu['pruefung'] = pruefen_alle(neu)
    for x in neu['pruefung']:
        print('WARNUNG:', x)
    if OUT.exists():
        alt = json.loads(OUT.read_text())
        if {k: v for k, v in alt.items() if k != 'abgerufen'} == {k: v for k, v in neu.items() if k != 'abgerufen'}:
            print('OK: keine inhaltliche Änderung, Datei bleibt unverändert.')
            return
    OUT.write_text(json.dumps(neu, ensure_ascii=False, indent=1))
    gesp = sum(s['th'] is not None for s in neu['spiele'])
    print(f"OK: {len(neu['tabelle'])} Mannschaften, {len(neu['spiele'])} Spiele ({gesp} gespielt), Stand Quelle: {neu['stand_quelle']}")


if __name__ == '__main__':
    main()
