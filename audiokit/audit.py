"""Prüft Geräusch-Dateien auf echte Qualitätsfehler (nicht auf Geschmack).

  python3 audit.py <ordner oder dateien...>        -> Tabelle
  from audit import audit, verdict                  -> in Pipelines

Harte Fehler (Sound wird automatisch nicht benutzt):
  - übersteuert (viele Samples an 0 dBFS)
  - reines Rauschen (spektral flach wie Wind/Rauschen) – außer Kategorie "amb" und gestaltete Sounds (Riser, Whoosh, Hiss …)
  - Vorschau-MP3 (< 128 kbit/s) oder Abtastrate < 32 kHz
Warnungen (nur Hinweis): Anfangsstille (wird beim Mischen abgeschnitten), hoher Rauschboden.
"""
import json, os, subprocess, sys, functools
import numpy as np

SR = 48000

def load(p, sr=SR, mono=True):
    cmd = ["ffmpeg", "-v", "error", "-i", p] + (["-ac", "1"] if mono else ["-ac", "2"]) + ["-ar", str(sr), "-f", "f32le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)
    return x if mono else x.reshape(-1, 2)

def _probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", p],
                                  capture_output=True, text=True).stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    return s.get("codec_name"), int(s.get("sample_rate", 0) or 0), int(j.get("format", {}).get("bit_rate", 0) or 0) // 1000

def loudness(x, sr=SR):
    """Lautheit des lauten Teils (dB, ~LUFS für kurze Sounds, wo ebur128 versagt)."""
    f = 2048; n = len(x) // f * f
    if n == 0: return -70.0
    r = np.sqrt((x[:n].reshape(-1, f) ** 2).mean(1)) + 1e-9
    top = np.sort(r)[-max(1, len(r) // 4):]          # lautestes Viertel
    return float(20 * np.log10(np.sqrt((top ** 2).mean())) - 0.7)

@functools.lru_cache(maxsize=4096)
def audit(p, category=""):
    x = load(p); n = len(x)
    if n < SR * 0.03: return {"file": os.path.basename(p), "fehler": ["leer"], "warn": [], "dauer": 0, "lautheit": -70}
    codec, fsr, kbps = _probe(p)
    f = 1024; fr = x[: n // f * f].reshape(-1, f); db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    floor, top = float(np.percentile(db, 10)), float(np.percentile(db, 95))
    # echtes Übersteuern = abgeschnittene Spitzen (>= 3 Samples in Folge am Anschlag, in Original-Abtastrate)
    raw = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-f", "f32le", "-"], capture_output=True).stdout, np.float32)
    hot = np.abs(raw) > 0.995; runs = np.diff(np.concatenate([[0], hot.astype(np.int8), [0]]))
    st, en = np.where(runs == 1)[0], np.where(runs == -1)[0]; clip = int(np.sum((en - st) >= 3)); dur = n / SR
    S_ = np.abs(np.fft.rfft(fr * np.hanning(f), axis=1)) + 1e-9; loud = (20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)) > np.percentile(db, 95) - 12
    flat = float(np.mean(np.exp(np.log(S_[loud]).mean(1)) / S_[loud].mean(1))) if loud.any() else 0.0
    lead = float(np.argmax(db > top - 40) * f / SR)
    err, warn = [], []
    if clip > 20: err.append(f"übersteuert ({clip} abgeschnittene Spitzen)")
    elif clip > 3: warn.append(f"leicht übersteuert ({clip})")
    designed = any(k in os.path.basename(p).lower() for k in ("drop", "riser", "braam", "boom", "hit", "whoosh", "swoosh", "impact", "hiss", "reveal"))
    if dur > 1.5 and flat > 0.3 and not category.startswith("amb") and not designed: err.append(f"reines Rauschen (Flachheit {flat:.2f})")
    elif dur > 1.5 and top - floor < 12 and not category.startswith("amb") and not designed: warn.append(f"gleichförmig/Teppich (Dynamik {top - floor:.0f} dB) – nur kurz einsetzen")
    if codec == "mp3" and 0 < kbps < 128: err.append(f"Vorschau-MP3 {kbps} kbit/s")
    if 0 < fsr < 32000: err.append(f"Abtastrate {fsr} Hz")
    if floor > -45 and dur > 1.5 and not category.startswith("amb"): warn.append(f"Rauschboden {floor:.0f} dB")
    if lead > 0.08: warn.append(f"Anfangsstille {lead:.2f} s")
    return {"file": os.path.basename(p), "dauer": round(dur, 2), "lautheit": round(loudness(x), 1), "spitze": round(20 * np.log10(np.abs(x).max() + 1e-9), 1),
            "rauschboden": round(floor), "dynamik": round(top - floor), "anfangsstille": round(lead, 2), "fehler": err, "warn": warn}

def verdict(p, category=""):
    """True = Sound darf benutzt werden."""
    return not audit(p, category)["fehler"]

if __name__ == "__main__":
    files = []
    for a in sys.argv[1:]:
        files += [os.path.join(a, f) for f in sorted(os.listdir(a)) if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg"))] if os.path.isdir(a) else [a]
    bad = 0
    for p in files:
        r = audit(p, "amb" if os.path.basename(p).startswith(("amb", "ambience")) else "")
        bad += bool(r["fehler"])
        flag = "RAUS" if r["fehler"] else ("ok* " if r["warn"] else "ok  ")
        print(f"{flag} {r['file'][:40]:40} {r['dauer']:5}s {r['lautheit']:6} dB  {'; '.join(r['fehler'] + r['warn'])}")
    print(f"\n{len(files)} Sounds, {bad} durchgefallen")
