# sub-handyman

**Find out how far a subtitle is off, and fix it, without opening an editor.**

`sub-handyman` compares a video with the subtitle file next to it, tells you how
many seconds the subtitle is off, works out whether one simple shift is enough or
whether the subtitle was timed for a different frame rate, and rewrites the
timings if you want it to. No re-encoding, no window to click through, no Python
packages to install.

```console
$ sub_handyman movie.mkv
🔧 movie
    subtitle: movie.tr.srt (1245 lines)
    offset: -5.30s · overlap: 98.4% (unchanged: 84.4%)
    compared with: subtitle track inside the video (stream 2)
    checks (start/middle/end): -5.30 / -5.30 / -5.30

$ sub_handyman movie.mkv --fix --yes
    done, backup: movie.tr.srt.bak
```

Türkçe doküman: [README.tr.md](README.tr.md)

---

## Contents

1. [What it is for](#what-it-is-for)
2. [Before you start](#before-you-start)
3. [Install](#install)
4. [Your first fix, step by step](#your-first-fix-step-by-step)
5. [What the report says](#what-the-report-says)
6. [How it decides](#how-it-decides)
7. [All options](#all-options)
8. [Everyday uses](#everyday-uses)
9. [How long it takes](#how-long-it-takes)
10. [What it cannot do](#what-it-cannot-do)
11. [When something goes wrong](#when-something-goes-wrong)
12. [Tests](#tests)
13. [License](#license)

## What it is for

A subtitle is usually translated for a *different release* of the same film. One
release starts with ten seconds of studio logo, another does not. One runs at 24
frames per second, another at 25. Either way the words appear at the wrong
moment, from the first minute to the last.

Most players let you drag the delay by hand. That helps for one evening only: the
file on disk stays wrong, and the next device you watch on starts again from
zero.

Two things exist already and are good: `ffsubsync`, which needs numpy and a stack
of dependencies, and `alass`, a compiled binary. This tool is one readable Python
file with no dependencies, and it answers a question the others skip: **is a
single shift actually the right fix?** When the answer is no, it says so instead
of writing a wrong change that looks plausible.

## Before you start

| | |
| --- | --- |
| Python | 3.10 or newer |
| ffmpeg | both `ffmpeg` and `ffprobe` on the PATH |
| Disk space | none, apart from a `.bak` copy of the subtitle |
| Internet | not needed, it never contacts anything |

Check the first two:

```bash
python3 --version            # 3.10 or newer
ffmpeg -version  | head -1
ffprobe -version | head -1
```

If ffmpeg is missing:

```bash
sudo apt install ffmpeg      # Debian, Ubuntu, Raspberry Pi OS
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

There is no virtual environment to create and nothing to install with pip.

## Install

```bash
git clone https://github.com/Doguerg/sub-handyman.git
cd sub-handyman
chmod +x sub_handyman.py
python3 sub_handyman.py --version
```

The last command should print `sub_handyman 1.2.1`. If it does, you are ready.

If you want to run it from any folder, link it into your PATH:

```bash
sudo ln -s "$PWD/sub_handyman.py" /usr/local/bin/sub_handyman
sub_handyman --version
```

On Windows, write `python sub_handyman.py` wherever this page shows
`sub_handyman`.

## Your first fix, step by step

Seven steps. Nothing is written to disk until step 5.

### 1. Keep the video and the subtitle in the same folder

```
Movies/
└── Some Movie/
    ├── Some Movie.mkv
    └── Some Movie.tr.srt      <- the subtitle you want to fix
```

The names do not have to be identical. The tool looks for subtitle files that
begin with the same name as the video, so `Some Movie.mkv` finds
`Some Movie.tr.srt`. Naming the subtitle after the video is still the habit worth
having, because it removes doubt when a folder holds several languages.

### 2. Measure first, change nothing

```bash
python3 sub_handyman.py "Movies/Some Movie/Some Movie.mkv"
```

This command only reads. It chooses something to compare against, searches for
the offset, prints a report and stops. It takes five seconds to half a minute,
depending on what it compared against.

If you are unsure at any point, stop here. Measuring never changes a file.

### 3. Look at the first character of the report

| Mark | What it means | What to do |
| --- | --- | --- |
| `✅` | The subtitle already fits | Nothing. Leave the file alone. |
| `🔧` | A shift would help | Go to step 4. |
| `❔` | The tool is not sure | Stop. Read [When something goes wrong](#when-something-goes-wrong) first. |
| `⚠️ name: …` | It could not measure | Read the message. Usually the subtitle is missing or the video cannot be read. |

### 4. Check that the number makes sense

The report measures the offset three times: near the start, in the middle and
near the end.

```
    checks (start/middle/end): -5.30 / -5.30 / -5.30
```

If all three agree, the subtitle is simply late everywhere and one shift fixes
the whole film. This is the usual case.

If they differ by more than about a second, the tool adds a `⚠️` line. That means
the subtitle is not just late, and a single shift will not help. Do not apply it.

A `?` instead of a number means that part of the film had fewer than ten lines,
so there was nothing to measure there.

### 5. Apply the shift

```bash
python3 sub_handyman.py "Movies/Some Movie/Some Movie.mkv" --fix
```

With `--fix` it asks before touching anything:

```
    → shift by -5.30s? [y/N]
```

Answer `y`. It saves a copy as `.bak`, then rewrites the timings in the same
file. For scripts and batch runs, add `--yes` so it does not ask:

```bash
python3 sub_handyman.py "Movies/Some Movie/Some Movie.mkv" --fix --yes
```

### 6. Check in your player

Close the player and open the film again. If the subtitle comes from a media
server (Jellyfin, Plex, Emby), close and reopen the film there too: a session
that is already open can keep showing the old subtitle even though the file on
disk is already correct.

If it still looks late, the file is fine and the player is showing a cached copy.
Force a refresh. Do not run `--fix` a second time.

### 7. Undo, if you need to

Every run leaves the previous version next to the subtitle:

```bash
mv "Movies/Some Movie/Some Movie.tr.srt.bak" "Movies/Some Movie/Some Movie.tr.srt"
```

The video file is never changed, and nothing else on disk is touched.

## What the report says

```
🔧 movie
    subtitle: movie.tr.srt (1245 lines)
    offset: -5.30s · overlap: 98.4% (unchanged: 84.4%)
    compared with: subtitle track inside the video (stream 2)
    checks (start/middle/end): -5.30 / -5.30 / -5.30
```

| Line | What it tells you |
| --- | --- |
| `subtitle` | Which file was measured, and how many lines it has. |
| `offset` | Seconds to add to every line. Minus means the subtitle appears **too late** and has to move earlier. |
| `overlap` | Out of 100, how much of the subtitle sits exactly where there is speech. Higher is better. |
| `unchanged` | The same score with no correction at all. Compare the two numbers: if they are close, the file was already fine and there is nothing to gain. |
| `compared with` | What the subtitle was measured against. A subtitle track inside the video, or another subtitle file in the folder, gives the most reliable answer. Sound is the fallback and is less exact. |
| `checks` | The offset measured near the start, the middle and the end. Three similar numbers mean one shift is enough. |

### When one offset is not enough

Sometimes a subtitle does not fit the whole video with a single shift. The usual
reason: the subtitle was timed for a broadcast that carried adverts. Cutting the
adverts out moves scenes around, so the drift grows minute by minute. Then the
report talks in parts instead of one number:

```
🔧 A Show - S01E02
    subtitle: A Show - S01E02.tr.srt (586 lines)
    offset: not one value, the subtitle fits the video in 5 parts, +10.68s to +24.70s
    overlap: 99.0% (unchanged: 70.6%)
    parts start at: 0:18 +10.68 · 6:23 +13.80 · 20:47 +17.92 · 28:52 +20.36 · 39:14 +24.70
    compared with: subtitle track inside the video (stream 2)
```

| Line | What it tells you |
| --- | --- |
| How many parts | How many pieces the subtitle was split into. Each part gets its own offset. |
| `+10.68s to +24.70s` | The smallest and the largest offset. The gap between them shows why one shift was not enough. |
| `parts start at` | Where each part starts and the offset that applies from that second on. `0:18 +10.68` means the subtitle moves 10.68 seconds from eighteen seconds onwards. |

With `--fix` the parts are written separately; it does not fall back to one number.

### The two cut-offs

| Situation | What the tool says |
| --- | --- |
| `overlap` is 90% or more, and the offset is under 0.35 s | `✅` leave it alone |
| `overlap` is 55% or more, and the offset is real | `🔧` it can be fixed |
| `overlap` is under 55% | `❔` do not trust it |

**Why 0.35 seconds?** Subtitle guidelines aim to keep errors under about four
frames, which is roughly 0.16 s. Below a third of a second nobody notices, and
rewriting a file is then more risk than benefit.

**Why 55%?** A translation merges and splits lines, so it never lines up with the
original word for word. Somewhere between 80% and 90% is normal, and 98% is very
good. Below half the two files are probably not describing the same version of
the film, and the tool refuses to guess.

## How it decides

### 1. It needs something to compare against

In this order:

| # | Compared with | When this happens |
| --- | --- | --- |
| 1 | The subtitle track inside the video | Most released files carry an English track |
| 2 | The English subtitle file in the same folder | `mp4` files and web downloads often have no track inside |
| 3 | The sound: when speech starts and stops | Only when there is no text anywhere; the least exact option |

That comparison becomes a simple timeline: here somebody is talking, here nobody
is. Then every line of your subtitle is asked one question: does it sit on a
place where somebody talks?

### 2. It tries every plausible offset

The subtitle is shifted from -25 to +25 seconds in steps of a tenth of a second,
then refined to two hundredths of a second around the best result. At the coarse
stage the "somebody is talking" timeline is widened by half a second, so lines
that start a frame or two apart do not spoil an otherwise correct match.

### 3. It avoids a trap that catches most tools

Judging a shift only by "how much of the subtitle sits on speech" is misleading.
If one part of the film has almost continuous dialogue, pushing the subtitle into
that part raises the score even when nothing matches. The first version of this
tool did exactly that and reported an offset of **+152 seconds** on a test file.

So the search looks at two things at once: how much of the subtitle sits on
speech, and how much of the speech is covered by the subtitle. A shift that
satisfies only one of them scores badly.

The final yes-or-no answer uses the first number alone, because a translation
never covers every single line of the original. Two English lines can become one
translated line, so full coverage is impossible even when the timing is perfect.

### 4. One shift, or a different frame rate?

These are two different problems. If the subtitle was timed for 25 frames per
second and your film runs at 24, the error grows the further you watch: nothing
at the start, twenty seconds by the end. Sliding the whole file cannot fix that.

That is why the tool measures three times, near the start, the middle and the
end:

- all three agree: one shift is the answer
- they do not agree: it tries the usual frame-rate ratios and, if one is clearly
  better, applies a speed correction on top of the shift
- still unclear: it tells you instead of writing a wrong change

### 5. When the drift comes in steps

If the three measurements disagree but the speed is fine, only one explanation is
left: the offset changes in steps over time. The tool handles it like this:

1. The film is cut into three-minute windows and the offset is measured in each.
2. Every line is given one of those offsets. Not greedily: changing part costs
   something, so the noise of a few lines cannot invent a new part.
3. Each part is measured again on its own lines. A part shorter than 10 lines or
   30 seconds counts as unproven and joins its neighbour. That is how credits,
   recaps and very sparse dialogue drop out.
4. The part-based answer is only used when it is measurably better than a single
   shift.

If one shift already covers 99.5%, this work is never done. A part list only
appears in the report when there is a real gain behind it.

### 6. What happens to your file

`--fix` rewrites the timings and keeps the rest as it was:

- a UTF-8 byte-order mark is kept if the file had one
- files saved in the older Turkish Windows encoding are detected and written
  back the same way
- Windows line endings become Unix line endings, which every player accepts
- the `.bak` copy is written **before** the file is touched
- a line pushed past 00:00:00 keeps its length instead of collapsing to nothing

## All options

```
sub_handyman [VIDEO | --scan DIR] [options]
```

| Option | What it does |
| --- | --- |
| `VIDEO` | A video file, or a folder (searched including subfolders) |
| `--scan DIR` | Search a folder for videos: `mkv`, `mp4`, `m4v`, `avi`, `mov`, `webm`, `ts` |
| `--sub FILE` | Use this subtitle instead of guessing |
| `--fix` | Apply the measured shift |
| `--yes` | Do not ask for confirmation |
| `--audio` | Ignore text, compare against the sound |
| `--json` | Print machine-readable output instead of a report |
| `--backup-dir DIR` | Put `.bak` files in this folder instead of next to the subtitle |
| `--lang {en,tr}` | Report language, English or Turkish |
| `--version` | Print the version |

`--help` follows the same language switch: `sub_handyman --help --lang tr`.

### Which subtitle it picks

Given `Some Movie.mkv`, it looks in the same folder for `.srt` files whose name
starts with `Some Movie`. If several are there, Turkish ones win (`.tr.`,
`tr.srt`). When comparing, it prefers English ones (`*.en.*`, `*.eng.*`). If it
picks the wrong one, say which you want with `--sub`.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Nothing to do, the subtitle already fits |
| `1` | A shift was applied, or was needed and `--fix` was not given |
| `2` | It could not measure: no subtitle, nothing to compare with, unreadable video |

That is handy in scripts, where "all fine" and "needs attention" are what you
actually branch on:

```bash
python3 sub_handyman.py --scan /media/movies --json > report.json || echo "needs attention"
```

### JSON output

```json
{
  "offset": -5.3,
  "overlap": 0.984,
  "overlap_unchanged": 0.844,
  "balance": 0.935,
  "speed": 1.0,
  "checks": [-5.3, -5.3, -5.3],
  "checks_apart": 0.05,
  "compared_with": "subtitle track inside the video (stream 2)",
  "video": "movie.mkv",
  "subtitle": "movie.tr.srt",
  "lines": 1245,
  "needs_fix": true,
  "aligned": false,
  "applied": true,
  "backup": "movie.tr.srt.bak"
}
```

| Field | Meaning |
| --- | --- |
| `offset` | Seconds added to every line. Minus means the subtitle was late. |
| `overlap` | Share of the subtitle that sits on speech, 0 to 1. |
| `overlap_unchanged` | The same share with no correction. |
| `balance` | The combined score the search used. Lower than `overlap` is normal for translated subtitles. |
| `speed` | Speed correction applied before the shift. `1.0` means none. |
| `checks` | Offset measured near the start, the middle and the end. |
| `checks_apart` | How far apart those three numbers are. Above about 1.5 s, do not trust a single shift. |
| `overlap_one_value` | Only with a part-based answer: what a single shift would have reached. |
| `parts` | Only with a part-based answer: `from`, `offset` and `lines` for each part. |
| `compared_with` | What the subtitle was measured against. |
| `lines` | Number of lines in the subtitle. |
| `needs_fix` | A shift is available and has not been applied yet. |
| `aligned` | The subtitle already fits. |
| `applied`, `backup` | Only present when `--fix` really rewrote the file. |

`--scan` always returns a list, even when it finds one video. A single `VIDEO`
returns one object.

## Everyday uses

### Look through a whole folder before changing anything

```bash
python3 sub_handyman.py --scan ~/Videos/Movies --json > report.json
python3 - <<'PY'
import json
for item in json.load(open("report.json")):
    if item.get("needs_fix"):
        print(f"{item['subtitle']}: {item['offset']:+.2f}s (overlap {item['overlap']:.0%})")
PY
```

### Fix everything that is clearly off

```bash
python3 sub_handyman.py --scan ~/Videos/Movies --fix --yes
```

Anything marked `❔` is skipped even when `--fix` is given. A confident wrong
change is worse than a subtitle you already know is bad.

### Run it after every download

```bash
for f in "$download_dir"/*.mkv "$download_dir"/*.mp4; do
  [ -e "$f" ] || continue
  python3 sub_handyman.py "$f" --fix --yes || true
done
```

It is cheap: when the video carries a subtitle track, only that track is read, so
the work does not grow with the size of the video.

### Compare against the sound

For files whose only text track is a commentary, or `mp4` files with subtitles
burned into the picture:

```bash
python3 sub_handyman.py movie.mp4 --audio
```

### Choose the subtitle yourself

When a folder holds several languages and the guess is wrong:

```bash
python3 sub_handyman.py movie.mkv --sub "movie.pt-BR.srt"
```

### Turkish report

```bash
export SUB_HANDYMAN_LANG=tr     # or: --lang tr
```

## How long it takes

Measured on a Raspberry Pi 5 (8 GB, NVMe) with a 15 GB 4K file:

| Compared with | Time | Why |
| --- | --- | --- |
| Subtitle track inside the video | about 20 s | ffmpeg reads only the subtitle track |
| English subtitle file in the folder | about 5 s | plain Python, nothing to decode |
| The sound (`--audio`) | 2 to 4 min | the whole soundtrack has to be scanned |

The search itself is quick. Reading the video is what takes time.

## What it cannot do

- It fixes timing, not translation. A bad translation stays bad.
- If the subtitle belongs to a different version of the film (extended vs.
  cinema, scenes in another order), the numbers come out low, it says `❔`, and it
  will not guess.
- The sound is a rough guide when music and effects are loud. A text comparison
  is always preferred, and `--audio` is something you ask for.
- One subtitle per video per run. In a folder it picks the Turkish file, or
  otherwise the first `.srt`.
- `.ass` and `.ssa` files can be measured with `--sub`, but only `.srt` timings
  are rewritten.
- Files with a variable frame rate and dropped frames can go out of step in a way
  that neither a shift nor a speed correction describes. The three checks reveal
  it, and then it is a manual job.
- Where dialogue is very sparse, such as an opening or end credits, the offset
  there can stay a few seconds off. With nothing to measure the tool does not
  guess and does not touch it.
- The part-based answer finds the steps, but a step shorter than about two
  minutes can be missed. If one scene is still off, measure the file again and
  the extra pass will surface that part.

## When something goes wrong

| What you see | Why | What to do |
| --- | --- | --- |
| `no .srt next to the video` | The subtitle has another name, or sits in another folder | Name it after the video, or pass `--sub` |
| `subtitle too short (3 lines)` | It is a stub, an advert or a track list | Point `--sub` at the real subtitle |
| `❔` on every film | It fell back to the sound and the film is music-heavy | Check whether the video has a subtitle track; if not, find a text subtitle |
| Fixed, but the player still shows it late | The player or server is showing a cached copy | Close and reopen the film |
| `⚠️ checks at the start, middle and end disagree` | Different version of the film, or variable frame rate | Do not apply. Find a subtitle for the exact release |
| `⚠️ timed for a different frame rate` | 23.976, 24 and 25 mixed up | `--fix` applies a speed correction too; check the last minutes afterwards |
| `measurement failed: …` | ffmpeg missing, video unreadable, no sound track | Read the message, check `ffmpeg -version` |
| A script breaks on the JSON | `--scan` returns a list, one file returns an object | Always use `--scan`, or handle both |

When in doubt, run without `--fix`. Measuring changes nothing.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

25 tests. No video and no ffmpeg needed. They cover reading subtitle files (byte
order marks, Windows line endings, broken input, timestamps with two, three or
four decimals), writing timestamps and clamping them at zero, recovering known
offsets including fractional ones, spotting a frame-rate difference, the three
checks agreeing, parsing the sound scan, keeping the old Turkish encoding, finding
files with awkward names, the wording of the report, and finding step-shaped
drift. One test also forbids a dense reference track from justifying a wrong
offset, so parts come from measurement, not invention.

## License

MIT, see [LICENSE](LICENSE).
