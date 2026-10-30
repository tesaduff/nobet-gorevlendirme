# NöbetGörev — Nöbet Çizelgesi ve Öğretmen Görevlendirme

Okulda gelmeyen (raporlu, izinli, görevli) öğretmenlerin boş kalan derslerine
nöbetçi öğretmenleri **adil** şekilde otomatik atayan Windows programı.

## Kurulum

1. [Releases](https://github.com/tesaduff/nobet-gorevlendirme/releases/latest) sayfasından
   **`NobetGorevlendirme-Kurulum.exe`** dosyasını indirin ve çift tıklayın.
2. Windows "bilinmeyen yayımcı" uyarısı verirse **Ek bilgi → Yine de çalıştır** seçin.
3. Kurulum soru sormadan biter, masaüstüne **NöbetGörev** kısayolu eklenir
   ve program açılır. Yönetici izni gerekmez.

Programı kaldırırken (Ayarlar → Uygulamalar) verilerin de silinip silinmeyeceği sorulur. Başka
bir okula/bilgisayara kurulan program her zaman boş başlar.

Kurmadan kullanmak isterseniz aynı sayfadaki taşınabilir `NobetGorevlendirme.exe` dosyasını
Masaüstü gibi bir klasöre koyup çalıştırın.

## Kayıtlar (Excel)

Her kayıttan sonra **Belgeler\Nöbet Görevlendirme\Kayıtlar.xlsx** dosyası yenilenir. Dosyada
şu sayfalar bulunur: Görevlendirmeler, Devamsızlık, Aylık Özet, Ders Programı ve Nöbet Çizelgesi.
Dosyanın konumunu Ayarlar'dan değiştirebilirsiniz. Excel dosyası açıkken yazılamaz; programdaki
kayıtlar yine de korunur ve dosya bir sonraki kayıtta güncellenir.

## Kullanım

0. **Okul Bilgileri** → okul adı, il/ilçe ve logo. Yeni kurulumda
   program bu sayfayla açılır.
1. **Ders Programı** → *Yeni ders programı yükle* (e-Okul/MEBBİS PDF'i veya Excel). Okunanları
   kontrol edip kaydedin. Hemen ardından **İdarecileri belirle** ile her idarecinin görevini (Okul
   Müdürü / Müdür Yardımcısı / Diğer idareci) seçin; onlara otomatik görev verilmez.
2. **Nöbet Çizelgesi** → *Otomatik oluştur*, *Hazır çizelgem var (PDF/Excel)* veya *Elle gir*. Adım adım: ay ve öğretmenler (muaflar ve
   mazeretleri), nöbet yerleri ve kişi sayıları, seçenekler, kurallar (sabitle, beraber, ayrı, gün
   kısıtı), dağıt. Önizleyip yazdırın, **Kaydet ve kullan** deyin. Hazır çizelgeniz varsa
   *PDF/Excel'den yükle* ile de alabilirsiniz.
3. **Görevlendirme** → tarihi seçin, gelmeyen öğretmenin durumunu (Raporlu, İzinli, Görevli…)
   seçin, *Devam*, *Görevlendir*. İsterseniz satır satır değiştirin, sonra **Onayla** deyin;
   görevlendirme ancak onaylanınca istatistiğe işlenir.
4. **Aylık Rapor** → kim bu ay ve bu eğitim yılında kaç derse girdi.

Yeni ay başlayınca program uyarır ve yeni nöbet çizelgesini oluşturmayı önerir.

### Dağıtım kuralları

1. Gelmeyen öğretmenin her dersi için yalnızca **o günün nöbetçi öğretmenlerine**, o saatte
   **dersi boş olanlara** görev verilir.
2. Birden fazla uygun nöbetçi varsa **bu eğitim yılında en az derse girmiş olan** seçilir (eşitlikte
   bu ay, sonra tüm zamanlar). Böylece sayılar eşitlenir.
3. O saatte boş nöbetçi yoksa ders **boş bırakılır** (hiç isim yazılmaz, kırmızı satır); sonuç
   ekranındaki açılır listeden elle seçilir.
4. **Ders kısıtları:** mazereti olan bir nöbetçiye belli gün ve saatlerde (ör. çarşamba 1. ve
   4. ders) görev verilmez; o saatte dersi boş olsa bile. Görevlendirme ekranından veya
   Ayarlar'dan eklenir.
5. Ayarlar'dan isteğe bağlı *"bir nöbetçiye günde en fazla X ders"* sınırı konabilir.

Yalnızca **onaylanan** görevlendirmeler sayımlara girer.

### Desteklenen belge biçimleri

- PDF (metin içeren; taranmış resim PDF'ler okunamaz), Excel (.xlsx) ve CSV.
- Öğretmen bazlı programlar: her sayfada bir öğretmen.
- Sınıf bazlı programlar: her sayfada bir şube; hücrede ders ve öğretmen adı.
- Çarşaf programlar: tek tabloda bütün öğretmenler, sütunlarda gün ve saat.
- Devrik tablolar: günler satırlarda.
- Nöbet çizelgeleri: gün veya tarih satırlarda ya da sütunlarda olabilir, nöbet yerleriyle birlikte
  veya düz metin olarak.

## Güncelleme

**Ayarlar → Güncellemeleri denetle.** Yeni sürüm varsa program indirir, kendini değiştirir ve
yeniden açılır. İsterseniz açılışta otomatik denetleme de açılabilir.

Veriler `%APPDATA%\NobetGorevlendirme\veri.db` dosyasında saklanır, güncelleme bu verileri
silmez. Program her gün otomatik yedek alır: **Belgeler\Nöbet Görevlendirme\Yedekler** (son 30 gün).

## Geliştirici notları

```bash
pip install -r requirements.txt
python run.py            # programı çalıştır
python -m pytest -q      # testler (reportlab gerekir)
```

Yeni sürüm yayınlamak için `nobet/version.py` içindeki sürüm numarasını artırın
(ör. `1.0.1`), `SURUM_NOTLARI.md` dosyasını güncelleyin ve `main`'e gönderin. GitHub Actions
testleri çalıştırır, Windows exe'sini derler ve `v1.0.1` adıyla Releases'a yükler.
Sürüm numarası değişmeyen gönderimlerde yalnızca testler çalışır.
