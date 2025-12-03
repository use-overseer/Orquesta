# Orquesta

## What is Orquesta?

Orquesta is an intelligent API specifically designed for the management and automatic assignment of tasks and privileges within congregations. Its purpose is to optimize the distribution of responsibilities in a fair, efficient, and data-driven manner, based on historical data and predefined rules.

## Why does it exist? (Privacy and Security)

Orquesta was born out of a critical need: **data privacy**.

Congregations handle sensitive information about their members and activities. In the age of Artificial Intelligence, sending this data to public models (like ChatGPT, Claude, or Gemini) implies a significant risk, as this information could be used to train global models or be exposed on third-party servers without adequate control.

Orquesta exists to offer a **secure and private alternative**. As a specialized system, it guarantees that congregation data:
1.  **Is not shared** with large tech corporations for model training.
2.  **Remains under control**, processed in a dedicated environment.
3.  **Is used solely** for the purpose of generating assignments and improving internal logistics.

---

## Available Endpoints

Below are the available endpoints to integrate Orquesta into your applications.

### 1. Verify Configuration
Verify that the API is active and get its version.

**Usage:**
```bash
curl -X GET https://orquesta.leapcell.app/v1/config
```

### 2. Request an Access Token
To use the assignment endpoints, you need a token. You can request one with this endpoint. An administrator will need to approve your request.

**Usage:**
```bash
curl -X POST https://orquesta.leapcell.app/v1/tokens/request \
  -H "Content-Type: application/json" \
  -d '{
    "owner": "Your Name",
    "email": "your@email.com",
    "purpose": "Description of why you will use the API"
  }'
```

### 3. Check Your Token Status
Check if your token is valid, active, or when it expires.

**Usage:**
```bash
curl -X GET https://orquesta.leapcell.app/v1/tokens/check \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 4. Generate an Individual Assignment (`/v1/assign`)
Ask the system to choose the best candidate for a specific task based on history and availability.

**Usage:**
```bash
curl -X POST https://orquesta.leapcell.app/v1/assign \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "task_type": "reading",
    "date": "2023-10-27",
    "candidates": [
      {"id": 1, "name": "Brother A", "last_assignment": "2023-10-01", "load": 0.5},
      {"id": 2, "name": "Brother B", "last_assignment": "2023-09-15", "load": 0.2}
    ]
  }'
```

### 5. Generate Assignments for a Complete Meeting (`/v1/assign_meeting`)
Generate all necessary assignments for an entire meeting in a single call.

**Usage:**
```bash
curl -X POST https://orquesta.leapcell.app/v1/assign_meeting \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "date": "2023-10-27",
    "meeting_type": "weekend",
    "requirements": [
      {"role": "chairman", "count": 1},
      {"role": "reader", "count": 1}
    ],
    "candidates": [
      {"id": 1, "name": "Brother A", "roles": ["chairman", "reader"]},
      {"id": 2, "name": "Brother B", "roles": ["reader"]}
    ]
  }'
```

### 6. Send Feedback (`/v1/feedback`)
Help Orquesta learn. Send information about whether an assignment was successful or rejected to improve future decisions.

**Usage:**
```bash
curl -X POST https://orquesta.leapcell.app/v1/feedback \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "assignment_id": "assignment_id_here",
    "success": true,
    "comments": "The brother accepted and performed the task correctly"
  }'
```