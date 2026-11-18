# Sound-Mediathek

Gemeinsames Ton-Werkzeug für Laurins fünf Kanäle (Goldsmith Productions, Meisterwerk, Unterbau, Denkmuster, Nachtausgabe).

**Wichtig:** Gemeinsam sind nur die *Regeln*. Sounds und Musik bleiben kanal-eigen (Laurin 17.11.2026) – sie liegen weiter im jeweiligen Kanal-Repo (`assets/sfx`, `assets/music`, Goldsmith: `sound-library`).

## audiokit/

Jede `setup.sh` lädt `audiokit/` nach `/home/claude/audiokit` (neu laden: `AK_UPDATE=1 sh setup.sh`). Die Pipelines nutzen es automatisch; fehlt es, laufen sie mit dem alten Ton-Weg weiter und warnen.

| Datei | Aufgabe |
|---|---|
| `profiles.json` | Regeln je Kanal: Sound-Dichte, Wiederholung, Verbote, Musik-Modus (`rests` = kurze Stille bei Enthüllungen, `continuous` = Nachtausgabe, nie Stopp) |
| `audit.py` | prüft Sound-Dateien: übersteuert, reines Rauschen, Vorschau-MP3, Anfangsstille. `python3 audit.py assets/sfx` |
| `sfx_rules.py` | räumt die Sound-Liste vor dem Mischen auf: Verbote, defekte Dateien, gleiche Lautheit, Kamera-Klick & Co. nicht im Dauerfeuer, kein Stapeln, keine Endlos-Schleifen. Geräusche zu sichtbarer Bewegung (Hammer, Schritte, Auto) bleiben synchron. |
| `dramaturgie.py` | Musik nach Spannungskurve: erkennt im Skript Enthüllungen, Zahlen, offene Fragen und Kapitel; Musik wechselt spätestens alle 60–80 s die Stelle/den Track, schwillt vor Enthüllungen an, Bogen pro Kapitel, Ducking unter der Stimme, Pegel automatisch 13–17 dB unter der Stimme |
| `mix_check.py` | Endkontrolle: −14…−16 LUFS, Spitze ≤ −1 dBTP, Musik-Abstand zur Stimme, Stille-Löcher |
| `adapter.py` | einfacher Einstieg für die Pipelines, schreibt `ton_bericht.txt` |

Der `ton_bericht.txt` jedes Videos gehört in die Prüfung vor der Freigabe (qa.md): Lücken > 22 s ohne neuen Reiz = Bild/Schnitt nacharbeiten.

## bibliothek/ (noch leer)

Platz für Laurins Sammlung mit ~1000 Effekten. Sobald sie hier liegt, können die Kanäle daraus automatisch passende Sounds ziehen (Ordner je Kategorie, z. B. `bibliothek/impacts/`, `bibliothek/ui/`, `bibliothek/foley/`). Hochladen: Ordner per GitHub-Weboberfläche in `bibliothek/` ziehen (max. 100 Dateien je Upload) oder als ZIP in einen Chat geben.
