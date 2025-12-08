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
    if not model:
        return jsonify({'error': 'Model not loaded'}), 500

    data = request.json
    name = data.get('name', 'Unknown')
    
    friends = data.get('friends', [])
    enemies = data.get('enemies', [])
    family = data.get('family', [])
    partners = data.get('partners', []) # List?
    
    # Process features: Count houses for each group
    # We need to look up these people in DB to see their houses.
    
    def get_house_counts(names):
        if not names:
            return {'Gryffindor': 0, 'Slytherin': 0, 'Ravenclaw': 0, 'Hufflepuff': 0}
            
        with driver.session() as session:
            result = session.run("""
                MATCH (p:Person)
                WHERE p.name IN $names
                RETURN p.house, count(p) as c
            """, {"names": names})
            
            counts = {'Gryffindor': 0, 'Slytherin': 0, 'Ravenclaw': 0, 'Hufflepuff': 0}
            for r in result:
                h = r['p.house']
                c = r['c']
                if h in counts:
                    counts[h] += c
            return counts

    f_counts = get_house_counts(friends)
    e_counts = get_house_counts(enemies)
    fam_counts = get_house_counts(family)
    p_counts = get_house_counts(partners)
    
    # Feature Vector (order must match training)
    features = [
        f_counts['Gryffindor'], f_counts['Slytherin'], f_counts['Ravenclaw'], f_counts['Hufflepuff'],
        e_counts['Gryffindor'], e_counts['Slytherin'], e_counts['Ravenclaw'], e_counts['Hufflepuff'],
        fam_counts['Gryffindor'], fam_counts['Slytherin'], fam_counts['Ravenclaw'], fam_counts['Hufflepuff'],
        p_counts['Gryffindor'], p_counts['Slytherin'], p_counts['Ravenclaw'], p_counts['Hufflepuff']
    ]
    
    # Predict
    df = pd.DataFrame([features], columns=[
        'friend_g', 'friend_s', 'friend_r', 'friend_h',
        'enemy_g', 'enemy_s', 'enemy_r', 'enemy_h',
        'fam_g', 'fam_s', 'fam_r', 'fam_h',
        'love_g', 'love_s', 'love_r', 'love_h'
    ])
    
    prediction = model.predict(df)[0]
    
    # "Enregistrer mon nom" - Save User to Graph? only if name is provided
    if name and name != "Unknown":
        with driver.session() as session:
            # Create User Node
             session.run("""
                MERGE (u:Person {name: $name})
                SET u.house = $house, u.isUser = true
            """, {"name": name, "house": prediction})
            
            # Create Relationships (Optional but cool)
             if friends:
                 session.run("""
                    MATCH (u:Person {name: $name}), (f:Person)
                    WHERE f.name IN $friends
                    MERGE (u)-[:FRIEND_OF]->(f)
                 """, {"name": name, "friends": friends})
             if enemies:
                 session.run("""
                    MATCH (u:Person {name: $name}), (e:Person)
                    WHERE e.name IN $enemies
                    MERGE (u)-[:ENEMY_OF]->(e)
                 """, {"name": name, "enemies": enemies})
             if family:
                 session.run("""
                    MATCH (u:Person {name: $name}), (fam:Person)
                    WHERE fam.name IN $family
                    MERGE (u)-[:SAME_FAMILY]->(fam)
                 """, {"name": name, "family": family})
             if partners:
                 session.run("""
                    MATCH (u:Person {name: $name}), (p:Person)
                    WHERE p.name IN $partners
                    MERGE (u)-[:ROMANTIC_WITH]->(p)
                 """, {"name": name, "partners": partners})

# ... Helper function or imports if needed

# --- SURVIVAL MODEL LOADING ---
SURVIVAL_MODEL_FILE = "survival_model.pkl"
SURVIVAL_ENCODER_FILE = "survival_encoder.pkl"

try:
    with open(SURVIVAL_MODEL_FILE, 'rb') as f:
        survival_model = pickle.load(f)
    with open(SURVIVAL_ENCODER_FILE, 'rb') as f:
        survival_le = pickle.load(f)
    print("✅ Survival Model Loaded")
except FileNotFoundError:
    print("⚠️ Survival Model missing")
    survival_model = None
    survival_le = None

