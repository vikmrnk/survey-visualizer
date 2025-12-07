from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

# Не імпортуємо services на верхньому рівні - буде лінивий імпорт
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "ml_models"

_model = None
_feature_cols: Optional[list[str]] = None


def _load_artifacts():
    global _model, _feature_cols
    if _model is not None and _feature_cols is not None:
        return

    try:
        import joblib  # lazy import to avoid heavy numpy cost at startup
    except ImportError:
        logger.warning("joblib is not installed. Falling back to rule-based scoring.")
        _model = None
        _feature_cols = None
        return

    try:
        model_path = MODEL_DIR / "survey_risk_model.pkl"
        feature_cols_path = MODEL_DIR / "feature_cols.pkl"
        
        # Перевіряємо наявність файлів перед завантаженням
        if not model_path.exists() or not feature_cols_path.exists():
            logger.warning("Survey risk model artifacts not found. Falling back to rule-based scoring.")
            _model = None
            _feature_cols = None
            return
        
        _model = joblib.load(model_path)
        _feature_cols = joblib.load(feature_cols_path)
        logger.info("Loaded survey risk model with %s features", len(_feature_cols))
    except (FileNotFoundError, OSError, Exception) as e:
        logger.warning("Failed to load survey risk model: %s. Falling back to rule-based scoring.", e)
        _model = None
        _feature_cols = None


def _build_feature_vector(features: dict, feature_cols: list[str]) -> list[float]:
    vector = []
    for col in feature_cols:
        value = features.get(col)
        vector.append(0.0 if value is None else float(value))
    return vector


def predict_survey_risk_proba(survey) -> Optional[float]:
    """
    Return the probability that a survey is risky (1.0 = highest risk).
    If the ML model is not available, fall back to a simple heuristic
    using the satisfaction index.
    """
    # Лінивий імпорт services, щоб не завантажувати при старті
    from analytics.services import compute_satisfaction_index, compute_survey_features
    
    try:
        features = compute_survey_features(survey)
        num_responses = features.get("num_responses", 0)
        
        if num_responses == 0:
            logger.debug("Survey %s has no responses", survey.id)
            return None

        # Обчислюємо satisfaction_index і додаємо до фіч
        satisfaction = compute_satisfaction_index(features)
        features["satisfaction_index"] = satisfaction

        _load_artifacts()
        if _model is not None and _feature_cols:
            try:
                vector = _build_feature_vector(features, _feature_cols)
                proba = _model.predict_proba([vector])[0][1]
                logger.debug("Survey %s: ML model prediction = %.2f", survey.id, proba)
                return float(proba)
            except Exception as e:
                logger.warning("Failed to use ML model for survey %s: %s", survey.id, e)

        # Fallback: convert satisfaction index into a pseudo-probability
        index = compute_satisfaction_index(features)
        proba = max(0.0, min(1.0, (60 - index) / 60))
        logger.debug("Survey %s: fallback prediction = %.2f (satisfaction = %.2f)", survey.id, proba, index)
        return proba
    except Exception as e:
        logger.error("Error computing risk for survey %s: %s", survey.id, e, exc_info=True)
        return None

