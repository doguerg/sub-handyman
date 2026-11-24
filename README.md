# sub-handyman

Fix subtitle timing with one command.

`sub-handyman` measures the offset between a video and its external subtitle,
tells you whether the drift is a constant delay or a frame-rate mismatch, and
rewrites the subtitle timings to match. No re-encoding, no GUI, no third-party
Python packages.

```console
$ sub_handyman "Jerry & Marge Go Large (2022).mkv"
🔧 Jerry & Marge Go Large (2022) WEBDL-2160p
    subtitle: Jerry & Marge Go Large (2022) WEBDL-2160p.tr.srt (1389 cues)
    offset: -5.30s · match: 98.4% (at zero 84.4%) · F1 93.5%
    reference: embedded subtitle (stream 2)
    regions (start/mid/end): -5.30 / -5.30 / -5.30

$ sub_handyman "Jerry & Marge Go Large (2022).mkv" --fix --yes
    applied, backup: /media/movies/Jerry & Marge Go Large (2022)/....tr.srt.bak
```

Türkçe doküman: [README.tr.md](README.tr.md)

---

## Why this exists

Subtitles are usually translated against a *different release* of the same film.
Ten extra seconds of studio logo at the front, or a different frame rate, and
every line lands in the wrong place. Players can nudge the delay by hand, but
only for that one viewing: the file stays wrong and the next device starts from
zero again.

Good tools already solve this, so this one had to earn its place. `ffsubsync`
pulls in numpy and a dependency chain; `alass` is a C++ binary. `sub-handyman`
is a single file, standard library only, and it answers a second question most
tools skip: *is a constant shift even the right model?*

## Requirements

- Python 3.10+ (uses `X | Y` type unions)
- `ffmpeg` and `ffprobe` on `PATH`

```bash
sudo apt install ffmpeg      # Debian / Ubuntu / Raspberry Pi OS
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

No virtualenv, no `pip install`.

## Install

```bash
git clone https://github.com/Doguerg/sub-handyman.git
cd sub-handyman
chmod +x sub_handyman.py

# optional: run it from anywhere
sudo ln -s "$PWD/sub_handyman.py" /usr/local/bin/sub_handyman
```

## Quick start

```bash
# 1. how far off is it?
python3 sub_handyman.py "Movies/Film (2022)/Film (2022).mkv"

# 2. fix it (writes a .bak next to the subtitle first)
python3 sub_handyman.py "Movies/Film (2022)/Film (2022).mkv" --fix

