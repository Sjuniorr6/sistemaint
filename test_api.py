import requests
import time
import threading
import math
from datetime import datetime

url_location = "http://localhost:8000/api/missao/4/location/"
url_panic = "http://localhost:8000/api/missao/4/panic/"

# Posição inicial
latitude = -23.6561866
longitude = -46.5712412

contador = 1
panico_acionado = False
rodando = True

# ==== CONFIGURAÇÃO DO "MOVIMENTO" ====
STEP_METERS = 5.0          # anda 1 metro a cada update (mude aqui)
BASE_BEARING_DEG = 45.0    # direção base (0=N, 90=E, 180=S, 270=O)
BEARING_JITTER_DEG = 3.0   # variação pequena de direção por update (0 para desativar)

def meters_to_latlon_delta(lat_deg: float, meters: float, bearing_deg: float):
    """
    Converte deslocamento em metros para delta de latitude/longitude (graus),
    usando aproximação esférica/local.
    bearing_deg: 0=N, 90=E, 180=S, 270=O
    """
    lat_rad = math.radians(lat_deg)
    bearing_rad = math.radians(bearing_deg)

    # Componentes do deslocamento (metros)
    north_m = meters * math.cos(bearing_rad)
    east_m  = meters * math.sin(bearing_rad)

    # Conversão metros -> graus
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(lat_rad)

    dlat = north_m / meters_per_deg_lat
    dlon = east_m / meters_per_deg_lon if meters_per_deg_lon != 0 else 0.0

    return dlat, dlon

def aguardar_panico():
    """Thread que aguarda input do usuário para acionar pânico"""
    global panico_acionado
    while rodando:
        input("Pressione ENTER para acionar o PÂNICO ou Ctrl+C para parar...\n")
        panico_acionado = True

print("🚨 Simulador de Rastreamento com Pânico Manual")
print("Enviando localizações a cada 5 segundos...")
print("Pressione ENTER a qualquer momento para acionar o PÂNICO")
print("Pressione Ctrl+C para parar\n")

thread_panico = threading.Thread(target=aguardar_panico, daemon=True)
thread_panico.start()

try:
    # Posição atual (vai sendo atualizada a cada envio)
    lat = latitude
    lng = longitude

    while True:
        # Define direção (bearing) para este update
        bearing = BASE_BEARING_DEG
        if BEARING_JITTER_DEG > 0:
            # Variação suave conforme o contador (sem random pra ficar reproduzível)
            bearing += math.sin(contador / 3.0) * BEARING_JITTER_DEG

        # Move STEP_METERS a partir da última posição
        dlat, dlon = meters_to_latlon_delta(lat, STEP_METERS, bearing)
        lat = lat + dlat
        lng = lng + dlon

        agora = datetime.now().strftime("%H:%M:%S")

        # Se usuário pressionou Enter, envia pânico
        if panico_acionado:
            print(f"\n{'='*60}")
            print(f"🚨🚨🚨 ACIONANDO BOTÃO DE PÂNICO! 🚨🚨🚨")
            print(f"{'='*60}\n")

            panic_data = {
                "latitude": lat,
                "longitude": lng,
                "accuracy": 13.024999618530273,
                "timestamp": int(time.time() * 1000),
                "message": "ALERTA DE PÂNICO ACIONADO!"
            }

            panic_response = requests.post(url_panic, json=panic_data)

            if panic_response.status_code == 200:
                print(f"[{agora}] 🚨 PÂNICO REGISTRADO - Lat: {lat:.6f}, Lng: {lng:.6f}")
                print(f"Response: {panic_response.json()}\n")
            else:
                print(f"[{agora}] ❌ Erro ao enviar pânico: {panic_response.status_code}\n")

            panico_acionado = False  # Reset para permitir novos pânicos

        # Envia localização normal
        data = {
            "latitude": lat,
            "longitude": lng,
            "accuracy": 13.024999618530273,
            "altitude": 764.0999755859375,
            "heading": bearing,  # já manda o heading coerente com o movimento
            "speed": STEP_METERS / 5.0,  # m/s aproximado (porque envia a cada 5s)
            "timestamp": int(time.time() * 1000)
        }

        response = requests.post(url_location, json=data)

        if response.status_code == 200:
            print(f"[{agora}] ✅ Envio #{contador} - Lat: {lat:.6f}, Lng: {lng:.6f} | +{STEP_METERS}m")
        else:
            print(f"[{agora}] ❌ Erro #{contador}: {response.status_code}")

        contador += 1
        time.sleep(5)

except KeyboardInterrupt:
    rodando = False
    print(f"\n\n🛑 Parado! Total de envios: {contador - 1}")
