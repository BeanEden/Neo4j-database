import requests
import json

def find_romances():
    print("Searching for characters with romances...")
    try:
        # Fetch a list of chars
        url = "https://api.potterdb.com/v1/characters?page[size]=50"
        data = requests.get(url).json()
        
        found = False
        if 'data' in data:
            for item in data['data']:
                attrs = item['attributes']
                if attrs.get('romances') and len(attrs['romances']) > 0:
                    print(f"\nCharacter: {attrs['name']}")
                    print("Romances:", json.dumps(attrs['romances'], indent=2))
                    found = True
                    break
        
        if not found:
            print("No romances found in first 50 chars.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_romances()
