import requests
import json

def inspect_hp_api():
    print("--- HP API ---")
    try:
        data = requests.get("https://hp-api.onrender.com/api/characters").json()
        if data:
            print("Keys:", data[0].keys())
            # Check for generic relationship fields
            for k in ['friends', 'enemies', 'relationships', 'family']:
                if k in data[0]:
                    print(f"Found '{k}':", data[0][k])
    except Exception as e:
        print(e)

def inspect_potter_db():
    print("\n--- Potter DB ---")
    try:
        data = requests.get("https://api.potterdb.com/v1/characters?page[size]=1").json()
        if data and 'data' in data:
            attrs = data['data'][0]['attributes']
            print("Keys:", attrs.keys())
            # PotterDB usually has 'jobs', 'titles', maybe 'familiars', 'relationships'?
            # It seems PotterDB relations are often links, but let's see.
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_hp_api()
    inspect_potter_db()
