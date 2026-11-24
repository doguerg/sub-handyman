# sub-handyman

**Replace guesswork with a measurement when subtitles are out of sync.**

`sub-handyman` compares a video with its external subtitle, reports how far the
timing is off, decides whether the drift is a constant delay or a frame-rate
mismatch, and rewrites the subtitle timings to match. No re-encoding, no GUI, no
third-party Python packages: one file, standard library only.

```console
$ sub_handyman movie.mkv
🔧 movie
    subtitle: movie.tr.srt (1245 cues)
    offset: -5.30s · match: 98.4% (at zero 84.4%) · F1 93.5%
    reference: embedded subtitle (stream 2)
    regions (start/mid/end): -5.30 / -5.30 / -5.30

$ sub_handyman movie.mkv --fix --yes
    applied, backup: movie.tr.srt.bak
```

Türkçe doküman: [README.tr.md](README.tr.md)

---

## Contents

1. [Why this exists](#why-this-exists)
2. [Requirements](#requirements)
3. [Install](#install)
4. [First run, step by step](#first-run-step-by-step)
5. [Reading the output](#reading-the-output)
6. [How it works](#how-it-works)
7. [Command reference](#command-reference)
8. [Recipes](#recipes)
9. [Performance](#performance)
10. [Limitations](#limitations)
11. [Troubleshooting](#troubleshooting)
12. [Tests](#tests)
13. [License](#license)

## Why this exists

Subtitles are usually translated against a *different release* of the same film.
Ten extra seconds of studio logo at the front, or a different frame rate, and
every line lands in the wrong place. Players can nudge the delay by hand, but
only for that one viewing: the file stays wrong, and the next device starts from
zero again.

Good tools already solve parts of this, so this one had to earn its place.
`ffsubsync` pulls in numpy and a dependency chain; `alass` is a compiled C++
binary. `sub-handyman` is a single readable file, and it answers a second
question most tools skip: *is a constant shift even the right model?*

When the answer is no, it says so instead of writing a plausible-looking wrong
fix.

## Requirements

| | |
| --- | --- |
| Python | 3.10 or newer (uses `X \| Y` type unions) |
| ffmpeg | `ffmpeg` **and** `ffprobe` on `PATH` |
| Disk | no extra space beyond a `.bak` copy of the subtitle |
| Network | none: it never calls an API or a subtitle site |

Check both before anything else:

```bash
python3 --version            # expect 3.10 or newer
ffmpeg -version  | head -1
ffprobe -version | head -1
```

Install ffmpeg:

```bash
sudo apt install ffmpeg      # Debian, Ubuntu, Raspberry Pi OS
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

No virtualenv is needed and there is nothing to `pip install`.

## Install

```bash
git clone https://github.com/Doguerg/sub-handyman.git
cd sub-handyman
chmod +x sub_handyman.py
python3 sub_handyman.py --version
```

The last line should print `sub_handyman 1.1.0`. If it does, you are done.

Optionally put it on `PATH` so you can call `sub_handyman` from anywhere:

```bash
sudo ln -s "$PWD/sub_handyman.py" /usr/local/bin/sub_handyman
sub_handyman --version
```

On Windows, use `python sub_handyman.py` wherever this document shows
`sub_handyman`.

## First run, step by step

This is the entire workflow, in order. Nothing is written until step 5.

### 1. Put the video and the subtitle in one folder

```
Movies/
└── Some Movie/
    ├── Some Movie.mkv
    └── Some Movie.tr.srt      <- the subtitle you want to fix
```

The names do not have to match exactly. The tool matches on the *start* of the
filename, so `Some Movie.mkv` finds `Some Movie.tr.srt`. Keeping the subtitle
named after the video is still the sane default: it removes ambiguity when a
folder holds several language files.

### 2. Measure, do not fix yet

```bash
python3 sub_handyman.py "Movies/Some Movie/Some Movie.mkv"
```

This only reads. It picks a reference, scans for the offset, prints a report and
exits. Five seconds to half a minute, depending on which reference it found.

If you are unsure about anything, stop here. A measurement never modifies a
file.

### 3. Read the first character of the report

| Mark | Meaning | What to do |
| --- | --- | --- |
| `✅` | Aligned | Nothing. Leave the file alone. |
| `🔧` | A fix is available | Go to step 4. |
| `❔` | Not trustworthy | Stop. See [Troubleshooting](#troubleshooting) before touching the file. |
| `⚠️ name: …` | Measurement failed | Read the message. Usually a missing subtitle or an unreadable video. |

### 4. Confirm the number makes sense

The report lists three offsets, measured in the first, middle and last third of
the film:

```
    regions (start/mid/end): -5.30 / -5.30 / -5.30
```

All three agree means the drift is a constant delay, and one shift fixes it.
That is the common case.

If they differ by more than about a second, the tool adds a `⚠️` warning: the
file is not simply late, and a single shift will not cure it. Do not apply.

### 5. Apply it

```bash
python3 sub_handyman.py "Movies/Some Movie/Some Movie.mkv" --fix
```

With `--fix` the tool asks before touching anything:

```
    → shift by -5.30s? [y/N]
```

Answer `y`. It copies the subtitle to `.bak`, then rewrites the timings in
place. For scripts and batch runs, add `--yes` to skip the question:

```bash
python3 sub_handyman.py "Movies/Some Movie/Some Movie.mkv" --fix --yes
```

### 6. Verify in your player

Close and reopen the player. If the subtitle is served by a media server
(Jellyfin, Plex, Emby), also close and reopen the item: an open session can keep
the old subtitle text cached even though the file on disk is already correct.

If it still looks late, the file is fine and the player cached it. Force a
refresh. Do not run `--fix` a second time.

### 7. Undo, if you have to

Every run leaves the previous version beside the subtitle:

```bash
mv "Movies/Some Movie/Some Movie.tr.srt.bak" "Movies/Some Movie/Some Movie.tr.srt"
```

The video file is never modified, and nothing else on disk is touched.

## Reading the output

```
🔧 movie
    subtitle: movie.tr.srt (1245 cues)
    offset: -5.30s · match: 98.4% (at zero 84.4%) · F1 93.5%
    reference: embedded subtitle (stream 2)
    regions (start/mid/end): -5.30 / -5.30 / -5.30
```

| Line | Meaning |
| --- | --- |
| `offset` | Seconds to add to every cue. Negative means the subtitles arrive **late** and need to move earlier. |
| `match` | How much of the subtitle lands on dialogue, 0-100%. This is the number the decision uses. |
| `at zero` | The same score with no correction. Compare it with `match`: if the two are nearly equal, the file was already fine. |
| `F1` | The balanced score the scan maximises. Lower than `match` when a translated subtitle merges or splits lines, which is expected. |
| `reference` | What the measurement was based on. Embedded or sibling text is reliable; `audio` is a fallback. |
| `regions` | Offset measured in the first, middle and last third. Equal values mean a constant delay. |

### Thresholds, and why they sit where they do

| Condition | Verdict |
| --- | --- |
| `match` ≥ 90% and offset under 0.35 s | `✅` aligned |
| `match` ≥ 55% with a real offset | `🔧` fix available |
| `match` < 55% | `❔` do not trust |

**0.35 s** is the no-op threshold. Subtitle guidelines tolerate about four frames
(≈0.16 s) of error. Below a third of a second nobody notices, and rewriting a
file is more risk than gain.

**55%** is the floor for acting. Translated subtitles merge and split cues, so a
`match` in the 80-90% band is normal and 98% is excellent. Much below half means
the two files probably do not describe the same cut, and the tool refuses to
guess.

## How it works

### 1. Pick a reference

The reference is what the candidate subtitle is aligned *against*, tried in this
order:

| # | Reference | When it applies |
| --- | --- | --- |
| 1 | Embedded subtitle track in the video | Most muxed releases carry an English track |
| 2 | Sibling `*.en.srt` / `*.eng.srt` beside the video | `mp4` / web-dl files with no subtitle stream |
| 3 | Audio: speech intervals from `ffmpeg silencedetect` | No text reference at all — last resort |

The reference becomes a boolean timeline at 0.1 s resolution: "is anybody talking
here?" Each candidate cue is scored by how much of its duration lands on that
timeline.

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

So the scan maximises **F1**, the harmonic mean of precision and recall, which
punishes both sliding into a dense region and covering only half the dialogue.
The final *decision* uses **precision**, because translated subtitles
legitimately split and merge cues: two source lines can become one translated
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
- CP1254 (Turkish Windows) files are detected and written back as CP1254
- CRLF normalised to LF on write (every player accepts both)
- a `.bak` (or `--backup-dir`) is written **before** the file is touched
- cues clamped at `00:00:00` keep their duration rather than collapsing to zero

## Command reference

```
sub_handyman [VIDEO | --scan DIR] [options]
```

| Option | Meaning |
| --- | --- |
| `VIDEO` | Video file, or a folder (searched recursively) |
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

Given `Some Movie.mkv`, the tool looks for files in the same folder whose name
starts with `Some Movie` and ends in `.srt`, and prefers Turkish ones (`.tr.`,
`tr.srt`). For a reference it prefers English (`*.en.*`, `*.eng.*`). Use `--sub`
when a folder holds several languages and detection picks the wrong one.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Aligned (or measured clean), nothing to do |
| `1` | A fix was applied, or is needed but `--fix` was not given |
| `2` | Measurement failed (no subtitle, no reference, unreadable video) |

The difference between "all good" and "drift found" is usually what you want to
branch on:

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
  "video": "movie.mkv",
  "subtitle": "movie.tr.srt",
  "cues": 1245,
  "needs_fix": true,
  "aligned": false,
  "applied": true,
  "backup": "movie.tr.srt.bak"
}
```

| Field | Meaning |
| --- | --- |
| `shift` | Seconds added to every cue (negative = subtitles arrive late) |
| `match` | Precision; `f1` is the score the scan optimised |
| `match_at_zero` | Precision without touching the file |
| `scale` | Multiplier applied to cue times before `shift` (1.0 = none) |
| `regions` | Offset measured in the first/middle/last third |
| `region_spread` | Max minus min of `regions`; above ~1.5 s the constant model is doubtful |
| `needs_fix` | The match is good enough to act on, and a correction is pending |
| `aligned` | High match and nothing to correct |
| `applied` / `backup` | Present only when `--fix` actually rewrote the file |

`--scan` always returns an array, even when it finds a single video. A single
`VIDEO` argument returns one object.

## Recipes

### Check a whole library before touching anything

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
python3 sub_handyman.py movie.mp4 --audio
```

### Pick the subtitle by hand

When a folder holds several languages and auto-detection guesses wrong:

```bash
python3 sub_handyman.py movie.mkv --sub "movie.pt-BR.srt"
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
- Releases with variable frame rate and dropped frames can drift in a way
  neither a shift nor a scale describes; the region check flags it, and from
  there it is manual work.

## Troubleshooting

| Symptom | Cause | What to do |
| --- | --- | --- |
| `no .srt next to the video` | Subtitle is named differently, or lives in another folder | Rename it after the video, or pass `--sub` |
| `subtitle too short (n cues)` | Stub file, an ad, or a soundtrack listing | Wrong file: point `--sub` at the real subtitle |
| `❔` on every film | Reference is the audio track and the mix is music-heavy | Check for an embedded subtitle track, or fetch a text reference |
| Fix applied, still late in the player | Player or media server cached the old subtitle | Close and reopen the item; force a refresh |
| `⚠️ region offsets disagree` | Different cut, or variable frame rate | Do not apply. Find a subtitle for the exact release |
| `⚠️ frame-rate mismatch suspected` | 23.976 vs 24 vs 25 mismatch | `--fix` applies scale + shift; check the end of the film afterwards |
| `measurement failed: …` | Missing ffmpeg, unreadable video, no audio stream | Read the message; check `ffmpeg -version` |
| A script breaks on the JSON | `--scan` returns an array, a single file returns an object | Normalise before parsing, or always use `--scan` |

If you are unsure at any point, run without `--fix`. Measurement never modifies
anything.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

19 tests, no video and no ffmpeg required. They cover SRT parsing (BOM, CRLF,
garbage input, 2/3/4-digit fractions), timestamp formatting and clamping, offset
recovery at several magnitudes including fractional values, frame-rate scale
detection, region stability, silence-detection parsing, CP1254 round-trip, and
file discovery with awkward filenames.

## License

MIT — see [LICENSE](LICENSE).
