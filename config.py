"""
Configuración centralizada para Orquesta API
Carga variables de entorno desde archivo .env
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL")

# Asegurar que se use el driver async para PostgreSQL
if DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1).replace("postgresql://", "postgresql+asyncpg://", 1)

# Configuración del servidor
HOST = os.getenv("HOST")
PORT_STR = os.getenv("PORT")
PORT = int(PORT_STR) if PORT_STR else None

# Token de administrador
ADMIN_TOKEN = os.getenv("ORQUESTA_ADMIN_TOKEN")

if not ADMIN_TOKEN:
    import secrets
    # Generar un token temporal para desarrollo
    ADMIN_TOKEN = secrets.token_urlsafe(32)
    print("WARNING: ORQUESTA_ADMIN_TOKEN no está configurado!")
    print(f"Usando token temporal: {ADMIN_TOKEN}")
    print("Para producción, configura ORQUESTA_ADMIN_TOKEN en .env o como variable de entorno")

# Configuración de tokens
DEFAULT_TOKEN_EXPIRY_DAYS = int(os.getenv("DEFAULT_TOKEN_EXPIRY_DAYS", "365"))

# Modo debug
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# Configuración de CORS (si es necesario)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
