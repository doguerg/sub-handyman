# sub-handyman

**Altyazı kaymasında tahmin yerine ölçüm.**

`sub-handyman` videoyu yanındaki altyazıyla karşılaştırır, zamanlamanın ne kadar
kaydığını söyler, bunun sabit bir gecikme mi yoksa kare hızı (fps) uyuşmazlığı mı
olduğuna karar verir ve altyazı zamanlarını buna göre yeniden yazar. Yeniden
kodlama yok, arayüz yok, üçüncü parti Python paketi yok: tek dosya, sadece
standart kütüphane.

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

English docs: [README.md](README.md)

> Yukarıdaki örnek çıktı İngilizce arayüzle alındı. Türkçe arayüz için `--lang tr`
> ekle ya da `export SUB_HANDYMAN_LANG=tr` yap.

---

## İçindekiler

1. [Neden var](#neden-var)
2. [Gereken](#gereken)
3. [Kurulum](#kurulum)
4. [İlk çalıştırma, adım adım](#i̇lk-çalıştırma-adım-adım)
5. [Çıktıyı okumak](#çıktıyı-okumak)
6. [Nasıl çalışıyor](#nasıl-çalışıyor)
7. [Komut referansı](#komut-referansı)
8. [Tarifler](#tarifler)
9. [Başarım](#başarım)
10. [Sınırlar](#sınırlar)
11. [Sorun giderme](#sorun-giderme)
12. [Testler](#testler)
13. [Lisans](#lisans)

## Neden var

Altyazı çevirileri çoğu zaman filmin **başka bir sürümü** üzerinden hazırlanır.
Başta on saniye fazla stüdyo logosu, ya da farklı bir kare hızı, ve her replik
yanlış yere düşer. Oynatıcıdan gecikmeyi elle kaydırabilirsin ama bu yalnızca o
izleme için geçerli: dosya yanlış kalır, yeni cihazda iş yine baştan başlar.

Bu işin bir kısmını yapan araçlar zaten var, o yüzden bu aracın kendini
kanıtlaması gerekti. `ffsubsync` numpy ve uzun bir bağımlılık zinciri getiriyor,
`alass` derlenmiş bir C++ ikilisi. `sub-handyman` tek okunabilir dosya, bir de
çoğu aracın atladığı ikinci soruyu soruyor: *sabit kayma gerçekten doğru model
mi?*

Cevap hayırsa, akla yatkın görünen yanlış bir düzeltme yazmak yerine bunu
söylüyor.

## Gereken

| | |
| --- | --- |
| Python | 3.10 veya üstü (`X \| Y` tip birleşimi kullanılıyor) |
| ffmpeg | `PATH` üzerinde `ffmpeg` **ve** `ffprobe` |
| Disk | altyazının `.bak` kopyası dışında ek yer yok |
| Ağ | yok: hiçbir API'ye ya da altyazı sitesine bağlanmaz |

Her şeyden önce ikisini de doğrula:

```bash
python3 --version            # 3.10 veya üstü bekleniyor
ffmpeg  -version | head -1
ffprobe -version | head -1
```

ffmpeg kurulumu:

```bash
sudo apt install ffmpeg      # Debian, Ubuntu, Raspberry Pi OS
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

Sanal ortam gerekmiyor, `pip install` ile kurulacak bir şey yok.

## Kurulum

```bash
git clone https://github.com/Doguerg/sub-handyman.git
cd sub-handyman
chmod +x sub_handyman.py
python3 sub_handyman.py --version
```

Son satır `sub_handyman 1.1.1` yazmalı. Yazıyorsa kurulum bitti.

İstersen `PATH`'e ekle, her yerden `sub_handyman` diye çağır:

```bash
sudo ln -s "$PWD/sub_handyman.py" /usr/local/bin/sub_handyman
sub_handyman --version
```

Windows'ta bu dokümandaki `sub_handyman` yerine `python sub_handyman.py` yaz.

## İlk çalıştırma, adım adım

Bütün akış sırayla aşağıda. 5. adıma kadar hiçbir şey yazılmaz.

### 1. Videoyu ve altyazıyı aynı klasöre koy

```
Filmler/
└── Bir Film/
    ├── Bir Film.mkv
    └── Bir Film.tr.srt      <- düzeltmek istediğin altyazı
```

Adların birebir aynı olması şart değil. Araç dosya adının *başına* bakıyor:
`Bir Film.mkv`, `Bir Film.tr.srt` dosyasını bulur. Yine de altyazıyı videonun
adıyla adlandırmak doğru varsayılan; klasörde birden çok dil varsa karışıklığı
bu önler.

### 2. Ölç, henüz düzeltme

```bash
python3 sub_handyman.py "Filmler/Bir Film/Bir Film.mkv"
```

Bu komut yalnız okur. Referansı seçer, kaymayı tarar, raporu basar ve çıkar.
Hangi referansı bulduğuna göre beş saniye ile yarım dakika arası sürer.

Bir noktada emin değilsen burada dur. Ölçüm hiçbir dosyayı değiştirmez.

### 3. Raporun ilk karakterine bak

| İşaret | Anlamı | Ne yapmalı |
| --- | --- | --- |
| `✅` | Hizalı | Hiçbir şey. Dosyaya dokunma. |
| `🔧` | Düzeltme var | 4. adıma geç. |
| `❔` | Güvenilir değil | Dur. Dosyaya dokunmadan önce [Sorun giderme](#sorun-giderme) bölümüne bak. |
| `⚠️ ad: …` | Ölçüm başarısız | Mesajı oku. Genelde altyazı yok ya da video okunamıyor. |

### 4. Sayının mantıklı olduğunu doğrula

Rapor üç kayma değeri verir: filmin ilk, orta ve son üçte birinde ölçülen.

```
    regions (start/mid/end): -5.30 / -5.30 / -5.30
```

Üçü de aynıysa kayma sabit bir gecikmedir ve tek kaydırma işi bitirir. Sık
karşılaşılan durum budur.

Aralarında yaklaşık bir saniyeden fazla fark varsa araç bir `⚠️` uyarısı ekler:
dosya sadece geç kalmamış, tek kaydırma yetmez. Uygulama.

### 5. Uygula

```bash
python3 sub_handyman.py "Filmler/Bir Film/Bir Film.mkv" --fix
```

`--fix` verildiğinde araç dokunmadan önce sorar:

```
    → shift by -5.30s? [y/N]
```

`y` yaz. Altyazıyı `.bak` olarak kopyalar, sonra zamanları yerinde yeniden
yazar. Script ve toplu işlerde soruyu atlamak için `--yes` ekle:

```bash
python3 sub_handyman.py "Filmler/Bir Film/Bir Film.mkv" --fix --yes
```

### 6. Oynatıcıda doğrula

Oynatıcıyı kapat, yeniden aç. Altyazı bir medya sunucusundan geliyorsa (Jellyfin,
Plex, Emby) içeriği de kapat-aç: açık kalan oturum, dosya diskte doğru olmasına
rağmen eski altyazı metnini bellekte tutabilir.

Hâlâ geç geliyorsa dosya doğru, oynatıcı önbellekte tutuyor. Yenilemeye zorla.
`--fix`'i ikinci kez çalıştırma.

### 7. Gerekirse geri al

Her koşu önceki sürümü altyazının yanında bırakır:

```bash
mv "Filmler/Bir Film/Bir Film.tr.srt.bak" "Filmler/Bir Film/Bir Film.tr.srt"
```

Video dosyası hiçbir zaman değişmez, diskte başka hiçbir şeye dokunulmaz.

## Çıktıyı okumak

```
🔧 movie
    subtitle: movie.tr.srt (1245 cues)
    offset: -5.30s · match: 98.4% (at zero 84.4%) · F1 93.5%
    reference: embedded subtitle (stream 2)
    regions (start/mid/end): -5.30 / -5.30 / -5.30
```

| Satır | Anlamı |
| --- | --- |
| `offset` | Her repliğe eklenecek saniye. Negatifse altyazı **geç** geliyor, öne alınmalı. |
| `match` | Altyazının ne kadarı diyaloğa oturuyor, %0-100. Karar bu sayıyla verilir. |
| `at zero` | Düzeltme yapılmadan aynı puan. `match` ile karşılaştır: ikisi birbirine yakınsa dosya zaten iyiydi. |
| `F1` | Taramanın büyüttüğü dengeli puan. Çeviri altyazısı satır birleştirip böldüğünde `match`'ten düşük çıkar, bu normaldir. |
| `reference` | Ölçümün neye dayandığı. Gömülü ya da yan dosya metni güvenilir; `audio` yedek yoldur. |
| `regions` | İlk, orta ve son üçte birde ölçülen kayma. Eşit değerler sabit gecikme demek. `?` o üçte birde ölçüm için yeterli replik (10'dan az) olmadığını gösterir. |

### Eşikler ve neden orada durdukları

| Koşul | Sonuç |
| --- | --- |
| `match` ≥ %90 ve kayma 0.35 s altında | `✅` hizalı |
| `match` ≥ %55 ve gerçek bir kayma | `🔧` düzeltme var |
| `match` < %55 | `❔` güvenme |

**0.35 saniye** boş verilen eşik. Altyazı kılavuzları yaklaşık dört kare
(≈0.16 s) hataya izin verir. Saniyenin üçte birinin altında kimse fark etmiyor,
dosyayı yeniden yazmak ise kazançtan çok risk.

**%55** işlem yapma tabanı. Çeviri altyazıları replikleri birleştirip böldüğü
için %80-90 bandı normal, %98 çok iyi. Yarıdan fazla düşükse iki dosya büyük
ihtimalle aynı kurguyu anlatmıyor ve araç tahmin etmeyi reddediyor.

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

Aday altyazı -25 ile +25 saniye arasında 0.1 saniyelik adımlarla kaydırılır, en
iyi değerin çevresinde 0.02 saniyeye kadar inceltilir. Kaba taramada referans
maskesi 0.5 saniye genişletilir; bir iki kare fark eden replik sınırları doğru
hizalamayı cezalandırmasın diye.

### 3. Arama F1 ile, karar kesinlikle

Sadece kesinlik üzerinden aramak tuzak, aracın ilk sürümü buna yakalandı. Film
bir bölgede yoğun diyalogluysa altyazıyı oraya kaydırmak kesinliği yükseltir,
oysa hiçbir replik yerine oturmaz. Sentetik testte "en iyi" kayma **+152 saniye**
çıktı.

Bu yüzden tarama **F1**'i büyütür: kesinlik ile duyarlılığın harmonik ortalaması.
Hem yoğun bölgeye kaçmayı hem de diyaloğun yarısını kaçırmayı cezalandırır. Nihai
*karar* ise **kesinlik** üzerinden verilir. Çünkü çeviri altyazıları replikleri
meşru biçimde birleştirip böler: iki kaynak satır tek çeviri satırına dönüşebilir,
o halde duyarlılık hiçbir zaman 1.0'a ulaşmaz.

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
- CP1254 (Türkçe Windows) dosyalar tanınır ve yine CP1254 olarak yazılır
- CRLF yazarken LF'ye normalize edilir (her oynatıcı ikisini de kabul eder)
- dosyaya dokunmadan **önce** `.bak` (ya da `--backup-dir`) yazılır
- `00:00:00`'a kırpılan replik sıfıra çökmez, süresini korur

## Komut referansı

```
sub_handyman [VİDEO | --scan DİZİN] [seçenekler]
```

| Seçenek | Anlamı |
| --- | --- |
| `VİDEO` | Video dosyası ya da klasör (alt klasörlerle taranır) |
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

`Bir Film.mkv` verildiğinde araç aynı klasörde adı `Bir Film` ile başlayıp `.srt`
ile biten dosyaları arar ve Türkçe işaretli olanları (`.tr.`, `tr.srt`) öne alır.
Referans için İngilizceyi (`*.en.*`, `*.eng.*`) tercih eder. Klasörde birden çok
dil varsa ve yanlış seçiliyorsa `--sub` ile açıkça ver.

### Çıkış kodları

| Kod | Anlamı |
| --- | --- |
| `0` | Hizalı (ya da temiz ölçüldü), iş yok |
| `1` | Düzeltme uygulandı ya da gerekiyor ama `--fix` verilmedi |
| `2` | Ölçüm başarısız (altyazı yok, referans yok, video okunamadı) |

Script tarafında asıl dallanmak istediğin şey genelde "her şey yolunda" ile
"kayma bulundu" ayrımı:

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

| Alan | Anlamı |
| --- | --- |
| `shift` | Her repliğe eklenecek saniye (negatif = altyazı geç geliyor) |
| `match` | Kesinlik; `f1` taramanın büyüttüğü puan |
| `match_at_zero` | Dosyaya dokunmadan kesinlik |
| `scale` | Replik zamanlarına `shift`'ten önce uygulanan çarpan (1.0 = yok) |
| `regions` | İlk, orta ve son üçte birde ölçülen kayma |
| `region_spread` | `regions` farkı; 1.5 saniyeyi geçerse sabit model şüpheli |
| `needs_fix` | Eşleşme işlem yapmaya yetiyor ve bekleyen bir düzeltme var |
| `aligned` | Eşleşme yüksek, düzeltilecek bir şey yok |
| `applied` / `backup` | Yalnız `--fix` dosyayı gerçekten yazdıysa gelir |

`--scan` tek video bulsa bile **her zaman dizi** döner. Tek `VİDEO` argümanı tek
nesne döner.

## Tarifler

### Dokunmadan önce bütün arşivi kontrol et

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
python3 sub_handyman.py movie.mp4 --audio
```

### Altyazıyı elle seç

Klasörde birden çok dil varsa ve otomatik bulma yanılıyorsa:

```bash
python3 sub_handyman.py movie.mkv --sub "movie.pt-BR.srt"
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
- Değişken kare hızı ve kare düşmesi olan sürümlerde kayma ne sabit ne ölçekli
  olur; bölge kontrolü bunu işaretler, gerisi elle iş.

## Sorun giderme

| Belirti | Nedeni | Ne yapmalı |
| --- | --- | --- |
| `no .srt next to the video` | Altyazı farklı adlandırılmış ya da başka klasörde | Videoyla aynı adı ver ya da `--sub` kullan |
| `subtitle too short (n cues)` | Dosya kırpılmış, reklam ya da müzik listesi | Yanlış dosya: `--sub` ile gerçek altyazıyı göster |
| Her filmde `❔` | Referans ses, karışım da müzik ağırlıklı | Gömülü altyazı izi var mı bak, yoksa metin referansı bul |
| Düzeltildi, oynatıcıda hâlâ geç | Oynatıcı ya da medya sunucusu eski altyazıyı önbellekte tutuyor | İçeriği kapat-aç, yenilemeye zorla |
| `⚠️ region offsets disagree` | Farklı kurgu ya da değişken kare hızı | Uygulama. Tam o sürüme ait altyazıyı bul |
| `⚠️ frame-rate mismatch suspected` | 23.976 / 24 / 25 uyuşmazlığı | `--fix` ölçek + kayma uygular; sonrasında filmin sonunu kontrol et |
| `measurement failed: …` | ffmpeg yok, video okunamıyor, ses izi yok | Mesajı oku; `ffmpeg -version` kontrol et |
| Script JSON'da patlıyor | `--scan` dizi, tek dosya nesne döner | Ayrıştırmadan önce normalize et ya da hep `--scan` kullan |

Bir noktada emin değilsen `--fix` vermeden çalıştır. Ölçüm hiçbir şeyi değiştirmez.

## Testler

```bash
python3 -m unittest discover -s tests -v
```

20 test var, video ve ffmpeg gerekmiyor. SRT ayrıştırma (BOM, CRLF, bozuk girdi,
2/3/4 haneli kesirler), zaman damgası biçimleme ve kırpma, kesirli değerler
dahil birkaç büyüklükte kayma kurtarma, fps ölçek tespiti, bölge tutarlılığı,
sessizlik tespiti ayrıştırma, CP1254 gidiş-dönüş ve zor dosya adlarıyla keşif
sınanıyor.

## Lisans

MIT, bkz. [LICENSE](LICENSE).
