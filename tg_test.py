import requests

token = "8703249842:AAFglF867yO_upDCybOQdzKrnp94WuHay-c"
chat_id = "8906444117"

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": "🔔 KAP Radarı Telegram bağlantı testi başarılı!"
}

cevap = requests.post(url, json=payload)
print("Sonuç:", cevap.json())