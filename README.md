# Orquesta - Sistema de Asignación Inteligente

Orquesta es un sistema de IA que asigna roles en reuniones de manera inteligente, aprendiendo de retroalimentaciones previas para mejorar futuras asignaciones.

## Inicio del Servidor

Para iniciar el servidor, ejecuta:

```bash
python server.py
```

El servidor se ejecutará en `http://127.0.0.1:8001` con modo debug activado.

## Endpoints Disponibles

### 1. POST /v1/assign_meeting

Asigna roles para una reunión basada en candidatos y actividades.

**URL:** `http://127.0.0.1:8001/v1/assign_meeting`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body de ejemplo:**

```json
{
  "week_date": "2025-12-08",
  "candidates": [
    {
      "name": "Juan Pérez",
      "gender": "M",
      "roles": ["lector", "ayudante"]
    },
    {
      "name": "María García",
      "gender": "F",
      "roles": ["discurso", "publicador"]
    },
    {
      "name": "Carlos López",
      "gender": "M",
      "roles": ["presidente", "conductor"]
    }
  ],
  "activities": [
    {
      "title": "Presidente de la reunión",
      "type": "presidente"
    },
    {
      "title": "Discurso público",
      "type": "discurso",
      "requires_assistant": true
    },
    {
      "title": "Lectura de la Biblia",
      "type": "lectura_biblia"
    }
  ],
  "exclude_names": []
}
```

**Respuesta exitosa (200):**

```json
{
  "assignments": [
    {
      "tema": "Presidente de la reunión",
      "publicador": {
        "nombre": "Carlos López",
        "genero": "M"
      },
      "ayudante": null
    },
    {
      "tema": "Discurso público",
      "publicador": {
        "nombre": "María García",
        "genero": "F"
      },
      "ayudante": {
        "nombre": "Juan Pérez",
        "genero": "M"
      }
    },
    {
      "tema": "Lectura de la Biblia",
      "publicador": {
        "nombre": "Juan Pérez",
        "genero": "M"
      },
      "ayudante": null
    }
  ],
  "week_date": "2025-12-08"
}
```

### 2. POST /v1/feedback

Envía retroalimentación sobre una asignación para que Orquesta aprenda.

**URL:** `http://127.0.0.1:8001/v1/feedback`

**Método:** POST

**Headers:**
```
Content-Type: application/json
```

**Body de ejemplo:**

```json
{
  "week_date": "2025-12-08",
  "gusto": true
}
```

- `gusto: true` → "Me gustó esta asignación"
- `gusto: false` → "No me gustó esta asignación"

**Respuesta exitosa (200):**

```json
{
  "msg": "¡Genial! Aprendí qué te gusta",
  "total_feedbacks": 1
}
```

## Pruebas con curl

### Asignar reunión:

```bash
curl -X POST http://127.0.0.1:8001/v1/assign_meeting \
  -H "Content-Type: application/json" \
  -d '{
    "week_date": "2025-12-08",
    "candidates": [
      {"name": "Juan Pérez", "gender": "M", "roles": ["lector", "ayudante"]},
      {"name": "María García", "gender": "F", "roles": ["discurso", "publicador"]}
    ],
    "activities": [
      {"title": "Presidente de la reunión", "type": "presidente"},
      {"title": "Discurso público", "type": "discurso", "requires_assistant": true}
    ]
  }'
```

### Enviar feedback:

```bash
curl -X POST http://127.0.0.1:8001/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"week_date": "2025-12-08", "gusto": true}'
```

## Pruebas con interfaz web

Abre `buttons.html` en un navegador para probar el envío de feedback de manera interactiva. Nota: El archivo HTML actualmente apunta al puerto 8000, pero el servidor corre en 8001. Actualiza la URL en el JavaScript si es necesario.

## Funcionalidades

- **Aprendizaje continuo:** Orquesta mejora sus asignaciones basándose en retroalimentaciones previas
- **Memoria persistente:** Las asignaciones y puntuaciones se guardan en `orquesta_v2_memory.pkl`
- **Rotación inteligente:** Prioriza personas que no han sido asignadas recientemente
- **Capacidad por roles:** Respeta las capacidades oficiales de cada persona
- **Exploración inicial:** Al inicio prueba asignaciones aleatorias, luego optimiza basado en aprendizaje

## Notas

- Las fechas deben estar en formato ISO (YYYY-MM-DD)
- Los roles disponibles incluyen: presidente, conductor, lector, discurso, lectura_biblia, busquemos_perlas_escondidas, ayudante, publicador
- El sistema aprende más rápido de retroalimentaciones negativas para evitar asignaciones problemáticas