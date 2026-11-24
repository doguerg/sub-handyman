# subtitle-sync

Video ile harici altyazının zamanlamasını ölçer, kaymayı tek komutla düzeltir.

Altyazı çevirileri çoğu zaman başka bir sürümün zamanlamasıyla hazırlanır: film
başlar, altyazı 3-6 saniye geç gelir. Bu araç kaymayı ölçer, sabit kayma mı yoksa
kare hızı (fps) uyuşmazlığı mı olduğunu ayırt eder ve düzeltir.

## Nasıl ölçüyor

Referans olarak sırasıyla şunları kullanır:

1. Videonun içindeki gömülü altyazı (genelde İngilizce)
2. Video yanındaki İngilizce `.srt`
3. Ses: `ffmpeg silencedetect` ile bulunan konuşma aralıkları

Aday altyazının her repliği referansın zaman çizelgesine oturtulur. Kayma
-25..+25 saniye aralığında taranır, eşleşme F1 skoruyla ölçülür (yalnız kesinlik
kullanmak yanıltıcı: maskenin yoğun olduğu bölgeye kaydırmak kesinliği yükseltir).
Karar kesinlik üzerinden verilir, çünkü çeviri altyazıları replikleri birleştirip
böler; duyarlılık doğal olarak düşük kalır.

Sabit kayma yeterli değilse bilinen fps oranları (23.976 / 24 / 25) denenir; ölçek
1'den belirgin saparsa araç bunu ayrıca söyler ve düzeltmeyi ölçekle uygular.
`scale` altyazı zamanlarına uygulanan çarpandır: 23.976 kare hızına göre yazılmış
bir altyazı 25 fps videoda `0.959` verir.

## Kurulum

Gereken tek şey Python 3.10+ ve `ffmpeg`/`ffprobe`. Üçüncü parti paket yok.

```bash
sudo apt install ffmpeg        # Debian/Ubuntu
brew install ffmpeg            # macOS
```

## Kullanım

```bash
# ölç, rapor et
python3 subtitle_sync.py "Film (2022)/Film.mkv"

# ölç ve düzelt (yedek: altyazının yanında .bak)
python3 subtitle_sync.py "Film.mkv" --fix

# soru sormadan düzelt
python3 subtitle_sync.py "Film.mkv" --fix --yes

# kütüphaneyi tara (video uzantıları: mkv, mp4, m4v, avi, mov, webm, ts)
python3 subtitle_sync.py --scan /media/movies

# makine okunur çıktı
python3 subtitle_sync.py "Film.mkv" --json
```

Kullanışlı seçenekler:

| Seçenek | Anlamı |
| --- | --- |
| `--sub FILE` | Altyazıyı elle seç (varsayılan: video yanındaki `.tr.srt`) |
| `--audio` | Gömülü altyazıyı atla, doğrudan sesi referans al |
| `--backup-dir DIR` | Yedekleri başka klasöre yaz (varsayılan: altyazının yanı) |
| `--json` | JSON çıktı (otomasyon için) |

Çıkış kodları:

- `0` hizalı, iş yok
- `1` düzeltme uygulandı ya da gerekiyor (ama `--fix` verilmedi)
- `2` ölçüm yapılamadı (video/altyazı yok, referans üretilemedi)

## Örnek çıktı

```
🔧 Jerry & Marge Go Large (2022) WEBDL-2160p
    altyazı: Jerry & Marge Go Large (2022) WEBDL-2160p.tr.srt (1389 replik)
    kayma: -5.30 sn · eşleşme: 98.4% (0 kaymada 84.4%) · F1 93.5%
    referans: gömülü altyazı (stream 2)
    bölgeler (baş/orta/son): -5.30 / -5.30 / -5.30
```

Baş/orta/son değerleri birbirini tutuyorsa kayma sabittir ve tek parça düzeltme
yeter. Tutmuyorsa araç uyarır: sabit kayma güvenilir değildir.

## Testler

```bash
python3 -m unittest discover -s tests -v
```

Testler video/ffmpeg gerektirmez; sentetik repliklerle ölçüm, kaydırma, sıfıra
kırpma, BOM/CRLF koruma, fps ölçeği ve dosya keşfi doğrulanır.

## Sınırlar

- Zamanlama düzeltir, çeviri yapmaz. Yanlış çeviri yanlış kalır.
- Altyazı tamamen farklı bir kurguya aitse (sahneler uyuşmuyorsa) ölçüm düşük
  çıkar ve araç `❔` ile uyarır; o durumda doğru altyazıyı indirmek gerekir.
- Ses referansı müzikli/efektli sahnelerde gürültülüdür; gömülü altyazı varsa o
  tercih edilir.
- 4K remux dosyalarda ses taraması (yalnız gerektiğinde) dakikalar sürebilir;
  gömülü altyazı varsa tarama saniyeler içinde biter.

## Lisans

MIT.
