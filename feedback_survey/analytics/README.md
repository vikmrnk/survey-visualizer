# Analytics & ML Workflow

This folder contains utilities that help you move from raw survey responses to a trained ML model that flags risky surveys.

## 1. Feature Engineering inside Django

The module `analytics/services.py` exposes:

* `compute_survey_features(survey)` – aggregates completed responses into numerical features (average scale scores, standard deviation, share of positive answers, etc.).
* `compute_satisfaction_index(features)` – converts the aggregated metrics into a 0–100 satisfaction score.
* `classify_risk_from_index(index)` – helper that maps the index to “low / medium / high” labels when no ML model is available.

These utilities are used both for reporting and to feed ML models with consistent features.

## 2. Building a Dataset

Run the management command to export a CSV dataset:

```bash
python manage.py build_ml_dataset --min-responses 5
```

* Output goes to `analytics/data/surveys_ml_dataset.csv`.
* A companion JSON file stores metadata (number of surveys and columns).
* Each row contains the engineered features plus the satisfaction index.

## 3. Training a Model (outside Django)

Use a notebook, e.g. `notebooks/survey_risk_model.ipynb`:

```python
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

df = pd.read_csv("analytics/data/surveys_ml_dataset.csv")
df["is_risky"] = (df["satisfaction_index"] < 60).astype(int)

feature_cols = [
    "num_responses",
    "avg_scale_overall",
    "std_scale_overall",
    "positive_share_overall",
]
X = df[feature_cols].fillna(0)
y = df["is_risky"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(random_state=42)
model.fit(X_train, y_train)
print(classification_report(y_test, model.predict(X_test)))
```

Persist the trained artefacts:

```python
import joblib
joblib.dump(model, "analytics/ml_models/survey_risk_model.pkl")
joblib.dump(feature_cols, "analytics/ml_models/feature_cols.pkl")
```

## 4. Using the Model in Django

The module `analytics/ml_model.py` loads the saved artefacts (or falls back to the rule-based satisfaction index) and exposes:

```python
from analytics.ml_model import predict_survey_risk_proba
```

The probability is shown as a badge on the teacher dashboard and the “My surveys” list. If the artefacts are missing, the UI automatically switches to the heuristic scoring, so you can iterate on the notebook workflow independently of the web app.

