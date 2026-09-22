import os
import re
import html
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
        "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s",
        "Ğ": "g", "ğ": "g", "Ü": "u", "ü": "u", "Ö": "o",
        "ö": "o", "Ç": "c", "ç": "c"
    }
    temiz = metin
    for buyuk, kucuk in donusum.items():
        temiz = temiz.replace(buyuk, kucuk)
    return temiz.lower()

def sayiyi_ayristir(ham_str):
    if not ham_str:
        return None
    ham_str = ham_str.strip().rstrip(".,")
    if "." in ham_str and "," in ham_str:
        if ham_str.rfind(",") > ham_str.rfind("."):
            temiz = ham_str.replace(".", "").replace(",", ".")
        else:
            temiz = ham_str.replace(",", "")
    elif "," in ham_str:
        parcalar = ham_str.split(",")
        temiz = ham_str.replace(",", ".") if len(parcalar[-1]) == 2 else ham_str.replace(",", "")
    elif "." in ham_str:
        parcalar = ham_str.split(".")
        temiz = ham_str.replace(".", "") if len(parcalar) > 1 and len(parcalar[-1]) == 3 else ham_str
    else:
        temiz = ham_str

    try:
        deger = float(temiz)
        return deger if deger > 0 else None
    except ValueError:
        return None

def para_birimi_normalize_et(pb_str):
    if not pb_str:
        return "TL"
    pb = pb_str.lower().strip()
    if any(k in pb for k in ["usd", "dolar", "$"]):
        return "USD"
    elif any(k in pb for k in ["eur", "euro", "avro", "€"]):
        return "EUR"
    elif any(k in pb for k in ["gbp", "sterlin", "£"]):
        return "GBP"
    return "TL"

# =====================================================================
# 1. YENİ İŞ İLİŞKİSİ AYRIŞTIRICI (TARİH VE SAHTE YIL KORUMALI)
# =====================================================================
def yeni_is_tutari_bul(metin):
    # Tarih kalıplarını (06/09/2026, 22.09.2026 vb.) metinden temizle (yıllar tutar sanılmasın)
    metin_temiz = re.sub(r'\b\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}\b', ' ', metin)
    metin_temiz = re.sub(r'\b\d{4}[./\-]\d{1,2}[./\-]\d{1,2}\b', ' ', metin_temiz)
    
    metin_kucuk = tr_kucult(metin_temiz)
    pb_desen = r"(?:abd\s*dolar[ıi]|amerikan\s*dolar[ıi]|dolar|usd|\$|euro|avro|eur|€|t[üu]rk\s*liras[ıi]|tl|try|₺|ingiliz\s*sterlin[ıi]|sterlin|gbp|£)"

    # 1. Öncelik: "Milyon / Milyar" yazılı kalıplar (Örn: 50 Milyon TL)
    milyon_desen = rf"([\d\.,]+)\s*(milyon|milyar)\s*({pb_desen})?"
    m_eslesme = re.search(milyon_desen, metin_kucuk)
    if m_eslesme:
        val = sayiyi_ayristir(m_eslesme.group(1))
        if val:
            carpan = 1_000_000_000 if m_eslesme.group(2) == "milyar" else 1_000_000
            return val * carpan, para_birimi_normalize_et(m_eslesme.group(3))

    # 2. Öncelik: Doğrudan sözleşme anahtar kelimesiyle bağlı tutar ve para birimi
    p1 = rf"(?:sozlesme\s+bedeli|is\s+tutari|siparis\s+tutari|toplam\s+bedel|sozlesme\s+tutari)\b.*?([\d\.,]{{3,}})\s*({pb_desen})"
    m1 = re.search(p1, metin_kucuk)
    if m1:
        val = sayiyi_ayristir(m1.group(1))
        pb = para_birimi_normalize_et(m1.group(2))
        if val and not (1990 <= val <= 2050 and pb == "TL") and val > 1000:
            return val, pb

    # 3. Öncelik: Genel anahtar kelime eşleşmeleri
    p2 = rf"(?:toplam|tutar[ıi]?|bedel[i]?|deger[i]?|sozlesme|anlasma|siparis)\w*\s*[:\-]?\s*([\d\.,]{{3,}})\s*({pb_desen})"
    m2 = re.findall(p2, metin_kucuk)
    for ham_rakam, ham_pb in m2:
        val = sayiyi_ayristir(ham_rakam)
        pb = para_birimi_normalize_et(ham_pb)
        if val and not (1990 <= val <= 2050 and pb == "TL") and val > 1000:
            return val, pb

    # 4. Öncelik: Yanında açıkça para birimi olan rakamlar
    p3 = rf"([\d\.,]{{3,}})\s*({pb_desen})"
    m3 = re.findall(p3, metin_kucuk)
    adaylar = []
    for ham_rakam, ham_pb in m3:
        val = sayiyi_ayristir(ham_rakam)
        pb = para_birimi_normalize_et(ham_pb)
        if val and not (1990 <= val <= 2050 and pb == "TL") and val > 1000:
            adaylar.append((val, pb))

    if adaylar:
        adaylar.sort(key=lambda x: x[0], reverse=True)
        return adaylar[0]

    return None, "TL"

