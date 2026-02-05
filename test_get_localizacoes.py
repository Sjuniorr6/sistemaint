import requests

url = "http://localhost:8000/api/missao/1/localizacoes/"

response = requests.get(url)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

if response.status_code == 200:
    data = response.json()
    print(f"\n✅ Total de localizações: {data['total']}")
    print(f"✅ Origem do acompanhamento: {data['origem_acompanhamento']}")
    
    if data['localizacoes']:
        print("\n📍 Última localização:")
        ultima = data['localizacoes'][-1]
        print(f"   Latitude: {ultima['latitude']}")
        print(f"   Longitude: {ultima['longitude']}")
        print(f"   Pânico: {'🚨 SIM' if ultima['is_panic'] else '❌ NÃO'}")
        print(f"   Data: {ultima['criado_em']}")
        print(f"   Origem: {ultima['origem']}")