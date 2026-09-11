import requests
import time
from datetime import datetime

url = "https://www.kap.org.tr/tr/api/disclosure/list/main"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}

# Daha önce gördüğümüz bildirimlerin ID'lerini hafızada tutacağımız küme
gorulen_bildirimler = set()

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
print("🎯 Filtre: BIST Şirketleri | Özel Durum Açıklaması (ODA) | Devre Kesici Hariç")
print("=" * 80)

# 1. Aşama: İlk açılışta mevcut bildirimleri hafızaya al
print("⏳ Mevcut güncel bildirimler taranıyor...")
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
    print("⚠️ Başlangıç verisi alınamadı, nöbete doğrudan başlanıyor...\n")

# 2. Aşama: Sonsuz döngüde canlı takip
kontrol_sayaci = 0

try:
    while True:
        veriler = bildirimleri_getir()
        
        if veriler:
            # En son gelen ilanlar genelde listenin başında olur, ters çevirip sırayla bakalım
            yeni_gelenler = []
            for ilan in veriler:
                basic = ilan.get("disclosureBasic", {})
                bildirim_id = basic.get("disclosureIndex")
                
                # Eğer daha önce görmediğimiz bir ID geldiyse
                if bildirim_id and bildirim_id not in gorulen_bildirimler:
                    baslik = basic.get("title", "")
                    ozet = basic.get("summary", "")
                    
                    # Filtre: Devre kesici ise hafızaya al ama ekrana basma
                    if "Devre Kesici" in baslik or "Devre Kesici" in ozet:
                        gorulen_bildirimler.add(bildirim_id)
                        continue
                    
                    yeni_gelenler.append((bildirim_id, basic))
                    gorulen_bildirimler.add(bildirim_id)
            
            # Yeni düşen ilanları kronolojik sırayla ekrana yazdır
            for b_id, basic in reversed(yeni_gelenler):
                sirket = basic.get("companyTitle", "Bilinmiyor")
                hisse = basic.get("stockCodes") or basic.get("relatedStocks") or "-"
                baslik = basic.get("title", "Başlık Yok")
                tarih = basic.get("publishDate", "Tarih Yok")
                saat = tarih.split()[-1] if ' ' in tarih else tarih
                link = f"https://www.kap.org.tr/tr/Bildirim/{b_id}"
                
                print("\a") # Windows varsayılan "bip" uyarı sesi çalar
                print(f"🚨 [YENİ BİLDİRİM DÜŞTÜ!] Saat: {saat}")
                print(f"📌 {hisse} | {sirket}")
                print(f"   Konu : {baslik}")
                print(f"   Link : {link}")
                print("-" * 80)
        
        kontrol_sayaci += 1
        # Her 1 dakikada bir (yaklaşık 6 kontrolde bir) ekranda nöbetçinin çalıştığını teyit eden ufak işaret
        if kontrol_sayaci % 6 == 0:
            su_an = datetime.now().strftime("%H:%M:%S")
            print(f"[{su_an}] Nöbetçi aktif... Sistem taranıyor...")

        # Sunucuyu yormamak ve banlanmamak için 10 saniye bekle
        time.sleep(10)

except KeyboardInterrupt:
    print("\n🛑 Canlı nöbetçi durduruldu.")