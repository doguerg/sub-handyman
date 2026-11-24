#!/usr/bin/env python3
"""Altyazı senkron denetleyici.

Bir video dosyası ile yanındaki harici altyazının zamanlamasını ölçer; kayma
varsa tek komutla düzeltir.

Ölçüm yöntemi: videodaki gömülü altyazı (yoksa ses) referans alınır, aday
altyazının her repliği referansın konuşma/diyalog maskesine oturtulur. Kayma
-25..+25 sn aralığında taranır, en iyi örtüşme veren değer seçilir. Aynı tarama
filmin başı/ortası/sonu için ayrı yapılır; bölgeler arası fark varsa bu sabit
kayma değil hız (fps) sorunudur ve araç bunu ayrıca söyler.

Kullanım:
  subtitle_sync.py "<film.mkv>"                # sadece ölç, rapor et
  subtitle_sync.py "<film.mkv>" --fix          # kaymayı düzelt (yedek alır)
  subtitle_sync.py "<film.mkv>" --fix --yes    # soru sormadan düzelt
  subtitle_sync.py --scan <klasör>             # klasördeki tüm filmleri tara
  subtitle_sync.py "<film.mkv>" --json         # makine okunur çıktı

Çıkış kodları: 0 ölçüm/gerek yok, 1 düzeltme yapıldı (veya yapılması gerekiyor
ama --fix yok), 2 ölçüm yapılamadı.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

__version__ = "1.1.0"

# ---------------------------------------------------------------- i18n
# CLI metinleri iki dilli. Varsayılan İngilizce; SUB_HANDYMAN_LANG=tr ya da
# --lang tr ile Türkçe. JSON alan adları dile bağlı değil.
LANG = os.environ.get("SUB_HANDYMAN_LANG", "en")

STRINGS = {
    "no_srt": {"en": "no .srt next to the video", "tr": "yanında .srt yok"},
    "too_short": {"en": "subtitle too short ({n} cues)", "tr": "altyazı çok kısa ({n} replik)"},
    "ref_too_short": {"en": "reference too short", "tr": "referans çok kısa"},
    "emb_method": {"en": "embedded subtitle (stream {i})", "tr": "gömülü altyazı (stream {i})"},
    "sib_method": {"en": "sibling reference ({name})", "tr": "yan dosya referansı ({name})"},
    "audio_method": {"en": "audio (silencedetect speech intervals)",
                     "tr": "ses (silencedetect konuşma aralıkları)"},
    "warn_scale": {"en": "frame-rate mismatch suspected (scale {scale:.5f}): a constant shift "
                         "cannot fix this, --fix applies scale + shift",
                   "tr": "fps uyuşmazlığı görünüyor (ölçek {scale:.5f}) → sabit kayma yetmez, "
                         "--fix ile ölçekli düzeltme uygulanır"},
    "warn_region": {"en": "region offsets disagree ({spread:.1f}s start to end): "
                          "a constant shift is not trustworthy",
                    "tr": "bölge kaymaları tutarsız (baş/orta/son arası {spread:.1f} sn) "
                          "→ sabit kayma güvenilir değil"},
    "sub_line": {"en": "    subtitle: {name} ({cues} cues)",
                 "tr": "    altyazı: {name} ({cues} replik)"},
    "shift_line": {"en": "    offset: {shift:+.2f}s · match: {match:.1f}% (at zero {zero:.1f}%) · F1 {f1:.1f}%",
                   "tr": "    kayma: {shift:+.2f} sn · eşleşme: {match:.1f}% (0 kaymada {zero:.1f}%) · F1 {f1:.1f}%"},
    "scale_line": {"en": "    scale: {scale:.5f} (frame-rate difference)",
                   "tr": "    ölçek: {scale:.5f} (fps farkı)"},
    "ref_line": {"en": "    reference: {method}", "tr": "    referans: {method}"},
    "regions_line": {"en": "    regions (start/mid/end): {regions}",
                     "tr": "    bölgeler (baş/orta/son): {regions}"},
    "low_conf": {"en": "    low confidence: weak match, do not apply without checking",
                 "tr": "    güvenilir ölçüm yok: eşleşme zayıf, doğrulamadan düzeltme yapma"},
    "measure_error": {"en": "measurement failed: {err}", "tr": "ölçüm hatası: {err}"},
    "no_videos": {"en": "no video files found", "tr": "klasörde video bulunamadı"},
    "confirm": {"en": "    → shift by {shift:+.2f}s? [y/N] ", "tr": "    → {shift:+.2f} sn kaydırılsın mı? [e/H] "},
    "applied": {"en": "    applied, backup: {path}", "tr": "    uygulandı, yedek: {path}"},
    "yes": {"en": ("y", "yes"), "tr": ("e", "evet")},
}


def t(key: str, **kw) -> str:
    entry = STRINGS[key]
    return entry.get(LANG, entry["en"]).format(**kw)


THRESH_OK = 0.90          # bu örtüşmenin üstü: hizalı say
THRESH_LOW = 0.55         # bunun altı: güvenilir ölçüm değil
MIN_DELTA = 0.35          # bu kadar kayma "kayma var" sayılır (saniye)
COARSE_STEP = 0.10
FPS_SCALES = (25 / 23.976, 24 / 23.976, 23.976 / 25, 23.976 / 24, 25 / 24, 24 / 25)
FINE_STEP = 0.02
COARSE_RANGE = 25.0
REGION_COUNT = 3


# ---------------------------------------------------------------- srt okuma
TS_RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def _ts_to_sec(m: re.Match | None) -> float:
    if m is None:
        return 0.0
    # kesir basamak sayısı sabit değil: SRT 3 hane, ASS 2 hane, ffmpeg 4 hane yazabilir
    frac = float("0." + m.group(4))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + frac


def parse_srt(path: Path) -> list[tuple[float, float]]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace").replace("\r", "")
    cues = []
    for line in text.split("\n"):
        if "-->" not in line:
            continue
        parts = line.split("-->")
        m1, m2 = TS_RE.search(parts[0]), TS_RE.search(parts[1])
        if not m1 or not m2:
            continue
        a, b = _ts_to_sec(m1), _ts_to_sec(m2)
        if b > a:
            cues.append((a, b))
    return cues


# ------------------------------------------------------------- ffmpeg/ffprobe
def _run(cmd: list[str], binary: bool = False):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or b"").decode("utf-8", "replace")[:400].strip()
                           or f"komut başarısız: {' '.join(cmd[:3])}")
    return p.stdout if binary else p.stdout.decode("utf-8", "replace")


def probe_streams(video: Path) -> list[dict]:
    out = _run(["ffprobe", "-v", "error", "-show_entries",
                "stream=index,codec_type,codec_name:stream_tags=language,title",
                "-of", "json", str(video)])
    return json.loads(out).get("streams", [])


def extract_embedded_srt(video: Path, stream_index: int, dest: Path) -> Path:
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(video),
          "-map", f"0:{stream_index}", "-c:s", "srt", str(dest)])
    return dest


def parse_silencedetect(log: str, duration: float = 0.0) -> list[tuple[float, float]]:
    """silencedetect log'undan konuşma aralıkları (sessizliğin tümleyeni).

    ffmpeg dosya sesle başlıyorsa ilk `silence_end`i `silence_start` olmadan
    yazar. O durumda 0..end aralığı konuşmadır ve çiftler bir kaymamalıdır.
    """
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    if not duration:
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", log)
        duration = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 0.0

    speech: list[tuple[float, float]] = []
    cursor = 0.0
    if ends and (not starts or ends[0] <= starts[0]):
        lead = ends.pop(0)
        if lead > 0:
            speech.append((0.0, lead))
        cursor = lead
    if len(ends) < len(starts):
        ends = ends + [duration] * (len(starts) - len(ends))

    for a, b in zip(starts, ends):
        a = max(cursor, max(0.0, a))
        b = max(b, cursor)
        if duration:
            b = min(b, duration)
        if a > cursor:
            speech.append((cursor, a))
        cursor = max(cursor, b)
    if duration and cursor < duration:
        speech.append((cursor, duration))
    return speech


def audio_speech_intervals(video: Path, duration: float,
                           noise_db: int = -32, min_silence: float = 0.3) -> list[tuple[float, float]]:
    """Sesi ffmpeg silencedetect ile tarayıp konuşma aralıklarını çıkarır.

    numpy bağımlılığı yok: sessizlik aralıklarının tümleyeni konuşmadır.
    """
    p = subprocess.run(["ffmpeg", "-v", "info", "-nostats", "-i", str(video), "-map", "0:a:0",
                        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
                        "-f", "null", "-"], capture_output=True)
    log = (p.stderr or b"").decode("utf-8", "replace")
    if p.returncode != 0:
        raise RuntimeError("ses taranamadı: " + (log.strip().splitlines() or ["bilinmeyen hata"])[-1][:200])
    return parse_silencedetect(log, duration)


# ------------------------------------------------------------------ ölçüm
def _mask_from_cues(cues, duration: float, step: float) -> bytearray:
    n = max(1, int(duration / step) + 2)
    m = bytearray(n)
    for a, b in cues:
        lo, hi = max(0, int(a / step)), min(n, int(b / step) + 1)
        if hi > lo:
            m[lo:hi] = b"\x01" * (hi - lo)
    return m


def _dilate(mask: bytearray, k: int) -> bytearray:
    if k <= 0:
        return mask
    n = len(mask)
    d = bytearray(mask)
    for i in range(n):
        if mask[i]:
            lo, hi = max(0, i - k), min(n, i + k + 1)
            d[lo:hi] = b"\x01" * (hi - lo)
    return d


def _prefix(mask: bytearray) -> list[int]:
    from itertools import accumulate
    return list(accumulate(mask, initial=0))


def _f1(cues, cum: list[int], step: float, shift: float,
        ref_cum: list[int] | None = None) -> tuple[float, float]:
    """(F1, kesinlik) döndürür. Arama F1 ile, karar kesinlikle verilir."""
    """Kesinlik ve duyarlılığın harmonik ortalaması (F1).

    Sadece kesinlik kullanmak yanıltıcı: maskenin yoğun olduğu bir bölgeye
    kaydırmak kesinliği yükseltir ama hiçbir replik doğru yere oturmaz.
    F1 iki hatayı birden cezalandırır.
    """
    n = len(cum) - 1
    tp = den_c = 0
    lo_span, hi_span = None, None
    for a, b in cues:
        lo, hi = int((a + shift) / step), int((b + shift) / step)
        if lo < 0 or hi >= n:
            continue
        hi = max(hi, lo)
        tp += cum[hi + 1] - cum[lo]
        den_c += hi - lo + 1
        lo_span = lo if lo_span is None else min(lo_span, lo)
        hi_span = hi if hi_span is None else max(hi_span, hi)
    if not den_c or lo_span is None or hi_span is None:
        return 0.0, 0.0
    # duyarlılık paydası genişletilmemiş referanstan: genişletme payı
    # eşleşmeyi abartmasın, aksi halde kusursuz hizalama bile 1.0 vermez
    ref_cum = ref_cum if ref_cum is not None else cum
    den_ref = ref_cum[hi_span + 1] - ref_cum[lo_span]
    if not den_ref:
        return 0.0, 0.0
    # tp'yi yerinde kırpmak precision'ı da kırpardı: sınırlama yalnız duyarlılıkta
    prec = min(1.0, tp / den_c)
    rec = min(1.0, tp / den_ref)
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return f1, prec


def best_shift(cues, cum: list[int], step: float, lo: float, hi: float,
               sub_step: float = 1.0, ref_cum: list[int] | None = None) -> tuple[float, float]:
    best_sc, best_sh = -1.0, 0.0
    k0, k1 = int(round(lo / sub_step)), int(round(hi / sub_step))
    for k in range(k0, k1 + 1):
        sh = k * sub_step
        sc = _f1(cues, cum, step, sh, ref_cum)[0]
        # eşit skorda 0'a yakın kayma tercih edilir: düzenli aralıklı repliklerde
        # birden çok kayma aynı skoru verir, keyfi olanı seçmek yanlış düzeltme üretir
        if sc > best_sc + 1e-12 or (abs(sc - best_sc) <= 1e-12 and abs(sh) < abs(best_sh)):
            best_sc, best_sh = sc, sh
    return best_sc, best_sh


def _scale_cues(cues, scale: float):
    return [(a * scale, b * scale) for a, b in cues] if scale != 1.0 else cues


def measure(cues, ref, ref_end: float) -> dict:
    """ref: referans replik listesi ya da ("audio", konuşma_aralıkları)."""
    step = COARSE_STEP
    if isinstance(ref, tuple) and ref and ref[0] == "audio":
        intervals = ref[1]
        ref_end = max([ref_end] + [b for _, b in intervals])
    else:
        intervals = ref
    raw = _mask_from_cues(intervals, ref_end, step)
    cum = _prefix(_dilate(raw, 2))          # 0.2 sn tolerans
    fine = _prefix(raw)

    def locate(cs, span=COARSE_RANGE):
        _, sh = best_shift(cs, cum, step, -span, span, sub_step=step, ref_cum=fine)
        f_sc, f_sh = best_shift(cs, fine, step, sh - 1.0, sh + 1.0, FINE_STEP)
        best = f_sh if f_sc > 0 else sh
        return best, _f1(cs, cum, step, best, fine)

    shift, (f1, prec) = locate(cues)
    scale = 1.0

    # sabit kayma yetmiyorsa fps uyuşmazlığı olabilir: bilinen oranları dene
    if f1 < 0.90 and prec < 0.90:
        for cand in FPS_SCALES:
            if cand == 1.0:
                continue
            c_sh, (c_f1, c_prec) = locate(_scale_cues(cues, cand))
            if c_f1 > f1 + 0.05:
                f1, prec, shift, scale = c_f1, c_prec, c_sh, cand

    sc_zero = _f1(cues, cum, step, 0.0, fine)[1]

    # bölgesel tutarlılık: sabit kaymada her bölge aynı değeri vermeli
    regions = []
    if cues:
        total = max(b for _, b in cues)
        cs = _scale_cues(cues, scale)
        for i in range(REGION_COUNT):
            lo, hi = total * i / REGION_COUNT, total * (i + 1) / REGION_COUNT
            sub = [c for c in cs if lo <= c[0] < hi]
            if len(sub) < 10:
                regions.append(None)
                continue
            regions.append(round(best_shift(sub, fine, step, shift - 4.0, shift + 4.0, 0.05)[1], 2))
        vals = [r for r in regions if r is not None]
        spread = round(max(vals) - min(vals), 2) if len(vals) >= 2 else None
    else:
        spread = None

    return {
        "shift": round(shift, 2),
        "match": round(prec, 3),
        "f1": round(f1, 3),
        "match_at_zero": round(sc_zero, 3),
        "scale": round(scale, 5),   # aday altyazıya uygulanacak çarpan (1.0 = sadece kayma)
        "regions": regions,
        "region_spread": spread,
    }


# ------------------------------------------------------------------- yazma
def shift_srt(path: Path, delta: float, backup_dir: Path | None = None,
              scale: float = 1.0) -> Path:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
        encoding = "utf-8"
    except UnicodeDecodeError:
        # CP1254 (Türkçe Windows) altyazılar yaygın; parse bunları zaten okur
        text = raw.decode("cp1254", errors="replace")
        encoding = "cp1254"
        bom = False
    text = text.replace("\r\n", "\n")
    out = []
    for line in text.split("\n"):
        m = re.match(r"^(\s*)(\d+:\d+:\d+[,.]\d+)(\s*-->\s*)(\d+:\d+:\d+[,.]\d+)(.*)$", line)
        if not m:
            out.append(line)
            continue
        a = _ts_to_sec(TS_RE.search(m.group(2))) * scale + delta
        b = _ts_to_sec(TS_RE.search(m.group(4))) * scale + delta
        length = max(0.2, b - a)
        if a < 0:
            # sıfırın önüne taşan replik: süresi korunur, sıfıra yaslanır
            a, b = 0.0, length
        else:
            b = max(b, a + 0.2)
        out.append(m.group(1) + _fmt_ts(a) + m.group(3) + _fmt_ts(b) + m.group(5))
    new = "\n".join(out).encode(encoding)
    if bom:
        new = b"\xef\xbb\xbf" + new
    bak = (backup_dir / (path.name + ".bak")) if backup_dir else Path(str(path) + ".bak")
    bak.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, bak)
    path.write_bytes(new)
    return path


def _shift_ts(ts: str, delta: float) -> str:
    return _fmt_ts(max(0.0, _ts_to_sec(TS_RE.search(ts)) + delta))


def _fmt_ts(t: float) -> str:
    h, rem = divmod(t, 3600)
    mi, s = divmod(rem, 60)
    ms = min(999, int(round((s - int(s)) * 1000)))
    return f"{int(h):02d}:{int(mi):02d}:{int(s):02d},{ms:03d}"


# ------------------------------------------------------------ film bulma
def _sibling_srts(video: Path) -> list[Path]:
    """Video kök adıyla başlayan .srt'ler. glob() değil iterdir(): dosya adındaki
    [ ] karakterleri glob'da karakter sınıfı sayılır ve dosya bulunamaz."""
    stem = video.stem
    try:
        items = list(video.parent.iterdir())
    except OSError:
        return []
    return sorted(p for p in items
                  if p.is_file() and p.suffix.lower() == ".srt" and p.name.startswith(stem))


