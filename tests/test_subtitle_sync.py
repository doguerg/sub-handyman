"""subtitle_sync.py birim testleri (ffmpeg gerektirmez)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import subtitle_sync as ss  # noqa: E402


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
            ss.shift_srt(p, -30.0, td / "bak")
            self.assertAlmostEqual(ss.parse_srt(p)[0][0], 0.0, places=2)

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
        cand = [(a + 7.0, b + 7.0) for a, b in ref]
        res = ss.measure(cand, ref, max(b for _, b in ref) + 30)
        self.assertAlmostEqual(res["shift"], -7.0, delta=0.15)
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
