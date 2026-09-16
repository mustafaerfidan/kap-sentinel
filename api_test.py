import requests
import time
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from analyzer import ilani_analiz_et, telegram_bildirim_gonder

url = "https://www.kap.org.tr/tr/api/disclosure/list/main"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest"
}

gorulen_bildirimler = set()

def tr_kucult(metin):
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

def bildirim_turu_belirle(baslik):
    # Sadece ve sadece resmi başlık/konu alanına bakar, serbest özet metnini yok sayar
    temiz_baslik = tr_kucult(baslik)
    
    if "yeni is iliskisi" in temiz_baslik:
        return "YENI_IS"
    elif "ihale sureci / sonucu" in temiz_baslik or "ihale sureci/sonucu" in temiz_baslik:
        return "IHALE"
        
    return None

def manuel_linki_tara_ve_isle(test_url):
    bildirim_id = test_url.rstrip("/").split("/")[-1]
    print(f"\n🔍 [RADAR SİMÜLASYONU] İlan taranıyor: {test_url}")

    sayfa_url = f"https://www.kap.org.tr/tr/Bildirim/{bildirim_id}"
    try:
        cevap = requests.get(sayfa_url, headers=headers, timeout=10)
        if cevap.status_code != 200:
            print(f"❌ Sayfaya ulaşılamadı. Kod: {cevap.status_code}")
            return
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return

    soup = BeautifulSoup(cevap.text, "html.parser")
    tam_metin = soup.get_text(separator=" ", strip=True)

    hisse_kodu = None
    kod_kutusu = soup.find("div", class_=lambda c: c and "lg:text-[23px]" in c and "font-semibold" in c)
    if kod_kutusu:
        hisse_kodu = kod_kutusu.get_text(strip=True).upper()

    tur = bildirim_turu_belirle(tam_metin)
    su_an = datetime.now().strftime("%H:%M:%S")

    if tur == "YENI_IS":
        print("\a\a")
        print("\n" + "#" * 80)
        print(f"💼 [YENİ İŞ İLİŞKİSİ BULUNDU] Saat: {su_an} | Şirket: {hisse_kodu or 'Tespit Ediliyor'}")
        print(f"🚀 Link analiz motoruna gönderildi: {test_url}")
        print("#" * 80)
        ilani_analiz_et(test_url, hisse_kodu=hisse_kodu)

    elif tur == "IHALE":
        print("\a\a\a")
        print("\n" + "=" * 80)
        print("🏆 [İHALE SONUCU BİLDİRİMİ YAKALANDI!]")
        print(f"🏢 Şirket : {hisse_kodu or 'Bilinmiyor'}")
        print(f"📅 Saat   : {su_an}")
        print(f"📌 Konu   : İhale Süreci / Sonucu")
        print(f"🔗 Link   : {test_url}")
        print("=" * 80 + "\n")
        
        # Telegram Bildirimi
        tg_ihale = f"🏆 <b>İHALE BİLDİRİMİ YAKALANDI!</b>\n\n"
        tg_ihale += f"🏢 <b>Şirket:</b> #{hisse_kodu or 'Bilinmiyor'}\n"
        tg_ihale += f"⏰ <b>Saat:</b> {su_an}\n"
        tg_ihale += f"📌 <b>Konu:</b> İhale Süreci / Sonucu\n\n"
        tg_ihale += f"🔗 <a href='{test_url}'>İhale Detayına Git</a>"
        telegram_bildirim_gonder(tg_ihale)
    else:
        print("ℹ️ Bildirim incelendi ancak hedeflenen kritik başlıklara uymuyor.")

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
print("🛡️  KAP CANLI NÖBETÇİ BAŞLATILDI (TELEGRAM ENTEGRELİ)")
print("=" * 80)

test_linki = input("\n🧪 Test etmek istediğiniz bir KAP linki var mı? (Yoksa Enter'a basıp geçin): ").strip()
if test_linki:
    manuel_linki_tara_ve_isle(test_linki)
    print("\n✅ Simülasyon tamamlandı. Canlı nöbete geçiliyor...\n" + "-" * 80)

print("⏳ Güncel bildirimler taranıyor...")
ilk_veri = bildirimleri_getir()

if ilk_veri:
    for ilan in ilk_veri:
        basic = ilan.get("disclosureBasic", {})
        b_id = basic.get("disclosureIndex")
        if b_id:
            gorulen_bildirimler.add(b_id)
    print(f"✅ Başlangıç tamamlandı. Hafızadaki mevcut ilan sayısı: {len(gorulen_bildirimler)}")
    print("👀 Canlı nöbet başladı, yeni bildirim bekleniyor... (Durdurmak için: Ctrl + C)\n")
    telegram_bildirim_gonder(f"🚀 <b>KAP Nöbetçisi Başlatıldı!</b>\n\nSistem devrede, <code>{len(gorulen_bildirimler)}</code> adet mevcut ilan hafızaya alındı. Canlı nöbet başladı.")
