import joblib
import pandas as pd

# Načtení modelu
model_package = joblib.load('machyn_model.joblib')
model = model_package['model']

# Získání názvů proměnných po transformaci (OneHotEncoding atd.)
preprocessor = model.named_steps['preprocessor']
feature_names = (preprocessor.transformers_[0][2] + 
                 list(preprocessor.transformers_[1][1].get_feature_names_out()))

# Extrakce koeficientů
coefs = pd.DataFrame(
    model.named_steps['regressor'].coef_,
    columns=['Váha (Koeficient)'],
    index=feature_names
)

print(coefs.sort_values(by='Váha (Koeficient)', ascending=False))