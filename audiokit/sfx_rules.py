"""Räumt eine Liste von Sound-Ereignissen automatisch auf, bevor gemischt wird.

    from sfx_rules import clean
    events, report = clean(events, "meisterwerk", sfx_dir, order="t,name,gain")

order beschreibt das Tupel-Format des Kanals: Meisterwerk/Goldsmith (t, name, gain) -> "t,name,gain",
Denkmuster (datei, t, v) -> "name,t,gain". Dateiname mit oder ohne Endung.

Was passiert (in dieser Reihenfolge):
 1. verbotene Sounds raus (profiles.json "banned", Teilwort im Namen)
 2. Sounds, die audit.py als fehlerhaft erkennt (übersteuert, reines Rauschen, Vorschau-MP3), raus
 3. Lautheit angleichen: jeder Sound wird auf ref_lufs gebracht, danach gilt der Gain aus dem Skript
    (so klingt Gain 0.4 bei jedem Sound gleich laut – vorher schwankten die Dateien um bis zu 20 dB)
 4. Wiederholung: derselbe UI-/Akzent-Sound frühestens nach min_repeat_s wieder, höchstens N-mal pro Minute
    (Geräusche zu sichtbarer Bewegung – Hammer, Schritte, Auto – bleiben synchron und werden nicht ausgedünnt)
 5. Stapeln: höchstens max_stack Sounds gleichzeitig (lauteste bleiben) – kein boom+stamp+sub_drop+thud-Brei
 6. Dichte: höchstens max_per_10s / max_per_min Ereignisse (Tastatur-Tippen key0–7 zählt als eines)
 7. Schleifen: dasselbe Geräusch direkt hintereinander höchstens max_loop_s lang (keine Minuten-Teppiche)
"""
import json, os
from audit import audit, load, loudness

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = json.load(open(os.path.join(HERE, "profiles.json")))
EXT = (".wav", ".mp3", ".flac", ".ogg")
_lcache = {}

def _resolve(sfx_dir, name):
    if name.lower().endswith(EXT): p = os.path.join(sfx_dir, name); return p if os.path.exists(p) else None
    for e in EXT:
        p = os.path.join(sfx_dir, name + e)
        if os.path.exists(p): return p
    return None

def _dur(p):
    return audit(p)["dauer"]

UI = ("click", "klick", "pop", "whoosh", "swoosh", "schwenk", "shutter", "tick", "ding", "glitch", "flip", "zip", "slap", "camera", "pin", "flash", "funkeln")
IMPACT = ("boom", "braam", "drop", "riser", "hit", "impact", "reveal", "stamp", "logo", "klang", "slam")

def kind(name):
    """ui = Einblendungs-/Schnitt-Sounds, impact = Akzente, foley = Geräusch zu sichtbarer Bewegung (bleibt synchron, wird nicht ausgedünnt)."""
    b = os.path.splitext(os.path.basename(str(name)))[0].lower()
    if any(k in b for k in IMPACT): return "impact"
    if any(k in b for k in UI): return "ui"
    return "foley"

def _is_typing(name):
    b = os.path.splitext(os.path.basename(name))[0]
    return b.startswith("key") and b[3:].isdigit()

