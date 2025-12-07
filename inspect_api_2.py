import requests
import json

def inspect_hp_api():
    print("\n--- HP API ---")
    try:
        data = requests.get("https://hp-api.onrender.com/api/characters").json()
        if data:
            print(json.dumps(list(data[0].keys()), indent=2))
    except Exception as e:
        print(e)

def inspect_potter_db():
    print("\n--- Potter DB ---")
    try:
        # Fetch one character
        data = requests.get("https://api.potterdb.com/v1/characters?page[size]=1").json()
        if data and 'data' in data:
            attrs = data['data'][0]['attributes']
            print("Attributes:", json.dumps(list(attrs.keys()), indent=2))
            
            # Check relationships specifically if possible?
            # PotterDB JSON:API format often puts relationships in a separate 'relationships' key along with attributes?
            # data['data'][0]['relationships']?
            if 'relationships' in data['data'][0]:
                 print("Relationships Found:", json.dumps(data['data'][0]['relationships'], indent=2))
            else:
                 print("No 'relationships' key found in data item.")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    inspect_hp_api()
    inspect_potter_db()