else:
    print("⚠️ Başlangıç verisi alınamadı, nöbete başlanıyor...\n")
    telegram_bildirim_gonder("⚠️ <b>KAP Nöbetçisi Başlatıldı</b> ancak başlangıç verisi çekilemedi. Nöbete yine de devam ediliyor.")

kontrol_sayaci = 0

try:
    while True:
        veriler = bildirimleri_getir()
        if veriler:
            yeni_gelenler = []
            for ilan in veriler:
                basic = ilan.get("disclosureBasic", {})
                b_id = basic.get("disclosureIndex")
                if b_id and b_id not in gorulen_bildirimler:
                    baslik = basic.get("title", "")
                    temiz_baslik = tr_kucult(baslik)
                    if "devre kesici" in temiz_baslik:
                        gorulen_bildirimler.add(b_id)
                        continue
                    yeni_gelenler.append((b_id, basic))
                    gorulen_bildirimler.add(b_id)

            for b_id, basic in reversed(yeni_gelenler):
                sirket = basic.get("companyTitle", "Bilinmiyor")
                
                # Hisse kodunu sağlamlaştırma: Boş veya '-' ise şirket unvanına döner
                hisse_raw = basic.get("stockCodes") or basic.get("relatedStocks") or ""
                if isinstance(hisse_raw, list):
                    hisse = ", ".join(hisse_raw)
                else:
                    hisse = str(hisse_raw).strip()
                    
                if not hisse or hisse == "-":
                    hisse = sirket

                baslik = basic.get("title", "Başlık Yok")
                ozet = basic.get("summary") or "Özet Bilgi Bulunmuyor"
                tarih = basic.get("publishDate", "Tarih Yok")
                saat = tarih.split()[-1] if ' ' in tarih else tarih
                link = f"https://www.kap.org.tr/tr/Bildirim/{b_id}"
                
                tur = bildirim_turu_belirle(baslik)
                if tur == "YENI_IS":
                    print("\n" + "#" * 80)
                    print(f"💼 [YENİ İŞ İLİŞKİSİ BULUNDU] Saat: {saat} | Şirket: {hisse} - {sirket}")
                    print(f"🚀 Link analiz motoruna gönderildi: {link}")
                    print("#" * 80)
                    hisse_temiz = hisse.split(",")[0].strip() if hisse != sirket else None
                    ilani_analiz_et(link, hisse_kodu=hisse_temiz)

                elif tur == "IHALE":
                    print("\n" + "=" * 80)
                    print("🏆 [İHALE SONUCU BİLDİRİMİ YAKALANDI!]")
                    print(f"🏢 Şirket : {hisse} ({sirket})")
                    print(f"📅 Tarih  : {tarih}")
                    print(f"📌 Konu   : {baslik}")
                    print(f"📝 Özet   : {ozet}")
                    print(f"🔗 Link   : {link}")
                    print("=" * 80 + "\n")
                    
                    # Telegram Bildirimi
                    tg_ihale = f"🏆 <b>İHALE BİLDİRİMİ YAKALANDI!</b>\n\n"
                    tg_ihale += f"🏢 <b>Şirket:</b> #{hisse}\n"
                    tg_ihale += f"⏰ <b>Saat:</b> {saat}\n"
                    tg_ihale += f"📌 <b>Başlık:</b> {baslik}\n"
                    tg_ihale += f"📝 <b>Özet:</b> {ozet}\n\n"
                    tg_ihale += f"🔗 <a href='{link}'>İhale Detayına Git</a>"
                    telegram_bildirim_gonder(tg_ihale)
                else:
                    print(f"ℹ️ [AKIS] {saat} | {hisse} | {baslik}")

        kontrol_sayaci += 1
        if kontrol_sayaci % 5 == 0:
            su_an = datetime.now().strftime("%H:%M:%S")
            print(f"[{su_an}] Nöbetçi aktif... Sistem taranıyor...")

        time.sleep(12)

except KeyboardInterrupt:
    print("\n🛑 Canlı nöbetçi durduruldu.")
    telegram_bildirim_gonder("🛑 <b>KAP Nöbetçisi manuel olarak durduruldu.</b>")

except Exception as e:
    hata_detay = traceback.format_exc()
    print(f"\n❌ BEKLENMEDİK ÇÖKME:\n{hata_detay}")
    
    hata_kisa = hata_detay[-800:] if len(hata_detay) > 800 else hata_detay
    mesaj = (
        f"🚨 <b>KAP NÖBETÇİSİ ÇÖKTÜ!</b>\n\n"
        f"<b>Hata Türü:</b> <code>{type(e).__name__}</code>\n"
        f"<b>Detay:</b>\n<pre>{hata_kisa}</pre>\n\n"
        f"⚠️ <i>Lütfen sunucuya bağlanıp botu kontrol edin.</i>"
    )
    telegram_bildirim_gonder(mesaj)