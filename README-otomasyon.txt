FIRSAT RADAR - OTOMATİK KATALOG TARAMA (İLK OTOMASYON SÜRÜMÜ)

Kurulum:
1) Depodaki mevcut index.html ve scrape_catalogs.py dosyalarını bu pakettekilerle değiştir.
2) data/ klasörünü ve içindeki products.json + scrape-report.json dosyalarını yükle.
3) .github/workflows/catalog-scan.yml dosyasını aynı yol ile GitHub deposuna ekle.
4) GitHub deposunda Settings > Actions > General bölümünde Actions izinleri açık olmalı.
5) Actions sekmesinden "Firsat Radar - katalog tarama" iş akışını Run workflow ile ilk kez elle çalıştır.
6) Başarılı taramadan sonra bot data/products.json dosyasını commit eder; Cloudflare Pages GitHub push ile siteyi tekrar yayınlar.

Zamanlama: Her gün 06:00 Türkiye saati (03:00 UTC).

Bu sürüm BİM/A101/ŞOK resmi sayfalarını taramayı dener. Yalnızca ürün adı ve fiyatı açıkça çıkarılabilen ürünleri ürün akışına ekler. Kaynak ve kontrol zamanı saklanır. Site, data/products.json içindeki published=true ve priceVerified=true ürünleri gösterir.

ÖNEMLİ SINIRLAR:
- Mağazaların sayfa yapısı ve bot korumaları değişebilir; her çalışmada Actions sonuçlarını kontrol et.
- ŞOK katalog PDF'leri ve dinamik sayfalar bu ilk sürümde tam ürün OCR/parsing kapsamına alınmadı.
- İnternet mağazası fiyatı henüz otomatik eşleştirilmiyor. onlinePrice boş kalır; site "Fiyat araştırılıyor" gösterir. Aynı model/ürün kodu doğrulanmadan fiyat kıyaslaması yapılmaz.
- Bu ilk sürüm, bulunan market ürünlerini otomatik olarak sitede gösterir; yanlış eşleşme/bozuk kaynak ihtimaline karşı kaynak bağlantısı ve kontrol zamanı tutulur.
- Herhangi bir mağazanın kullanım koşullarını ve robots.txt kurallarını ihlal edecek şekilde istek sıklığını artırma.
