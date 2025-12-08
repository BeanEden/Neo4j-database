import pandas as pd
from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def inspect_data():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    query = """
    MATCH (p:Person)
    WHERE p.house IN ['Gryffindor', 'Slytherin', 'Ravenclaw', 'Hufflepuff']
    
    OPTIONAL MATCH (p)-[:FRIEND_OF]-(f:Person)
    WITH p, sum(CASE WHEN f.house='Gryffindor' THEN 1 ELSE 0 END) as friend_g
    
    WHERE friend_g > 0
    RETURN p.name, p.house, friend_g LIMIT 20
    """
    
    print("--- Sampling Gryffindor Friends ---")
    with driver.session() as session:
        result = session.run(query)
        for r in result:
             print(f"{r['p.name']} ({r['p.house']}) - Friends in G: {r['friend_g']}")

    driver.close()

if __name__ == "__main__":
    inspect_data()
