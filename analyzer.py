import os
import re
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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

def sayiyi_ayristir(ham_str):
    ham_str = ham_str.strip().rstrip(".,")
    if "." in ham_str and "," in ham_str:
        if ham_str.rfind(",") > ham_str.rfind("."):
            temiz = ham_str.replace(".", "").replace(",", ".")
        else:
            temiz = ham_str.replace(",", "")
    elif "," in ham_str:
        parcalar = ham_str.split(",")
        if len(parcalar[-1]) == 2:
            temiz = ham_str.replace(",", ".")
        else:
            temiz = ham_str.replace(",", "")
    elif "." in ham_str:
        parcalar = ham_str.split(".")
        if len(parcalar) > 1 and len(parcalar[-1]) == 3:
            temiz = ham_str.replace(".", "")
        else:
            temiz = ham_str
    else:
        temiz = ham_str

    try:
        deger = float(temiz)
        return deger if deger > 0 else None
    except ValueError:
        return None

def para_birimi_normalize_et(pb_str):
    pb = pb_str.lower().strip()
    if any(k in pb for k in ["usd", "dolar", "$"]):
        return "USD"
    elif any(k in pb for k in ["eur", "euro", "avro", "€"]):
        return "EUR"
    elif any(k in pb for k in ["gbp", "sterlin", "£"]):
        return "GBP"
    return "TL"

def tutar_ve_para_birimi_bul(metin):
    metin_kucuk = tr_kucult(metin)
    pb_desen = r"(?:abd\s*dolar[ıi]|amerikan\s*dolar[ıi]|dolar|usd|\$|euro|avro|eur|€|t[üu]rk\s*liras[ıi]|tl|try|₺|ingiliz\s*sterlin[ıi]|sterlin|gbp|£)"

    # 1. Öncelik: Anahtar kelimelerle bitişik tutarlar (Örn: "toplam 2.983.897,76 abd dolari tutarinda")
    p1 = rf"(?:toplam|tutar[ıi]?|bedel[i]?|deger[i]?|sozlesme|anlasma)\w*\s*[:\-]?\s*([\d\.,]{{3,}})\s*({pb_desen})"
    p2 = rf"([\d\.,]{{3,}})\s*({pb_desen})\s*(?:tutar|bedel|deger|anlasma|sozlesme)\w*"

    for desen in [p1, p2]:
        eslesmeler = re.findall(desen, metin_kucuk)
        for ham_rakam, ham_pb in eslesmeler:
            val = sayiyi_ayristir(ham_rakam)
            if val and val > 1000:
                return val, para_birimi_normalize_et(ham_pb)

    # 2. Öncelik: Genel tutar + para birimi
    p3 = rf"([\d\.,]{{3,}})\s*({pb_desen})"
    eslesmeler = re.findall(p3, metin_kucuk)
    adaylar = []
    for ham_rakam, ham_pb in eslesmeler:
        val = sayiyi_ayristir(ham_rakam)
        if val and val > 1000:
            adaylar.append((val, para_birimi_normalize_et(ham_pb)))

    if adaylar:
        adaylar.sort(key=lambda x: x[0], reverse=True)
        return adaylar[0]

    # 3. Öncelik: Sembol başta olanlar (Örn: "$ 2,983,897.76")
    p4 = r"(\$|€|₺|£)\s*([\d\.,]{3,})"
    eslesmeler = re.findall(p4, metin_kucuk)
    for ham_pb, ham_rakam in eslesmeler:
        val = sayiyi_ayristir(ham_rakam)
        if val and val > 1000:
            return val, para_birimi_normalize_et(ham_pb)

    return None, "TL"

def canli_kur_al(para_birimi):
    pb = para_birimi.upper().strip()
    if pb in ["TL", "TRY"]:
        return 1.0
    parite = f"{pb}TRY=X"
    try:
        fiyat = yf.Ticker(parite).fast_info.last_price
        if fiyat:
            return round(float(fiyat), 4)
    except Exception:
        pass
    varsayilanlar = {"USD": 38.5, "EUR": 41.0, "GBP": 48.0}
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

def telegram_bildirim_gonder(mesaj_metni):
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

    tam_metin = soup.get_text(separator=" ", strip=True)
    
    ham_tutar, pb = tutar_ve_para_birimi_bul(tam_metin)
    tutar_tl = None
    if ham_tutar:
        kur = canli_kur_al(pb)
        tutar_tl = ham_tutar * kur

    ozsermaye = ozsermaye_al(hisse_kodu) if hisse_kodu else None
    oran = None
    if ozsermaye and tutar_tl:
        oran = (tutar_tl / ozsermaye) * 100

    # Terminal Çıktısı
    print("\n" + "=" * 60)
    print(f"📊 [FİNANSAL ANALİZ KARTI]")
    print(f"🏢 Hisse Kodu : {hisse_kodu or 'Bilinmiyor'}")
    if ham_tutar:
        print(f"💰 İş Tutarı  : {ham_tutar:,.2f} {pb} (~{tutar_tl:,.2f} TL)")
    else:
        print("💰 İş Tutarı  : Metinde net rakam ayrıştırılamadı.")

    if ozsermaye:
        print(f"🏛️ Öz Sermaye : {ozsermaye:,.2f} TL")
    if oran:
        print(f"📈 Oran       : %{oran:.2f}")
    print(f"🔗 Link       : {link}")
    print("=" * 60 + "\n")

    # Telegram Mesajı
    tg_mesaj = f"💼 <b>YENİ İŞ İLİŞKİSİ BİLDİRİMİ</b>\n\n"
    tg_mesaj += f"🏢 <b>Hisse:</b> #{hisse_kodu or 'Bilinmiyor'}\n"
    
    if ham_tutar:
        tg_mesaj += f"💰 <b>İş Tutarı:</b> {ham_tutar:,.2f} {pb} (~{tutar_tl:,.2f} TL)\n"
    else:
        tg_mesaj += f"💰 <b>İş Tutarı:</b> Belirtilmemiş (veya Ticari Sır)\n"

    if ozsermaye:
        tg_mesaj += f"🏛️ <b>Öz Sermaye:</b> {ozsermaye:,.2f} TL\n"
        
    if oran:
        tg_mesaj += f"📈 <b>İş / Öz Sermaye:</b> %{oran:.2f}\n"
        if oran >= 50:
            tg_mesaj += f"\n🚨 <b>DİKKAT: İş tutarı şirketin öz sermayesinin %50'sinden büyük!</b>\n"

    tg_mesaj += f"\n🔗 <a href='{link}'>KAP İlanını Görüntüle</a>"
    telegram_bildirim_gonder(tg_mesaj)