import requests
import pandas as pd
import numpy as np
import pickle
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report

MODEL_FILE = "house_classifier.pkl"
ENCODERS_FILE = "encoders.pkl"

def fetch_data():
    print("Fetching data from HP API...")
    response = requests.get("https://hp-api.onrender.com/api/characters")
    data = response.json()
    return pd.DataFrame(data)

def preprocess_data(df):
    print("Preprocessing data...")
    # Keep relevant columns for prediction
    # precise attributes that might indicate house
    features = ['ancestry', 'species', 'gender', 'hogwartsStudent', 'hogwartsStaff', 'wizard', 'alive']
    target = 'house'

    # Filter out records with no house
    df = df[df['house'] != '']
    df = df[features + [target]].copy()

    # Fill missing values
    df['ancestry'] = df['ancestry'].replace('', 'unknown').fillna('unknown')
    df['species'] = df['species'].replace('', 'human').fillna('human') # Assumption
    
    # Encode categorical variables
    encoders = {}
    for col in ['ancestry', 'species', 'gender']:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le
    
    return df, encoders

def train_model():
    df = fetch_data()
    df_clean, encoders = preprocess_data(df)

    X = df_clean.drop('house', axis=1)
    y = df_clean['house']

    print(f"Training on {len(df_clean)} characters...")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print(classification_report(y_test, y_pred))

    # Save model and encoders
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(clf, f)
    
    with open(ENCODERS_FILE, 'wb') as f:
        pickle.dump(encoders, f)
    
    print(f"Model saved to {MODEL_FILE}")
    print(f"Encoders saved to {ENCODERS_FILE}")

if __name__ == "__main__":
    train_model()
