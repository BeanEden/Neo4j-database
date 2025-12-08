import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder
from neo4j import GraphDatabase
import pickle
import os

MODEL_FILE = "survival_model.pkl"
ENCODER_FILE = "survival_encoder.pkl"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

def fetch_data():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Fetch Data: House, Friends Count, Enemies Count, Family Count -> Target: Alive
    query = """
    MATCH (p:Person)
    WHERE p.house IN ['Gryffindor', 'Slytherin', 'Ravenclaw', 'Hufflepuff']
    // Get counts
    OPTIONAL MATCH (p)-[:FRIEND_OF]-(f:Person)
    WITH p, count(f) as friends_count
    
    OPTIONAL MATCH (p)-[:ENEMY_OF]-(e:Person)
    WITH p, friends_count, count(e) as enemy_count
    
    OPTIONAL MATCH (p)-[:SAME_FAMILY]-(fam:Person)
    WITH p, friends_count, enemy_count, count(fam) as fam_count
    
    RETURN p.name as name, p.house as house, p.alive as alive,
           friends_count, enemy_count, fam_count
    """
    
    with driver.session() as session:
        result = session.run(query)
        data = [r.data() for r in result]
        
    driver.close()
    return pd.DataFrame(data)

def train_survival_model():
    df = fetch_data()
    print(f"Total dataset: {len(df)}")
    
    # Encode House
    le = LabelEncoder()
    df['house_code'] = le.fit_transform(df['house'])
    
    # Features & Target
    # We want to predict 'alive'
    # Check NaN
    df['alive'] = df['alive'].fillna(True) # Assume alive if unknown? Or drop?
    # Ensure boolean
    df['alive'] = df['alive'].astype(bool)
    
    X = df[['friends_count', 'enemy_count', 'fam_count', 'house_code']]
    y = df['alive']
    
    print(f"Survival Rate in set: {y.mean():.2%}")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    print("Accuracy:", accuracy_score(y_test, clf.predict(X_test)))
    
    # Save
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(clf, f)
        
    with open(ENCODER_FILE, 'wb') as f:
        pickle.dump(le, f)
        
    print("Survival Model Saved.")

if __name__ == "__main__":
    train_survival_model()
