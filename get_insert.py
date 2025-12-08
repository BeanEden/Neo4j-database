import requests
from neo4j import GraphDatabase
import os

# --- CONFIG ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

# --- Connexion à Neo4j ---
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# --- Fonctions d'insertion ---
def clear_db(tx):
    tx.run("MATCH (n) DETACH DELETE n")

def create_constraints(tx):
    tx.run("CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;")
    tx.run("CREATE CONSTRAINT house_id IF NOT EXISTS FOR (h:House) REQUIRE h.name IS UNIQUE;")

def insert_person(tx, person):
    tx.run("""
        MERGE (p:Person {id: $id})
        SET p.name = $name,
            p.house = $house,
            p.image = $image,
            p.gender = $gender,
            p.patronus = $patronus,
            p.ancestry = $ancestry,
            p.wand = $wand,
            p.species = $species,
            p.hogwartsStudent = $hogwartsStudent,
            p.hogwartsStaff = $hogwartsStaff,
            p.alive = $alive
    """, person)

def insert_house(tx, house_name):
    if house_name:
        tx.run("MERGE (h:House {name: $name})", {"name": house_name})

def link_person_house(tx, person_id, house_name):
    if house_name:
        tx.run("""
            MATCH (p:Person {id: $person_id})
            MATCH (h:House {name: $house_name})
            MERGE (p)-[:BELONGS_TO]->(h)
        """, {"person_id": person_id, "house_name": house_name})