def clean(events, channel, sfx_dir, order="t,name,gain", extra_dirs=()):
    prof = PROFILES[channel]["sfx"]; keys = order.split(",")
    it, iname, ig = keys.index("t"), keys.index("name"), keys.index("gain")
    rep = {"in": len(events), "verboten": 0, "defekt": 0, "fehlt": 0, "wiederholung": 0, "gestapelt": 0, "dichte": 0, "schleife": 0, "defekte_dateien": set()}
    ev = []
    for e in events:
        e = list(e); name = str(e[iname]); low = name.lower()
        if any(b in low for b in prof.get("banned", [])): rep["verboten"] += 1; continue
        p = _resolve(sfx_dir, name) or next((q for d in extra_dirs for q in [_resolve(d, name)] if q), None)
        if p is None:
            if not _is_typing(name): rep["fehlt"] += 1
            ev.append((e, None)); continue
        a = audit(p, "amb" if low.startswith(("amb", "ambience")) else "")
        if a["fehler"] and not _is_typing(name): rep["defekt"] += 1; rep["defekte_dateien"].add(f"{os.path.basename(p)}: {'; '.join(a['fehler'])}"); continue
        if prof.get("normalize") and not _is_typing(name):
            corr = 10 ** (max(-12, min(12, prof.get("ref_lufs", -20) - a["lautheit"])) / 20)
            e[ig] = float(e[ig]) * corr
        ev.append((e, p))
    ev.sort(key=lambda x: float(x[0][it]))
    base = lambda e: os.path.splitext(os.path.basename(str(e[iname])))[0]

    # 7. Schleifen kürzen: gleiche Sounds, die lückenlos aneinanderhängen
    out, run_start, last = [], {}, {}
    for e, p in ev:
        b = base(e); t = float(e[it]); d = _dur(p) if p else 0.5
        if b in last and t - last[b] <= d * 1.2 + 0.3:
            if t - run_start[b] > prof.get("max_loop_s", 8): rep["schleife"] += 1; last[b] = t; continue
        else: run_start[b] = t
        last[b] = t; out.append((e, p))
    ev = out

    # 4. Wiederholungen
    out, seen = [], {}
    ro, pmo = prof.get("repeat_overrides", {}), prof.get("per_min_overrides", {})
    def _ov(d, b, default):
        for k in (b, b + ".wav", b + ".mp3"):
            if k in d: return d[k]
        return default
    for e, p in ev:
        b = base(e); t = float(e[it])
        if _is_typing(b): out.append((e, p)); continue
        mr = _ov(ro, b, prof.get("min_repeat_s", 1.5) if kind(b) != "foley" else 0); hist = seen.setdefault(b, [])
        looped = any(abs(t - h) < 1e-6 for h in hist[-1:])
        if hist and mr and t - hist[-1] < mr and not looped: rep["wiederholung"] += 1; continue
        pm = _ov(pmo, b, None)
        if pm is not None and sum(1 for h in hist if t - h < 60) >= pm: rep["wiederholung"] += 1; continue
        hist.append(t); out.append((e, p))
    ev = out

    # 5. Stapeln
    out, i = [], 0
    while i < len(ev):
        j = i
        while j + 1 < len(ev) and float(ev[j + 1][0][it]) - float(ev[i][0][it]) < 0.12: j += 1
        grp = ev[i:j + 1]
        if len(grp) > prof.get("max_stack", 2):
            keep = sorted(grp, key=lambda x: -float(x[0][ig]))[: prof["max_stack"]]
            rep["gestapelt"] += len(grp) - len(keep); grp = sorted(keep, key=lambda x: float(x[0][it]))
        out += grp; i = j + 1
    ev = out

    # 6. Dichte (Tippen zählt als ein Ereignis pro 1,5 s)
    out, times = [], []
    for e, p in ev:
        t = float(e[it]); b = base(e)
        if kind(b) == "foley" and not _is_typing(b): out.append((e, p)); continue   # Bewegungsgeräusche bleiben synchron
        if _is_typing(b):
            if times and t - times[-1] < 1.5 and getattr(clean, "_lt", None) == "key": out.append((e, p)); continue
            clean._lt = "key"
        else: clean._lt = "x"
        n10 = sum(1 for x in times if t - x < 10); n60 = sum(1 for x in times if t - x < 60)
        if n10 >= prof.get("max_per_10s", 3) or n60 >= prof.get("max_per_min", 12):
            # zu dicht: leise Ereignisse fallen weg, laute (Gain hoch) bleiben
            if float(e[ig]) < 0.5 * max([float(o[0][ig]) for o in out[-6:]] or [1]): rep["dichte"] += 1; continue
        times.append(t); out.append((e, p))
    rep["out"] = len(out); rep["defekte_dateien"] = sorted(rep["defekte_dateien"])
    dur_total = max([float(e[it]) for e, _ in out] or [1]) / 60
    rep["pro_minute"] = round(len([1 for e, _ in out if not _is_typing(base(e))]) / max(dur_total, 0.1), 1)
    return [tuple(e) for e, _ in out], rep

def report_text(rep):
    s = (f"Sounds: {rep['in']} geplant -> {rep['out']} behalten (~{rep['pro_minute']}/Min.). Entfernt: verboten {rep['verboten']}, defekt {rep['defekt']}, "
         f"Wiederholung {rep['wiederholung']}, gestapelt {rep['gestapelt']}, zu dicht {rep['dichte']}, Schleife {rep['schleife']}, Datei fehlt {rep['fehlt']}.")
    if rep["defekte_dateien"]: s += "\n  Defekte Dateien (ersetzen!): " + " | ".join(rep["defekte_dateien"])
    return s
