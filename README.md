# Orquesta

Orquesta is an intelligent, self-learning task assignment service. It combines configurable heuristics with an auto-updating Machine Learning model to deliver fair and efficient recommendations.

## Setup

1. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

## Authentication

The API is protected by a Bearer token.
**Default Token**: `secret-token` (Change this in `main.py` for production).

Include the header in your requests:
`Authorization: Bearer secret-token`

## Usage Examples

### 1. Check Status
```bash
curl http://127.0.0.1:8000/
```

### 2. Assign a Task (Get Recommendation)
Ask Orquesta to pick the best candidate for a role.

```bash
curl -X POST http://127.0.0.1:8000/v1/assign \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer secret-token" \
  -d '{
    "role": "Lector",
    "person_ids": [1, 2, 3],
    "stats": {},
    "weights": null
  }'
```

### 3. Provide Feedback (Teach the Model)
Tell Orquesta if the assignment was accepted or corrected. This **automatically retrains** the ML model.

```bash
curl -X POST http://127.0.0.1:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer secret-token" \
  -d '{
    "role": "Lector",
    "person_id": 2,
    "result": "aceptada"
  }'
```
*Result options: "aceptada", "corrigida"*

### 4. Batch Meeting Assignment (New)
Generate assignments for an entire meeting, respecting gender rules, role capabilities, and rotation.

```bash
curl -X POST http://127.0.0.1:8000/v1/assign_meeting \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer secret-token" \
  -d '{
    "week_date": "2023-11-01",
    "exclude_names": ["Busy Person"],
    "candidates": [
      {"id": 1, "name": "Bro. Smith", "gender": "M", "roles": ["presidente"], "last_assignment_weeks_ago": 4},
      {"id": 2, "name": "Sis. Jones", "gender": "F", "roles": ["publicador"], "last_assignment_weeks_ago": 8},
      {"id": 3, "name": "Sis. Doe", "gender": "F", "roles": ["publicador"], "last_assignment_weeks_ago": 6}
    ],
    "activities": [
      {"type": "presidente", "title": "Chairman", "requires_assistant": false},
      {"type": "seamos_mejores_maestros", "title": "Bible Study", "requires_assistant": true}
    ]
  }'
```

## Project Structure

- `main.py`: API endpoints and authentication.
- `assigner.py`: Scoring logic, ML training loop, feedback processing, and **batch assignment logic**.
- `models.py`: Database schemas (Persons, History, Weights).
- `database.py`: Async DB connection.
- `train_model.py`: Script to bootstrap the initial dummy model.