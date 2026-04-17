import pandas as pd
import numpy as np
import os
import joblib
import random
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, r2_score


base_path = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_path, 'data_stitky_EPC_enriched.csv')

print(f"Looking for data at: {file_path}")

try:
    df = pd.read_csv(file_path, sep=';', encoding='utf-8')
    df = df.replace(r'^\s*$', np.nan, regex=True)
except FileNotFoundError:
    print(f"Error: The file 'data_stitky_EPC_with_ruian.csv' was not found in {base_path}.")
    print("Please ensure the CSV file is in the same folder as this script.")
    exit()

# Přepis hodnot
epc_map = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7}

df = df.dropna(subset=['Energy Performance Certificate (EPC)'])
df['target'] = df['Energy Performance Certificate (EPC)'].map(epc_map)

# Převedení na datum a extrakce roku
df['Rok dokončení'] = pd.to_datetime(df['Datum dokončení'], errors='coerce').dt.year
# Vyplnění chybějících hodnot (např. mediánem)
df['Rok dokončení'] = df['Rok dokončení'].fillna(df['Rok dokončení'].median())

# Distribuce v populaci - rok 2024
epc_probabilities = {
    'A': 0.05,
    'B': 0.17,
    'C': 0.25,
    'D': 0.23,
    'E': 0.11,
    'F': 0.06,
    'G': 0.12
}

def get_epc_label_probabilistic(score, probabilities):
    labels = list(probabilities.keys())
    weights = list(probabilities.values())

    fractional_part = score % 1
    
    if 0.25 <= fractional_part <= 0.75:
        return random.choices(labels, weights=weights, k=1)[0]
    else:
        inv_map = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F', 7: 'G'}
        rounded = int(np.clip(round(score), 1, 7))
        return inv_map[rounded]


numeric_features = ['Počet podlaží', 'Počet bytů', 'Zastavěná plocha [m2]', 'heating_days', 'Rok dokončení']
categorical_features = ['Druh svislé nosné konstrukce', 'Vybavení výtahem', 'Způsob vytápění']


for col in numeric_features:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(df[col].median())
for col in categorical_features:
    df[col] = df[col].astype(str).fillna('Unknown')

# 1. Nahrazení textu "Nezjištěno" a prázdných hodnot za NaN
df = df.replace(['Nezjištěno', 'nezjištěno', 'Unknown'], np.nan)

# 2. Definice sloupců, které model používá
categorical_features = ['Druh svislé nosné konstrukce', 'Vybavení výtahem', 'Způsob vytápění']
numeric_features = ['Počet podlaží', 'Počet bytů', 'Zastavěná plocha [m2]', 'heating_days', 'Rok dokončení']

# 3. Odstranění řádků, které mají v těchto klíčových sloupcích NaN (tedy i původní "Nezjištěno")
print(f"Původní počet řádků: {len(df)}")
df = df.dropna(subset=categorical_features + numeric_features)
print(f"Počet řádků po očištění od 'Nezjištěno': {len(df)}")


### Modýlek
X = df[numeric_features + categorical_features]
y = df['target']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numeric_features),
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
    ])

model_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', LinearRegression())
])

print("Training model...")
model_pipeline.fit(X_train, y_train)

# Evaluace
y_pred = model_pipeline.predict(X_test)
print(f"R² Score: {r2_score(y_test, y_pred):.4f}")
print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")

def get_epc_label(score):
    inv_map = {v: k for k, v in epc_map.items()}
    rounded = int(np.clip(round(score), 1, 7))
    return inv_map[rounded]

# ULOŽTO
model_data = {
    'model': model_pipeline,
    'epc_map': epc_map,
    'population_dist': epc_probabilities
}

model_output_path = os.path.join(base_path, 'machyn_model.joblib')
joblib.dump(model_data, model_output_path)

print(f"✅ Model successfully saved to: {model_output_path}")

# sample_pred = y_pred[0]
# print(f"Example Prediction - Score: {sample_pred:.2f} -> Label: {get_epc_label(sample_pred)}")