def find_subtitle(video: Path) -> Path | None:
    cands = _sibling_srts(video)
    pref = [c for c in cands if re.search(r"\.tr(\.|\.srt$)", c.name, re.I)]
    return (pref or cands or [None])[0]


def find_reference_subtitle(video: Path, exclude: Path | None = None) -> Path | None:
    """Video yanındaki İngilizce altyazıyı referans olarak bul."""
    for c in _sibling_srts(video):
        if exclude and c.resolve() == exclude.resolve():
            continue
        if re.search(r"[._](en|eng)\b", c.name, re.I) or re.search(r"\.en\.", c.name, re.I):
            return c
    return None


VIDEO_EXTS = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".webm", ".ts"}


def find_videos(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.suffix.lower() in VIDEO_EXTS)


# ------------------------------------------------------------------ sürücü
def analyze(video: Path, sub: Path | None, use_audio: bool) -> dict:
    sub = sub or find_subtitle(video)
    if not sub or not sub.exists():
        return {"video": str(video), "error": t("no_srt")}
    cues = parse_srt(sub)
    if len(cues) < 20:
        return {"video": str(video), "subtitle": str(sub), "error": t("too_short", n=len(cues))}

    streams = probe_streams(video)
    subs = [s for s in streams if s.get("codec_type") == "subtitle"
            and s.get("codec_name") in ("subrip", "srt", "ass", "ssa", "mov_text")]
    def _is_english(stream: dict) -> bool:
        lang = (stream.get("tags", {}).get("language") or "").strip().lower()
        return lang in ("en", "eng") or lang.startswith("en-")

    eng = [s for s in subs if _is_english(s)]
    pick = (eng or subs or [None])[0]

    tmp = None
    m = None
    if pick and not use_audio:
        import tempfile
        fd, tmp_name = tempfile.mkstemp(prefix="sub_handyman_ref_", suffix=".srt")
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            extract_embedded_srt(video, pick["index"], tmp)
            ref_cues = parse_srt(tmp)
            if len(ref_cues) < 20:
                raise RuntimeError(t("ref_too_short"))
            ref_end = max(b for _, b in ref_cues) + 30
            m = measure(cues, ref_cues, ref_end)
            m["method"] = t("emb_method", i=pick["index"])
        except Exception:
            pick = None
    if m is None and not use_audio:
        ref = find_reference_subtitle(video, exclude=sub)
        if ref:
            try:
                ref_cues = parse_srt(ref)
                if len(ref_cues) < 20:
                    raise RuntimeError(t("ref_too_short"))
                m = measure(cues, ref_cues, max(b for _, b in ref_cues) + 30)
                m["method"] = t("sib_method", name=ref.name)
            except Exception:
                m = None
    if m is None:
        dur_raw = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1", str(video)])
        dur_match = re.search(r"duration=([\d.]+)", dur_raw)
        if not dur_match:
            raise RuntimeError("video süresi okunamadı (duration=N/A)")
        dur = float(dur_match.group(1))
        intervals = audio_speech_intervals(video, dur)
        m = measure(cues, ("audio", intervals), dur)
        m["method"] = t("audio_method")

    m.update({
        "video": str(video),
        "subtitle": str(sub),
        "cues": len(cues),
        "needs_fix": (m["match"] >= THRESH_LOW
                      and (abs(m["shift"]) >= MIN_DELTA or abs(m["scale"] - 1.0) > 0.002)),
        "aligned": (m["match"] >= THRESH_OK and abs(m["shift"]) < MIN_DELTA
                    and abs(m["scale"] - 1.0) <= 0.002),
    })
    if abs(m["scale"] - 1.0) > 0.002:
        m["warning"] = t("warn_scale", scale=m["scale"])
    elif m["region_spread"] is not None and m["region_spread"] > 1.5:
        m["warning"] = t("warn_region", spread=m["region_spread"])
    if tmp and tmp.exists():
        tmp.unlink(missing_ok=True)
    return m


