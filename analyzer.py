import requests
from bs4 import BeautifulSoup
import re
import yfinance as yf

def canli_kurlari_al():
    """Piyasa kurunu Yahoo Finance üzerinden alır; hata durumunda yedek kur döner."""
    try:
        usd = yf.Ticker("USDTRY=X").fast_info.last_price
        eur = yf.Ticker("EURTRY=X").fast_info.last_price
        return float(usd), float(eur)
    except Exception:
        return 48.55, 56.32

def sirket_ozkaynak_al(hisse_kodu):
    """BIST hissesinin son bilançosundaki Özkaynak tutarını çeker."""
    if not hisse_kodu:
        return None
    temiz_kod = hisse_kodu.strip().split(",")[0].replace(".IS", "").upper()
    sembol = f"{temiz_kod}.IS"
    
    try:
        ticker = yf.Ticker(sembol)
        bilanco = ticker.balance_sheet
        if not bilanco.empty:
            for alan in ["Total Equity Gross Minority Interest", "Stockholders Equity", "Common Stock Equity"]:
                if alan in bilanco.index:
                    return float(bilanco.loc[alan].iloc[0])
        # Alternatif bakiye kontrolü
        info = ticker.info
        if "totalStockholderEquity" in info and info["totalStockholderEquity"]:
            return float(info["totalStockholderEquity"])
    except Exception as e:
        print(f"⚠️ Öz sermaye hatası ({sembol}): {e}")
    return None

def ilani_analiz_et(bildirim_linki, hisse_kodu=None):
    bildirim_id = bildirim_linki.rstrip("/").split("/")[-1]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    sayfa_url = f"https://www.kap.org.tr/tr/Bildirim/{bildirim_id}"
    try:
        cevap = requests.get(sayfa_url, headers=headers, timeout=10)
        if cevap.status_code != 200:
            print(f"❌ Sayfa verisi alınamadı. HTTP Kod: {cevap.status_code}")
            return None
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return None

    soup = BeautifulSoup(cevap.text, "html.parser")

    # 1. Aşama: Şirket Kodunu Dinamik Yakalama (Doğrulanan Yöntem)
    if not hisse_kodu:
        kod_kutusu = soup.find("div", class_=lambda c: c and "lg:text-[23px]" in c and "font-semibold" in c)
        if kod_kutusu:
            hisse_kodu = kod_kutusu.get_text(strip=True).upper()
        else:
            for d in soup.find_all("div", class_=lambda c: c and "font-semibold" in c):
                metin = d.get_text(strip=True)
                if 3 <= len(metin) <= 5 and metin.isupper():
                    hisse_kodu = metin
                    break

    tam_metin = soup.get_text(separator=" ", strip=True)

    def metni_sayiya_cevir(deger_str):
        if not deger_str:
            return None
        temiz = deger_str.replace(".", "").replace(",", ".")
        try:
            return float(temiz)
        except ValueError:
            return None

    # 2. Aşama: Ham Değerleri Yakalama
    usd_match = re.search(r"([\d\.,]+)\s*(?:ABD Doları|USD|\$)", tam_metin, re.IGNORECASE)
    eur_match = re.search(r"([\d\.,]+)\s*(?:Avro|Euro|EUR|€)", tam_metin, re.IGNORECASE)
    tl_match = re.search(r"([\d\.,]+)\s*(?:TL|Türk Lirası)", tam_metin, re.IGNORECASE)
    oran_match = re.search(r"%\s*([\d\.,]+)", tam_metin)

    ham_usd = metni_sayiya_cevir(usd_match.group(1)) if usd_match else None
    ham_eur = metni_sayiya_cevir(eur_match.group(1)) if eur_match else None
    ham_tl = metni_sayiya_cevir(tl_match.group(1)) if tl_match else None
    ciro_orani = metni_sayiya_cevir(oran_match.group(1)) if oran_match else None

    # 3. Aşama: Canlı Kurlar ve Dönüşüm
    usd_kuru, eur_kuru = canli_kurlari_al()
    nihai_tl_tutar = 0.0
    hesaplama_detayi = "Bilinmiyor"

    if ham_tl:
        nihai_tl_tutar = ham_tl
        hesaplama_detayi = "Doğrudan İlandaki TL Değeri Kullanıldı"
    elif ham_usd:
        nihai_tl_tutar = ham_usd * usd_kuru
        hesaplama_detayi = f"USD -> TL Çevrildi ({ham_usd:,.2f} USD × {usd_kuru:.2f} ₺)"
    elif ham_eur:
        nihai_tl_tutar = ham_eur * eur_kuru
        hesaplama_detayi = f"EUR -> TL Çevrildi ({ham_eur:,.2f} EUR × {eur_kuru:.2f} ₺)"

    # 4. Aşama: Öz Sermaye Kıyaslaması
    oz_sermaye = sirket_ozkaynak_al(hisse_kodu)

    print("\n" + "=" * 70)
    print(f"📌 Bildirim ID          : {bildirim_id}")
    print(f"🏢 Tespit Edilen Hisse  : {hisse_kodu}")
    print("-" * 70)
    print(f"💱 Güncel Piyasa Kuru   : USD = {usd_kuru:.2f} ₺ | EUR = {eur_kuru:.2f} ₺")
    print("-" * 70)
    print("📖 İLANDAN OKUNAN HAM DEĞERLER:")
    print(f"   • Ham USD Tutarı     : {ham_usd:,.2f} USD" if ham_usd else "   • Ham USD Tutarı     : -")
    print(f"   • Ham EUR Tutarı     : {ham_eur:,.2f} EUR" if ham_eur else "   • Ham EUR Tutarı     : -")
    print(f"   • Ham TL Tutarı      : {ham_tl:,.2f} TL" if ham_tl else "   • Ham TL Tutarı      : -")
    print(f"   • İlandaki Ciro Oranı: %{ciro_orani}" if ciro_orani else "   • İlandaki Ciro Oranı: -")
    print("-" * 70)
    print(f"🎯 NİHAİ TL TUTARI      : {nihai_tl_tutar:,.2f} TL")
    print(f"⚙️  Hesaplama Yöntemi    : {hesaplama_detayi}")
    print("-" * 70)

    if oz_sermaye:
        oran = (nihai_tl_tutar / oz_sermaye) * 100
        print(f"🏛️ Şirket Öz Sermayesi  : {oz_sermaye:,.2f} TL")
        print(f"📊 Oran (İş / Özser)    : %{oran:.2f}")
        print("-" * 70)
        if nihai_tl_tutar > oz_sermaye:
            print("🚨 KARAR: [ÖZ SERMAYEDEN BÜYÜK!] (Şirket ölçeğini aşan dev anlaşma)")
        else:
            print("ℹ️ KARAR: [Öz sermayeden büyük değil]")
    else:
        print("⚠️ Şirketin bilanço verisi Yahoo Finance üzerinden çekilemedi.")

    print("=" * 70 + "\n")

    return {
        "hisse": hisse_kodu,
        "ham_usd": ham_usd,
        "ham_eur": ham_eur,
        "ham_tl": ham_tl,
        "usd_kuru": usd_kuru,
        "nihai_tl": nihai_tl_tutar,
        "oz_sermaye": oz_sermaye,
        "buyuk_mu": (nihai_tl_tutar > oz_sermaye) if oz_sermaye else False
    }

if __name__ == "__main__":
    # Test linki (Hisse kodu vermene gerek yok, kendisi bulur)
    test_linki = "https://www.kap.org.tr/tr/Bildirim/1660591"
    ilani_analiz_et(test_linki)