# =====================================================================
# 2. İHALE SONUCU AYRIŞTIRICI (İNGİLİZCE TAKSONOMİ VE ESNEK ARAMA)
# =====================================================================
def ihale_bedeli_bul(tam_metin):
    metin_kucuk = tr_kucult(tam_metin)
    pb_desen = r"(?:abd\s*dolar[ıi]|amerikan\s*dolar[ıi]|dolar|usd|\$|euro|avro|eur|€|t[üu]rk\s*liras[ıi]|tl|try|₺)"

    # 1. Öncelik: "İhale Bedeli" (Araya Tender Value, taksonomi, boşluk, KDV hariç girse de 0-60 karakter toleransla yakalar)
    p1 = rf"ihale\s+bedeli(?!\s*(?:nden)?\s*ortakl[ıi]k)\b.{{0,60}}?([\d\.,]{{3,}})\s*({pb_desen})?"
    m1 = re.search(p1, metin_kucuk, re.DOTALL)
    if m1:
        val = sayiyi_ayristir(m1.group(1))
        pb = para_birimi_normalize_et(m1.group(2))
        if val and val > 1000:
            return val, pb

    # 2. Öncelik: "İhale Bedelinden Ortaklık Payına Düşen Kısım"
    p2 = rf"ortakl[ıi]k\s+pay[ıi]na\s+d[üu]sen\s+(?:k[ıi]s[ıi]m|tutar|bedel)\b.{{0,60}}?([\d\.,]{{3,}})\s*({pb_desen})?"
    m2 = re.search(p2, metin_kucuk, re.DOTALL)
    if m2:
        val = sayiyi_ayristir(m2.group(1))
        pb = para_birimi_normalize_et(m2.group(2))
        if val and val > 1000:
            return val, pb

    # 3. Öncelik: Açıklamalardaki baz bedel / ihale bedeli cümleleri
    p3 = rf"(?:baz\s+bedel[i]?|ihale\s+bedeli\s+kdv\s+(?:haric|dahil))\s*[:\-]?\s*([\d\.,]{{3,}})\s*({pb_desen})?"
    m3 = re.search(p3, metin_kucuk)
    if m3:
        val = sayiyi_ayristir(m3.group(1))
        pb = para_birimi_normalize_et(m3.group(2))
        if val and val > 1000:
            return val, pb

    # 4. Öncelik: Açıklamadaki "+ KDV ... uhdesinde / kazanıldı" kalıbı
    p4 = rf"([\d\.,]{{3,}})\s*({pb_desen})?\s*(?:\+\s*kdv)?\s*(?:tutarla|bedelle|uhdesinde|kazan)"
    m4 = re.search(p4, metin_kucuk)
    if m4:
        val = sayiyi_ayristir(m4.group(1))
        pb = para_birimi_normalize_et(m4.group(2))
        if val and val > 1000:
            return val, pb

    return None, "TL"

# =====================================================================
# 3. YARDIMCI FİNANS VE ENTEGRASYON MODÜLLERİ
# =====================================================================
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
    if not hisse_kodu or len(hisse_kodu) > 10 or " " in hisse_kodu:
        return None
    try:
        sembol = f"{hisse_kodu.upper().strip()}.IS"
        t = yf.Ticker(sembol)
        # Önce en güncel çeyreklik bilanço taranır
        bilanco = t.quarterly_balance_sheet
        if bilanco is None or bilanco.empty:
            bilanco = t.balance_sheet

        if bilanco is not None and not bilanco.empty:
            for etiket in ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]:
                if etiket in bilanco.index:
                    deger = bilanco.loc[etiket].iloc[0]
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
        res = requests.post(url, json=payload, timeout=8)
        if res.status_code != 200:
            print(f"⚠️ Telegram API Uyarısı ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Telegram gönderim hatası: {e}")

def baslik_formatla(hisse_kodu, sirket_unvani=None):
    if hisse_kodu and len(hisse_kodu) <= 10 and " " not in hisse_kodu:
        return f"#{html.escape(hisse_kodu)}"
    elif sirket_unvani:
        return html.escape(sirket_unvani)
    return "Bilinmiyor"

