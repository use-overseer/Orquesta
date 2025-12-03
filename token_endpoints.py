"""Token Management Endpoints for Orquesta API

Este módulo añade endpoints seguros para gestionar tokens API:
1. Solicitar un nuevo token (requiere aprobación)
2. Aprobar/rechazar solicitudes (solo admin)
3. Listar tokens activos (solo admin)
4. Revocar tokens (solo admin)
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, EmailStr
from datetime import date, datetime, timedelta
from typing import List, Optional
import secrets

from database import get_db
from models import ApiKey, TokenRequest
from config import ADMIN_TOKEN, DEFAULT_TOKEN_EXPIRY_DAYS

router = APIRouter(prefix="/v1/tokens", tags=["Token Management"])

# ============================================================================
# Schemas
# ============================================================================

class TokenRequestCreate(BaseModel):
    owner: str
    email: EmailStr
    purpose: str

class TokenRequestResponse(BaseModel):
    id: int
    owner: str
    email: str
    purpose: str
    status: str
    requested_at: datetime
    
class TokenApproval(BaseModel):
    request_id: int
    approved: bool
    notes: Optional[str] = None
    expires_days: Optional[int] = None  # Si es None, usa DEFAULT_TOKEN_EXPIRY_DAYS

class TokenInfo(BaseModel):
    id: int
    owner: str
    purpose: Optional[str]
    is_active: bool
    created_at: date
    expires_at: Optional[date]
    last_used: Optional[datetime]

# ============================================================================
# Dependency: Verificar que el token sea de admin
# ============================================================================

async def verify_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.split(" ")[1]
    
    # Verificar contra el token maestro de admin
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    return token

# ============================================================================
# Endpoints Públicos
# ============================================================================

@router.post("/request", response_model=TokenRequestResponse)
async def request_token(
    request: TokenRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Solicitar un nuevo token API.
    
    Cualquiera puede solicitar un token, pero debe ser aprobado por un admin.
    
    Ejemplo:
    ```bash
    curl -X POST https://orquesta.leapcell.app/v1/tokens/request \\
      -H "Content-Type: application/json" \\
      -d '{
        "owner": "Juan Pérez",
        "email": "juan@example.com",
        "purpose": "Aplicación móvil para asignaciones"
      }'
    ```
    """
    
    # Verificar que no haya una solicitud pendiente del mismo email
    stmt = select(TokenRequest).where(
        TokenRequest.email == request.email,
        TokenRequest.status == "pending"
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Ya tienes una solicitud pendiente. Por favor espera la revisión del administrador."
        )
    
    # Crear nueva solicitud
    new_request = TokenRequest(
        owner=request.owner,
        email=request.email,
        purpose=request.purpose,
        status="pending",
        requested_at=datetime.utcnow()
    )
    
    db.add(new_request)
    await db.commit()
    await db.refresh(new_request)
    
    return TokenRequestResponse(
        id=new_request.id,
        owner=new_request.owner,
        email=new_request.email,
        purpose=new_request.purpose,
        status=new_request.status,
        requested_at=new_request.requested_at
    )

# ============================================================================
# Endpoints de Administración
# ============================================================================

@router.get("/requests", response_model=List[TokenRequestResponse])
async def list_token_requests(
    status: Optional[str] = "pending",
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin)
):
    """
    Listar solicitudes de tokens (solo admin).
    
    Ejemplo:
    ```bash
    curl https://orquesta.leapcell.app/v1/tokens/requests?status=pending \\
      -H "Authorization: Bearer admin-master-key-change-me-in-production"
    ```
    """
    
    stmt = select(TokenRequest)
    if status:
        stmt = stmt.where(TokenRequest.status == status)
    stmt = stmt.order_by(TokenRequest.requested_at.desc())
    
    result = await db.execute(stmt)
    requests = result.scalars().all()
    
    return [
        TokenRequestResponse(
            id=r.id,
            owner=r.owner,
            email=r.email,
            purpose=r.purpose,
            status=r.status,
            requested_at=r.requested_at
        )
        for r in requests
    ]

