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

## bibliothek/ (Laurins Sammlung, eingepflegt 19.11.2026)

Aus Laurins drei Paketen (936 Dateien) wurden **574 Sounds** übernommen: geprüft, doppelte entfernt, Anfangsstille abgeschnitten, als FLAC 48 kHz gespeichert, nach Kategorie sortiert und **jedem Kanal eigene Effekte** zugeteilt (Laurin 17.11.2026). Goldsmith behält seine eigene sound-library.

| Ordner | Inhalt |
|---|---|
| `meisterwerk/` | Impacts (HITS), Kamera-Klicks, Whooshes (Cinematic Pack 2/3, Pack 4), Sub-Drops, Riser |
| `unterbau/` | Glitches + Digital-HUD (Daten-Grafiken), Riser, Sub-Drops Low+Hi, Whooshes, Impacts |
| `denkmuster/` | weiche Klicks/Buttons/Pops, Glocken/Funkeln (Aha-Momente), Swooshes/Swishes, Riser |
| `nachtausgabe/` | Spannung/Horror/Drones/Uhr-Ticken, alte Kamera (Blitz), Whooshes (Cinematic Pack 1, Pack 5), Sub-Drops |
| `gemeinsam/` | realistische Geräusche für alle: Foley, Atmos (Feuer, Wasser, U-Bahn, Zug), Waffen |
| `reserve/` | noch keinem Kanal zugeteilt (vor allem Übergänge) – nur nach Rückfrage vergeben |

`katalog.json` = alle Sounds mit Kanal, Kategorie, Dauer, Lautheit, Original-Datei, Lizenz. Je Ordner `LISTE.md`. `AUSSORTIERT.md` = was nicht übernommen wurde und warum:
- **Memes, Anime, Games, TV, Klingeltöne** (ganzes 230er-Paket + memes-Ordner) – urheberrechtlich geschützt, riskant für monetarisierte Videos
- **kommerzielle Libraries** (Epidemic Sound, Blastwave FX, SFX Bible …) – Lizenz nicht nachweisbar
- **technisch defekt** (übersteuert, Vorschau-MP3, zu niedrige Abtastrate) und **Doppelte**

Nutzung in Pipelines: `audiokit/bibliothek.py` (`ensure(kanal)`, `pick(kanal, kategorie, seed)`, `suche("auto")`). Lädt nur den eigenen Kanal-Ordner + gemeinsam.