# =====================================================================
# 4. ANA ÇALIŞTIRICI FONKSİYONLAR
# =====================================================================
def ilani_analiz_et(link, hisse_kodu=None, sirket_unvani=None):
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
    ham_tutar, pb = yeni_is_tutari_bul(tam_metin)
    
    tutar_tl = None
    if ham_tutar:
        kur = canli_kur_al(pb)
        tutar_tl = ham_tutar * kur

    ozsermaye = ozsermaye_al(hisse_kodu) if hisse_kodu else None
    oran = (tutar_tl / ozsermaye * 100) if (ozsermaye and tutar_tl) else None

    etiket = baslik_formatla(hisse_kodu, sirket_unvani)

    print("\n" + "=" * 60)
    print(f"💼 [YENİ İŞ İLİŞKİSİ ANALİZ KARTI]")
    print(f"🏢 Şirket     : {hisse_kodu or sirket_unvani or 'Bilinmiyor'}")
    if ham_tutar:
        tutar_str = f"{ham_tutar:,.2f} {pb}" if pb == "TL" else f"{ham_tutar:,.2f} {pb} (~{tutar_tl:,.2f} TL)"
        print(f"💰 İş Tutarı  : {tutar_str}")
    else:
        print("💰 İş Tutarı  : Metinde net rakam ayrıştırılamadı.")
    if ozsermaye:
        print(f"🏛️ Öz Sermaye : {ozsermaye:,.2f} TL")
    if oran:
        print(f"📈 Oran       : %{oran:.2f}")
    print(f"🔗 Link       : {link}")
    print("=" * 60 + "\n")

    tg_mesaj = f"💼 <b>YENİ İŞ İLİŞKİSİ BİLDİRİMİ</b>\n\n"
    tg_mesaj += f"🏢 <b>Şirket:</b> {etiket}\n"
    
    if ham_tutar:
        tutar_str = f"{ham_tutar:,.2f} {pb}" if pb == "TL" else f"{ham_tutar:,.2f} {pb} (~{tutar_tl:,.2f} TL)"
        tg_mesaj += f"💰 <b>İş Tutarı:</b> {tutar_str}\n"
    else:
        tg_mesaj += f"💰 <b>İş Tutarı:</b> Belirtilmemiş (veya Ticari Sır)\n"

    if ozsermaye:
        tg_mesaj += f"🏛️ <b>Öz Sermaye:</b> {ozsermaye:,.2f} TL\n"
    if oran:
        tg_mesaj += f"📈 <b>İş / Öz Sermaye:</b> %{oran:.2f}\n"
        if oran >= 50:
            tg_mesaj += f"\n🚨 <b>DİKKAT: İş tutarı öz sermayenin %50'sinden büyük!</b>\n"

    tg_mesaj += f"\n🔗 <a href='{link}'>KAP İlanını Görüntüle</a>"
    telegram_bildirim_gonder(tg_mesaj)

def ihale_analiz_et(link, hisse_kodu=None, sirket_unvani=None):
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
    ham_tutar, pb = ihale_bedeli_bul(tam_metin)

    tutar_tl = None
    if ham_tutar:
        kur = canli_kur_al(pb)
        tutar_tl = ham_tutar * kur

    ozsermaye = ozsermaye_al(hisse_kodu) if hisse_kodu else None
    oran = (tutar_tl / ozsermaye * 100) if (ozsermaye and tutar_tl) else None

    etiket = baslik_formatla(hisse_kodu, sirket_unvani)

    print("\n" + "=" * 60)
    print(f"🏆 [İHALE SONUCU ANALİZ KARTI]")
    print(f"🏢 Şirket     : {hisse_kodu or sirket_unvani or 'Bilinmiyor'}")
    if ham_tutar:
        tutar_str = f"{ham_tutar:,.2f} {pb}" if pb == "TL" else f"{ham_tutar:,.2f} {pb} (~{tutar_tl:,.2f} TL)"
        print(f"💰 İhale Bedel: {tutar_str}")
    else:
        print("💰 İhale Bedel: İlan tablosunda bedel yayınlanmamış.")
    if ozsermaye:
        print(f"🏛️ Öz Sermaye : {ozsermaye:,.2f} TL")
    if oran:
        print(f"📈 Oran       : %{oran:.2f}")
    print(f"🔗 Link       : {link}")
    print("=" * 60 + "\n")

    tg_mesaj = f"🏆 <b>İHALE SONUCU BİLDİRİMİ</b>\n\n"
    tg_mesaj += f"🏢 <b>Şirket:</b> {etiket}\n"

    if ham_tutar:
        tutar_str = f"{ham_tutar:,.2f} {pb}" if pb == "TL" else f"{ham_tutar:,.2f} {pb} (~{tutar_tl:,.2f} TL)"
        tg_mesaj += f"💰 <b>İhale Bedeli:</b> {tutar_str}\n"
        if ozsermaye:
            tg_mesaj += f"🏛️ <b>Öz Sermaye:</b> {ozsermaye:,.2f} TL\n"
        if oran:
            tg_mesaj += f"📈 <b>İhale / Öz Sermaye:</b> %{oran:.2f}\n"
            if oran >= 50:
                tg_mesaj += f"\n🚨 <b>DİKKAT: İhale bedeli şirketin öz sermayesinin %50'sinden büyük!</b>\n"
    else:
        tg_mesaj += f"💰 <b>İhale Bedeli:</b> <i>Yayınlanmamış</i>\n"
        if ozsermaye:
            tg_mesaj += f"🏛️ <b>Öz Sermaye:</b> {ozsermaye:,.2f} TL\n"
        tg_mesaj += f"\nℹ️ <i>Not: İhale bedeli şirket tarafından KAP tablosunda yayınlanmamıştır.</i>\n"

    tg_mesaj += f"\n🔗 <a href='{link}'>KAP İlanını Görüntüle</a>"
    telegram_bildirim_gonder(tg_mesaj)