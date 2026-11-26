#!/usr/bin/env python3
"""Wertet Spielberichte (handball4all 'Presseinformation - lang', PDF) aus
und schreibt site/data/spieler.json neu.

Aufruf:  python3 scripts/bericht_auswerten.py ordner_mit_pdfs [weitere.pdf ...]
Bereits vorhandene Spiele in spieler.json bleiben erhalten; ein Bericht mit
gleicher Spielnummer ersetzt den alten Eintrag.
Benötigt: pdftotext (poppler-utils).

Prüfungen (Abbruch bei Fehler):
  - Summe der Tore aus dem Spielverlauf == Endstand (beide Mannschaften)
  - Tore je Spieler aus dem Spielverlauf == Spalte 'Tore' der Mannschaftsliste
  - 'N.N.' wird über data/trikotliste.json zugeordnet; steht der zugeordnete
    Spieler im selben Spiel schon namentlich im Bericht -> Konflikt, Abbruch.
"""
import json, re, subprocess, sys, pathlib

TEAM = 'TSV Lindau'
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'site/data/spieler.json'
LISTE = json.loads((ROOT / 'site/data/trikotliste.json').read_text())['nummern']
EV = re.compile(r'^\s+\d\d:\d\d:\d\d\s+(\d\d):(\d\d)\s+(?:(\d+):(\d+)\s+)?(.*)$')
ACT = re.compile(r'(Tor|7m-Tor|7m, KEIN Tor|2-min Strafe|Verwarnung|Disqualifikation\S*|Rote Karte|Blaue Karte)\s+'
                 r'(?:durch|für)\s+(?:(.+?) \((\d+), (.+?)\)|Spieler (\d+), (.+))$')


def text(pdf):
    return subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True, check=True).stdout


def kader(t):
    m = re.search(r'(Heim|Gast): ' + TEAM + r'\n(.*?)(?:\n(?:Heim|Gast): |Handball4all AG)', t, re.S)
    out = []
    for line in m.group(2).splitlines():
        r = re.match(r'^\s*(\d+)\s{2,}(\S.*?)(?:\s{2,}(.*)|$)', line)
        if r:
            rest = (r.group(3) or '').split()
            out.append((int(r.group(1)), r.group(2).strip(), int(rest[0]) if rest and rest[0].isdigit() else 0))
    return out


def auswerten(pdf):
    t = text(pdf)
    no = re.search(r'Spiel/Datum (\d+) , am (\S+) um (\S+)h', t)
    hg = re.search(r'Heim - Gast (.+?) - (.+)', t)
    end = re.search(r'Endstand (\d+):(\d+) \((\d+):(\d+)\).*?Zuschauer:\s+(\S+)', t)
    if not (no and hg and end):
        raise SystemExit(f'{pdf}: Kopfdaten nicht gefunden – ist das ein Bericht "Presseinformation - lang"?')
    heim = hg.group(1).strip() == TEAM
    gegner = (hg.group(2) if heim else hg.group(1)).strip()
    f, a = (int(end.group(1)), int(end.group(2))) if heim else (int(end.group(2)), int(end.group(1)))
    k = kader(t)
    namen = {nm for _, nm, _ in k}
    spieler, zuordnung = {}, []
    for nr, nm, tore_liste in k:
        if nm.startswith('N.N.'):
            ziel = LISTE.get(str(nr))
            if not ziel:
                raise SystemExit(f'{pdf}: N.N. mit Nr. {nr} – Nummer nicht in der Trikotliste. Bitte nachfragen.')
            if ziel in namen:
                raise SystemExit(f'{pdf}: N.N. Nr. {nr} -> {ziel}, aber {ziel} steht im selben Spiel schon namentlich. Bitte nachfragen.')
            zuordnung.append(f'Nr. {nr} -> {ziel}')
            nm = ziel
        spieler[nr] = dict(name=nm, nr=nr, t=0, s7=0, v7=0, ver=0, z=0, disq=0, _liste=tore_liste)
    seg_f, seg_a = [0] * 6, [0] * 6
    team = dict(s7=0, v7=0, z=0, ver=0, os7=0, ov7=0, oz=0)
    unbekannt = []
    for line in t.splitlines():
        e = EV.match(line)
        if not e:
            continue
        txt = e.group(5).strip()
        p = ACT.match(txt)
        if not p:
            if not txt.startswith('Auszeit') and 'Offizielle' not in txt:
                unbekannt.append(txt)
            continue
        typ = p.group(1)
        nr = int(p.group(3) or p.group(5))
        mannschaft = (p.group(4) or p.group(6)).strip()
        minute = int(e.group(1))
        ours = mannschaft == TEAM
        tor = typ in ('Tor', '7m-Tor')
        if tor:
            (seg_f if ours else seg_a)[min(minute // 10, 5)] += 1
        if not ours:
            if typ == '7m-Tor': team['os7'] += 1; team['ov7'] += 1
            if typ == '7m, KEIN Tor': team['ov7'] += 1
            if typ == '2-min Strafe': team['oz'] += 1
            continue
        if nr not in spieler:
            unbekannt.append(txt + ' (Nummer nicht in Mannschaftsliste)')
            continue
        s = spieler[nr]
        if tor: s['t'] += 1
        if typ == '7m-Tor': s['s7'] += 1; s['v7'] += 1; team['s7'] += 1; team['v7'] += 1
        if typ == '7m, KEIN Tor': s['v7'] += 1; team['v7'] += 1
        if typ == 'Verwarnung': s['ver'] += 1; team['ver'] += 1
        if typ == '2-min Strafe': s['z'] += 1; team['z'] += 1
        if typ.startswith('Disqualifikation') or typ in ('Rote Karte', 'Blaue Karte'): s['disq'] += 1
    # Prüfungen
    if sum(seg_f) != f or sum(seg_a) != a:
        raise SystemExit(f'{pdf}: Tore im Spielverlauf ({sum(seg_f)}:{sum(seg_a)}) passen nicht zum Endstand ({f}:{a}).')
    for s in spieler.values():
        if s['t'] != s['_liste']:
            raise SystemExit(f"{pdf}: {s['name']} – Spielverlauf {s['t']} Tore, Mannschaftsliste {s['_liste']}.")
        del s['_liste']
    d = no.group(2)
    return dict(nr=no.group(1), datum=d, iso='20' + d[6:8] + '-' + d[3:5] + '-' + d[0:2], gegner=gegner, heim=heim,
                f=f, a=a, zuschauer=end.group(5), seg_f=seg_f, seg_a=seg_a, team=team, nn=len(zuordnung),
                spieler=sorted(spieler.values(), key=lambda s: s['nr'])), zuordnung, unbekannt


def main(args):
    pdfs = []
    for a in args:
        p = pathlib.Path(a)
        pdfs += sorted(p.glob('*.pdf')) if p.is_dir() else [p]
    data = json.loads(OUT.read_text()) if OUT.exists() else {'spiele': []}
    alt = {g['nr']: g for g in data['spiele']}
    for pdf in pdfs:
        g, zu, unb = auswerten(pdf)
        alt[g['nr']] = g
        print(f"OK {g['datum']} {'vs.' if g['heim'] else 'bei'} {g['gegner']} {g['f']}:{g['a']}"
              + (f" | N.N.: {', '.join(zu)}" if zu else '') + (f" | NICHT ERKANNT: {unb}" if unb else ''))
    data['spiele'] = sorted(alt.values(), key=lambda g: g['iso'])
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f'{len(data["spiele"])} Spiele in {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main(sys.argv[1:] or sys.exit(__doc__))