@app.route('/predict_survival', methods=['POST'])
def predict_survival():
    if not survival_model:
        return jsonify({'error': 'Survival Model not loaded'}), 500
        
    data = request.json
    friends = data.get('friends', [])
    enemies = data.get('enemies', [])
    family = data.get('family', [])
    house = data.get('house', 'Gryffindor')
    
    # Features: friends_count, enemy_count, fam_count, house_code
    f_count = len(friends)
    e_count = len(enemies)
    fam_count = len(family)
    
    try:
        # Check if house is valid
        if house not in survival_le.classes_:
             house = 'Gryffindor' # Fallback
        house_code = survival_le.transform([house])[0]
    except:
        house_code = 0 
        
    df = pd.DataFrame([[f_count, e_count, fam_count, house_code]], 
                      columns=['friends_count', 'enemy_count', 'fam_count', 'house_code'])
                      
    pred = survival_model.predict(df)[0]
    
    return jsonify({'alive': bool(pred)})

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

@app.route('/winder', methods=['POST'])
def winder_match():
    data = request.json
    friends = data.get('friends', [])
    
    if not friends:
        return jsonify({'error': 'No friends provided to base matches on!'}), 400
        
    with driver.session() as session:
        # Link Prediction: Common Neighbors
        # "Find people who are friends with my friends"
        query = """
        MATCH (f:Person)
        WHERE f.name IN $friends
        MATCH (f)-[:FRIEND_OF]-(candidate:Person)
        WHERE NOT candidate.name IN $friends
        
        WITH candidate, count(f) as common_friends, collect(f.name) as shared_with
        RETURN candidate.name as name, 
               candidate.house as house, 
               candidate.image as image, 
               common_friends,
               shared_with
        ORDER BY common_friends DESC
        LIMIT 3
        """
        
        result = session.run(query, {"friends": friends})
        matches = []
        for r in result:
             matches.append({
                 "name": r["name"],
                 "house": r["house"],
                 "image": r["image"],
                 "score": r["common_friends"],
                 "reason": r["shared_with"]
             })
             
             
    return jsonify(matches)

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
            LIMIT 500
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

@app.route('/api/graph/houses')
def get_graph_by_houses():
    houses_param = request.args.get('houses', '')
    if not houses_param:
        return jsonify({"elements": {"nodes": [], "edges": []}})
        
    houses = houses_param.split(',')
    
    with driver.session() as session:
        # 1. Fetch Persons and Internal Relationships
        result_persons = session.run("""
            MATCH (p:Person)
            WHERE p.house IN $houses
            OPTIONAL MATCH (p)-[r]-(m:Person)
            WHERE m.house IN $houses
            RETURN p, r, m
            LIMIT 5000
        """, {"houses": houses})
        
        nodes = []
        edges = []
        added_nodes = set()
        
        for record in result_persons:
            p = record['p']
            r = record['r']
            m = record['m']
            
            p_data = {"id": p["id"], "label": p.get("name", "Unknown"), "group": "person", "house": p.get("house")}
            
            if p_data["id"] not in added_nodes:
                nodes.append({"data": p_data})
                added_nodes.add(p_data["id"])
                
            if r and m:
                m_label = m.get("name", m.get("id"))
                m_data = {"id": m.get("id", m_label), "label": m_label, "group": "person", "house": m.get("house")}
                
                if m_data["id"] not in added_nodes:
                    nodes.append({"data": m_data})
                    added_nodes.add(m_data["id"])
                
                edges.append({"data": {"source": p_data["id"], "target": m_data["id"], "label": r.type}})

        # 2. Fetch House Nodes and BELONGS_TO Relationships
        # This ensures the "House Connection" filter works and we see the House Node hub.
        result_houses = session.run("""
            MATCH (h:House)
            WHERE h.name IN $houses
            OPTIONAL MATCH (p:Person)-[r:BELONGS_TO]->(h)
            RETURN h, r, p
        """, {"houses": houses})
        
        for record in result_houses:
            h = record['h']
            r = record['r']
            p = record['p']
            
            h_data = {"id": h.get("id", h["name"]), "label": h["name"], "group": "house"}
            if h_data["id"] not in added_nodes:
                nodes.append({"data": h_data})
                added_nodes.add(h_data["id"])
                
            if r and p:
                 p_id = p["id"]
                 # p should already be in nodes from step 1, but we check to be safe or if unconnected otherwise
                 if p_id in added_nodes:
                     edges.append({"data": {"source": p_id, "target": h_data["id"], "label": "BELONGS_TO"}})

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
