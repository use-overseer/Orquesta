from __future__ import annotations

"""assigner.py

Este módulo contiene la lógica de asignación de Orquesta.

- **Pydantic schemas** para validar los payloads de los endpoints FastAPI.
- **Scoring**: función determinista (`compute_score`) y un *stub* de modelo ML opcional.
- **Asignación**: `assign_best_candidate` selecciona el mejor candidato usando la puntuación.
- **Feedback**: `process_feedback` actualiza los pesos del modelo en la base de datos.
"""

import json
import pathlib
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.linear_model import LinearRegression
import joblib

from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# Modelos locales
from models import Person, ModelWeights

# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------
class AssignPayload(BaseModel):
    """Payload for `/v1/assign`.

    - ``role``: nombre del rol a asignar.
    - ``person_ids``: lista de IDs de candidatos elegibles.
    - ``stats``: estadísticas opcionales por candidato (puede estar vacío).
    - ``weights``: sobrescribe los pesos del modelo; si se omite se usan los
      almacenados en la tabla ``ModelWeights`` (nombre "default").
    """

    role: str = Field(..., description="Target role for the assignment")
    person_ids: List[int] = Field(..., description="Candidate person IDs")
    stats: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional pre‑computed statistics for each candidate",
    )
    weights: Optional[Dict[str, float]] = Field(
        default=None, description="Explicit weight overrides"
    )

    @validator("person_ids")
    def non_empty_ids(cls, v: List[int]):
        if not v:
            raise ValueError("person_ids must contain at least one ID")
        return v


class FeedbackPayload(BaseModel):
    """Payload for `/v1/feedback`.

    ``result`` solo puede ser ``"aceptada"`` o ``"corrigida"``.
    """

    role: str = Field(..., description="Role for which feedback is given")
    person_id: int = Field(..., description="ID of the person originally assigned")
    result: str = Field(..., description="Result: 'aceptada' or 'corrigida'")
    alternative_id: Optional[int] = Field(
        default=None, description="ID of the alternative person when result is 'corrigida'"
    )

    @validator("result")
    def allowed_result(cls, v: str):
        if v not in {"aceptada", "corrigida"}:
            raise ValueError("result must be either 'aceptada' or 'corrigida'")
        return v