def create_social_relations(tx):
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.ancestry IS NOT NULL AND a.ancestry = b.ancestry AND a.id < b.id
        MERGE (a)-[:SAME_ANCESTRY]->(b)
    """)
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.wand IS NOT NULL AND b.wand IS NOT NULL 
        AND a.wand CONTAINS 'wood' AND b.wand CONTAINS 'wood'
        AND a.id < b.id
        MERGE (a)-[:SAME_WAND_MATERIAL]->(b)
    """)
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.species IS NOT NULL AND a.species = b.species AND a.id < b.id
        MERGE (a)-[:SAME_SPECIES]->(b)
    """)

def create_extended_social_relations(tx, people_data):
    # 1. Custom Canon Relationships (Manual)
    canon_friends = [
        ("Harry Potter", "Ron Weasley"),
        ("Harry Potter", "Hermione Granger"),
        ("Ron Weasley", "Hermione Granger"),
        ("Albus Dumbledore", "Minerva McGonagall"),
        ("James Potter I", "Sirius Black"),
        ("Harry Potter", "Rubeus Hagrid")
    ]
    
    canon_enemies = [
        ("Harry Potter", "Lord Voldemort"),
        ("Harry Potter", "Draco Malfoy"),
        ("Albus Dumbledore", "Lord Voldemort"),
        ("Harry Potter", "Bellatrix Lestrange"),
         ("Harry Potter", "Dolores Umbridge")
    ]
    
    print("  Creating Canon Friendships...")
    for a, b in canon_friends:
        tx.run("""
            MATCH (a:Person {name: $a}), (b:Person {name: $b})
            MERGE (a)-[:FRIEND_OF]->(b)
        """, {"a": a, "b": b})
        
    print("  Creating Canon Enemies...")
    for a, b in canon_enemies:
        tx.run("""
            MATCH (a:Person {name: $a}), (b:Person {name: $b})
            MERGE (a)-[:ENEMY_OF]->(b)
        """, {"a": a, "b": b})
        
    # 2. Dynamic Romances (From PotterDB)
    print("  Creating Romances...")
    for p in people_data:
        romances = p.get('romances')
        if romances:
            for r in romances:
                partner_name = r.split('(')[0].strip()
                tx.run("""
                    MATCH (a:Person {name: $name})
                    MATCH (b:Person) WHERE b.name CONTAINS $partner
                    MERGE (a)-[:ROMANTIC_WITH]->(b)
                """, {"name": p['name'], "partner": partner_name})

# --- FETCH & MERGE ---
def fetch_hp_api():
    print("Fetching HP-API...")
    try:
        response = requests.get("https://hp-api.onrender.com/api/characters")
        return response.json()
    except Exception as e:
        print(f"Error fetching HP-API: {e}")
        return []

def fetch_potter_db():
    print("Fetching PotterDB...")
    characters = []
    # Fetch first 10 pages for hybrid mode
    url = "https://api.potterdb.com/v1/characters?page[size]=100"
    count = 0
    max_pages = 10 
    
    while url and count < max_pages:
        print(f"  Fetching page {count+1}...")
        try:
            resp = requests.get(url)
            if resp.status_code != 200:
                break
            data = resp.json()
            for item in data.get('data', []):
                characters.append(item['attributes'])
            
            url = data.get('links', {}).get('next')
            count += 1
        except Exception as e:
            print(f"Error PotterDB: {e}")
            break
    return characters

def merge_data():
    hp_data = fetch_hp_api()
    potter_data = fetch_potter_db()
    
    merged = {}
    
    # 1. Base: HP-API
    for c in hp_data:
        name = c.get('name')
        if not name: continue
        
        merged[name] = {
            "name": name,
            "house": c.get("house") or None,
            "species": c.get("species") or "human",
            "gender": c.get("gender"),
            "ancestry": c.get("ancestry"),
            "wand": str(c.get("wand", {})), 
            "patronus": c.get("patronus"),
            "hogwartsStudent": c.get("hogwartsStudent", False),
            "hogwartsStaff": c.get("hogwartsStaff", False),
            "alive": c.get("alive", True),
            "image": c.get("image"),
            "romances": []
        }

    # 2. Merge PotterDB
    for c in potter_data:
        name = c.get('name')
        if not name: continue
        
        p_house = c.get('house')
        p_species = c.get('species')
        p_gender = c.get('gender')
        p_image = c.get('image')
        p_patronus = c.get('patronus')
        p_alive = True
        if c.get('died'): p_alive = False
        
        if name in merged:
            # Update
            target = merged[name]
            if not target['house'] and p_house: target['house'] = p_house
            if not target['species'] and p_species: target['species'] = p_species
            if not target['gender'] and p_gender: target['gender'] = p_gender
            if not target['image'] and p_image: target['image'] = p_image
            if not target['patronus'] and p_patronus: target['patronus'] = p_patronus
            if c.get('romances'): target['romances'] = c.get('romances')
        else:
            # Add new
            merged[name] = {
                "name": name,
                "house": p_house,
                "species": p_species or "human",
                "gender": p_gender,
                "ancestry": None,
                "wand": str(c.get('wands', [])),
                "patronus": p_patronus,
                "hogwartsStudent": False,
                "hogwartsStaff": False,
                "alive": p_alive,
                "image": p_image,
                "romances": c.get("romances", [])
            }
            
    return list(merged.values())

if __name__ == "__main__":
    final_data = merge_data()
    
    with driver.session() as session:
        print("Clearing DB...")
        session.execute_write(clear_db)
        print("Creating Constraints...")
        session.execute_write(create_constraints)
        
        print(f"Inserting {len(final_data)} characters...")
        
        houses_set = set()
        for i, p in enumerate(final_data):
            p["id"] = f"ch{i}"
            session.execute_write(insert_person, p)
            h = p.get("house")
            if h:
                houses_set.add(h)
                session.execute_write(link_person_house, p["id"], h)
                
        print(f"Creating {len(houses_set)} houses...")
        for h in houses_set:
             session.execute_write(insert_house, h)
            
        print("Creating Base Relations...")
        session.execute_write(create_social_relations)
        
        print("Creating Extended Social Relations (Friends, Enemies, Romances)...")
        session.execute_write(create_extended_social_relations, final_data)

    print("Success: DB Reverted to Hybrid and Populated!")
