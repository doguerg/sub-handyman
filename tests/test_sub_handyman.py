"""sub_handyman.py birim testleri (ffmpeg gerektirmez)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sub_handyman as ss  # noqa: E402


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,500
Merhaba.

2
00:00:05,250 --> 00:00:07,000
İkinci replik.

3
00:00:09,000 --> 00:00:10,000
Üçüncü.
"""


def write_srt(dirpath: Path, name: str, text: str, bom: bool = False) -> Path:
    p = dirpath / name
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    p.write_bytes(data)
    return p


def make_cues(start: float = 5.0, count: int = 200, seed: int = 7):
    """Düzensiz aralıklı replikler: gerçek altyazıya benzer, periyodik değil."""
    import random
    rnd = random.Random(seed)
    cues, t = [], start
    for _ in range(count):
        dur = rnd.uniform(0.8, 4.5)
        cues.append((t, t + dur))
        t += dur + rnd.uniform(0.15, 6.0) + (12.0 if rnd.random() < 0.05 else 0.0)
    return cues


class ParseTests(unittest.TestCase):
    def test_parse_srt_basic(self):
        with tempfile.TemporaryDirectory() as td:
            p = write_srt(Path(td), "a.srt", SRT_SAMPLE)
            cues = ss.parse_srt(p)
        self.assertEqual(len(cues), 3)
        self.assertAlmostEqual(cues[0][0], 1.0)
        self.assertAlmostEqual(cues[1][1], 7.0)

    def test_parse_srt_bom_and_crlf(self):
        with tempfile.TemporaryDirectory() as td:
            p = write_srt(Path(td), "b.srt", SRT_SAMPLE.replace("\n", "\r\n"), bom=True)
            cues = ss.parse_srt(p)
        self.assertEqual(len(cues), 3)
        self.assertAlmostEqual(cues[2][0], 9.0)

    def test_parse_srt_ignores_garbage(self):
        with tempfile.TemporaryDirectory() as td:
            p = write_srt(Path(td), "c.srt", "reklam\n\n1\n00:00:02,000 --> 00:00:01,000\ngeri\n")
            self.assertEqual(ss.parse_srt(p), [])


class TimestampTests(unittest.TestCase):
    def test_fraction_digit_counts(self):
        # SRT 3 hane, ASS 2 hane, ffmpeg 4 hane yazabilir
        for ts, expected in (("00:00:01,500", 1.5), ("00:00:01,5", 1.5),
                             ("00:00:01,05", 1.05), ("00:00:01,5000", 1.5),
                             ("00:00:01,50", 1.5)):
            with self.subTest(ts=ts):
                self.assertAlmostEqual(ss._ts_to_sec(ss.TS_RE.search(ts)), expected, places=3)


class SubprocessTests(unittest.TestCase):
    def test_ffmpeg_never_inherits_stdin(self):
        """ffmpeg stdin'i okur; miras alırsa `yes | ... --fix` onayını yutar."""
        from unittest import mock

        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=b"")
            ss._run(["ffprobe", "-version"], binary=True)
        self.assertIs(run.call_args.kwargs.get("stdin"), ss.subprocess.DEVNULL)

        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stderr=b"")
            ss.audio_speech_intervals(Path("x.mkv"), 10.0)
        self.assertIs(run.call_args.kwargs.get("stdin"), ss.subprocess.DEVNULL)


class SilenceDetectTests(unittest.TestCase):
    def test_leading_sound_does_not_shift_intervals(self):
        # dosya sesle başlıyor: ilk silence_end, silence_start olmadan gelir
        log = ("silence_end: 10.000 | silence_duration: 10.000\n"
               "silence_start: 10.000\n"
               "silence_end: 20.000 | silence_duration: 10.000\n")
        speech = ss.parse_silencedetect(log, duration=30.0)
        self.assertEqual(len(speech), 2)
        self.assertAlmostEqual(speech[0][0], 0.0, places=2)
        self.assertAlmostEqual(speech[0][1], 10.0, places=2)
        self.assertAlmostEqual(speech[1][0], 20.0, places=2)

    def test_leading_silence_is_handled(self):
        log = ("silence_start: 0\n"
               "silence_end: 5.000 | silence_duration: 5.000\n"
               "silence_start: 15.000\n")
        speech = ss.parse_silencedetect(log, duration=20.0)
        self.assertAlmostEqual(speech[0][0], 5.0, places=2)
        self.assertAlmostEqual(speech[0][1], 15.0, places=2)


