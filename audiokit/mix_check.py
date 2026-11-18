"""Endkontrolle des Tons vor jeder Freigabe.

    python3 mix_check.py video.mp4 [--voice voice.wav] [--music music.wav]
    from mix_check import check; ok, text = check("video.mp4", voice="voice.wav", music="music_bed.wav")

Prüft:
  * Gesamtlautheit −14 bis −16 LUFS, True Peak <= −1 dBTP
  * Musik unter Stimme: während gesprochen wird 12–24 dB unter der Stimme (zu laut = verdeckt, zu leise = langweilig)
  * Musik „lebt“: kein Abschnitt > 75 s ohne spürbare Pegeländerung (>= 3 dB) oder Wechsel
  * keine Stille-Löcher > 2,5 s (außer gewollte Pausen am Ende)
"""
import re, subprocess, sys
import numpy as np
from audit import load

SR = 48000

def ebur(p):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r); TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    return (float(I[-1]) if I else None), (float(TP[-1]) if TP else None)

def _rms_db(x, w):
    n = len(x) // w
    return 20 * np.log10(np.sqrt((x[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)

def check(path, voice=None, music=None):
    res, ok = [], True
    I, TP = ebur(path)
    good = I is not None and -16.5 <= I <= -13.5
    res.append(f"{'OK ' if good else 'FEHLER'} Lautheit {I} LUFS (Ziel −14…−16)"); ok &= good
    good = TP is not None and TP <= -0.9
    res.append(f"{'OK ' if good else 'FEHLER'} Spitze {TP} dBTP (Ziel ≤ −1)"); ok &= good
    mix = load(path); d = _rms_db(mix, SR // 2)
    holes = 0; run = 0
    for v in d[:-6]:
        run = run + 1 if v < -55 else 0
        if run == 6: holes += 1
    res.append(f"{'OK ' if holes == 0 else 'FEHLER'} Stille-Löcher > 2,5 s: {holes}"); ok &= holes == 0
    if voice and music:
        v = load(voice); m = load(music); n = min(len(v), len(m), len(mix))
        dv, dm = _rms_db(v[:n], SR // 2), _rms_db(m[:n], SR // 2)
        sp = dv > -40
        if sp.any():
            gap = float(np.median(dv[sp] - dm[sp]))
            good = 12 <= gap <= 24
            res.append(f"{'OK ' if good else 'WARN'} Musik unter Stimme: {gap:.1f} dB (Ziel 12–24)")
        # Musik lebt? gleitendes Fenster 75 s: Spannweite des geglätteten Pegels
        sm = np.convolve(dm, np.ones(8) / 8, "same"); W = 150; flat = []
        for i in range(0, max(1, len(sm) - W), 10):
            seg = sm[i:i + W]; seg = seg[seg > -60]
            if len(seg) > W * 0.8 and seg.max() - seg.min() < 3: flat.append(i / 2)
        good = not flat
        res.append(f"{'OK ' if good else 'WARN'} Musik ohne Bewegung > 75 s: " + (", ".join(f"ab {int(s // 60)}:{int(s % 60):02d}" for s in flat[:5]) or "keine"))
    return ok, "\n".join(res)

if __name__ == "__main__":
    a = sys.argv[1:]; v = a[a.index("--voice") + 1] if "--voice" in a else None; m = a[a.index("--music") + 1] if "--music" in a else None
    ok, txt = check(a[0], v, m); print(txt); sys.exit(0 if ok else 1)
