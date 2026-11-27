# sub-handyman

**Altyazı ne kadar kaymış, ölç ve düzelt. Editör açmadan.**

`sub-handyman` videoyu yanındaki altyazı dosyasıyla karşılaştırır, altyazının kaç
saniye kaydığını söyler, tek bir kaydırmanın yetip yetmediğini ya da altyazının
farklı bir kare hızına göre mi hazırlandığını çözer, istersen zamanları yeniden
yazar. Yeniden kodlama yok, tıklanacak pencere yok, kurulacak Python paketi yok.

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

English docs: [README.md](README.md)

> Örnek çıktı İngilizce yazılmış; Türkçe rapor için `--lang tr` ekle ya da
> `export SUB_HANDYMAN_LANG=tr` yap.

---

## İçindekiler

1. [Ne işe yarar](#ne-işe-yarar)
2. [Başlamadan önce](#başlamadan-önce)
3. [Kurulum](#kurulum)
4. [İlk düzeltme, adım adım](#i̇lk-düzeltme-adım-adım)
5. [Rapor ne söylüyor](#rapor-ne-söylüyor)
6. [Nasıl karar veriyor](#nasıl-karar-veriyor)
7. [Bütün seçenekler](#bütün-seçenekler)
8. [Günlük kullanım](#günlük-kullanım)
9. [Ne kadar sürüyor](#ne-kadar-sürüyor)
10. [Yapamadıkları](#yapamadıkları)
11. [Bir şey ters giderse](#bir-şey-ters-giderse)
12. [Testler](#testler)
13. [Lisans](#lisans)

## Ne işe yarar

Altyazı çoğu zaman filmin **başka bir sürümü** için çevrilir. Bir sürümün başında
on saniye stüdyo logosu vardır, diğerinde yok. Biri saniyede 24 kare oynar, öteki
25. Her iki durumda da sözler yanlış anda görünür, ilk dakikadan son dakikaya
kadar.

Çoğu oynatıcı gecikmeyi elle kaydırmaya izin verir. Bu yalnızca o akşam işe
yarar: diskteki dosya yanlış kalır, başka cihazda yine sıfırdan başlarsın.

Bu işi yapan iki iyi araç zaten var: `ffsubsync` numpy ve bir yığın bağımlılık
istiyor, `alass` derlenmiş bir ikili. Bu araç tek okunabilir Python dosyası ve
hiçbir bağımlılığı yok. Bir de ötekilerin atladığı soruyu soruyor: **tek bir
kaydırma gerçekten doğru çözüm mü?** Cevap hayırsa, kulağa mantıklı gelen yanlış
bir değişiklik yazmak yerine bunu söylüyor.

## Başlamadan önce

| | |
| --- | --- |
| Python | 3.10 ya da üstü |
| ffmpeg | `ffmpeg` ve `ffprobe`, ikisi de PATH üzerinde |
| Disk | altyazının `.bak` kopyası dışında yer gerekmiyor |
| İnternet | gerekmiyor, hiçbir yere bağlanmıyor |

İlk ikisini kontrol et:

```bash
python3 --version            # 3.10 ya da üstü
ffmpeg -version  | head -1
ffprobe -version | head -1
```

ffmpeg yoksa:

```bash
sudo apt install ffmpeg      # Debian, Ubuntu, Raspberry Pi OS
brew install ffmpeg          # macOS
winget install Gyan.FFmpeg   # Windows
```

Sanal ortam kurmak gerekmiyor, pip ile kurulacak bir şey yok.

## Kurulum

```bash
git clone https://github.com/Doguerg/sub-handyman.git
cd sub-handyman
chmod +x sub_handyman.py
python3 sub_handyman.py --version
```

Son komut `sub_handyman 1.2.1` yazmalı. Yazıyorsa hazırsın.

Her klasörden çalıştırmak istersen PATH'e bağla:

```bash
sudo ln -s "$PWD/sub_handyman.py" /usr/local/bin/sub_handyman
sub_handyman --version
```

Windows'ta bu sayfadaki `sub_handyman` yerine `python sub_handyman.py` yaz.

## İlk düzeltme, adım adım

Yedi adım. 5. adıma kadar diske hiçbir şey yazılmaz.

### 1. Videoyu ve altyazıyı aynı klasöre koy

```
Filmler/
└── Bir Film/
    ├── Bir Film.mkv
    └── Bir Film.tr.srt      <- düzeltmek istediğin altyazı
```

Adların birebir aynı olması şart değil. Araç, adı videonun adıyla başlayan
altyazı dosyalarına bakıyor; `Bir Film.mkv` dosyası `Bir Film.tr.srt` dosyasını
bulur. Yine de altyazıyı videonun adıyla adlandırmak iyi bir alışkanlık, klasörde
birkaç dil varsa karışıklığı bu önler.

### 2. Önce ölç, hiçbir şeyi değiştirme

```bash
python3 sub_handyman.py "Filmler/Bir Film/Bir Film.mkv"
```

Bu komut yalnız okur. Karşılaştıracak bir şey seçer, kaymayı arar, raporu basar ve
durur. Neyle karşılaştırdığına göre beş saniye ile yarım dakika arası sürer.

Bir noktada emin değilsen burada dur. Ölçmek hiçbir dosyayı değiştirmez.

### 3. Raporun ilk karakterine bak

| İşaret | Anlamı | Ne yapmalı |
| --- | --- | --- |
| `✅` | Altyazı zaten oturuyor | Hiçbir şey. Dosyaya dokunma. |
| `🔧` | Kaydırma işe yarar | 4. adıma geç. |
| `❔` | Araç emin değil | Dur. Önce [Bir şey ters giderse](#bir-şey-ters-giderse) bölümünü oku. |
| `⚠️ ad: …` | Ölçemedi | Mesajı oku. Genelde altyazı yok ya da video okunamıyor. |

### 4. Sayının mantıklı olduğunu kontrol et

Rapor kaymayı üç yerde ölçer: filmin başında, ortasında ve sonunda.

```
    checks (start/middle/end): -5.30 / -5.30 / -5.30
```

Üçü de aynıysa altyazı her yerde aynı kadar geç kalmış demektir ve tek kaydırma
bütün filmi düzeltir. Sık görülen durum bu.

Aralarında bir saniyeden fazla fark varsa araç bir `⚠️` satırı ekler. O zaman
altyazı sadece geç kalmamış, tek kaydırma yetmez. Uygulama.

Sayı yerine `?` görürsen o bölümde on satırdan az replik var, ölçülecek bir şey
yok demektir.

### 5. Kaydırmayı uygula

```bash
python3 sub_handyman.py "Filmler/Bir Film/Bir Film.mkv" --fix
```

`--fix` verildiğinde dokunmadan önce sorar:

```
    → shift by -5.30s? [y/N]
```

`y` yaz. Altyazıyı `.bak` olarak saklar, sonra zamanları aynı dosyada yeniden
yazar. Script ve toplu işlerde soru sormasın diye `--yes` ekle:

```bash
python3 sub_handyman.py "Filmler/Bir Film/Bir Film.mkv" --fix --yes
```

### 6. Oynatıcıda kontrol et

Oynatıcıyı kapat, filmi yeniden aç. Altyazı bir medya sunucusundan geliyorsa
(Jellyfin, Plex, Emby) orada da filmi kapat-aç: açık kalan oturum, dosya diskte
doğru olmasına rağmen eski altyazıyı göstermeye devam edebilir.

Hâlâ geç geliyorsa dosya doğru, oynatıcı eski kopyayı gösteriyor. Yenilemeye
zorla. `--fix` komutunu ikinci kez çalıştırma.

### 7. Gerekirse geri al

Her koşu önceki sürümü altyazının yanında bırakır:

```bash
mv "Filmler/Bir Film/Bir Film.tr.srt.bak" "Filmler/Bir Film/Bir Film.tr.srt"
```

Video dosyası hiçbir zaman değişmez, diskte başka hiçbir şeye dokunulmaz.

## Rapor ne söylüyor

```
🔧 Bir Film
    altyazı: Bir Film.tr.srt (1245 replik)
    kayma: -5.30 sn · örtüşme: 98.4% (değiştirmeden: 84.4%)
    karşılaştırma: videonun içindeki altyazı izi (stream 2)
    kontroller (baş/orta/son): -5.30 / -5.30 / -5.30
```

(Bu örnek `--lang tr` ile alınmış çıktı. Dil verilmezse rapor İngilizce gelir.)

| Satır | Ne anlatıyor |
| --- | --- |
| `altyazı` | Hangi dosya ölçüldü ve kaç repliği var. |
| `kayma` | Her repliğe eklenecek saniye. Eksi, altyazının **geç** geldiğini ve öne alınması gerektiğini gösterir. |
| `örtüşme` | Yüz üzerinden, altyazının ne kadarı konuşmanın olduğu yere oturuyor. Yüksek olması iyi. |
| `değiştirmeden` | Hiç düzeltme yapılmadan aynı ölçüm. İki sayıyı karşılaştır: birbirine yakınsa dosya zaten iyiydi, kazanç yok. |
| `karşılaştırma` | Neyle karşılaştırıldığı. Videonun içindeki altyazı izi ya da klasördeki başka bir altyazı en güvenilir sonucu verir. Ses, son çare ve daha kaba. |
| `kontroller` | Başta, ortada ve sonda ölçülen kayma. Üç sayı birbirine yakınsa tek kaydırma yeter. |

### Kayma tek değer değilse

Altyazı bazen videonun tamamına tek kaymayla oturmaz. Sebep genelde şu: altyazı,
araya reklam girmiş bir yayına göre hazırlanmıştır. Reklamlar kesilip birleştirilirken
sahneler kayar, kayma da dakika dakika büyür. O zaman rapor tek sayı yerine parça
parça konuşur:

```
🔧 Bir Dizi - S01E02
    altyazı: Bir Dizi - S01E02.tr.srt (586 replik)
    kayma: tek değer değil, altyazı videoya 5 parçada oturuyor (+10.68 ile +24.70 sn)
    örtüşme: 99.0% (değiştirmeden: 70.6%)
    parçaların başladığı yerler: 0:18 +10.68 · 6:23 +13.80 · 20:47 +17.92 · 28:52 +20.36 · 39:14 +24.70
    karşılaştırma: videonun içindeki altyazı izi (stream 2)
```

| Satır | Ne anlatıyor |
| --- | --- |
| `parts` sayısı | Altyazının kaç parçaya bölündüğü. Her parça kendi kaymasını alır. |
| `+10.68s to +24.70s` | En küçük ve en büyük kayma. İkisi arasındaki fark, tek kaydırmanın neden yetmediğini gösterir. |
| `parts start at` | Her parçanın hangi dakikada başladığı ve o dakikadan sonra geçerli kayma. `0:18 +10.68`, on sekiz saniyeden sonra altyazıya 10.68 saniye eklenir demek. |

`--fix` bu durumda parçaları ayrı ayrı uygular, tek sayı yazmaz.

### İki eşik

| Durum | Araç ne der |
| --- | --- |
| `overlap` yüzde 90 ve üstü, kayma 0.35 saniyenin altında | `✅` dokunma |
| `overlap` yüzde 55 ve üstü, kayma gerçekten var | `🔧` düzeltilebilir |
| `overlap` yüzde 55'in altında | `❔` güvenme |

**Neden 0.35 saniye?** Altyazı kılavuzları hatanın yaklaşık dört karenin, yani
0.16 saniyenin altında kalmasını ister. Saniyenin üçte birinin altında kimse fark
etmiyor, dosyayı yeniden yazmak da o noktada kazançtan çok risk.

**Neden yüzde 55?** Çeviri, satırları birleştirip böler, bu yüzden asla kelimesi
kelimesine örtüşmez. Yüzde 80 ile 90 arası normal, 98 çok iyi. Yarıdan aşağısı,
iki dosyanın büyük ihtimalle filmin aynı sürümünü anlatmadığını gösterir ve araç
tahmin yürütmeyi reddeder.

## Nasıl karar veriyor

### 1. Karşılaştıracak bir şey bulması gerekiyor

Sırayla şunlara bakar:

| # | Neyle karşılaştırır | Ne zaman |
| --- | --- | --- |
| 1 | Videonun içindeki altyazı izi | Yayınlanan dosyaların çoğunda İngilizce iz var |
| 2 | Aynı klasördeki İngilizce altyazı dosyası | `mp4` dosyalarında ve internet indirmelerinde içeride iz olmaz |
| 3 | Ses: konuşmanın başladığı ve bittiği anlar | Hiç metin yoksa, en kaba yol |

Bu karşılaştırma basit bir zaman çizelgesine dönüşür: burada konuşan var, burada
yok. Sonra altyazının her satırına tek bir soru sorulur: konuşmanın olduğu yere mi
düşüyor?

### 2. Bütün olası kaymaları dener

Altyazı eksi 25 ile artı 25 saniye arasında, saniyenin onda biri adımlarla
kaydırılır. En iyi sonucun çevresinde yüzde birlik adımlara inilir. Kaba aramada
"konuşan var" çizelgesi yarım saniye genişletilir, bir iki kare fark eden satır
başlangıçları doğru eşleşmeyi bozmasın diye.

### 3. Çoğu aracı yakalayan tuzağa düşmemeye çalışıyor

Bir kaydırmayı yalnızca "altyazının ne kadarı konuşmanın üstüne düşüyor" diye
ölçmek yanıltıcı. Filmin bir bölümünde neredeyse kesintisiz diyalog varsa,
altyazıyı oraya itmek ölçümü yükseltir, oysa hiçbir satır yerine oturmaz. Bu aracın
ilk sürümü tam olarak bunu yaptı ve bir test dosyasında **+152 saniye** gibi
saçma bir sonuç verdi.

Bu yüzden arama iki şeye birlikte bakıyor: altyazının ne kadarı konuşmanın üstüne
düşüyor, konuşmanın ne kadarı altyazıyla kaplanıyor. Yalnızca birini tutan kaydırma
kötü puan alıyor.

Son evet-hayır kararı ilk sayıya bakılarak veriliyor, çünkü çeviri orijinalin her
satırını kaplamaz. İki İngilizce satır tek Türkçe satıra dönüşebilir, yani
zamanlama kusursuz olsa bile tam kapsama imkânsız.

### 4. Tek kaydırma mı, farklı kare hızı mı?

Bunlar iki ayrı sorun. Altyazı saniyede 25 kare için hazırlanmışsa ve film 24 kare
oynuyorsa hata izledikçe büyür: başta hiç yok, sonda yirmi saniye. Bütün dosyayı
kaydırmak bunu düzeltmez.

Araç bu yüzden üç kez ölçüyor: başta, ortada, sonda.

- üçü de aynı: tek kaydırma yeter
- ayrışıyorlar: bilinen kare hızı oranlarını deniyor, biri belirgin biçimde iyiyse
  kaydırmanın yanında bir hız düzeltmesi de uyguluyor
- hâlâ belirsiz: yanlış bir değişiklik yazmak yerine bunu söylüyor

### 5. Kayma basamak basamaksa

Üç ölçüm birbirini tutmuyor ama hız da suçlu değilse, geriye tek açıklama kalıyor:
kayma zamanla basamak basamak değişiyor. Araç bunu şöyle çözüyor:

1. Film üçer dakikalık pencerelere bölünür, her pencerede kayma ayrı ölçülür.
2. Her repliğe bu ölçümlerden biri atanır. Atama açgözlü değil: parça değiştirmenin
   bir bedeli var, böylece üç beş repliğin gürültüsü yeni parça uydurmaz.
3. Her parçanın kayması kendi replikleriyle yeniden ölçülür. 10 replikten ya da
   30 saniyeden kısa parça kendi kaymasını kanıtlayamaz sayılır, komşusuna katılır.
   Jenerik, ön tanıtım ve çok seyrek diyalog böyle elenir.
4. Parçalı çözüm ancak tek kaydırmadan ölçülebilir biçimde daha iyi çıkarsa kullanılır.

Tek kaydırma zaten yüzde 99.5'i tutuyorsa bu iş hiç yapılmaz. Tek kaydırma yeterli
olan bir dosyada parça listesi görmenin tek yolu bu değil: parçalar yalnız gerçekten
kazanç varsa rapora girer.

### 6. Dosyaya ne yapıyor

`--fix` yalnız zamanları değiştirir, gerisini olduğu gibi bırakır:

- dosyada UTF-8 imzası varsa korunur
- eski Türkçe Windows kodlamasıyla kaydedilmiş dosyalar tanınır ve aynı kodlamayla
  yazılır
- Windows satır sonları Unix satır sonuna çevrilir, her oynatıcı ikisini de okur
- dosyaya dokunmadan **önce** `.bak` kopyası yazılır
- sıfırın önüne taşan satır yok olmaz, uzunluğunu korur

## Bütün seçenekler

```
sub_handyman [VİDEO | --scan DİZİN] [seçenekler]
```

| Seçenek | Ne yapar |
| --- | --- |
| `VİDEO` | Video dosyası ya da klasör (alt klasörler dahil taranır) |
| `--scan DİZİN` | Klasördeki videoları arar: `mkv`, `mp4`, `m4v`, `avi`, `mov`, `webm`, `ts` |
| `--sub DOSYA` | Tahmin etmek yerine bu altyazıyı kullan |
| `--fix` | Ölçülen kaydırmayı uygula |
| `--yes` | Onay sorma |
| `--audio` | Metni bırak, sesle karşılaştır |
| `--json` | Rapor yerine makine okunur çıktı ver |
| `--backup-dir DİZİN` | `.bak` dosyalarını altyazının yanı yerine buraya koy |
| `--lang {en,tr}` | Rapor dili, İngilizce ya da Türkçe |
| `--version` | Sürümü yazdır |

`--help` de aynı dil anahtarına uyuyor: `sub_handyman --help --lang tr`.

### Hangi altyazıyı seçiyor

`Bir Film.mkv` verildiğinde aynı klasörde adı `Bir Film` ile başlayan `.srt`
dosyalarına bakar. Birden çok varsa Türkçe olanları (`.tr.`, `tr.srt`) öne alır.
Karşılaştırma için İngilizce olanları (`*.en.*`, `*.eng.*`) tercih eder. Yanlış
olanı seçiyorsa `--sub` ile istediğini söyle.

### Çıkış kodları

| Kod | Anlamı |
| --- | --- |
| `0` | İş yok, altyazı zaten oturuyor |
| `1` | Kaydırma uygulandı ya da gerekiyordu ama `--fix` verilmedi |
| `2` | Ölçemedi: altyazı yok, karşılaştıracak bir şey yok, video okunamıyor |

Script içinde asıl merak ettiğin şey "her şey yolunda" ile "buna bakmak lazım"
ayrımı oluyor:

```bash
python3 sub_handyman.py --scan /media/filmler --json > rapor.json || echo "bakılacak var"
```

### JSON çıktısı

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

| Alan | Anlamı |
| --- | --- |
| `offset` | Her satıra eklenecek saniye. Eksi, altyazının geç geldiğini gösterir. |
| `overlap` | Altyazının konuşmanın üstüne düşen oranı, 0 ile 1 arası. |
| `overlap_unchanged` | Hiç düzeltme yapılmadan aynı oran. |
| `balance` | Aramanın kullandığı birleşik puan. Çeviri altyazılarında `overlap`'ten düşük çıkması normal. |
| `speed` | Kaydırmadan önce uygulanan hız düzeltmesi. `1.0` ise yok. |
| `checks` | Başta, ortada ve sonda ölçülen kayma. |
| `checks_apart` | Bu üç sayının birbirinden uzaklığı. 1.5 saniyeyi geçerse tek kaydırmaya güvenme. |
| `overlap_one_value` | Parçalı çözüm varsa, tek kaydırmayla ne kadar kalındığı. |
| `parts` | Parçalı çözüm varsa her parçanın başlangıcı, kayması ve replik sayısı: `from`, `offset`, `lines`. |
| `compared_with` | Neyle karşılaştırıldığı. |
| `lines` | Altyazıdaki satır sayısı. |
| `needs_fix` | Bir kaydırma mümkün ve henüz uygulanmadı. |
| `aligned` | Altyazı zaten oturuyor. |
| `applied`, `backup` | Yalnız `--fix` dosyayı gerçekten yazdıysa gelir. |

`--scan` tek video bulsa bile **her zaman liste** döner. Tek `VİDEO` verirsen tek
nesne döner.

## Günlük kullanım

### Değiştirmeden önce bütün klasöre bak

```bash
python3 sub_handyman.py --scan ~/Videolar/Filmler --json > rapor.json
python3 - <<'PY'
import json
for item in json.load(open("rapor.json")):
    if item.get("needs_fix"):
        print(f"{item['subtitle']}: {item['offset']:+.2f} sn (örtüşme {item['overlap']:.0%})")
PY
```

### Açıkça kaymış olanları düzelt

```bash
python3 sub_handyman.py --scan ~/Videolar/Filmler --fix --yes
```

`❔` işaretli dosyalar `--fix` verilse bile atlanır. Kendinden emin biçimde yanlış
yazmak, bozuk olduğunu bildiğin bir altyazıdan daha kötü.

### Her indirmeden sonra çalıştır

```bash
for f in "$indirme_dizini"/*.mkv "$indirme_dizini"/*.mp4; do
  [ -e "$f" ] || continue
  python3 sub_handyman.py "$f" --fix --yes || true
done
```

Ucuz bir adım: videonun içinde altyazı izi varsa yalnız o iz okunur, iş dosya
boyutuyla büyümez.

### Sesle karşılaştır

Tek metin izi yorum olan dosyalar ya da altyazısı görüntünün içine gömülmüş `mp4`
dosyaları için:

```bash
python3 sub_handyman.py movie.mp4 --audio
```

### Altyazıyı kendin seç

Klasörde birkaç dil varsa ve tahmin yanlışsa:

```bash
python3 sub_handyman.py movie.mkv --sub "movie.pt-BR.srt"
```

### Türkçe rapor

```bash
export SUB_HANDYMAN_LANG=tr     # ya da: --lang tr
```

## Ne kadar sürüyor

Raspberry Pi 5 (8 GB, NVMe) ve 15 GB'lık bir 4K dosyayla ölçüldü:

| Neyle karşılaştırıyor | Süre | Nedeni |
| --- | --- | --- |
| Videonun içindeki altyazı izi | yaklaşık 20 sn | ffmpeg yalnız altyazı izini okuyor |
| Klasördeki İngilizce altyazı | yaklaşık 5 sn | saf Python, çözülecek bir şey yok |
| Ses (`--audio`) | 2 ile 4 dk | sesin tamamı taranıyor |

Arama hızlı. Asıl zamanı videoyu okumak alıyor.

## Yapamadıkları

- Zamanlamayı düzeltir, çeviriyi değil. Kötü çeviri kötü kalır.
- Altyazı filmin başka bir sürümüne aitse (uzatılmış sürüm, sinema sürümü, farklı
  sahne sırası) puan düşük çıkar, araç `❔` der ve tahmin yürütmez.
- Ses, müzik ve efektin yüksek olduğu sahnelerde kaba bir rehber. Metinle
  karşılaştırma her zaman tercih edilir, `--audio` senin açıkça istediğin bir şey.
- Her koşuda video başına tek altyazı. Klasörde Türkçe dosya varsa onu, yoksa ilk
  `.srt` dosyasını seçer.
- `.ass` ve `.ssa` dosyaları `--sub` ile ölçülebilir, ama yalnız `.srt` zamanları
  yazılır.
- Değişken kare hızı olan ve kare düşüren dosyalarda kayma ne kaydırmayla ne hız
  düzeltmesiyle anlatılabilir. Üç ölçüm bunu ortaya çıkarır, gerisi elle iş.
- Açılışta ya da jenerikte diyalog çok seyrekse oradaki kayma birkaç saniye kalabilir.
  Ölçülecek replik yoksa araç tahmin yürütmez, dokunmaz.
- Parçalı çözüm basamakları bulur, ama iki dakikadan kısa bir basamağı kaçırabilir.
  Bir sahnede hâlâ kayma görüyorsan dosyayı tekrar ölçmek yeni bir parça çıkarır.

## Bir şey ters giderse

| Ne görüyorsun | Nedeni | Ne yapmalı |
| --- | --- | --- |
| `no .srt next to the video` | Altyazının adı farklı ya da başka klasörde | Videonun adını ver ya da `--sub` kullan |
| `subtitle too short (3 lines)` | Dosya kırpılmış, reklam ya da müzik listesi | `--sub` ile gerçek altyazıyı göster |
| Her filmde `❔` | Sesle karşılaştırmaya düşmüş ve film müzikli | Videonun içinde altyazı izi var mı bak, yoksa metin altyazı bul |
| Düzelttim, oynatıcı hâlâ geç gösteriyor | Oynatıcı ya da sunucu eski kopyayı gösteriyor | Filmi kapat-aç |
| `⚠️ checks at the start, middle and end disagree` | Filmin farklı sürümü ya da değişken kare hızı | Uygulama. O sürüme ait altyazıyı bul |
| `⚠️ timed for a different frame rate` | 23.976, 24 ve 25 karışmış | `--fix` hız düzeltmesini de uygular, sonra son dakikaları kontrol et |
| `measurement failed: …` | ffmpeg yok, video okunamıyor, ses izi yok | Mesajı oku, `ffmpeg -version` kontrol et |
| Script JSON'da hata veriyor | `--scan` liste döner, tek dosya nesne döner | Hep `--scan` kullan ya da iki biçimi de ele al |

Emin olamadığında `--fix` vermeden çalıştır. Ölçmek hiçbir şeyi değiştirmez.

## Testler

```bash
python3 -m unittest discover -s tests -v
```

25 test var. Video ve ffmpeg gerekmiyor. Altyazı dosyası okumayı (UTF-8 imzası,
Windows satır sonları, bozuk girdi, iki, üç ve dört ondalıklı zamanlar), zaman
yazmayı ve sıfırda kırpmayı, bilinen kaymaları kesirli değerler dahil geri
bulmayı, kare hızı farkını yakalamayı, üç ölçümün birbirini tutmasını, ses
taramasının ayrıştırılmasını, eski Türkçe kodlamanın korunmasını, zor adlı
dosyaların bulunmasını, raporun dilini ve basamaklı kaymanın bulunmasını sınıyor.
Basamak testi, yoğun diyaloglu bir referansın yanlış kaymayı haklı göstermesini
de yasaklıyor; parçalar uydurma değil, ölçümle geliyor.

## Lisans

MIT, bkz. [LICENSE](LICENSE).
