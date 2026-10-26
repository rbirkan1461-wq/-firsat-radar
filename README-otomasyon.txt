FIRSAT RADAR - OTOMATİK KATALOG TOPLAYICI (MVP)

Dosyalar:
- scrape_catalogs.py: BİM, A101 ve ŞOK kaynaklarını kontrol eder.
- incoming-products.json: bulunan kayıtları üretir.
- requirements.txt: gerekli Python paketleri.

Yerelde çalıştırma:
  python -m pip install -r requirements.txt
  python scrape_catalogs.py

Çıktı:
  incoming-products.json

ÖNEMLİ SINIRLAR:
- Bu bir ilk sürüm toplayıcıdır; kaynak sitelerin HTML yapısı değişirse uyarlama gerekir.
- BİM ve A101 ürün/fiyatları kaynak sayfadan okunmaya çalışılır.
- ŞOK kurumsal sayfası katalog PDF bağlantılarını verebilir; PDF içeriği her zaman makinece okunabilir değildir. Ürün adı/fiyat çıkarılamayan kayıtlar tahmin edilmez.
- Kampanya başlangıç/bitiş tarihleri kaynakta açıkça yakalanmadıkça boş bırakılır.
- Ürünler yayınlanmaz; onay bekleyen taslaklardır.
- Bu script bu bilgisayarda kendi kendine çalışmaz. Sürekli otomasyon için sunucuda/VPS'de zamanlayıcı (cron/GitHub Actions) ve merkezi veritabanı/API gerekir.

Günlük cron örneği (sunucuda):
  15 7 * * * cd /opt/firsat-radar && /usr/bin/python3 scrape_catalogs.py

Yönetim paneli şu an localStorage kullanır. JSON dosyasını içe aktarmak için paneldeki
“Katalogdan ürün aktar” alanı kullanılır. Canlı, çok cihazlı otomatik senkron için
sonraki aşamada API + veritabanı entegrasyonu gereklidir.

Kaynak sayfalar:
BİM: https://www.bim.com.tr/
A101: https://www.a101.com.tr/liste/aldin-aldin
ŞOK: https://kurumsal.sokmarket.com.tr/tr/firsatlar
