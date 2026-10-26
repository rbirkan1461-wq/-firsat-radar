#!/usr/bin/env python3
# Fırsat Radar - katalog toplayıcı (MVP)
# Kaynak sayfaları günlük kontrol eder; ürünleri taslak JSON olarak üretir.
import json, re, hashlib, sys, logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

OUT = Path(__file__).with_name('incoming-products.json')
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; FirsatRadarBot/1.0; +catalog-monitor)'}
SOURCES = {
 'BİM': 'https://www.bim.com.tr/',
 'A101': 'https://www.a101.com.tr/liste/aldin-aldin',
 'ŞOK': 'https://kurumsal.sokmarket.com.tr/tr/firsatlar',
}
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def get(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text, r.url

def price_num(s):
    s = s.replace('\xa0',' ').strip()
    m = re.search(r'(?:₺\s*)?([\d.]+,[0-9]{2})\s*(?:₺|TL)?', s)
    if not m: return None
    return float(m.group(1).replace('.','').replace(',','.'))

def slug_id(store, name, price):
    raw = f'{store}|{name.casefold()}|{price}'.encode('utf-8')
    return hashlib.sha1(raw).hexdigest()[:16]

def category(name):
    n=name.casefold()
    if any(x in n for x in ['tv','televizyon','telefon','kulaklık','qled','led','tablet','bilgisayar']): return 'Elektronik'
    if any(x in n for x in ['çamaşır','bulaşık','buzdolabı','süpürge','ütü','mikser','kahve makinesi']): return 'Beyaz eşya' if any(x in n for x in ['çamaşır','bulaşık','buzdolabı']) else 'Küçük ev aletleri'
    if any(x in n for x in ['yorgan','yastık','halı','tencere','sahan','kavanoz','borcam','nevresim']): return 'Ev & yaşam'
    return 'Diğer'

def make_item(store, name, price, url, image='', start='', end='', source_note=''):
    name=re.sub(r'\s+',' ',name).strip(' -|')
    if not name or price is None or len(name)<3: return None
    return {'id':slug_id(store,name,price),'name':name,'store':store,'category':category(name),
      'marketPrice':str(price),'onlinePrice':'','url':url,'image':image,'start':start,'end':end,
      'notes':f'Otomatik kaynak: {source_note or url} · Kontrol: {datetime.now().strftime("%d.%m.%Y %H:%M")}',
      'published':False,'sourceUrl':url,'checkedAt':datetime.now(timezone.utc).isoformat()}

def scrape_bim():
    html, base=get(SOURCES['BİM']); soup=BeautifulSoup(html,'html.parser'); out=[]
    # BİM sayfasındaki ürün adları h2 ve fiyat bağlantılarında sunuluyor.
    for h in soup.find_all(['h2','h3']):
        name=h.get_text(' ',strip=True)
        if not name or len(name)>140: continue
        parent=h.parent
        area=' '.join(parent.get_text(' ',strip=True).split()) if parent else ''
        if len(area)<len(name): area=name
        p=price_num(area)
        if p is None:
            # fiyat çoğunlukla ürün kartının birkaç sonraki kardeşinde
            node=h
            for _ in range(4):
                node=node.parent if node and node.parent else node
                if node:
                    p=price_num(node.get_text(' ',strip=True))
                    if p is not None: break
        if p is None: continue
        img=(parent.find('img') if parent else None) or h.find_next('img')
        image=urljoin(base, img.get('src') or img.get('data-src') or '') if img else ''
        out.append(make_item('BİM',name,p,base,image,source_note='BİM resmi web sitesi'))
    return out

def scrape_a101():
    html, base=get(SOURCES['A101']); soup=BeautifulSoup(html,'html.parser'); out=[]
    # Ürün kartları farklı sürümlerde değişebildiği için başlıkların en yakın kart kapsayıcısı taranır.
    for h in soup.find_all(['h2','h3']):
        name=h.get_text(' ',strip=True)
        if not name or len(name)>180: continue
        node=h
        best=None
        for _ in range(5):
            if not node.parent: break
            node=node.parent
            txt=node.get_text(' ',strip=True)
            p=price_num(txt)
            if p is not None and len(txt)<900:
                best=(node,p); break
        if not best: continue
        card,p=best
        a=card.find('a',href=True); img=card.find('img')
        url=urljoin(base,a['href']) if a else base
        image=urljoin(base,(img.get('src') or img.get('data-src') or '')) if img else ''
        out.append(make_item('A101',name,p,url,image,source_note='A101 Aldın Aldın resmi liste'))
    return out

def scrape_sok():
    # ŞOK kurumsal sayfası katalog PDF bağlantılarını yayınlar. PDF metni ürün/fiyat vermiyorsa
    # tahmin yapılmaz; katalog bağlantısı inceleme kuyruğuna metadata olarak yazılır.
    html, base=get(SOURCES['ŞOK']); soup=BeautifulSoup(html,'html.parser'); out=[]
    for a in soup.find_all('a',href=True):
        href=urljoin(base,a['href']); label=' '.join(a.get_text(' ',strip=True).split())
        if '.pdf' in href.lower() or 'indir' in label.casefold():
            name=label or 'ŞOK haftalık aktüel katalog'
            item={'id':slug_id('ŞOK',name,0),'name':name,'store':'ŞOK','category':'Diğer',
              'marketPrice':'','onlinePrice':'','url':href,'image':'','start':'','end':'',
              'notes':'Katalog bağlantısı otomatik bulundu; ürün ve fiyatlar doğrulanmadan yayınlanmaz.',
              'published':False,'sourceUrl':href,'checkedAt':datetime.now(timezone.utc).isoformat(),'needsReview':True}
            out.append(item)
    return out

def main():
    all_items=[]; status={}
    for store, fn in [('BİM',scrape_bim),('A101',scrape_a101),('ŞOK',scrape_sok)]:
        try:
            items=fn(); status[store]={'ok':True,'count':len(items)}; all_items.extend(items)
            logging.info('%s: %s kayıt bulundu',store,len(items))
        except Exception as e:
            status[store]={'ok':False,'error':str(e)}; logging.exception('%s kaynağı okunamadı',store)
    # Fiyatlı ürünlerde tekrarları ayıkla; fiyatı olmayan ŞOK katalog kayıtlarını ayrıca koru.
    seen=set(); unique=[]
    for x in all_items:
        key=(x['store'],x['name'].casefold(),x.get('marketPrice',''))
        if key not in seen: seen.add(key); unique.append(x)
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'status':status,'products':unique}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(OUT),'status':status,'total':len(unique)},ensure_ascii=False,indent=2))
    # exit non-zero only if every source failed
    if not any(x.get('ok') for x in status.values()): sys.exit(2)

if __name__=='__main__': main()
