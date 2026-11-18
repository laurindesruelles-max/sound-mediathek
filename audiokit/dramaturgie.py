"""Musik-Dramaturgie: aus Skript (Wortzeiten) und Kapiteln automatisch eine Spannungskurve bauen und die Musik danach mischen.

    from dramaturgie import Dramaturgie
    d = Dramaturgie("denkmuster", total=718.0, chapters=[(0.0, None), (42.1, "Kapitel 1"), ...],
                    words=[(t, "Wort"), ...], extra_beats=[(t, "enthuellung", 3)])
    bed = d.music_bed(N, SR, voice_mono, pools)   # pools[i] = Liste von Musikdateien für Kapitel i (erste = Haupttrack)
    print(d.report())                              # Spannungskurve, Musikwechsel, Lücken ohne neuen Reiz

Was die Musik dadurch macht (statt einen Track pro Kapitel gleichförmig durchlaufen zu lassen):
  * kein Abschnitt läuft länger als max_same_s gleich: danach Wechsel auf eine andere Stelle des Tracks bzw. den Zweittrack
  * vor jeder Enthüllung schwillt die Musik an (swell_db über swell_s), die passende Stelle im Track wird nach Energie gewählt
  * große Enthüllungen: kurze Stille (mode "rests") bzw. Anschwellen + Absacken ohne Stopp (mode "continuous", Nachtausgabe)
  * kurz vor Kapiteln leiser, dann neuer Track; unter der Stimme Ducking, in Sprechpausen voller
  * leise Stellen der Tracks werden angehoben, damit die Musik nie „verschwindet“
"""
import json, os, re
import numpy as np
from audit import load

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = json.load(open(os.path.join(HERE, "profiles.json")))

REVEAL = re.compile(r"^(aber|doch|jedoch|plötzlich|ploetzlich|wahrheit|geheim\w*|niemand|nie|niemals|tot|starb|getötet|ermordet|mord\w*|verhaftet|"
                    r"entdeckt\w*|herausgefunden|herausstellt|enthüllt\w*|ergebnis\w*|überraschend\w*|schock\w*|eigentlich|wirklich|betrug|"
                    r"verschwunden|verschwand|leiche|urteil|schuldig|lüge|gelogen|verraten|explodiert\w*|katastrophe|einsturz|stürzte|"
                    r"but|however|secret\w*|truth|never|nobody|dead|killed|murder\w*|arrested|discovered|revealed|actually|really|fraud|"
                    r"vanished|guilty|lie|lied|betrayed|exploded|collapsed)$", re.I)
BIG = re.compile(r"^(milliard\w*|million\w*|billion\w*|prozent|percent|tausend\w*|hundert\w*|%)$", re.I)
NUM = re.compile(r"\d")

def db(x): return 10 ** (x / 20)

