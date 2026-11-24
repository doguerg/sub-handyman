# sub-handyman

Altyazı kaymasını tek komutla düzeltir.

Video ile yanındaki altyazı arasındaki kaymayı ölçer, bunun sabit bir gecikme mi
yoksa kare hızı (fps) uyuşmazlığı mı olduğunu ayırır, istersen altyazının
zamanlarını yeniden yazar. Yeniden kodlama yok, arayüz yok, üçüncü parti Python
paketi yok.

```console
$ sub_handyman "Jerry & Marge Go Large (2022).mkv"
🔧 Jerry & Marge Go Large (2022) WEBDL-2160p
    altyazı: Jerry & Marge Go Large (2022) WEBDL-2160p.tr.srt (1389 replik)
    kayma: -5.30 sn · eşleşme: 98.4% (0 kaymada 84.4%) · F1 93.5%
    referans: gömülü altyazı (stream 2)
    bölgeler (baş/orta/son): -5.30 / -5.30 / -5.30

$ sub_handyman "Jerry & Marge Go Large (2022).mkv" --fix --yes
    uygulandı, yedek: /media/movies/.../Jerry & Marge Go Large (2022) WEBDL-2160p.tr.srt.bak
```

English docs: [README.md](README.md)

---

## Neden var

Altyazı çevirileri çoğu zaman filmin **başka bir sürümü** üzerinden hazırlanır.
Başta on saniye fazla stüdyo logosu, ya da farklı bir kare hızı, ve her replik
yanlış yere düşer. Oynatıcıdan gecikmeyi elle kaydırabilirsin ama bu yalnızca o
izleme için geçerli: dosya yanlış kalır, yeni cihazda iş yine baştan başlar.

Bu işi yapan araçlar zaten var, o yüzden bu aracın kendini kanıtlaması gerekti.
`ffsubsync` numpy ve uzun bir bağımlılık zinciri getiriyor, `alass` derlenmiş bir
C++ ikilisi. `sub-handyman` tek dosya, sadece standart kütüphane. Bir de çoğu
aracın atladığı ikinci soruyu soruyor: *sabit kayma gerçekten doğru model mi?*

## Gereken

- Python 3.10+ (`X | Y` tip birleşimi kullanılıyor)
- `PATH` üzerinde `ffmpeg` ve `ffprobe`

```bash
sudo apt install ffmpeg      # Debian / Ubuntu / Raspberry Pi OS
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

Sanal ortam yok, `pip install` yok.

## Kurulum

```bash
git clone https://github.com/Doguerg/sub-handyman.git
cd sub-handyman
chmod +x sub_handyman.py

# istersen her yerden çalıştır
sudo ln -s "$PWD/sub_handyman.py" /usr/local/bin/sub_handyman
```

## Hızlı başlangıç

```bash
# 1. ne kadar kaymış?
python3 sub_handyman.py "Filmler/Film (2022)/Film (2022).mkv"

# 2. düzelt (önce yanına .bak yazar)
python3 sub_handyman.py "Filmler/Film (2022)/Film (2022).mkv" --fix

