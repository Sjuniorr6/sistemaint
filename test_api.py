import requests
import time
from datetime import datetime

url = "http://localhost:8000/api/missao/1/location/"

print("Enviando localizações a cada 5 segundos...")
print("Pressione Ctrl+C para parar\n")

latitude = -23.6561866
longitude = -46.5712412

try:
    contador = 1
    while True:
        # Simula pequena variação na localização
        lat = latitude + (contador * 0.0001)
        lng = longitude + (contador * 0.0001)
        
        data = {
            "latitude": lat,
            "longitude": lng,
            "accuracy": 13.024999618530273,
            "altitude": 764.0999755859375,
            "heading": 200.69674682617188,
            "speed": 0.40316444635391235,
            "timestamp": int(time.time() * 1000)
        }
        
        response = requests.post(url, json=data)
        
        agora = datetime.now().strftime("%H:%M:%S")
        if response.status_code == 200:
            print(f"[{agora}] ✅ Envio #{contador} - Lat: {lat:.6f}, Lng: {lng:.6f}")
        else:
            print(f"[{agora}] ❌ Erro #{contador}: {response.status_code}")
        
        contador += 1
        time.sleep(5)  # Aguarda 5 segundos
        
except KeyboardInterrupt:
    print(f"\n\n🛑 Parado! Total de envios: {contador - 1}")