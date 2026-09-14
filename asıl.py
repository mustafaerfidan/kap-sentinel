import requests
import time
from datetime import datetime
from analyzer import ilani_analiz_et

url = "https://www.kap.org.tr/tr/api/disclosure/list/main"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}

gorulen_bildirimler = set()

def tr_kucult(metin):
    """Türkçe karakter ve harf büyüklüğü farklarını sıfırlar."""
    if not metin:
        return ""
    donusum = {
        "İ": "i", "I": "i", "ı": "i",
        "Ş": "s", "ş": "s",
        "Ğ": "g", "ğ": "g",
        "Ü": "u", "ü": "u",
        "Ö": "o", "ö": "o",
        "Ç": "c", "ç": "c"
    }
    temiz = metin
    for buyuk, kucuk in donusum.items():
        temiz = temiz.replace(buyuk, kucuk)
    return temiz.lower()

def bildirim_turu_belirle(baslik, ozet):
    """Metni inceleyip ilanın türünü ayrıştırır."""
    metin = tr_kucult(f"{baslik} {ozet}")
    
    if "yeni is iliskisi" in metin:
        return "YENI_IS"
    elif "ihale sureci / sonucu" in metin or "ihale sureci/sonucu" in metin:
        return "IHALE"
    return None

def bildirimleri_getir():
    bugun = datetime.now().strftime("%d.%m.%Y")
    payload = {
        "fromDate": bugun,
        "toDate": bugun,
        "disclosureTypes": ["ODA"],
        "memberTypes": ["IGS"],
        "mkkMemberOid": None
    }
    
    try:
        cevap = requests.post(url, json=payload, headers=headers, timeout=10)
        if cevap.status_code == 200:
            return cevap.json()
    except Exception as e:
        print(f"⚠️ Bağlantı hatası: {e}")
    return None

print("=" * 80)
print("🛡️  KAP CANLI NÖBETÇİ BAŞLATILDI")
print("🎯 Hedef 1: Yeni İş İlişkisi -> Doğrudan analyzer.py motoruna aktarılır")
print("🎯 Hedef 2: İhale Süreci / Sonucu -> Ekrana detaylı kart ve link basılır")
print("=" * 80)

print("⏳ Güncel bildirimler taranıyor...")
ilk_veri = bildirimleri_getir()

if ilk_veri:
    for ilan in ilk_veri:
        basic = ilan.get("disclosureBasic", {})
        bildirim_id = basic.get("disclosureIndex")
        if bildirim_id:
            gorulen_bildirimler.add(bildirim_id)
    print(f"✅ Başlangıç tamamlandı. Hafızadaki mevcut ilan sayısı: {len(gorulen_bildirimler)}")
    print("👀 Canlı nöbet başladı, yeni bildirim bekleniyor... (Durdurmak için: Ctrl + C)\n")
else:
    print("⚠️ Başlangıç verisi alınamadı, nöbete başlanıyor...\n")

kontrol_sayaci = 0

try:
    while True:
        veriler = bildirimleri_getir()
        
        if veriler:
            yeni_gelenler = []
            for ilan in veriler:
                basic = ilan.get("disclosureBasic", {})
                bildirim_id = basic.get("disclosureIndex")
                
                if bildirim_id and bildirim_id not in gorulen_bildirimler:
                    baslik = basic.get("title", "")
                    ozet = basic.get("summary", "")
                    
                    temiz_baslik = tr_kucult(baslik)
                    temiz_ozet = tr_kucult(ozet)
                    if "devre kesici" in temiz_baslik or "devre kesici" in temiz_ozet:
                        gorulen_bildirimler.add(bildirim_id)
                        continue
                    
                    yeni_gelenler.append((bildirim_id, basic))
                    gorulen_bildirimler.add(bildirim_id)
            
            for b_id, basic in reversed(yeni_gelenler):
                sirket = basic.get("companyTitle", "Bilinmiyor")
                hisse = basic.get("stockCodes") or basic.get("relatedStocks") or "-"
                baslik = basic.get("title", "Başlık Yok")
                ozet = basic.get("summary") or "Özet Bilgi Bulunmuyor"
                tarih = basic.get("publishDate", "Tarih Yok")
                saat = tarih.split()[-1] if ' ' in tarih else tarih
                link = f"https://www.kap.org.tr/tr/Bildirim/{b_id}"
                
                tur = bildirim_turu_belirle(baslik, ozet)
                
                # Durum 1: Yeni İş İlişkisi -> Analiz motoruna sevk et
                if tur == "YENI_IS":
                    print("\a\a")
                    print("\n" + "#" * 80)
                    print(f"💼 [YENİ İŞ İLİŞKİSİ BULUNDU] Saat: {saat} | Şirket: {hisse} - {sirket}")
                    print(f"🚀 Link analiz motoruna gönderildi: {link}")
                    print("#" * 80)
                    
                    hisse_temiz = hisse.split(",")[0].strip() if hisse != "-" else None
                    ilani_analiz_et(link, hisse_kodu=hisse_temiz)

                # Durum 2: İhale Süreci / Sonucu -> Detaylı ihale kartını ekrana bas
                elif tur == "IHALE":
                    print("\a\a\a")
                    print("\n" + "=" * 80)
                    print("🏆 [İHALE SONUCU BİLDİRİMİ YAKALANDI!]")
                    print(f"🏢 Şirket : {hisse} ({sirket})")
                    print(f"📅 Tarih  : {tarih}")
                    print(f"📌 Konu   : {baslik}")
                    print(f"📝 Özet   : {ozet}")
                    print(f"🔗 Link   : {link}")
                    print("=" * 80 + "\n")

                # Diğer genel bildirimler (Akış kaydı)
                else:
                    print(f"ℹ️ [AKIS] {saat} | {hisse} | {baslik}")

        kontrol_sayaci += 1
        if kontrol_sayaci % 6 == 0:
            su_an = datetime.now().strftime("%H:%M:%S")
            print(f"[{su_an}] Nöbetçi aktif... Sistem taranıyor...")

        time.sleep(10)

except KeyboardInterrupt:
    print("\n🛑 Canlı nöbetçi durduruldu.")