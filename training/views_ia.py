# training/views_ia.py
import os
import json
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# ── Ruta a los modelos ────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "ml_models"

# ── Carga de modelos al iniciar Django ────────────────────
_pose_clf = None
_label_enc = None
_exercise_enc = None
_recommender = None


def _load_models():
    global _pose_clf, _label_enc, _exercise_enc, _recommender
    try:
        _pose_clf = joblib.load(MODELS_DIR / "pose_classifier.pkl")
        _label_enc = joblib.load(MODELS_DIR / "label_encoder.pkl")
        _exercise_enc = joblib.load(MODELS_DIR / "exercise_encoder.pkl")
        _recommender = joblib.load(MODELS_DIR / "recommender_similarity.pkl")
        print("[IA] Modelos cargados correctamente.")
    except Exception as e:
        print(f"[IA] Error cargando modelos: {e}")


_load_models()

# ── Mensajes por tipo de error ────────────────────────────
ERROR_MESSAGES = {
    "correcto": "¡Excelente técnica! Sigue así.",
    "rodilla_valgo": "Rodillas cayendo hacia adentro — empújalas hacia afuera.",
    "espalda_redondeada": "Espalda redondeada — mantén columna neutra y pecho arriba.",
    "codo_abierto": "Codos muy abiertos — mantenlos entre 45° y 75°.",
    "codo_movido": "Codo moviéndose — pégalo al costado del cuerpo.",
    "cadera_caida": "Caderas caídas — aprieta abdomen y glúteos para subirlas.",
    "rango_incompleto": "Rango de movimiento incompleto — lleva el ejercicio al límite.",
}

FEATURE_NAMES = [
    "knee_l",
    "knee_r",
    "valgus_l",
    "valgus_r",
    "shoulder_sym",
    "hip_angle",
]


