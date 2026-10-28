#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transforma feedul public REBS (Home Listings CSV) intr-un feed de PRODUSE pentru Meta/WhatsApp.

Sursa:   https://www.enjoyestate.ro/catalog_home_listing.csv   (publica, fara cheie API)
Iesire:  public/whatsapp_catalog.csv

Utilizare:  python generate_feed.py                 (descarca sursa)
            python generate_feed.py --source fisier.csv   (test local)
"""
import argparse, csv, html, io, json, re, sys, urllib.request
from datetime import date

SOURCE_URL = "https://www.enjoyestate.ro/catalog_home_listing.csv"
OUT_PATH = "public/whatsapp_catalog.csv"
BRAND = "Enjoy Estate"
CURRENCY = "EUR"            # toate preturile sunt in euro
MAX_ADDITIONAL_IMAGES = 9    # Meta accepta pana la 20; 10 in total e suficient

FIELDS = ["id", "title", "description", "availability", "condition", "price",
          "link", "image_link", "additional_image_link", "brand", "product_type",
          "custom_label_0", "custom_label_1"]

TYPE_RO = {"apartment": "Apartamente", "house": "Case și vile", "land": "Terenuri",
           "commercial": "Spații comerciale", "office": "Spații de birouri"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; EnjoyEstateFeedBot/1.0)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig")


def clean(text, limit):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def images(value):
    value = (value or "").strip()
    if not value:
        return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [str(u).strip() for u in data if str(u).strip().startswith("http")]
    except ValueError:
        pass
    return [u.strip() for u in re.split(r"[,\s]+", value) if u.strip().startswith("http")]


def price_eur(value):
    v = re.sub(r"[^\d.,]", "", str(value or "")).replace(",", ".")
    try:
        n = float(v)
    except ValueError:
        return None
    return f"{n:.2f} {CURRENCY}" if n > 0 else None


def condition(row):
    if (row.get("property_type") or "").lower() == "land":
        return "new"          # terenurile nu au "stare"; Meta cere totusi campul
    status = (row.get("construction_status") or "").lower()
    if status in ("under_construction", "new_construction"):
        return "new"
    try:
        year = int(float(row.get("year_built") or 0))
    except ValueError:
        year = 0
    return "new" if year >= date.today().year - 1 else "used"


def convert(rows):
    out, skipped = [], 0
    for r in rows:
        avail = (r.get("availability") or "").strip().lower()
        imgs = images(r.get("image"))
        price = price_eur(r.get("price"))
        link = (r.get("url") or "").strip()
        title = clean(r.get("name"), 150)
        if avail not in ("for_sale", "for_rent") or not (imgs and price and link and title):
            skipped += 1
            continue
        rent = avail == "for_rent"
        if rent:
            title = clean(title + " – închiriere (preț/lună)", 200)
        city = clean(r.get("address.city"), 60)
        desc = clean(r.get("description"), 4800) or title
        if city:
            desc = f"{city}. {desc}"
        out.append({
            "id": r["home_listing_id"].strip(),
            "title": title,
            "description": desc,
            "availability": "in stock",
            "condition": condition(r),
            "price": price,
            "link": link,
            "image_link": imgs[0],
            "additional_image_link": ",".join(imgs[1:1 + MAX_ADDITIONAL_IMAGES]),
            "brand": BRAND,
            "product_type": TYPE_RO.get((r.get("property_type") or "").lower(), "Proprietăți"),
            "custom_label_0": "inchiriere" if rent else "vanzare",
            "custom_label_1": (r.get("property_type") or "").lower(),
        })
    return out, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="fisier CSV local (pentru test)")
    ap.add_argument("--out", default=OUT_PATH)
    a = ap.parse_args()
    text = open(a.source, encoding="utf-8-sig").read() if a.source else fetch(SOURCE_URL)
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "home_listing_id" not in rows[0]:
        sys.exit("EROARE: sursa nu are formatul asteptat (lipseste home_listing_id). Feedul NU a fost actualizat.")
    items, skipped = convert(rows)
    if not items:
        sys.exit("EROARE: nicio proprietate valida. Feedul NU a fost actualizat.")
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader(); w.writerows(items)
    print(f"OK: {len(items)} proprietati in feed, {skipped} omise (fara poza/pret/link sau tranzactionate).")


if __name__ == "__main__":
    main()