# 3. bütün arşivi tara
python3 sub_handyman.py --scan ~/Videolar/Filmler
```

## Nasıl çalışıyor

### 1. Referans seçimi

Referans, aday altyazının hizalandığı şey. Sırayla denenir:

| # | Referans | Ne zaman kullanılır |
| --- | --- | --- |
| 1 | Videodaki gömülü altyazı izi | Mux'lu sürümlerin çoğunda İngilizce iz var |
| 2 | Video yanındaki `*.en.srt` / `*.eng.srt` | Altyazı izi olmayan `mp4` / web-dl dosyalar |
| 3 | Ses: `ffmpeg silencedetect` ile konuşma aralıkları | Metin referansı hiç yoksa, son çare |

Referans 0.1 saniyelik adımlarla ikili bir zaman çizelgesine indirgenir: "burada
konuşan var mı?" Aday altyazının her repliği, süresinin ne kadarı bu çizelgeye
düştüğüne göre puanlanır.

### 2. Kaymanın taranması

Aday altyazı -25 ile +25 saniye arasında 0.1 saniyelik adımlarla kaydırılır,
en iyi değerin çevresinde 0.02 saniyeye kadar inceltilir. Kaba taramada referans
maskesi 0.5 saniye genişletilir; bir iki kare fark eden replik sınırları doğru
hizalamayı cezalandırmasın diye.

### 3. Arama F1 ile, karar kesinlikle

Sadece kesinlik üzerinden aramak tuzak, aracın ilk sürümü buna yakalandı. Film
bir bölgede yoğun diyalogluysa altyazıyı oraya kaydırmak kesinliği yükseltir,
oysa hiçbir replik yerine oturmaz. Sentetik testte "en iyi" kayma **+152 saniye**
çıktı.

Bu yüzden tarama **F1**'i büyütür: kesinlik ile duyarlılığın harmonik ortalaması.
Hem yoğun bölgeye kaçmayı hem de diyaloğun yarısını kaçırmayı cezalandırır.
Nihai *karar* ise **kesinlik** üzerinden verilir. Çünkü çeviri altyazıları
replikleri meşru biçimde birleştirip böler: iki İngilizce satır tek Türkçe satıra
dönüşebilir, o halde duyarlılık hiçbir zaman 1.0'a ulaşmaz.

Duyarlılığın paydası genişletilmemiş maskeden hesaplanır; yoksa kusursuz hizalama
bile yüzde yüzün çok altında puan alır.

### 4. Sabit gecikme mi, kare hızı mı?

Kare hızı uyuşmazlığı bir kayma değil. Hata doğrusal büyür: başta sıfır, sonda
onlarca saniye. Elle kaydırmak bunu düzeltmez.

Araç kaymayı filmin ilk, orta ve son üçte birinde ayrı ayrı ölçer:

- üçü de aynı → sabit kayma, uygula
- dağılıyorlar → bilinen oranlar (24000/1001, 24, 25) denenir; biri belirgin
  biçimde iyiyse **ölçek + kayma** birlikte uygulanır
- yine ikna edici değilse → yanlış düzeltme yazmak yerine bunu söyler

### 5. Dosyaya yazma

`--fix` zamanları yerinde yeniden yazar, biçimi korur:

- UTF-8 BOM varsa korunur
- CRLF yazarken LF'ye normalize edilir (her oynatıcı ikisini de kabul eder)
- dosyaya dokunmadan **önce** `.bak` (ya da `--backup-dir`) yazılır
- `00:00:00`'a kırpılan replik sıfıra çökmez, süresini korur

## Komut referansı

```
sub_handyman [VİDEO | --scan DİZİN] [seçenekler]
```

| Seçenek | Anlamı |
| --- | --- |
| `VİDEO` | Video dosyası ya da tek film içeren klasör |
| `--scan DİZİN` | Dizini alt klasörleriyle tarar (`mkv`, `mp4`, `m4v`, `avi`, `mov`, `webm`, `ts`) |
| `--sub DOSYA` | Otomatik bulma yerine bu altyazıyı kullan |
| `--fix` | Ölçülen düzeltmeyi uygula |
| `--yes` | Onay sorma (cron, script) |
| `--audio` | Metin referanslarını atla, doğrudan sesi kullan |
| `--json` | Makine okunur çıktı (`--scan` ile dizi döner) |
| `--backup-dir DİZİN` | `.bak` dosyalarını altyazının yanı yerine buraya yaz |
| `--lang {en,tr}` | Çıktı dili (varsayılan: `SUB_HANDYMAN_LANG`, yoksa `en`) |
| `--version` | Sürümü yazdır |

### Altyazının otomatik bulunması

`Film (2022).mkv` verildiğinde araç aynı klasörde `Film (2022)*.srt` arar ve
Türkçe işaretli olanları (`.tr.`, `tr.srt`) öne alır. Referans için İngilizceyi
(`*.en.*`, `*.eng.*`) tercih eder. Klasörde birden çok dil varsa ve yanlış
seçiliyorsa `--sub` ile açıkça ver.

### Çıkış kodları

| Kod | Anlamı |
| --- | --- |
| `0` | Hizalı, iş yok |
| `1` | Düzeltme uygulandı ya da gerekiyor ama `--fix` verilmedi |
| `2` | Ölçüm başarısız (altyazı yok, referans yok, video okunamadı) |

Script tarafında işe yarar, çünkü "her şey yolunda" ile "kayma bulundu" ayrımı
asıl dallanmak istediğin şey:

```bash
python3 sub_handyman.py --scan /media/filmler --json > rapor.json || echo "kayma var"
```

### JSON çıktısı

```json
{
  "shift": -5.3,
  "match": 0.984,
  "match_at_zero": 0.844,
  "f1": 0.935,
  "scale": 1.0,
  "regions": [-5.3, -5.3, -5.3],
  "region_spread": 0.05,
  "method": "gömülü altyazı (stream 2)",
  "video": "Film (2022).mkv",
  "subtitle": "Film (2022).tr.srt",
  "cues": 1389,
  "needs_fix": false,
  "aligned": true
}
```

| Alan | Anlamı |
| --- | --- |
| `shift` | Her repliğe eklenecek saniye (negatif = altyazı geç geliyor) |
| `match` | Kesinlik; `f1` taramanın büyüttüğü puan |
| `match_at_zero` | Dosyaya dokunmadan kesinlik, yani "zaten iyi mi?" sayısı |
| `scale` | Replik zamanlarına `shift`'ten önce uygulanan çarpan (1.0 = yok) |
| `regions` | İlk, orta ve son üçte birde ölçülen kayma |
| `region_spread` | `regions` farkı; 1.5 saniyeyi geçerse sabit model şüpheli |
| `needs_fix` | Eşleşme işlem yapmaya yetiyor ve bekleyen bir düzeltme var |
| `aligned` | Eşleşme yüksek, düzeltilecek bir şey yok |
| `applied` / `backup` | Yalnız `--fix` dosyayı gerçekten yazdıysa gelir |

## Çıktıyı okumak

| İşaret | Anlamı |
| --- | --- |
| `✅` | Hizalı: eşleşme ≥ %90 ve kayma 0.35 saniyenin altında |
| `🔧` | Düzeltme var: eşleşme ≥ %55 ve düzeltilecek bir şey var |
| `❔` | Güvenilir değil: eşleşme zayıf, **uygulama**, dosyaya bak |
| `⚠️` | Ölçüm tuttu ama model şüpheli (tutarsız bölgeler, fps) |

**Neden 0.35 saniye?** Altyazı kılavuzları yaklaşık dört kare (0.16 saniye)
hatanın altında kalmasını ister. Saniyenin üçte birinin altında kimse fark
etmiyor, dosyayı yeniden yazmak ise kazançtan çok risk.

**Neden %55?** Çeviri altyazıları replikleri birleştirip böldüğü için yüzde
80-90 bandı normal, yüzde 98 çok iyi. Yarıdan fazla düşükse iki dosya büyük
ihtimalle aynı kurguyu anlatmıyor.

## Tarifler

### Dokunmadan önce toplu kontrol

```bash
python3 sub_handyman.py --scan ~/Videolar/Filmler --json > rapor.json
python3 - <<'PY'
import json
for r in json.load(open("rapor.json")):
    if r.get("needs_fix"):
        print(f"{r['subtitle']}: {r['shift']:+.2f} sn (eşleşme {r['match']:.0%})")
