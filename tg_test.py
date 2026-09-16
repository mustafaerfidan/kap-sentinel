import requests

token = " "
chat_id = " "

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": "🔔 KAP Radarı Telegram bağlantı testi başarılı!"
}

cevap = requests.post(url, json=payload)
print("Sonuç:", cevap.json())