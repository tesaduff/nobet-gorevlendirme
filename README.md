# Nöbetçi Öğretmen Görevlendirme

Okulda gelmeyen (raporlu, izinli, görevli) öğretmenlerin boş kalan derslerine
nöbetçi öğretmenleri **adil** şekilde otomatik atayan Windows programı.

## Kurulum

1. [Releases](https://github.com/tesaduff/nobet-gorevlendirme/releases/latest) sayfasından
   `NobetGorevlendirme.exe` dosyasını indirin.
2. Dosyayı **Masaüstü** veya **Belgeler** gibi bir klasöre koyun. Program Files'a koymayın,
   çünkü güncelleme o klasöre yazamaz.
3. Çift tıklayıp açın. Windows "bilinmeyen yayımcı" uyarısı verirse
   **Ek bilgi → Yine de çalıştır** seçin.

## Kullanım

1. **Ders Programı** sekmesi → *Yeni ders programı yükle*. e-Okul/MEBBİS'ten aldığınız
   PDF'i veya Excel dosyasını seçin. Okunan program önizlemede görünür. Yanlış okunan isimleri
   düzeltip *program şu tarihten itibaren geçerli* tarihini girerek kaydedin.
   Program değişirse yeni dosyayı yeni bir tarihle yükleyin. Eski günler eski programla kalır.
2. **Nöbet Çizelgesi** sekmesi → her ay o ayın çizelgesini yükleyin. İsimler ders
   programındaki öğretmenlerle otomatik eşleştirilir. Kaydetmeden önce kontrol edip
   düzeltebilirsiniz.
3. **Günlük Görevlendirme** sekmesi → tarihi seçin, gelmeyen öğretmenlerin durumunu
   *Raporlu / İzinli / Görevli / Diğer* yapın ve **Görevlendirmeyi Oluştur**'a basın.
   Sonuçta isterseniz görevlendirilen kişiyi elle değiştirin, sonra **Kaydet**. Çizelgeyi Excel'e
   aktarabilir veya yazdırabilirsiniz.
4. **Aylık Rapor** → kim bu ay kaç derse girdi, nöbetçi olarak mı yoksa boş saatinde mi.

### Dağıtım kuralları

1. Gelmeyen öğretmenin her dersi için önce o saatte **dersi olmayan nöbetçi öğretmen** aranır.
2. Birden fazla uygun nöbetçi varsa **bu ay en az derse girmiş olan** seçilir. Eşitlik olursa
   sırayla bugün en az derse giren, sonra tüm zamanlarda en az derse giren seçilir.
   Böylece ay sonunda sayılar eşitlenir.
3. Boş nöbetçi yoksa o gün okulda olan ve **o saatte dersi olmayan nöbetçi olmayan öğretmen**
   atanır. İki dersi arasında boşluğu olan öğretmene öncelik verilir. Bu satırlar **sarı** renkle
   ve *"nöbetçi değil"* notuyla gösterilir.
4. Kimse boş değilse ders **kırmızı** renkle *"atanamadı"* olarak işaretlenir.
5. Ayarlar'dan isteğe bağlı *"bir nöbetçiye günde en fazla X ders"* sınırı konabilir.

Yalnızca **kaydedilen** günler aylık sayımlara girer.

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
silmez. Ayarlar sekmesinden yedek alabilirsiniz.

## Geliştirici notları

```bash
pip install -r requirements.txt
python run.py            # programı çalıştır
python -m pytest -q      # testler (reportlab gerekir)
```

Yeni sürüm yayınlamak için önce `SURUM_NOTLARI.md` dosyasını güncelleyin, sonra etiket gönderin:

```bash
git tag v1.0.1 && git push origin v1.0.1
```

GitHub Actions testleri çalıştırır, Windows exe'sini derler ve Releases'a yükler.