# 3. or sweep the whole library
python3 sub_handyman.py --scan ~/Videos/Movies
```

## How it works

### 1. Pick a reference

The reference is what the candidate subtitle is aligned *against*, tried in this
order:

| # | Reference | When it applies |
| --- | --- | --- |
| 1 | Embedded subtitle track in the video | Most muxed releases carry an English track |
| 2 | Sibling `*.en.srt` / `*.eng.srt` beside the video | `mp4` / web-dl files with no subtitle stream |
| 3 | Audio: speech intervals from `ffmpeg silencedetect` | No text reference at all — last resort |

The reference becomes a boolean timeline at 0.1 s resolution: "is anybody
talking here?" Each candidate cue is scored by how much of its duration lands on
that timeline.

### 2. Scan the offset

The candidate slides from -25 s to +25 s in 0.1 s steps, then gets refined to
0.02 s around the best value. During the coarse pass the reference mask is
dilated by 0.5 s, so cue boundaries that differ by a frame or two do not punish
an otherwise correct alignment.

### 3. Score with F1, decide with precision

Searching on precision alone is a trap, and it caught the first version of this
tool. When the reference is dense in one stretch of the film, sliding the
subtitle into that stretch raises precision even though nothing matches. In a
synthetic test the "best" offset came out as **+152 s**.

So the scan maximises **F1** — the harmonic mean of precision and recall — which
punishes both sliding into a dense region and covering only half the dialogue.
The final *decision* uses **precision**, because translated subtitles
legitimately split and merge cues: two English lines can become one Turkish
line, so recall can never reach 1.0 even with perfect timing.

Recall's denominator is computed from the undilated mask, otherwise a perfect
alignment would score well below 100%.

### 4. Constant delay, or frame-rate mismatch?

A frame-rate mismatch is not a shift. The error grows linearly: zero at the
start, tens of seconds by the end. Nudging cannot fix it.

The tool measures the offset separately in the first, middle and last third of
the film:

- all three agree → constant delay, apply it
- they diverge → try known ratios (24000/1001, 24, 25); if one scores clearly
  better, apply **scale + shift** together
- still unconvincing → say so instead of writing a wrong fix

### 5. Write it back

`--fix` rewrites the timings in place and preserves the original formatting:

- UTF-8 BOM kept if present
- CRLF normalised to LF on write (every player accepts both)
- a `.bak` (or `--backup-dir`) is written **before** the file is touched
- cues clamped at `00:00:00` keep their duration rather than collapsing to zero

## Command reference

```
sub_handyman [VIDEO | --scan DIR] [options]
```

| Option | Meaning |
| --- | --- |
| `VIDEO` | Video file, or a folder holding one movie |
| `--scan DIR` | Walk a directory recursively (`mkv`, `mp4`, `m4v`, `avi`, `mov`, `webm`, `ts`) |
| `--sub FILE` | Use this subtitle instead of auto-detection |
| `--fix` | Apply the measured correction |
| `--yes` | Skip the confirmation prompt (cron, scripts) |
| `--audio` | Skip text references, go straight to the audio track |
| `--json` | Machine-readable output (an array when `--scan` is used) |
| `--backup-dir DIR` | Write `.bak` files here instead of beside the subtitle |
| `--lang {en,tr}` | Output language (default: `SUB_HANDYMAN_LANG`, else `en`) |
| `--version` | Print version |

### Subtitle auto-detection

Given `Film (2022).mkv`, the tool looks for `Film (2022)*.srt` in the same
folder and prefers Turkish ones (`.tr.`, `tr.srt`). For a reference it prefers
English (`*.en.*`, `*.eng.*`). Use `--sub` when a folder holds several
languages and detection picks the wrong one.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Aligned, nothing to do |
| `1` | A fix was applied, or is needed but `--fix` was not given |
| `2` | Measurement failed (no subtitle, no reference, unreadable video) |

Handy in scripts, where the difference between "all good" and "drift found" is
what you actually want to branch on:

```bash
python3 sub_handyman.py --scan /media/movies --json > report.json || echo "drift found"
```

### JSON output

```json
{
  "shift": -5.3,
  "match": 0.984,
  "match_at_zero": 0.844,
  "f1": 0.935,
  "scale": 1.0,
  "regions": [-5.3, -5.3, -5.3],
  "region_spread": 0.05,
  "method": "embedded subtitle (stream 2)",
  "video": "Film (2022).mkv",
  "subtitle": "Film (2022).tr.srt",
  "cues": 1389,
  "needs_fix": false,
  "aligned": true
}
```

| Field | Meaning |
| --- | --- |
| `shift` | Seconds added to every cue (negative = subtitles arrive late) |
| `match` | Precision; `f1` is the score the scan optimised |
| `match_at_zero` | Precision without touching the file — the "is it already fine?" number |
| `scale` | Multiplier applied to cue times before `shift` (1.0 = none) |
| `regions` | Offset measured in the first/middle/last third |
| `region_spread` | Max minus min of `regions`; above ~1.5 s the constant model is doubtful |
| `needs_fix` | The match is good enough to act on, and a correction is pending |
| `aligned` | High match and nothing to correct |
| `applied` / `backup` | Present only when `--fix` actually rewrote the file |

## Reading the output

| Marker | Meaning |
| --- | --- |
| `✅` | Aligned — match ≥ 90% and offset under 0.35 s |
| `🔧` | Fix available — match ≥ 55% and something to correct |
| `❔` | Not trustworthy — weak match; do **not** apply, inspect the file |
| `⚠️` | Measured, but the model is doubtful (unstable regions, fps suspect) |

**Why 0.35 s?** Subtitle guidelines tolerate roughly four frames (≈0.16 s).
Below a third of a second nobody notices, and rewriting the file is more risk
than gain.

**Why 55%?** Translated subtitles merge and split cues, so precision in the
80-90% band is normal and 98% is excellent. Much below half means the two files
probably do not describe the same cut.

## Recipes

### Check a batch before touching anything

```bash
python3 sub_handyman.py --scan ~/Videos/Movies --json > report.json
python3 - <<'PY'
import json
for r in json.load(open("report.json")):
    if r.get("needs_fix"):
        print(f"{r['subtitle']}: {r['shift']:+.2f}s (match {r['match']:.0%})")
PY
```

### Fix everything that is confidently off

```bash
python3 sub_handyman.py --scan ~/Videos/Movies --fix --yes
```

Anything reported as `❔` is skipped even when `--fix` is given: a confident
wrong rewrite is worse than a known-bad subtitle.

### Hook into a download pipeline

```bash
for f in "$download_dir"/*.mkv "$download_dir"/*.mp4; do
  [ -e "$f" ] || continue
  python3 sub_handyman.py "$f" --fix --yes || true
done
```

Cheap to run: with an embedded reference it reads only the subtitle stream, so
the cost does not scale with file size.

### Force the audio path

For remuxes whose only text track is a commentary, or `mp4` files with a
hardcoded dubtitle:

```bash
python3 sub_handyman.py "Film.mp4" --audio
```

### Turkish output

```bash
export SUB_HANDYMAN_LANG=tr     # or: --lang tr
```

## Performance

Measured on a Raspberry Pi 5 (8 GB, NVMe) against a 15 GB 4K HEVC remux:

| Reference | Time | Note |
| --- | --- | --- |
| Embedded subtitle | ~20 s | ffmpeg extracts the subtitle stream only |
| Sibling `.srt` | ~5 s | pure Python, no decode |
| Audio (`--audio`) | 2-4 min | full audio pass through `silencedetect` |

The scan itself is not the bottleneck; decoding is.

## Limitations

- Fixes timing, not translation. A bad translation stays bad.
- Subtitles from a different cut (extended vs. theatrical, re-ordered scenes)
  score low; the tool reports `❔` and refuses to guess.
- The audio reference is noisy over music and effects. If a text reference
  exists it is always preferred, and `--audio` is opt-in.
- One subtitle per video per run. Batch mode picks the Turkish file, else the
  first `.srt`.
- `.ass`/`.ssa` can be *measured* via `--sub`, but only `.srt` timings are
  rewritten.
- Two-pass VFR releases with dropped frames can drift in a way neither a shift
  nor a scale describes; the region check flags it, and from there it is manual
  work.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

14 tests, no video and no ffmpeg required. They cover SRT parsing (BOM, CRLF,
garbage input), timestamp formatting and clamping, offset recovery at four
magnitudes, fps-scale detection, region stability, and file discovery.

## License

MIT — see [LICENSE](LICENSE).