def fmt_report(r: dict) -> str:
    name = Path(r.get("video", "?")).stem
    if r.get("error"):
        return f"⚠️  {name}: {r['error']}"
    mark = "✅" if r["aligned"] else ("🔧" if r["needs_fix"] else "❔")
    lines = [f"{mark} {name}"]
    lines.append(t("sub_line", name=Path(r["subtitle"]).name, cues=r["cues"]))
    lines.append(t("shift_line", shift=r["shift"], match=r["match"] * 100,
                   zero=r["match_at_zero"] * 100, f1=r["f1"] * 100))
    if abs(r.get("scale", 1.0) - 1.0) > 0.002:
        lines.append(t("scale_line", scale=r["scale"]))
    lines.append(t("ref_line", method=r["method"]))
    if r.get("regions"):
        reg = " / ".join("?" if x is None else f"{x:+.2f}" for x in r["regions"])
        lines.append(t("regions_line", regions=reg))
    if not r["aligned"] and not r["needs_fix"]:
        lines.append(t("low_conf"))
    if r.get("warning"):
        lines.append(f"    ⚠️  {r['warning']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="sub_handyman",
        description="Altyazı-video senkron denetleyici: kaymayı ölçer, istersen düzeltir.")
    ap.add_argument("video", nargs="?", help="video dosyası veya film klasörü")
    ap.add_argument("--scan", metavar="DIR", help="klasördeki tüm video dosyalarını tara")
    ap.add_argument("--sub", help="altyazı dosyası (verilmezse video yanındaki .tr.srt)")
    ap.add_argument("--fix", action="store_true", help="ölçülen kaymayı uygula")
    ap.add_argument("--yes", action="store_true", help="onay sorma")
    ap.add_argument("--audio", action="store_true", help="gömülü altyazı yerine sesi referans al")
    ap.add_argument("--json", action="store_true", help="JSON çıktı")
    ap.add_argument("--backup-dir", default=None,
                    help="yedek klasörü (varsayılan: altyazının yanında .bak)")
    ap.add_argument("--lang", choices=("en", "tr"), default=None,
                    help="output language (default: SUB_HANDYMAN_LANG or en)")
    ap.add_argument("--version", action="version", version=f"sub_handyman {__version__}")
    args = ap.parse_args()

    if args.lang:
        global LANG
        LANG = args.lang
    elif LANG not in ("en", "tr"):
        LANG = "en"

    if not args.video and not args.scan:
        ap.error("video dosyası ya da --scan <klasör> gerekli")

    root = Path(args.scan or args.video).expanduser()
    targets = find_videos(root)
    if not targets:
        print(t("no_videos"))
        return 2

    results, worst = [], 0
    for v in targets:
        try:
            r = analyze(v, Path(args.sub) if args.sub else None, args.audio)
        except Exception as e:  # ölçüm yapılamadı
            r = {"video": str(v), "error": t("measure_error", err=e)}
        results.append(r)

        if not args.json:
            print(fmt_report(r))

        if r.get("needs_fix"):
            worst = max(worst, 1)
            if args.fix:
                go = args.yes
                if not go:
                    try:
                        ans = input(t("confirm", shift=r["shift"])).strip().lower()
                        go = ans.startswith(STRINGS["yes"].get(LANG, ("y",))[0])
                    except EOFError:
                        go = False
                if go:
                    bak_dir = Path(args.backup_dir) if args.backup_dir else None
                    shift_srt(Path(r["subtitle"]), float(r["shift"]), bak_dir,
                              float(r.get("scale", 1.0)))
                    bak_path = (bak_dir / (Path(r["subtitle"]).name + ".bak")) if bak_dir \
                        else Path(str(r["subtitle"]) + ".bak")
                    r["applied"] = True
                    r["backup"] = str(bak_path)
                    if not args.json:
                        print(t("applied", path=bak_path))
                    worst = 1
        elif r.get("error"):
            worst = max(worst, 2)

    if args.json:
        # --scan her zaman dizi döner (tek sonuçta bile), tek dosya modu nesne
        payload = results if (args.scan or len(results) > 1) else (results[0] if results else {})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
