from flask import Flask, render_template, request, jsonify
import pickle
import pandas as pd
import numpy as np
from neo4j import GraphDatabase
import os

app = Flask(__name__)

# --- CONFIG ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# --- ML MODEL LOADING ---
MODEL_FILE = "house_classifier.pkl"
ENCODERS_FILE = "encoders.pkl"

try:
    with open(MODEL_FILE, 'rb') as f:
        model = pickle.load(f)
    with open(ENCODERS_FILE, 'rb') as f:
        encoders = pickle.load(f)
    print("✅ ML Model Loaded")
except FileNotFoundError:
    print("⚠️ ML Model not found. Training now...")
    import ml_model
    ml_model.train_model()
    with open(MODEL_FILE, 'rb') as f:
        model = pickle.load(f)
    with open(ENCODERS_FILE, 'rb') as f:
        encoders = pickle.load(f)
    print("✅ ML Model Trained and Loaded")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if not model or not encoders:
        return jsonify({'error': 'Model not loaded'}), 500

    data = request.json
    
    # Prepare dataframe for prediction
    input_data = {
        'ancestry': [data.get('ancestry', 'unknown')],
        'species': [data.get('species', 'human')],
        'gender': [data.get('gender', 'male')],
        'hogwartsStudent': [data.get('hogwartsStudent', False)],
        'hogwartsStaff': [data.get('hogwartsStaff', False)],
        'wizard': [data.get('wizard', True)],
        'alive': [data.get('alive', True)]
    }
    
    df = pd.DataFrame(input_data)
    
    # Encode categorical
    for col, le in encoders.items():
        # Handle unseen labels carefully
        df[col] = df[col].apply(lambda x: x if x in le.classes_ else 'unknown') 
        # Note: Ideally 'unknown' should be in training classes, or we handle fallback
        # For simplicity, we might force mapping or catch error.
        # Let's map to first class if unknown for now to prevent crash
        df[col] = df[col].apply(lambda x: le.transform([x])[0] if x in le.classes_ else le.transform([le.classes_[0]])[0])

    prediction = model.predict(df)[0]
    return jsonify({'house': prediction})

@app.route('/characters')
def characters_page():
    return render_template('characters.html')

@app.route('/api/characters')
def get_all_characters():
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Person)
            RETURN p
            ORDER BY p.name
        """)
        chars = []
        for record in result:
            p = record['p']
            chars.append({
                "name": p.get("name"),
                "house": p.get("house"),
                "species": p.get("species"),
                "alive": p.get("alive"),
                "image": p.get("image")
            })
        return jsonify(chars)

@app.route('/graph')
def graph_page():
    return render_template('graph.html')

@app.route('/api/graph/<name>')
def get_graph(name):
    with driver.session() as session:
        # 1. Fetch direct connections (Person -[r]- Other)
        result = session.run("""
            MATCH (p:Person {name: $name})-[r]-(m)
            RETURN p, r, m
            LIMIT 50
        """, {"name": name})
        
        nodes = []
        edges = []
        added_nodes = set()
        
        records = list(result)
        
        # If input not found directly, try partial match for the MAIN person
        if not records:
             # Try Partial match to find the main person 'p'
            result = session.run("""
                MATCH (p:Person)-[r]-(m)
                WHERE toLower(p.name) CONTAINS toLower($name)
                RETURN p, r, m
                LIMIT 50
            """, {"name": name})
            records = list(result)

        # 2. Fetch Housemates (Person -> House <- Mate) using the NAME found in records (or input name if exact)
        # We need to know the specific 'p' we are dealing with to find its housemates correctly.
        # Let's extract 'p' from the first record if available, or just use the name input if we assume exact match logic.
        
        target_name = name
        if records:
             target_name = records[0]['p']['name']

        housemates_result = session.run("""
            MATCH (p:Person {name: $target_name})-[:BELONGS_TO]->(h:House)<-[:BELONGS_TO]-(mate:Person)
            RETURN h, mate
            LIMIT 100
        """, {"target_name": target_name})
        
        housemates_records = list(housemates_result)
        
        # Helper to process records
        all_records = []
        
        # Add Direct Connections
        for record in records:
            all_records.append({
                'source': record['p'],
                'target': record['m'],
                'rel': record['r']
            })
            
        # Add Housemates Connections (Source=Mate, Target=House, Rel=Implicit BELONGS_TO)
        # Note: In the query `(p)->(h)<-[mate]`, we want to show the connection `mate->h`.
        # And we assume `p->h` is already covered by the direct connections query if `p` has a house.
        # But wait, `p-[r]-m` might NOT include `p->House` if `m` is only People?
        # The first query `MATCH (p)-[r]-(m)` matches ANY neighbor `m`, so if `p` is connected to House, it shows up.
        # So we just need to add `mate -> House`.
        
        for record in housemates_records:
            h = record['h']
            mate = record['mate']
            # Create a fake relationship object or just dict for consistency
            # Neo4j python driver returns Relationship objects, but we can mock it or just handle data directly.
            # Only need type for the graph.
            
            # Check if this edge is already added? 
            # We filter by nodes later, but explicit edges need handling.
            # Let's just add to nodes/edges lists directly.
            
            h_data = {"id": h.get("id", h["name"]), "label": h["name"], "group": "house"}
            mate_label = mate.get("name", "Unknown")
            mate_data = {"id": mate["id"], "label": mate_label, "group": "person", "house": mate.get("house")}
            
            # Add House Node
            if h_data["id"] not in added_nodes:
                nodes.append({"data": h_data})
                added_nodes.add(h_data["id"])
            
            # Add Mate Node
            if mate_data["id"] not in added_nodes:
                nodes.append({"data": mate_data})
                added_nodes.add(mate_data["id"])
            
            # Add Edge (Mate -> House)
            edges.append({"data": {"source": mate_data["id"], "target": h_data["id"], "label": "BELONGS_TO"}})

        # Process Direct Connections
        for record in records:
            p = record['p']
            m = record['m']
            r = record['r']
            
            p_data = {"id": p["id"], "label": p.get("name", "Unknown"), "group": "person", "house": p.get("house")}
            m_label = m.get("name", m.get("id"))
            m_group = "house" if "House" in m.labels else "person"
            m_data = {"id": m.get("id", m_label), "label": m_label, "group": m_group}
            
            if p_data["id"] not in added_nodes:
                nodes.append({"data": p_data})
                added_nodes.add(p_data["id"])
            
            if m_data["id"] not in added_nodes:
                nodes.append({"data": m_data})
                added_nodes.add(m_data["id"])
                
            edges.append({"data": {"source": p_data["id"], "target": m_data["id"], "label": r.type}})

        return jsonify({"elements": {"nodes": nodes, "edges": edges}})

@app.route('/api/search')
def search_person():
    q = request.args.get('q', '')
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Person)
            WHERE toLower(p.name) CONTAINS toLower($q)
            RETURN p.name as name
            LIMIT 10
        """, {"q": q})
        return jsonify([record["name"] for record in result])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
