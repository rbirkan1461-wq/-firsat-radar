#!/usr/bin/env python3
"""Firsat Radar: scheduled collector for public weekly-deal pages.
Only products with a clear title and parsed TRY price are emitted. This is a
best-effort collector: source markup can change and every item keeps provenance.
"""
from __future__ import annotations
import json, re, hashlib, logging, os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
PRODUCTS_FILE = DATA / "products.json"
REPORT_FILE = DATA / "scrape-report.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FirsatRadar/1.0; +https://firsat-radar.pages.dev)"}
SOURCES = {
    "BİM": "https://www.bim.com.tr/",
    "A101": "https://www.a101.com.tr/liste/aldin-aldin",
    "ŞOK": "https://kurumsal.sokmarket.com.tr/tr/firsatlar",
}
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def price_num(value):
    if value is None: return None
    s = str(value).replace("\xa0", " ").strip()
    # Structured data may use 1234.5; Turkish pages usually use 1.234,50 TL.
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        try: return round(float(s), 2)
        except ValueError: return None
    m = re.search(r"(?<!\d)(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})(?!\d)", s)
    if not m: return None
    try: return round(float(m.group(1).replace(".", "") + "." + m.group(2)), 2)
    except ValueError: return None


def category(name):
    n = name.casefold()
    if any(x in n for x in ["tv", "televizyon", "telefon", "kulaklık", "qled", "led", "tablet", "bilgisayar"]): return "Elektronik"
    if any(x in n for x in ["ütü", "süpürge", "mikser", "kahve makinesi", "airfryer", "fritöz"]): return "Küçük ev aletleri"
    if any(x in n for x in ["çamaşır", "bulaşık", "buzdolabı", "derin dondurucu"]): return "Beyaz eşya"
    if any(x in n for x in ["yorgan", "yastık", "halı", "tencere", "sahan", "kavanoz", "borcam", "nevresim"]): return "Ev & yaşam"
    return "Diğer"


def stable_id(store, name, url):
    raw = f"{store}|{name.casefold()}|{url}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def make_item(store, name, price, product_url, image_url, source_url, method):
    name = re.sub(r"\s+", " ", str(name or "")).strip(" -|\n\t")
    price = price_num(price)
    if len(name) < 4 or len(name) > 180 or price is None or price <= 0: return None
    now = datetime.now(timezone.utc).isoformat()
    product_url = urljoin(source_url, product_url or source_url)
    image_url = urljoin(source_url, image_url) if image_url else ""
    # The market listing itself is verified as the source of this market price.
    # Online comparison is deliberately left blank until an exact model match exists.
    return {
        "id": stable_id(store, name, product_url), "name": name, "store": store,
        "category": category(name), "marketPrice": price, "onlinePrice": "",
        "url": product_url, "image": image_url, "start": "", "end": "",
        "notes": f"Otomatik katalog taraması ({method}). İnternet fiyatı henüz doğrulanmadı.",
        "published": True, "sourceUrl": source_url, "checkedAt": now,
        "priceVerified": True, "onlinePriceVerified": False, "needsReview": False,
    }


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text, r.url


def walk_jsonld(obj):
    if isinstance(obj, list):
        for x in obj: yield from walk_jsonld(x)
    elif isinstance(obj, dict):
        yield obj
        graph = obj.get("@graph")
        if graph: yield from walk_jsonld(graph)


def structured_products(store, html, base):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try: data = json.loads(tag.string or tag.get_text())
        except Exception: continue
        for obj in walk_jsonld(data):
            typ = obj.get("@type", [])
            if isinstance(typ, str): typ = [typ]
            if not any("Product" in str(t) for t in typ): continue
            name = obj.get("name")
            offers = obj.get("offers", {})
            if isinstance(offers, list): offers = offers[0] if offers else {}
            if isinstance(offers, dict) and "price" not in offers and "offers" in offers:
                nested = offers.get("offers")
                offers = nested[0] if isinstance(nested, list) and nested else nested or {}
            price = offers.get("price") if isinstance(offers, dict) else None
            currency = offers.get("priceCurrency", "TRY") if isinstance(offers, dict) else "TRY"
            if currency not in ("TRY", "TL"): continue
            image = obj.get("image", "")
            if isinstance(image, list): image = image[0] if image else ""
            url = obj.get("url") or offers.get("url", "") if isinstance(offers, dict) else obj.get("url", "")
            item = make_item(store, name, price, url, image, base, "JSON-LD ürün verisi")
            if item: found.append(item)
    return found


def fallback_cards(store, html, base):
    """Conservative fallback: only card-like elements with title and price."""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    selectors = ["article", "[class*=product]", "[class*=Product]", "[data-product]"]
    seen_nodes = set()
    for selector in selectors:
        for card in soup.select(selector)[:500]:
            if id(card) in seen_nodes: continue
            seen_nodes.add(id(card))
            text = " ".join(card.get_text(" ", strip=True).split())
            price = price_num(text)
            if price is None: continue
            title_node = card.select_one("h2,h3,[class*=title],[class*=name]")
            name = title_node.get_text(" ", strip=True) if title_node else ""
            if not name: continue
            link = card.find("a", href=True)
            img = card.find("img")
            item = make_item(store, name, price, link.get("href") if link else base,
                             (img.get("src") or img.get("data-src") or "") if img else "", base,
                             "ürün kartı HTML taraması")
            if item: found.append(item)
    return found


def scrape_store(store, url):
    html, final_url = fetch(url)
    items = structured_products(store, html, final_url)
    method = "JSON-LD"
    if not items:
        items = fallback_cards(store, html, final_url)
        method = "HTML kart taraması"
    # Deduplicate on canonical item id.
    dedup = {x["id"]: x for x in items}
    logging.info("%s: %d ürün (%s)", store, len(dedup), method)
    return list(dedup.values()), {"ok": True, "count": len(dedup), "method": method, "url": final_url}


def main():
    previous = {x.get("id"): x for x in json.loads(PRODUCTS_FILE.read_text("utf-8")).get("products", [])} if PRODUCTS_FILE.exists() else {}
    current, status = {}, {}
    for store, url in SOURCES.items():
        try:
            items, info = scrape_store(store, url)
            for item in items:
                # Keep first-seen date; update the latest observed price and timestamp.
                old = previous.get(item["id"], {})
                item["firstSeenAt"] = old.get("firstSeenAt", item["checkedAt"])
                current[item["id"]] = item
            status[store] = info
        except Exception as exc:
            logging.exception("%s taranamadı", store)
            status[store] = {"ok": False, "error": str(exc), "url": url}
    # Keep previously discovered products if a source temporarily fails; mark stale.
    for pid, old in previous.items():
        if pid not in current:
            store = old.get("store")
            if not status.get(store, {}).get("ok"):
                old["stale"] = True
                current[pid] = old
    payload = {"generatedAt": datetime.now(timezone.utc).isoformat(),
               "status": status, "products": sorted(current.values(), key=lambda x: x.get("checkedAt", ""), reverse=True)}
    PRODUCTS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(json.dumps({"generatedAt": payload["generatedAt"], "status": status,
                                       "totalProducts": len(current)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "totalProducts": len(current)}, ensure_ascii=False, indent=2))
    if not any(v.get("ok") for v in status.values()): raise SystemExit("All sources failed")

if __name__ == "__main__": main()