# ══════════════════════════════════════════════════════════
# ENDPOINT 1: ANALIZAR POSE
# POST /api/training/analyze-pose/
# ══════════════════════════════════════════════════════════


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def analyze_pose(request):
    if _pose_clf is None:
        return Response(
            {"error": "Modelo de IA no disponible."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        data = request.data
        exercise = data.get("exercise", "").lower().strip()
        angles = data.get("angles", {})

        # Validar features
        missing = [f for f in FEATURE_NAMES if f not in angles]
        if missing:
            return Response(
                {"error": f"Faltan features: {missing}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Codificar ejercicio
        if exercise in _exercise_enc.classes_:
            exercise_code = int(_exercise_enc.transform([exercise])[0])
        else:
            exercise_code = 0  

        # Construir vector de features
        feature_vector = np.array(
            [[float(angles.get(f, 0)) for f in FEATURE_NAMES] + [exercise_code]]
        )

        # Predicción
        pred_idx = _pose_clf.predict(feature_vector)[0]
        pred_proba = _pose_clf.predict_proba(feature_vector)[0]
        pred_label = _label_enc.inverse_transform([pred_idx])[0]
        confidence = float(pred_proba.max())

        all_probs = {
            _label_enc.inverse_transform([i])[0]: round(float(p), 4)
            for i, p in enumerate(pred_proba)
        }

        has_error = pred_label != "correcto"

        # ── Guardar en CorrectionLog ──────────────────────
        try:
            from training.models import CorrectionLog

            if confidence >= 0.85:
                severity = "high"
            elif confidence >= 0.60:
                severity = "medium"
            else:
                severity = "low"

            CorrectionLog.objects.create(
                user=request.user,
                exercise_name=exercise,
                error_type=pred_label,
                confidence=confidence,
                angles=angles,
                severity=severity,
                corrected=not has_error,
            )
        except Exception as log_err:
            print(f"[IA] Warning: no se pudo guardar CorrectionLog: {log_err}")

        return Response(
            {
                "has_error": has_error,
                "error_type": pred_label,
                "message": ERROR_MESSAGES.get(pred_label, "Analizado."),
                "confidence": round(confidence, 4),
                "all_probs": all_probs,
            }
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ══════════════════════════════════════════════════════════
# ENDPOINT 2: RECOMENDAR RUTINA
# GET /api/training/recommend-routine/
# ══════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommend_routine(request):
    if _recommender is None:
        return Response(
            {"error": "Modelo de recomendación no disponible."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    user = request.user
    goal = request.query_params.get("goal", "fuerza")
    level = request.query_params.get("level", "intermedio")

    sim_matrix = _recommender["sim_matrix"]
    id_to_idx = _recommender["id_to_idx"]
    idx_to_id = _recommender["idx_to_id"]
    exercises = _recommender["exercises"]

    user_completed_ids = _get_user_completed_exercises(user)

    if not user_completed_ids:
        recommendations = _fallback_by_rules(goal, level, exercises)
        return Response(
            {
                "method": "fallback_rules",
                "message": "Rutina generada por perfil (sin historial suficiente).",
                "exercises": recommendations,
            }
        )

    # Filtrado colaborativo
    score_accumulator = np.zeros(len(exercises))
    for completed_id in user_completed_ids:
        if completed_id not in id_to_idx:
            continue
        idx = id_to_idx[completed_id]
        score_accumulator += sim_matrix[idx]

    for ex_id in user_completed_ids:
        if ex_id in id_to_idx:
            score_accumulator[id_to_idx[ex_id]] *= 0.3

    top_indices = np.argsort(score_accumulator)[::-1][:6]

    recommendations = []
    for idx in top_indices:
        ex_id = idx_to_id[idx]
        ex = exercises[ex_id]
        recommendations.append(
            {
                "exercise_id": ex_id,
                "name": ex["name"],
                "muscle": ex["muscle"],
                "level": ex["level"],
                "similarity_score": round(float(score_accumulator[idx]), 4),
                "sets": _suggest_sets(ex["level"], goal),
                "reps": _suggest_reps(ex["level"], goal),
                "rest_seconds": _suggest_rest(goal),
            }
        )

    return Response(
        {
            "method": "collaborative_filtering",
            "message": f"Rutina personalizada basada en {len(user_completed_ids)} ejercicios completados.",
            "exercises": recommendations,
        }
    )


def _get_user_completed_exercises(user):
    try:
        from training.models import ExerciseCompletion
        from django.utils import timezone
        from datetime import timedelta

        since = timezone.now() - timedelta(days=30)
        completions = ExerciseCompletion.objects.filter(
            user=user,
            completed=True,
        ).values_list("exercise_id", flat=True)

        return list(set(completions))
    except Exception as e:
        print(f"[IA] Warning: no se pudo obtener historial: {e}")
        return []


def _fallback_by_rules(goal, level, exercises):
    goal_muscles = {
        "fuerza": ["piernas", "espalda", "pecho"],
        "hipertrofia": ["pecho", "espalda", "brazos", "hombros"],
        "perdida_peso": ["piernas", "core", "glúteos"],
        "resistencia": ["core", "piernas", "hombros"],
        "tonificacion": ["piernas", "core", "brazos", "glúteos"],
    }
    target_muscles = goal_muscles.get(goal, ["piernas", "pecho", "espalda"])

    candidates = [
        ex
        for ex_id, ex in exercises.items()
        if ex["muscle"] in target_muscles or ex["level"] == level
    ]
    if len(candidates) < 6:
        candidates += [ex for ex_id, ex in exercises.items() if ex["level"] == level]

    seen = set()
    result = []
    for ex in candidates:
        if ex["name"] not in seen:
            seen.add(ex["name"])
            result.append(
                {
                    "exercise_id": [
                        k for k, v in exercises.items() if v["name"] == ex["name"]
                    ][0],
                    "name": ex["name"],
                    "muscle": ex["muscle"],
                    "level": ex["level"],
                    "similarity_score": 0.0,
                    "sets": _suggest_sets(ex["level"], goal),
                    "reps": _suggest_reps(ex["level"], goal),
                    "rest_seconds": _suggest_rest(goal),
                }
            )
        if len(result) >= 6:
            break
    return result


def _suggest_sets(level, goal):
    if goal == "fuerza":
        return 5 if level == "avanzado" else 4
    if goal == "hipertrofia":
        return 4
    return 3


def _suggest_reps(level, goal):
    if goal == "fuerza":
        return 5
    if goal == "hipertrofia":
        return 10
    if goal == "perdida_peso":
        return 15
    return 12


def _suggest_rest(goal):
    if goal == "fuerza":
        return 180
    if goal in ("hipertrofia", "tonificacion"):
        return 90
    return 60


# ══════════════════════════════════════════════════════════
# ENDPOINT 3: REENTRENAMIENTO MANUAL
# POST /api/training/retrain/  (solo admin/staff)
# ══════════════════════════════════════════════════════════


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retrain_model(request):
    if not request.user.is_staff:
        return Response(
            {"error": "Solo administradores pueden reentrenar el modelo."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score
        from sklearn.preprocessing import LabelEncoder
        from training.models import CorrectionLog

        logs = CorrectionLog.objects.filter(angles__isnull=False).values(
            "exercise_name", "error_type", "angles"
        )

        if logs.count() < 30:
            return Response(
                {
                    "status": "skipped",
                    "message": f"Solo {logs.count()} registros reales. Se necesitan al menos 30.",
                }
            )

        real_rows = []
        for log in logs:
            ang = (
                log["angles"]
                if isinstance(log["angles"], dict)
                else json.loads(log["angles"])
            )
            row = {f: ang.get(f, 0) for f in FEATURE_NAMES}
            row["exercise"] = log["exercise_name"]
            row["label"] = log["error_type"]
            real_rows.append(row)

        real_df = pd.DataFrame(real_rows)

        synthetic_path = MODELS_DIR / "pose_dataset.csv"
        if synthetic_path.exists():
            synth_df = pd.read_csv(synthetic_path)
            synth_df = synth_df[FEATURE_NAMES + ["exercise", "label"]]
            combined_df = pd.concat([synth_df, real_df], ignore_index=True)
        else:
            combined_df = real_df

        combined_df = combined_df.sample(frac=1, random_state=42).reset_index(drop=True)

        new_exercise_enc = LabelEncoder()
        combined_df["exercise_enc"] = new_exercise_enc.fit_transform(
            combined_df["exercise"]
        )
        new_label_enc = LabelEncoder()
        y = new_label_enc.fit_transform(combined_df["label"])
        X = combined_df[FEATURE_NAMES + ["exercise_enc"]].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        new_clf = RandomForestClassifier(
            n_estimators=150,
            max_depth=10,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        new_clf.fit(X_train, y_train)
        acc = accuracy_score(y_test, new_clf.predict(X_test))

        joblib.dump(new_clf, MODELS_DIR / "pose_classifier.pkl")
        joblib.dump(new_label_enc, MODELS_DIR / "label_encoder.pkl")
        joblib.dump(new_exercise_enc, MODELS_DIR / "exercise_encoder.pkl")

        _load_models()

        return Response(
            {
                "status": "ok",
                "accuracy": round(acc, 4),
                "total_samples": len(combined_df),
                "real_samples": len(real_rows),
                "message": f"Modelo reentrenado con {len(combined_df)} muestras ({len(real_rows)} reales).",
            }
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
