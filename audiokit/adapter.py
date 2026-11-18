"""Einfacher Einstieg für alle Pipelines (Goldsmith, Meisterwerk, Unterbau, Denkmuster, Nachtausgabe).

    import sys; sys.path.insert(0, os.environ.get("AUDIOKIT", "/home/claude/audiokit"))
    import adapter as AK
    ev = AK.clean_events(ev, "meisterwerk", SFX_DIR, order="t,name,gain")             # Sounds aufräumen
    bed = AK.music_bed("meisterwerk", N, SR, voice_mono, total, chapters, words, pools)  # Musik mit Spannungskurve
    AK.final_check(out_path, voice_wav, music_wav)                                    # Endkontrolle, Bericht in ak_report.txt

Alle Funktionen schreiben ihren Bericht in AK.LOG; write_report(pfad) legt ihn als Datei ab (für qa.md).
"""
import os
from sfx_rules import clean, report_text
from dramaturgie import Dramaturgie
from mix_check import check

LOG = []

def clean_events(events, channel, sfx_dir, order="t,name,gain", extra_dirs=()):
    ev, rep = clean(events, channel, sfx_dir, order, extra_dirs)
    LOG.append("SOUNDS  " + report_text(rep)); print(LOG[-1])
    return ev

def music_bed(channel, N, sr, voice_mono, total, chapters, words, pools, extra_beats=(), music_from=None, stimuli=None):
    d = Dramaturgie(channel, total, chapters, words, extra_beats, music_from=music_from)
    bed = d.music_bed(N, sr, voice_mono, pools)
    LOG.append("MUSIK   " + d.report(stimuli)); print(LOG[-1])
    return bed

def final_check(path, voice=None, music=None):
    ok, txt = check(path, voice, music)
    LOG.append("ENDKONTROLLE\n" + txt); print(LOG[-1])
    return ok

def write_report(path):
    open(path, "w").write("\n\n".join(LOG) + "\n"); return path
