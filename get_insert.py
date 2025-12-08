import requests
from neo4j import GraphDatabase
import os

# --- CONFIG ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# --- ROMANCE DATA ---
# Mapped to likely HP-API names (English) where possible, or kept as User provided if unsure.
# We will match by stripping substrings if needed or exact match.
ROMANCES = [
    ("Harry Potter", "Ginny Weasley"),
    ("Ron Weasley", "Hermione Granger"),
    ("James Potter", "Lily Potter"), # User said Lily Evans
    ("Arthur Weasley", "Molly Weasley"), # User said Molly Prewett
    ("Bill Weasley", "Fleur Delacour"),
    ("Remus Lupin", "Nymphadora Tonks"),
    ("Rubeus Hagrid", "Olympe Maxime"),
    ("Vernon Dursley", "Petunia Dursley"), # User said Petunia Evans
    ("Frank Longbottom", "Alice Longbottom"), # User said Londubat
    ("Teddy Lupin", "Victoire Weasley"),
    ("George Weasley", "Angelina Johnson"),
    ("Neville Longbottom", "Hannah Abbott"), # User said Londubat
    ("Luna Lovegood", "Rolf Scamander"),
    ("Percy Weasley", "Audrey"),
    ("Hermione Granger", "Viktor Krum"),
    ("Ron Weasley", "Lavender Brown"),
    ("Harry Potter", "Cho Chang"),
    ("Ginny Weasley", "Dean Thomas"),
    ("Ginny Weasley", "Michael Corner"),
    ("Percy Weasley", "Penelope Clearwater"),
    ("Draco Malfoy", "Astoria Greengrass"),
    ("Tom Riddle", "Merope Gaunt"), # User said Tom Jedusor Sr
    ("Xenophilius Lovegood", "Pandora Lovegood"),
    ("Lucius Malfoy", "Narcissa Malfoy"), # User said Narcissa Black
    ("Ted Tonks", "Andromeda Tonks"), # User said Andromeda Black
    ("Fleamont Potter", "Euphemia Potter"),
    ("Septimus Weasley", "Cedrella Black")
]

# Alternate names map to help matching User Input to HP API
NAME_MAP = {
    "Lily Evans": "Lily Potter",
    "Molly Prewett": "Molly Weasley",
    "Petunia Evans": "Petunia Dursley",
    "Frank Londubat": "Frank Longbottom",
    "Alice Londubat": "Alice Longbottom",
    "Neville Londubat": "Neville Longbottom",
    "Tom Jedusor": "Tom Riddle",
    "Tom Jedusor Sr": "Tom Riddle",
    "Narcissa Black": "Narcissa Malfoy",
    "Andromeda Black": "Andromeda Tonks"
}

def fetch_hp_api():
    print("Fetching HP-API...")
    try:
        return requests.get("https://hp-api.onrender.com/api/characters").json()
    except Exception as e:
        print(f"Error fetching HP-API: {e}")
        return []

def clear_db(tx):
    tx.run("MATCH (n) DETACH DELETE n")

def create_constraints(tx):
    tx.run("CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;")
    tx.run("CREATE CONSTRAINT house_name IF NOT EXISTS FOR (h:House) REQUIRE h.name IS UNIQUE;")

def insert_data(tx, characters):
    print("  Inserting Characters & Houses...")
    for c in characters:
        name = c.get('name')
        if not name: continue
        
        house = c.get('house') or "Unknown"
        
        # Insert House
        if house:
            tx.run("MERGE (h:House {name: $name})", {"name": house})
            
        # Insert Person
        tx.run("""
            MERGE (p:Person {name: $name})
            SET p.house = $house,
                p.species = $species,
                p.gender = $gender,
                p.alive = $alive,
                p.image = $image,
                p.id = $id
        """, {
            "name": name,
            "house": house,
            "species": c.get("species"),
            "gender": c.get("gender"),
            "alive": c.get("alive", True),
            "image": c.get("image", ""),
            "id": c.get("id", name) 
        })
        
        # Link Person -> House
        if house:
            tx.run("""
                MATCH (p:Person {name: $name})
                MATCH (h:House {name: $house})
                MERGE (p)-[:BELONGS_TO]->(h)
            """, {"name": name, "house": house})

def create_rules_relationships(tx):
    print("  Creating Rule-Based Relationships...")
    
    # 1. SAME FAMILY (Same Last Name)
    # We'll do this in Cypher by splitting name. 
    # Assumption: Last word is last name.
    # We avoid matching common names or single names loosely if possible, 
    # but for HP-API 'First Last' is standard.
    # excluding 'Unknown' houses or empty names
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.name CONTAINS ' ' AND b.name CONTAINS ' ' 
        AND split(a.name, ' ')[-1] = split(b.name, ' ')[-1]
        AND id(a) < id(b)
        MERGE (a)-[:SAME_FAMILY]->(b)
    """)
    
    # 2. FRIEND (AMI) = Same House
    # User specified "Gryffondor", implied all houses.
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.house <> '' AND a.house <> 'Unknown' 
        AND a.house = b.house
        AND id(a) < id(b)
        MERGE (a)-[:FRIEND_OF]->(b)
    """)

    # 3. ENEMY (ENNEMI) = Gryffindor vs Slytherin
    tx.run("""
        MATCH (a:Person {house: 'Gryffindor'}), (b:Person {house: 'Slytherin'})
        MERGE (a)-[:ENEMY_OF]->(b)
        MERGE (b)-[:ENEMY_OF]->(a)
    """)

def create_romances(tx):
    print("  Creating Romances...")
    for p1, p2 in ROMANCES:
        # Check constraints mappings
        if p1 in NAME_MAP: p1 = NAME_MAP[p1]
        if p2 in NAME_MAP: p2 = NAME_MAP[p2]
        
        # Try to match names loosely if exact match fails? 
        # For now, strict match on Name as stored in DB.
        # Note: If nodes don't exist, this does nothing which is safer than creating empty nodes.
        tx.run("""
            MATCH (a:Person), (b:Person)
            WHERE (a.name = $p1 OR a.name CONTAINS $p1) 
              AND (b.name = $p2 OR b.name CONTAINS $p2)
            MERGE (a)-[:ROMANTIC_WITH]->(b)
            MERGE (b)-[:ROMANTIC_WITH]->(a)
        """, {"p1": p1, "p2": p2})

if __name__ == "__main__":
    data = fetch_hp_api()
    print(f"Fetched {len(data)} characters from HP-API.")
    
    with driver.session() as session:
        session.execute_write(clear_db)
        session.execute_write(create_constraints)
        session.execute_write(insert_data, data)
        session.execute_write(create_rules_relationships)
        session.execute_write(create_romances)
        
    print("Done! Database updated with HP-API and new rules.")
