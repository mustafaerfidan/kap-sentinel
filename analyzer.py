import os
import re
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükler
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def telegram_bildirim_gonder(mesaj_metni):
    """Telegram üzerinden formatlı mesaj gönderir."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram token veya Chat ID bulunamadı (.env kontrol edin).")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj_metni,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"❌ Telegram gönderim hatası: {e}")

def canli_kur_al(para_birimi):
    pb = para_birimi.upper().strip()
    if pb in ["TL", "TRY"]:
        return 1.0
    parite = f"{pb}TRY=X"
    try:
        fiyat = yf.Ticker(parite).fast_info.last_price
        if fiyat:
            return round(fiyat, 4)
    except Exception:
        pass
    varsayilanlar = {"USD": 34.0, "EUR": 37.5}
    return varsayilanlar.get(pb, 1.0)

def ozsermaye_al(hisse_kodu):
    if not hisse_kodu:
        return None
    try:
        sembol = f"{hisse_kodu.upper().strip()}.IS"
        bilanço = yf.Ticker(sembol).balance_sheet
        if bilanço is not None and not bilanço.empty:
            for etiket in ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]:
                if etiket in bilanço.index:
                    deger = bilanço.loc[etiket].iloc[0]
                    if deger and deger > 0:
                        return float(deger)
    except Exception:
        pass
    return None

def ilani_analiz_et(link, hisse_kodu=None):
    try:
        r = requests.get(link, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"❌ Sayfa çekilemedi: {e}")
        return

    if not hisse_kodu:
        kod_kutusu = soup.find("div", class_=lambda c: c and "lg:text-[23px]" in c and "font-semibold" in c)
        if kod_kutusu:
            hisse_kodu = kod_kutusu.get_text(strip=True).upper()

    metin = soup.get_text(separator=" ", strip=True)
    
    tutar_desen = re.search(r"([\d\.,]+)\s*(TL|USD|EUR|TRY)", metin, re.IGNORECASE)
    tutar_tl = None
    ham_tutar = None
    pb = "TL"

    if tutar_desen:
        ham_str = tutar_desen.group(1).replace(".", "").replace(",", ".")
        pb = tutar_desen.group(2).upper()
        try:
            ham_tutar = float(ham_str)
            kur = canli_kur_al(pb)
            tutar_tl = ham_tutar * kur
        except ValueError:
            pass

    # Terminal Kartı
    print("\n" + "=" * 60)
    print(f"📊 [FİNANSAL ANALİZ KARTI]")
    print(f"🏢 Hisse Kodu : {hisse_kodu or 'Bilinmiyor'}")
    if ham_tutar:
        print(f"💰 İş Tutarı  : {ham_tutar:,.2f} {pb} (Yaklaşık {tutar_tl:,.2f} TL)")
    else:
        print("💰 İş Tutarı  : İlan metninde net rakam ayrıştırılamadı.")

    ozsermaye = ozsermaye_al(hisse_kodu) if hisse_kodu else None
    oran = None
    if ozsermaye and tutar_tl:
        oran = (tutar_tl / ozsermaye) * 100
        print(f"🏛️ Öz Sermaye : {ozsermaye:,.2f} TL")
        print(f"📈 Sözleşme / Öz Sermaye Oranı: %{oran:.2f}")
        if oran >= 50:
            print("🚨 [DİKKAT: Sözleşme bedeli şirketin öz sermayesinin %50'sinden büyük!]")
    elif ozsermaye:
        print(f"🏛️ Öz Sermaye : {ozsermaye:,.2f} TL")

    print(f"🔗 Bildirim   : {link}")
    print("=" * 60 + "\n")

    # Telegram Mesajı
    tg_mesaj = f"💼 <b>YENİ İŞ İLİŞKİSİ BİLDİRİMİ</b>\n\n"
    tg_mesaj += f"🏢 <b>Hisse:</b> #{hisse_kodu or 'Bilinmiyor'}\n"
    if ham_tutar:
        tg_mesaj += f"💰 <b>İş Tutarı:</b> {ham_tutar:,.2f} {pb} (~{tutar_tl:,.2f} TL)\n"
    if ozsermaye:
        tg_mesaj += f"🏛️ <b>Öz Sermaye:</b> {ozsermaye:,.2f} TL\n"
    if oran:
        tg_mesaj += f"📈 <b>İş / Öz Sermaye:</b> %{oran:.2f}\n"
        if oran >= 50:
            tg_mesaj += f"\n🚨 <b>DİKKAT: İş tutarı öz sermayenin %50'sinden büyük!</b>\n"
    
    tg_mesaj += f"\n🔗 <a href='{link}'>KAP İlanını Görüntüle</a>"
    telegram_bildirim_gonder(tg_mesaj)