@router.post("/approve")
async def approve_token_request(
    approval: TokenApproval,
    db: AsyncSession = Depends(get_db),
    admin_token: str = Depends(verify_admin)
):
    """
    Aprobar o rechazar una solicitud de token (solo admin).
    
    Ejemplo - Aprobar:
    ```bash
    curl -X POST https://orquesta.leapcell.app/v1/tokens/approve \\
      -H "Content-Type: application/json" \\
      -H "Authorization: Bearer admin-master-key-change-me-in-production" \\
      -d '{
        "request_id": 1,
        "approved": true,
        "notes": "Aprobado para desarrollo",
        "expires_days": 90
      }'
    ```
    
    Ejemplo - Rechazar:
    ```bash
    curl -X POST https://orquesta.leapcell.app/v1/tokens/approve \\
      -H "Content-Type: application/json" \\
      -H "Authorization: Bearer admin-master-key-change-me-in-production" \\
      -d '{
        "request_id": 1,
        "approved": false,
        "notes": "Propósito no especificado claramente"
      }'
    ```
    """
    
    # Obtener la solicitud
    stmt = select(TokenRequest).where(TokenRequest.id == approval.request_id)
    result = await db.execute(stmt)
    request = result.scalar_one_or_none()
    
    if not request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Esta solicitud ya fue revisada")
    
    # Actualizar estado de la solicitud
    request.status = "approved" if approval.approved else "rejected"
    request.reviewed_at = datetime.utcnow()
    request.reviewed_by = "admin"
    request.notes = approval.notes
    
    response_data = {
        "request_id": request.id,
        "owner": request.owner,
        "status": request.status
    }
    
    # Si se aprueba, crear el token
    if approval.approved:
        new_token = secrets.token_urlsafe(32)
        expiry_days = approval.expires_days if approval.expires_days is not None else DEFAULT_TOKEN_EXPIRY_DAYS
        expires_at = date.today() + timedelta(days=expiry_days)
        
        api_key = ApiKey(
            key=new_token,
            owner=request.owner,
            purpose=request.purpose,
            is_active=True,
            created_at=date.today(),
            expires_at=expires_at
        )
        
        db.add(api_key)
        
        response_data["token"] = new_token
        response_data["expires_at"] = expires_at.isoformat()
        response_data["message"] = "Token creado exitosamente"
    else:
        response_data["message"] = "Solicitud rechazada"
    
    await db.commit()
    
    return response_data

@router.get("/list", response_model=List[TokenInfo])
async def list_active_tokens(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin)
):
    """
    Listar todos los tokens activos (solo admin).
    
    Ejemplo:
    ```bash
    curl https://orquesta.leapcell.app/v1/tokens/list \\
      -H "Authorization: Bearer admin-master-key-change-me-in-production"
    ```
    """
    
    stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
    result = await db.execute(stmt)
    keys = result.scalars().all()
    
    return [
        TokenInfo(
            id=k.id,
            owner=k.owner,
            purpose=k.purpose,
            is_active=k.is_active,
            created_at=k.created_at,
            expires_at=k.expires_at,
            last_used=k.last_used
        )
        for k in keys
    ]

@router.post("/revoke/{token_id}")
async def revoke_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin)
):
    """
    Revocar un token existente (solo admin).
    
    Ejemplo:
    ```bash
    curl -X POST https://orquesta.leapcell.app/v1/tokens/revoke/1 \\
      -H "Authorization: Bearer admin-master-key-change-me-in-production"
    ```
    """
    
    stmt = select(ApiKey).where(ApiKey.id == token_id)
    result = await db.execute(stmt)
    key = result.scalar_one_or_none()
    
    if not key:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    
    key.is_active = False
    await db.commit()
    
    return {
        "message": "Token revocado exitosamente",
        "token_id": token_id,
        "owner": key.owner
    }

@router.get("/check")
async def check_token_status(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Verificar el estado de tu propio token.
    
    Ejemplo:
    ```bash
    curl https://orquesta.leapcell.app/v1/tokens/check \\
      -H "Authorization: Bearer tu-token-aqui"
    ```
    """
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    
    token = authorization.split(" ")[1]
    
    stmt = select(ApiKey).where(ApiKey.key == token)
    result = await db.execute(stmt)
    key = result.scalar_one_or_none()
    
    if not key:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    
    # Actualizar last_used
    key.last_used = datetime.utcnow()
    await db.commit()
    
    is_expired = False
    if key.expires_at and key.expires_at < date.today():
        is_expired = True
    
    return {
        "owner": key.owner,
        "purpose": key.purpose,
        "is_active": key.is_active,
        "is_expired": is_expired,
        "created_at": key.created_at.isoformat(),
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "days_until_expiration": (key.expires_at - date.today()).days if key.expires_at and not is_expired else None
    }