PY
```

### Emin olunanları düzelt

```bash
python3 sub_handyman.py --scan ~/Videolar/Filmler --fix --yes
```

`❔` diye raporlanan dosyalar `--fix` verilse bile atlanır: kendinden emin yanlış
bir yazma, bilinen bozuk bir altyazıdan daha kötü.

### İndirme hattına ekle

```bash
for f in "$indirme_dizini"/*.mkv "$indirme_dizini"/*.mp4; do
  [ -e "$f" ] || continue
  python3 sub_handyman.py "$f" --fix --yes || true
done
```

Ucuz adım: gömülü referans varsa yalnız altyazı izi okunur, maliyet dosya
boyutuyla artmaz.

### Ses yolunu zorla

Tek metin izi yorum (commentary) olan remux'lar ya da gömülü dubtitle taşıyan
`mp4` dosyalar için:

```bash
python3 sub_handyman.py "Film.mp4" --audio
```

### Türkçe çıktı

```bash
export SUB_HANDYMAN_LANG=tr     # ya da: --lang tr
```

## Başarım

Raspberry Pi 5 (8 GB, NVMe), 15 GB'lık 4K HEVC remux ile ölçüldü:

| Referans | Süre | Not |
| --- | --- | --- |
| Gömülü altyazı | ~20 sn | ffmpeg yalnız altyazı izini çıkarır |
| Yan dosya `.srt` | ~5 sn | saf Python, kod çözme yok |
| Ses (`--audio`) | 2-4 dk | sesin tamamı `silencedetect`'ten geçer |

Darboğaz tarama değil, kod çözme.

## Sınırlar

- Zamanlamayı düzeltir, çeviriyi değil. Kötü çeviri kötü kalır.
- Farklı kurguya ait altyazı (uzatılmış/ekstra sürüm, değişmiş sahne sırası)
  düşük puan alır; araç `❔` der ve tahmin etmez.
- Ses referansı müzik ve efektin yoğun olduğu sahnelerde gürültülü. Metin
  referansı varsa o her zaman tercih edilir, `--audio` bilinçli bir seçim.
- Her koşuda video başına tek altyazı. Toplu modda Türkçe dosya, yoksa ilk
  `.srt` seçilir.
- `.ass`/`.ssa` dosyaları `--sub` ile *ölçülebilir*, ama yalnız `.srt` zamanları
  yeniden yazılır.
- Kare düşüren değişken kare hızlı (VFR) sürümlerde kayma ne sabit ne ölçekli
  olur; bölge kontrolü bunu işaretler, gerisi elle iş.

## Testler

```bash
python3 -m unittest discover -s tests -v
```

14 test var, video ve ffmpeg gerekmiyor. SRT ayrıştırma (BOM, CRLF, bozuk girdi),
zaman damgası biçimleme ve kırpma, dört ayrı büyüklükte kayma kurtarma, fps ölçek
tespiti, bölge tutarlılığı ve dosya keşfi sınanıyor.

## Lisans

MIT, bkz. [LICENSE](LICENSE).
