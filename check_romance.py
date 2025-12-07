import requests
import json

def check_potterdb_romances():
    print("Checking PotterDB for 'romances'...")
    try:
        # Harry Potter slug is usually 'harry-potter' or similar, let's try to find a character with romances
        # Fetch a few chars
        url = "https://api.potterdb.com/v1/characters?filter[name_cont]=Harry%20Potter" 
        data = requests.get(url).json()
        
        if 'data' in data and len(data['data']) > 0:
            attrs = data['data'][0]['attributes']
            print("Harry Attributes Keys:", json.dumps(list(attrs.keys()), indent=2))
            if 'romances' in attrs:
                print("Romances Found:", attrs['romances'])
            else:
                print("'romances' key NOT found.")
        else:
            print("Harry Potter not found in PotterDB search.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_potterdb_romances()
