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
            p.role = $role,
            p.gender = $gender,
            p.patronus = $patronus,
            p.ancestry = $ancestry,
            p.wand = $wand,
            p.species = $species,
            p.dateOfBirth = $dateOfBirth,
            p.hogwartsStudent = $hogwartsStudent,
            p.hogwartsStaff = $hogwartsStaff,
            p.alive = $alive
    """, person)

def insert_house(tx, house_name):
    tx.run("MERGE (h:House {name: $name})", {"name": house_name})

def link_person_house(tx, person_id, house_name):
    tx.run("""
        MATCH (p:Person {id: $person_id})
        MATCH (h:House {name: $house_name})
        MERGE (p)-[:BELONGS_TO]->(h)
    """, {"person_id": person_id, "house_name": house_name})

# Relations sociales automatiques
def create_social_relations(tx):
    # Même ancestry
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.ancestry IS NOT NULL AND a.ancestry = b.ancestry AND a.id < b.id
        MERGE (a)-[:SAME_ANCESTRY]->(b)
    """)
    # Même matériau de baguette
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.wand IS NOT NULL AND b.wand IS NOT NULL 
        AND a.wand CONTAINS 'wood' AND b.wand CONTAINS 'wood'
        AND a.id < b.id
        MERGE (a)-[:SAME_WAND_MATERIAL]->(b)
    """)
    # Même espèce
    tx.run("""
        MATCH (a:Person), (b:Person)
        WHERE a.species IS NOT NULL AND a.species = b.species AND a.id < b.id
        MERGE (a)-[:SAME_SPECIES]->(b)
    """)

# --- Récupération des personnages depuis l'API ---
response = requests.get("https://hp-api.onrender.com/api/characters")
characters = response.json()

persons = []
houses_set = set()

for idx, c in enumerate(characters):
    persons.append({
        "id": f"p{idx+1}",
        "name": c.get("name"),
        "house": c.get("house"),
        "role": c.get("role"),
        "gender": c.get("gender"),
        "patronus": c.get("patronus"),
        "ancestry": c.get("ancestry"),
        "wand": str(c.get("wand")),
        "species": c.get("species"),
        "dateOfBirth": c.get("dateOfBirth"),
        "hogwartsStudent": c.get("hogwartsStudent"),
        "hogwartsStaff": c.get("hogwartsStaff"),
        "alive": c.get("alive")
    })
    if c.get("house"):
        houses_set.add(c.get("house"))

# --- Import dans Neo4j ---
with driver.session() as session:
    # Vider la base
    session.execute_write(clear_db)

    # Création contraintes
    session.execute_write(create_constraints)

    # Création des maisons
    for h in houses_set:
        session.execute_write(insert_house, h)

    # Création des personnages et liens
    for person in persons:
        session.execute_write(insert_person, person)
        if person["house"]:
            session.execute_write(link_person_house, person["id"], person["house"])

    # Création des relations sociales automatiques
    session.execute_write(create_social_relations)

print("✅ Graphe HP API complet avec relations sociales automatiques créé !")
