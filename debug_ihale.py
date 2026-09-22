import requests
from bs4 import BeautifulSoup
import re

url = "https://www.kap.org.tr/tr/Bildirim/1664983"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print(f"📡 İlan çekiliyor: {url}")
r = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(r.text, "html.parser")
html_metin = r.text

print("\n" + "=" * 60)
print("1. HTML İÇİNDEKİ TAKSONOMİ ETİKETLERİ:")
print("=" * 60)

# KAP'ın oda_TenderValue etiketini ara
for satir in html_metin.splitlines():
    if any(k in satir.lower() for k in ["oda_tendervalue", "ihale bedeli"]):
        print("Bulunan Satır:", satir.strip()[:140])

print("\n" + "=" * 60)
print("2. DÜZELTİLMİŞ AYIKLAMA TESTİ:")
print("=" * 60)

tam_metin = soup.get_text(separator=" ", strip=True)

# Arada 'Tender Value', 'KDV hariç' vb. olsa bile tutarı yakalayan desen
pb_desen = r"(?:usd|\$|eur|€|tl|try|₺)"
desen = rf"ihale\s+bedeli(?!\s*(?:nden)?\s*ortakl[ıi]k)\b.{{0,50}}?([\d\.,]{{3,}})\s*({pb_desen})?"

eslesme = re.search(desen, tam_metin, re.IGNORECASE | re.DOTALL)
if eslesme:
    print(f"✅ Rakam Başarıyla Yakalandı: {eslesme.group(1)} {eslesme.group(2) or 'TL'}")
else:
    print("❌ Yakalanamadı.")