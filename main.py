from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, init_db
from models import Base
import assigner
from token_endpoints import router as token_router
from config import HOST, PORT
import asyncio

app = FastAPI(
    title="Orquesta",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Incluir el router de gestión de tokens
app.include_router(token_router)

# Health check para Leapcell
@app.get("/kaithheathcheck")
async def health_check():
    """Endpoint de health check requerido por Leapcell"""
    return {"status": "healthy", "service": "orquesta"}

async def init_db_background():
    """Ejecuta init_db en background sin bloquear el startup"""
    try:
        await init_db()
        print("[Startup] ✓ Base de datos inicializada")
    except Exception as e:
        print(f"[Startup] ⚠ Error en init_db: {e}")

@app.on_event("startup")
async def startup_event():
    """Inicialización no bloqueante - init_db en background"""
    print("[Startup] Iniciando Orquesta API...")
    # Ejecutar init_db en background sin bloquear el startup
    asyncio.create_task(init_db_background())
    print("[Startup] ✓ API lista (DB inicializándose en background)")

@app.get("/v1/config")
async def get_config():
    return {"version": "1.0.0", "status": "active"}

from sqlalchemy import select
from models import ApiKey

async def verify_token(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = authorization.split(" ")[1]
    
    # Check against database
    result = await db.execute(select(ApiKey).where(ApiKey.key == token, ApiKey.is_active == True))
    key_record = result.scalar_one_or_none()
    
    if not key_record:
        # Fallback for development/bootstrap (optional, remove in strict prod)
        if token == "secret-token":
            return token
        raise HTTPException(status_code=403, detail="Invalid or inactive token")
        
    return key_record.key

@app.post("/v1/assign")
async def assign_task(
    payload: assigner.AssignPayload,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token),
):
    """Endpoint that receives an assignment request and returns the best candidate."""
    result = await assigner.assign_best_candidate(payload, db)
    return {"status": "assigned", "data": result}

@app.post("/v1/feedback")
async def feedback(
    payload: assigner.FeedbackPayload,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token),
):
    """Endpoint to receive feedback about a previous assignment and update model weights."""
    result = await assigner.process_feedback(payload, db)
    return {"status": "feedback_processed", "data": result}

@app.post("/v1/assign_meeting")
async def assign_meeting(
    payload: assigner.MeetingPayload,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token),
):
    """Genera asignaciones para toda una reunión basándose en reglas y candidatos."""
    result = await assigner.assign_meeting(payload, db)
    return result

@app.get("/")
async def root():
    return {
        "message": "Orquesta API is running",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST or "0.0.0.0", port=PORT or 8080)