class ShiftTests(unittest.TestCase):
    def test_shift_ts_formats_and_clamps(self):
        self.assertEqual(ss._shift_ts("00:00:01,000", 2.5), "00:00:03,500")
        self.assertEqual(ss._shift_ts("00:00:01,000", -5.0), "00:00:00,000")
        self.assertEqual(ss._shift_ts("01:59:59,900", 0.2), "02:00:00,100")

    def test_shift_srt_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            p = write_srt(td, "x.srt", SRT_SAMPLE)
            before = ss.parse_srt(p)
            ss.shift_srt(p, -0.5, td / "bak")
            after = ss.parse_srt(p)
            self.assertTrue((td / "bak" / "x.srt.bak").exists())
        for (a0, a1), (b0, b1) in zip(before, after):
            self.assertAlmostEqual(a0 - 0.5, b0, places=2)
            self.assertAlmostEqual(a1 - 0.5, b1, places=2)

    def test_shift_srt_clamps_at_zero(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            p = write_srt(td, "z.srt", SRT_SAMPLE)
            before = ss.parse_srt(p)
            ss.shift_srt(p, -30.0, td / "bak")
            after = ss.parse_srt(p)
        # sıfıra yaslanan replik süresini korumalı, 0.2 sn'ye çökmemeli
        self.assertAlmostEqual(after[0][0], 0.0, places=2)
        self.assertAlmostEqual(after[0][1] - after[0][0], (before[0][1] - before[0][0]) - 30.0 + 30.0,
                               places=2)
        self.assertGreater(after[0][1] - after[0][0], 2.0)

    def test_shift_srt_reads_cp1254_and_keeps_text(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            p = td / "w.tr.srt"
            body = "1\n00:00:02,000 --> 00:00:04,000\nGüneşli bir gün.\n"
            p.write_bytes(body.encode("cp1254"))
            ss.shift_srt(p, 1.0, td / "bak")
            text = p.read_bytes().decode("cp1254")
        self.assertIn("Güneşli bir gün.", text)
        self.assertIn("00:00:03,000 --> 00:00:05,000", text)

    def test_shift_srt_preserves_bom_and_text(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            p = write_srt(td, "y.srt", SRT_SAMPLE, bom=True)
            ss.shift_srt(p, 0.0, td / "bak")
            raw = p.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertIn("Merhaba.".encode(), raw)


class MeasureTests(unittest.TestCase):
    def test_recovers_known_shift(self):
        ref = make_cues()
        for injected in (7.0, 7.45, -3.33, 12.5):
            cand = [(a + injected, b + injected) for a, b in ref]
            res = ss.measure(cand, ref, max(b for _, b in ref) + 30)
            with self.subTest(injected=injected):
                self.assertAlmostEqual(res["shift"], -injected, delta=0.15)
                self.assertGreater(res["match"], 0.95)

    def test_identity_scores_high(self):
        ref = make_cues()
        res = ss.measure(ref, ref, max(b for _, b in ref) + 30)
        self.assertAlmostEqual(res["shift"], 0.0, delta=0.1)
        self.assertGreaterEqual(res["match"], 0.95)
        self.assertAlmostEqual(res["scale"], 1.0, places=5)
        self.assertIsNotNone(res["region_spread"])
        self.assertLessEqual(res["region_spread"], 1.0)

    def test_detects_fps_scale(self):
        ref = make_cues(count=400, seed=11)
        cand = [(a * (25 / 23.976), b * (25 / 23.976)) for a, b in ref]
        res = ss.measure(cand, ref, max(b for _, b in ref) + 30)
        # ölçek 25/23.976'ya yakın bulunmalı (sabit kayma bu sapmayı taşıyamaz)
        self.assertGreater(abs(res["scale"] - 1.0), 0.02)

    def test_constant_shift_is_not_mistaken_for_scale(self):
        ref = make_cues(count=300, seed=5)
        cand = [(a + 3.4, b + 3.4) for a, b in ref]
        res = ss.measure(cand, ref, max(b for _, b in ref) + 30)
        self.assertAlmostEqual(res["scale"], 1.0, places=5)


class DiscoveryTests(unittest.TestCase):
    def test_find_subtitle_prefers_turkish(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            write_srt(td, "Film.en.srt", SRT_SAMPLE)
            tr = write_srt(td, "Film.tr.srt", SRT_SAMPLE)
            video = td / "Film.mkv"
            video.write_bytes(b"")
            self.assertEqual(ss.find_subtitle(video), tr)

    def test_find_reference_subtitle_skips_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            en = write_srt(td, "Film.en.hi.srt", SRT_SAMPLE)
            tr = write_srt(td, "Film.tr.srt", SRT_SAMPLE)
            video = td / "Film.mkv"
            video.write_bytes(b"")
            self.assertEqual(ss.find_reference_subtitle(video, exclude=tr), en)
            self.assertIsNone(ss.find_reference_subtitle(video, exclude=en))

    def test_find_subtitle_with_brackets_in_name(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            name = "[Subs] Film [1080p]"
            (td / f"{name}.mkv").write_bytes(b"")
            tr = write_srt(td, f"{name}.tr.srt", SRT_SAMPLE)
            self.assertEqual(ss.find_subtitle(td / f"{name}.mkv"), tr)

    def test_find_videos_includes_mp4(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "a.mkv").write_bytes(b"")
            (td / "b.mp4").write_bytes(b"")
            (td / "c.nfo").write_bytes(b"")
            names = sorted(p.name for p in ss.find_videos(td))
            self.assertEqual(names, ["a.mkv", "b.mp4"])


if __name__ == "__main__":
    unittest.main()
