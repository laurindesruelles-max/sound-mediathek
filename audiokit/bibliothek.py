"""Zugriff auf Laurins Sound-Bibliothek (Repo sound-mediathek, Ordner bibliothek/).

Jeder Kanal hat EIGENE Effekte (bibliothek/<kanal>/…); realistische Geräusche (foley, amb, waffe) liegen in bibliothek/gemeinsam/.
Goldsmith behält seine sound-library im eigenen Repo. reserve/ = noch keinem Kanal zugeteilt (nur nach Rückfrage bei Laurin vergeben).

    import bibliothek as BIB
    d = BIB.ensure("meisterwerk")                    # lädt nur bibliothek/meisterwerk + gemeinsam (sparse), gibt Ordner zurück
    BIB.liste("meisterwerk", "whoosh")               # alle Whooshes dieses Kanals (Katalog-Einträge)
    p = BIB.pick("meisterwerk", "impact", seed="003-tunnel", i=0)   # stabil, wechselt von Video zu Video
    BIB.suche("auto")                                # gemeinsam/foley + amb nach Stichwort

Die Dateien sind FLAC 48 kHz, Anfangsstille entfernt, technisch geprüft (audit.py), Memes/geschützte/kommerzielle Sounds aussortiert.
"""
import os, json, subprocess, hashlib, shutil

REPO = "https://github.com/laurindesruelles-max/sound-mediathek"
DEST = os.environ.get("SFX_BIBLIOTHEK", "/home/claude/sfx-bibliothek")

def ensure(kanal):
    """Sparse-Checkout von bibliothek/<kanal>, bibliothek/gemeinsam und katalog.json."""
    want = {f"bibliothek/{kanal}", "bibliothek/gemeinsam"}
    if not os.path.exists(f"{DEST}/.git"):
        if os.path.exists(DEST): shutil.rmtree(DEST)
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", REPO, DEST], check=True)
        subprocess.run(["git", "-C", DEST, "sparse-checkout", "set", "--no-cone", "/bibliothek/katalog.json", *[f"/{w}/" for w in sorted(want)]], check=True)
    else:
        cur = subprocess.run(["git", "-C", DEST, "sparse-checkout", "list"], capture_output=True, text=True).stdout
        add = [f"/{w}/" for w in want if w not in cur]
        if add: subprocess.run(["git", "-C", DEST, "sparse-checkout", "add", *add], check=True)
    return f"{DEST}/bibliothek"

def _kat():
    return json.load(open(f"{DEST}/bibliothek/katalog.json"))["sounds"]

def liste(kanal, kategorie=None):
    return [s for s in _kat() if s["kanal"] in (kanal, "gemeinsam") and (kategorie is None or s["kategorie"] == kategorie)
            and os.path.exists(f"{DEST}/bibliothek/{s['pfad']}")]

def pick(kanal, kategorie, seed="", i=0):
    """Stabile Auswahl: gleiches Video -> gleicher Sound, neues Video -> andere Reihenfolge (Abwechslung zwischen Videos)."""
    items = sorted(liste(kanal, kategorie), key=lambda s: hashlib.md5((seed + s["pfad"]).encode()).hexdigest())
    if not items: raise LookupError(f"keine Sounds: {kanal}/{kategorie}")
    return f"{DEST}/bibliothek/{items[i % len(items)]['pfad']}"

def suche(wort, kanal="gemeinsam"):
    w = wort.lower()
    return [f"{DEST}/bibliothek/{s['pfad']}" for s in _kat() if s["kanal"] in (kanal, "gemeinsam") and (w in s["pfad"].lower() or w in s["original"].lower())]