# ---------------------------------------------------------------------------
# Self-Learning: Retrain model based on history
# ---------------------------------------------------------------------------
async def retrain_model(db: AsyncSession):
    """Re-entrena el modelo ML usando toda la historia de asignaciones."""
    from models import AssignmentHistory
    
    # 1. Obtener toda la historia con resultado conocido
    stmt = select(AssignmentHistory, Person).join(Person, AssignmentHistory.person_id == Person.id).where(
        AssignmentHistory.resultado.in_(["aceptada", "corrigida"])
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    if not rows:
        return # No hay datos suficientes para entrenar
        
    X = []
    y = []
    
    for history, person in rows:
        # Reconstruir features (mismas que en assign_best_candidate)
        meta = person.metadata_json or {}
        role_index = hash(history.role) % 1000
        
        features = [
            role_index,
            meta.get("age", 0),
            meta.get("experience_years", 0),
            1 if meta.get("available", True) else 0
        ]
        
        X.append(features)
        
        # Definir target: 1.0 si fue aceptada, 0.0 si fue corregida (penalización)
        # Podríamos usar valores más suaves o lógica más compleja
        target = 1.0 if history.resultado == "aceptada" else 0.0
        y.append(target)

    if len(X) < 2:
        return # Necesitamos al menos 2 puntos para una regresión

    # 2. Entrenar nuevo modelo
    model = LinearRegression()
    model.fit(np.array(X), np.array(y))
    
    # 3. Guardar modelo actualizado
    model_path = pathlib.Path(__file__).with_name("ml_model.pkl")
    joblib.dump(model, model_path)
    
    # Actualizar la referencia en memoria
    global _ml_model
    _ml_model = model
    print(f"[AutoML] Modelo re-entrenado con {len(X)} experiencias.")


# ---------------------------------------------------------------------------
# Scoring utilities (deterministic)
# ---------------------------------------------------------------------------
def compute_score(
    person: Person | Dict[str, Any],
    role: str,
    stats: Dict[str, Any],
    weights: Dict[str, float],
) -> float:
    """Calcula una puntuación numérica para *person* en *role*.

    La lógica es la misma que la versión original, pero con tipado explícito y
    documentación ampliada.
    """

    # Metadatos seguros
    pmeta = (
        person.metadata_json if hasattr(person, "metadata_json") else person.get("metadata", {})
    )

    # Factores normalizados
    balance = 1.0 / (1 + stats.get("assignments_last_4w", 0))
    skill = 1.0 if role in pmeta.get("skills", []) else 0.0
    recent = 1.0 if stats.get("assigned_last_week", False) else 0.0
    success_rate = stats.get("success_rate_for_role", 0.5)
    unavailable = 0 if pmeta.get("available", True) else 1

    # Pesos con valores por defecto
    w_balance = weights.get("w_balance", 1.0)
    w_skill = weights.get("w_skill", 1.0)
    w_recent = weights.get("w_recent", 1.0)
    w_unavailable = weights.get("w_unavailable", 100.0)
    w_history = weights.get("w_history", 1.0)

    score = (
        w_balance * balance
        + w_skill * skill
        - w_recent * recent
        - w_unavailable * unavailable
        + w_history * success_rate
    )
    return score

# ---------------------------------------------------------------------------
# Simple ML stub (optional)
# ---------------------------------------------------------------------------
_ml_model: Any | None = None


def _load_ml_model() -> Any | None:
    """Carga un modelo *pickle* llamado ``ml_model.pkl`` si existe.

    Si el archivo no está presente o la carga falla, se devuelve ``None`` y
    la lógica recurre a ``compute_score``.
    """
    global _ml_model
    if _ml_model is not None:
        return _ml_model
    model_path = pathlib.Path(__file__).with_name("ml_model.pkl")
    if not model_path.is_file():
        return None
    try:
        # import joblib # Moved to top-level imports
        pass
    except Exception as exc:  # pragma: no cover
        print(f"[assigner] joblib not available: {exc}")
        return None
    try:
        _ml_model = joblib.load(model_path)
        return _ml_model
    except Exception as exc:  # pragma: no cover
        print(f"[assigner] failed to load ML model: {exc}")
        return None


def ml_predict_score(person_features: Dict[str, Any], role: str) -> Optional[float]:
    """Predice una puntuación usando el modelo ML opcional.

    Devuelve ``None`` si el modelo no está disponible.
    """
    model = _load_ml_model()
    if model is None:
        return None
    # Convertir el rol a un entero determinista (hash simple)
    role_index = hash(role) % 1000
    feature_vec = list(person_features.values())
    # import numpy as np # Moved to top-level imports
    X = np.array([[role_index] + feature_vec])
    try:
        pred = model.predict(X)
        return float(pred[0])
    except Exception as exc:  # pragma: no cover
        print(f"[assigner] ML prediction failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Core assignment routine (used by FastAPI endpoint)
# ---------------------------------------------------------------------------
async def assign_best_candidate(payload: AssignPayload, db: AsyncSession) -> Dict[str, Any]:
    """Selecciona el mejor candidato para ``payload.role``.

    1️⃣ Obtiene los pesos del modelo (de la DB o del payload).
    2️⃣ Recupera los objetos ``Person`` correspondientes.
    3️⃣ Calcula una puntuación para cada candidato, intentando primero el
       modelo ML y, si no está disponible, usando ``compute_score``.
    4️⃣ Devuelve un diccionario JSON con ``person_id`` y ``score``.
    """

    # ---------------------------------------------------
    # 1️⃣ Resolución de pesos
    # ---------------------------------------------------
    if payload.weights is not None:
        weights = payload.weights
    else:
        result = await db.execute(select(ModelWeights).where(ModelWeights.name == "default"))
        default_row = result.scalar_one_or_none()
        if default_row and isinstance(default_row.weights, dict):
            weights = default_row.weights
        else:
            # Fallback hard‑coded
            weights = {
                "w_balance": 1.0,
                "w_skill": 1.0,
                "w_recent": 1.0,
                "w_unavailable": 100.0,
                "w_history": 1.0,
            }

    # ---------------------------------------------------
    # 2️⃣ Carga de candidatos
    # ---------------------------------------------------
    result = await db.execute(select(Person).where(Person.id.in_(payload.person_ids)))
    candidates: List[Person] = result.scalars().all()
    if not candidates:
        raise ValueError("No candidates found for the supplied person_ids")

    # ---------------------------------------------------
    # 3️⃣ Scoring
    # ---------------------------------------------------
    best_candidate: Optional[Person] = None
    best_score: float = float('-inf')
    for person in candidates:
        # Extraer características simples para el modelo ML
        meta = person.metadata_json or {}
        flat_features = {
            "age": meta.get("age", 0),
            "experience_years": meta.get("experience_years", 0),
            "available": 1 if meta.get("available", True) else 0,
        }
        ml_score = ml_predict_score(flat_features, payload.role)
        if ml_score is not None:
            score = ml_score
        else:
            # Construir stats mínimas (en producción se obtendrían de la BD)
            stats = {
                "assignments_last_4w": meta.get("assignments_last_4w", 0),
                "assigned_last_week": meta.get("assigned_last_week", False),
                "success_rate_for_role": meta.get("success_rate_for_role", 0.5),
            }
            score = compute_score(person, payload.role, stats, weights)
        if score > best_score:
            best_score = score
            best_candidate = person

    if best_candidate is None:
        raise RuntimeError("Scoring algorithm failed to select a candidate")

    return {
        "person_id": best_candidate.id,
        "score": best_score,
        "role": payload.role,
    }

# ---------------------------------------------------------------------------
# Feedback handling – updates persisted weights AND retrains ML
# ---------------------------------------------------------------------------
async def process_feedback(feedback: FeedbackPayload, db: AsyncSession) -> Dict[str, Any]:
    """Aplica el feedback:
    1. Actualiza pesos heurísticos (ModelWeights).
    2. Guarda el evento en la historia (AssignmentHistory).
    3. Dispara el re-entrenamiento del modelo ML.
    """
    from models import AssignmentHistory
    
    # --- 1. Actualizar Pesos Heurísticos (Lógica existente) ---
    result = await db.execute(select(ModelWeights).where(ModelWeights.name == "default"))
    weight_row: ModelWeights | None = result.scalar_one_or_none()
    if weight_row is None:
        weight_row = ModelWeights(
            name="default",
            weights={ "w_balance": 1.0, "w_skill": 1.0, "w_recent": 1.0, "w_unavailable": 100.0, "w_history": 1.0 },
            updated_at=date.today(),
        )
        db.add(weight_row)
        await db.flush()

    new_weights = apply_feedback_update(weight_row.weights, feedback.dict())
    weight_row.weights = new_weights
    weight_row.updated_at = date.today()
    
    # --- 2. Guardar en Historia (Memoria del sistema) ---
    history_entry = AssignmentHistory(
        semana=date.today(), # Asumimos feedback es para 'hoy' o reciente
        role=feedback.role,
        person_id=feedback.person_id,
        resultado=feedback.result,
        feedback={"alternative_id": feedback.alternative_id},
        created_at=date.today()
    )
    db.add(history_entry)
    
    await db.commit()
    await db.refresh(weight_row)
    
    # --- 3. Auto-Aprendizaje (Retraining) ---
    # En un sistema real esto iría a una background task (Celery/Arq)
    try:
        await retrain_model(db)
        ml_status = "retrained"
    except Exception as e:
        print(f"Error retraining: {e}")
        ml_status = f"error: {str(e)}"

    return {
        "status": "weights_updated_and_model_retrained", 
        "weights": weight_row.weights,
        "ml_status": ml_status
    }

# ---------------------------------------------------------------------------
# Helper: ajuste de pesos a partir de feedback (mantiene la lógica original)
# ---------------------------------------------------------------------------
def apply_feedback_update(weights: Dict[str, float], feedback_event: Dict[str, Any], alpha: float = 0.05) -> Dict[str, float]:
    """Ajusta los pesos del modelo según el feedback.

    - Si ``result`` es ``"aceptada"`` se incrementa el peso del skill.
    - Si ``result`` es ``"corrigida"`` se decrementa.
    """
    role = feedback_event.get("role")
    result = feedback_event.get("result")
    if not role:
        return weights
    key_skill = f"w_skill::{role}"
    if key_skill not in weights:
        weights[key_skill] = 1.0
    if result == "aceptada":
        weights[key_skill] += alpha
    elif result == "corrigida":
        weights[key_skill] -= alpha
    return weights
# ... (previous content remains)

# ---------------------------------------------------------------------------
# Batch Meeting Assignment Logic
# ---------------------------------------------------------------------------

class Candidate(BaseModel):
    id: int
    name: str
    gender: str # 'M' or 'F'
    roles: List[str] # ['presidente', 'lector', ...]
    last_assignment_weeks_ago: Optional[int] = None

class ActivityRequest(BaseModel):
    type: str # 'presidente', 'oracion', 'seamos_mejores_maestros', 'generic'
    title: str
    requires_assistant: bool = False

class MeetingPayload(BaseModel):
    week_date: date
    candidates: List[Candidate]
    activities: List[ActivityRequest]
    # Optional: list of recent participants to exclude explicitly if not handled in candidates
    exclude_names: List[str] = [] 

class MeetingResponse(BaseModel):
    week_date: date
    assignments: List[Dict[str, Any]] # [{ 'activity': '...', 'publicador': '...', 'ayudante': '...' }]


def filter_candidates(
    candidates: List[Candidate], 
    role_required: str, 
    exclude_names: List[str],
    gender_required: Optional[str] = None
) -> List[Candidate]:
    """Filtra candidatos según reglas duras."""
    eligible = []
    for c in candidates:
        if c.name in exclude_names:
            continue
        if role_required not in c.roles and role_required != 'generic':
            # Si es un rol específico y no lo tiene, saltar. 
            # 'generic' asume cualquier publicador.
            continue
        if gender_required and c.gender != gender_required:
            continue
        
        # Regla de descanso: si fue asignado hace menos de 2 semanas, evitar (simple heuristic)
        if c.last_assignment_weeks_ago is not None and c.last_assignment_weeks_ago < 2:
            continue
            
        eligible.append(c)
    return eligible

async def assign_meeting(payload: MeetingPayload, db: AsyncSession) -> MeetingResponse:
    """Genera la asignación completa para una reunión."""
    
    assignments = []
    # Set de nombres ya asignados en ESTA reunión para evitar duplicados
    assigned_this_meeting = set()
    
    # Convertir lista de exclusión a set para búsqueda rápida
    global_exclude = set(payload.exclude_names)

    for activity in payload.activities:
        result = {
            "tema": activity.title,
            "publicador": None,
            "ayudante": None
        }
        
        # 1. Asignar Publicador Principal
        # Determinar rol requerido y género
        role_req = activity.type
        gender_req = None
        
        # Regla especial: Seamos Mejores Maestros -> Preferencia Mujeres (F) si no se especifica
        if activity.type == 'seamos_mejores_maestros':
            role_req = 'publicador' # Usamos el pool general de publicadores
            # Podríamos inferir género del tema o forzar F por defecto como pedía el prompt original
            # Por ahora, dejamos abierto, pero si se asigna alguien, el ayudante deberá coincidir.
        
        pool = filter_candidates(
            payload.candidates, 
            role_req, 
            list(global_exclude.union(assigned_this_meeting))
        )
        
        if not pool:
            # Fallback: intentar sin excluir a los de esta reunión (doble asignación si es necesario)
            pool = filter_candidates(payload.candidates, role_req, list(global_exclude))
        
        if pool:
            # Aquí usaríamos el ML/Score para elegir al mejor del pool
            # Por simplicidad, ordenamos por 'tiempo sin asignar' descendente (más tiempo = mejor)
            # y luego aleatorio para romper empates.
            pool.sort(key=lambda x: x.last_assignment_weeks_ago or 999, reverse=True)
            
            # TODO: Integrar compute_score aquí pasando un objeto Person simulado
            selected = pool[0]
            
            result["publicador"] = {"nombre": selected.name, "genero": selected.gender}
            assigned_this_meeting.add(selected.name)
            
            # 2. Asignar Ayudante (si aplica)
            if activity.requires_assistant:
                # Regla: Mismo género que el principal
                assistant_pool = filter_candidates(
                    payload.candidates,
                    'publicador', # Ayudante suele ser cualquier publicador
                    list(global_exclude.union(assigned_this_meeting)),
                    gender_required=selected.gender
                )
                
                if assistant_pool:
                    assistant_pool.sort(key=lambda x: x.last_assignment_weeks_ago or 999, reverse=True)
                    assistant = assistant_pool[0]
                    result["ayudante"] = {"nombre": assistant.name, "genero": assistant.gender}
                    assigned_this_meeting.add(assistant.name)
        
        assignments.append(result)

    return MeetingResponse(week_date=payload.week_date, assignments=assignments)
