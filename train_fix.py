import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils import resample
from neo4j import GraphDatabase
import pickle
import os

MODEL_FILE = "house_classifier.pkl"
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def fetch_graph_data():
    print("Fetching training data from Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    query = """
    MATCH (p:Person)
    WHERE p.house IN ['Gryffindor', 'Slytherin', 'Ravenclaw', 'Hufflepuff']
    
    // Friends
    OPTIONAL MATCH (p)-[:FRIEND_OF]-(f:Person)
    WITH p, 
         sum(CASE WHEN f.house='Gryffindor' THEN 1 ELSE 0 END) as friend_g,
         sum(CASE WHEN f.house='Slytherin' THEN 1 ELSE 0 END) as friend_s,
         sum(CASE WHEN f.house='Ravenclaw' THEN 1 ELSE 0 END) as friend_r,
         sum(CASE WHEN f.house='Hufflepuff' THEN 1 ELSE 0 END) as friend_h

    // Enemies
    OPTIONAL MATCH (p)-[:ENEMY_OF]-(e:Person)
    WITH p, friend_g, friend_s, friend_r, friend_h,
         sum(CASE WHEN e.house='Gryffindor' THEN 1 ELSE 0 END) as enemy_g,
         sum(CASE WHEN e.house='Slytherin' THEN 1 ELSE 0 END) as enemy_s,
         sum(CASE WHEN e.house='Ravenclaw' THEN 1 ELSE 0 END) as enemy_r,
         sum(CASE WHEN e.house='Hufflepuff' THEN 1 ELSE 0 END) as enemy_h
         
    // Family
    OPTIONAL MATCH (p)-[:SAME_FAMILY]-(fam:Person)
    WITH p, friend_g, friend_s, friend_r, friend_h, enemy_g, enemy_s, enemy_r, enemy_h,
         sum(CASE WHEN fam.house='Gryffindor' THEN 1 ELSE 0 END) as fam_g,
         sum(CASE WHEN fam.house='Slytherin' THEN 1 ELSE 0 END) as fam_s,
         sum(CASE WHEN fam.house='Ravenclaw' THEN 1 ELSE 0 END) as fam_r,
         sum(CASE WHEN fam.house='Hufflepuff' THEN 1 ELSE 0 END) as fam_h

    // Romance (Weighted highly?)
    OPTIONAL MATCH (p)-[:ROMANTIC_WITH]-(r:Person)
    WITH p, friend_g, friend_s, friend_r, friend_h, enemy_g, enemy_s, enemy_r, enemy_h, fam_g, fam_s, fam_r, fam_h,
         sum(CASE WHEN r.house='Gryffindor' THEN 1 ELSE 0 END) as love_g,
         sum(CASE WHEN r.house='Slytherin' THEN 1 ELSE 0 END) as love_s,
         sum(CASE WHEN r.house='Ravenclaw' THEN 1 ELSE 0 END) as love_r,
         sum(CASE WHEN r.house='Hufflepuff' THEN 1 ELSE 0 END) as love_h
         
    RETURN p.name as name, p.house as house,
           friend_g, friend_s, friend_r, friend_h,
           enemy_g, enemy_s, enemy_r, enemy_h,
           fam_g, fam_s, fam_r, fam_h,
           love_g, love_s, love_r, love_h
    """
    
    with driver.session() as session:
        result = session.run(query)
        data = [r.data() for r in result]
        
    driver.close()
    return pd.DataFrame(data)

def train_balanced_model():
    df = fetch_graph_data()
    
    features = [
        'friend_g', 'friend_s', 'friend_r', 'friend_h',
        'enemy_g', 'enemy_s', 'enemy_r', 'enemy_h',
        'fam_g', 'fam_s', 'fam_r', 'fam_h',
        'love_g', 'love_s', 'love_r', 'love_h'
    ]
    
    # Filter to meaningful data
    df['total'] = df[features].sum(axis=1)
    df_active = df[df['total'] > 2].copy() # At least 3 connections to be significant
    
    print(f"Training on {len(df_active)} active characters (filtered from {len(df)})")
    
    X = df_active[features]
    y = df_active['house']
    
    # Simple Random Forest
    clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    clf.fit(X, y)
    
    print("Feature Importances:")
    for name, score in zip(features, clf.feature_importances_):
        print(f"  {name}: {score:.4f}")
        
    # Test Sanity
    test_vec = pd.DataFrame([[10,0,0,0, 0,10,0,0, 5,0,0,0, 1,0,0,0]], columns=features)
    # Friend=G(10), Enemy=S(10), Fam=G(5), Love=G(1) -> Should be GRYFFINDOR
    print("Test Vector (Gryffindor Heavy):", clf.predict(test_vec)[0])
    
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(clf, f)

if __name__ == "__main__":
    train_balanced_model()