class Dramaturgie:
    def __init__(self, channel, total, chapters, words, extra_beats=(), voice_start=0.0, music_from=None):
        self.ch, self.p = channel, PROFILES[channel]["music"]
        self.music_from = music_from   # z. B. Denkmuster: Hook erst ab 8 s mit Musik
        self.total = float(total)
        # Kapitel: (start, titel) oder (start, titel, musik_start) – musik_start > start = Musikpause während der Kapitelkarte
        self.chapters = [(float(c[0]), c[1]) for c in sorted(chapters, key=lambda c: c[0])]
        self.mstart = [float(c[2]) if len(c) > 2 and c[2] is not None else float(c[0]) for c in sorted(chapters, key=lambda c: c[0])]
        self.words = [(float(t) + voice_start, str(w)) for t, w in words]
        self.beats = self._detect() + [(float(t), k, int(s)) for t, k, s in extra_beats]
        self.beats = self._thin(sorted(self.beats))
        self.sections = []

    # ---------- Spannungskurve ----------
    def _detect(self):
        beats, sent, t0 = [], [], None
        for t, w in self.words:
            if t0 is None: t0 = t
            sent.append((t, w))
            if re.search(r"[.!?…:]$", w):
                beats += self._score(sent); sent, t0 = [], None
        if sent: beats += self._score(sent)
        for t, title in self.chapters:
            if title: beats.append((t, "kapitel", 2))
        return beats

    def _score(self, sent):
        s, key_t = 0, sent[0][0]
        for t, w in sent:
            c = re.sub(r"[^\w%äöüß]", "", w.lower())
            if REVEAL.match(c): s += 1; key_t = t
            if BIG.match(c): s += 2; key_t = t
            elif NUM.search(c) and len(re.sub(r"\D", "", c)) >= 3: s += 1; key_t = t
        last = sent[-1][1]
        if last.endswith("?"): return [(sent[-1][0] + 0.3, "frage", 2)]       # offene Frage = Spannung bis zur Antwort
        if last.endswith("!"): s += 1
        return [(key_t, "enthuellung", min(4, s))] if s >= 2 else []

    def _thin(self, beats):
        """max. eine große Enthüllung (>=3) pro 45 s, sonst wird alles gleich laut und nichts wirkt mehr."""
        out = []
        for b in sorted(beats, key=lambda x: -x[2]):
            if b[2] >= 3 and any(o[2] >= 3 and abs(o[0] - b[0]) < 45 for o in out): b = (b[0], b[1], 2)
            if any(abs(o[0] - b[0]) < 6 for o in out) and b[1] != "kapitel": continue
            out.append(b)
        return sorted(out)

    # ---------- Musik-Abschnitte ----------
    @staticmethod
    def _energy(x, sr):
        w = sr; n = len(x) // w
        return np.sqrt((x[: n * w].reshape(n, w, -1) ** 2).mean(axis=(1, 2))) if n else np.zeros(1)

    def _pick_offset(self, energy, want_high, used, length):
        n = len(energy); L = int(min(length, n - 1)) or 1
        if n <= L + 2: return 0
        win = np.convolve(energy, np.ones(L) / L, mode="valid")
        order = np.argsort(win)[::-1] if want_high else np.argsort(np.abs(win - np.median(win)))
        for o in order:
            if all(abs(o - u) > L * 0.6 for u in used): return int(o)
        return int(order[0])

    def plan(self, pools, sr=48000):
        """pools[i]: Musikdateien für Kapitel i. Liefert Abschnitte (start, ende, datei, offset_s)."""
        cache = {}
        starts = list(self.mstart) + [self.total]; ends = [c[0] for c in self.chapters[1:]] + [self.total]
        if not self.p.get("intro_music", True) and len(self.chapters) > 1: starts[0] = None
        elif self.music_from is not None: starts[0] = max(starts[0], float(self.music_from))
        sec = []
        for i, (cs, title) in enumerate(self.chapters):
            if starts[i] is None: continue
            cs = starts[i]; ce = ends[i] if ends[i] < starts[i + 1] - 0.3 else starts[i + 1]; pool = pools[i] if i < len(pools) else pools[-1]
            pool = [pool] if isinstance(pool, str) else list(pool)
            # Schnittpunkte: direkt nach starken Beats, spätestens alle max_same_s
            cuts = [cs]
            for b in self.beats:
                if cs + 20 < b[0] < ce - 15 and b[2] >= 2 and b[0] + 1.2 - cuts[-1] > 25: cuts.append(b[0] + 1.2)
            out = [cuts[0]]
            for c in cuts[1:] + [ce]:
                while c - out[-1] > self.p["max_same_s"]: out.append(out[-1] + self.p["max_same_s"] * 0.85)
                if c < ce: out.append(c)
            out.append(ce)
            used = {}
            for k in range(len(out) - 1):
                a, e = out[k], out[k + 1]
                tr = pool[k % len(pool)] if len(pool) > 1 and k % 2 == 1 else pool[0]
                if tr not in cache: cache[tr] = self._energy(load(tr, sr, mono=False), sr)
                nxt = [b for b in self.beats if a < b[0] <= e + 1 and b[2] >= 2]
                off = self._pick_offset(cache[tr], bool(nxt), used.setdefault(tr, []), e - a)
                used[tr].append(off); sec.append((a, e, tr, float(off)))
        self.sections = sec
        return sec

    # ---------- Mischen ----------
    def music_bed(self, N, sr, voice_mono, pools, xf=2.0, envelope=True, calibrate=True):
        """envelope/calibrate=False: nur die wechselnden Abschnitte (für Kanäle mit eigener, abgenommener Lautstärke-Kurve)."""
        if not self.sections: self.plan(pools, sr)
        bed = np.zeros((N, 2), np.float32); cache = {}; X = int(xf * sr)
        for a, e, tr, off in self.sections:
            if tr not in cache:
                x = load(tr, sr, mono=False)
                # leise Stellen anheben (sanfte Kompression auf 1-s-Fenstern)
                w = sr // 2; n = len(x) // w; r = np.sqrt((x[: n * w].reshape(n, w, 2) ** 2).mean(axis=(1, 2))) + 1e-6
                tgt = np.median(r); g = np.clip((tgt / r) ** 0.5, 0.7, 2.2); g = np.convolve(g, np.ones(5) / 5, "same")
                gg = np.interp(np.arange(len(x)), np.arange(n) * w + w / 2, g).astype(np.float32)
                x = x * gg[:, None]; cache[tr] = x / (np.sqrt((x ** 2).mean()) + 1e-9) * 0.1
            x = cache[tr]; i0 = int(a * sr)
            follows = any(abs(a2 - e) < 0.3 for a2, *_ in self.sections)
            i1 = min(N, int(e * sr) + (X if follows else 0)); L = i1 - i0
            o = int(off * sr) % max(1, len(x) - 1)
            seg = np.concatenate([x[o:]] + [x] * (2 + L // max(1, len(x))))[:L].copy()
            r = min(X, L); seg[:r] *= np.linspace(0, 1, r)[:, None] ** 0.7
            if i1 < N: seg[-r:] *= np.linspace(1, 0, r)[:, None] ** 0.7
            bed[i0:i0 + L] += seg
        if envelope: bed *= self.envelope(N, sr, voice_mono)[:, None]
        if not calibrate: return bed
        # Pegel automatisch einstellen: während gesprochen wird liegt die Musik under_voice_db unter der Stimme
        if voice_mono is not None and len(voice_mono):
            w = sr // 2; n = min(len(voice_mono), N) // w
            dv = 20 * np.log10(np.sqrt((voice_mono[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)
            dm = 20 * np.log10(np.sqrt((bed[: n * w].reshape(n, w, 2) ** 2).mean(axis=(1, 2))) + 1e-9)
            sp = (dv > dv.max() - 30) & (dm > -80)
            if sp.any(): bed *= db(float(np.median(dv[sp] - dm[sp])) - self.p.get("under_voice_db", 16))
        return bed

    def envelope(self, N, sr, voice_mono):
        p = self.p; t = np.arange(N) / sr; g = np.ones(N, np.float32)
        # Ducking unter der Stimme (Attack 0,15 s, Release 0,6 s)
        if voice_mono is not None and len(voice_mono):
            v = np.abs(voice_mono[:N]); v = np.pad(v, (0, N - len(v)))
            hop = sr // 100; n = N // hop; vr = np.sqrt((v[: n * hop].reshape(n, hop) ** 2).mean(1))
            act = np.clip(vr / (np.percentile(vr[vr > 1e-5], 60) + 1e-9) if (vr > 1e-5).any() else vr, 0, 1)
            sm = np.zeros_like(act); a_, r_ = 1 - np.exp(-1 / 15), 1 - np.exp(-1 / 60)
            for i in range(1, n): sm[i] = sm[i - 1] + (a_ if act[i] > sm[i - 1] else r_) * (act[i] - sm[i - 1])
            duck = 1 - (1 - db(p["duck_db"])) * sm
            g *= np.interp(t, np.arange(n) * hop / sr, duck).astype(np.float32)
        # Anschwellen vor Beats, Stille bzw. Absacken danach
        for bt, kind, s in self.beats:
            if s < 2: continue
            amt = p["swell_db"] * (0.8 if s == 2 else 1.0)
            m = (t > bt - p["swell_s"]) & (t <= bt); g[m] *= db(amt * ((t[m] - (bt - p["swell_s"])) / p["swell_s"]) ** 1.5)
            if p["mode"] == "rests" and s >= p["rest_min_strength"] and kind != "kapitel":
                r0, r1 = bt + 0.05, bt + 0.05 + p["rest_s"]
                m = (t > r0 - 0.15) & (t <= r0); g[m] *= np.clip((r0 - t[m]) / 0.15, 0, 1)
                m = (t > r0) & (t <= r1); g[m] *= 0
                m = (t > r1) & (t <= r1 + 0.5); g[m] *= ((t[m] - r1) / 0.5)
            else:
                m = (t > bt) & (t <= bt + 1.5); g[m] *= db(amt * (1 - (t[m] - bt) / 1.5) - 1.5 * np.sin(np.pi * (t[m] - bt) / 1.5))
        # Bogen pro Kapitel: beginnt etwas zurückgenommen und steigt bis kurz vor Kapitelende an (Spannung baut sich auf)
        arc = p.get("chapter_arc_db", 4.0); bounds = [c[0] for c in self.chapters] + [self.total]
        for a, e in zip(bounds, bounds[1:]):
            if e - a < 20: continue
            m = (t >= a) & (t < e); g[m] *= db(-arc * 0.6 + arc * np.clip((t[m] - a) / (e - a - 3), 0, 1))
        # kurz vor Kapiteln leiser
        if p.get("pre_chapter_dip_db"):
            for cs, title in self.chapters:
                if not title or cs < 5: continue
                m = (t > cs - 2.5) & (t <= cs); g[m] *= db(p["pre_chapter_dip_db"] * (t[m] - (cs - 2.5)) / 2.5)
        # Ende ausblenden
        m = t > self.total - 2.5; g[m] *= np.clip((self.total - t[m]) / 2.5, 0, 1)
        return g

    # ---------- Bericht ----------
    def gaps(self, stimuli, max_gap=22.0):
        """stimuli: Zeitpunkte neuer Reize (Schnitt, Grafik, Text, Sound). Ergänzt Musikwechsel und Beats."""
        pts = sorted(set([0.0, self.total] + [float(s) for s in stimuli] + [s[0] for s in self.sections] + [b[0] for b in self.beats]))
        return [(a, b) for a, b in zip(pts, pts[1:]) if b - a > max_gap]

    def report(self, stimuli=None):
        mm = lambda x: f"{int(x // 60)}:{x % 60:04.1f}"
        L = [f"Spannungskurve {self.ch}: {len(self.beats)} Beats, {len(self.sections)} Musikabschnitte, "
             f"längster Abschnitt {max([e - a for a, e, _, _ in self.sections] or [0]):.0f} s"]
        for t, k, s in self.beats: L.append(f"  {mm(t)}  {k:12} {'█' * s}")
        L.append("Musik:")
        for a, e, tr, off in self.sections: L.append(f"  {mm(a)}–{mm(e)}  {os.path.basename(tr)} ab {off:.0f} s")
        if stimuli is not None:
            g = self.gaps(stimuli)
            L.append(f"Lücken ohne neuen Reiz > 22 s: {len(g)}" + "".join(f"\n  {mm(a)}–{mm(b)} ({b - a:.0f} s)" for a, b in g))
        return "\n".join(L)
