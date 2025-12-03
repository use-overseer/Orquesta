"""
Script de migración para añadir las nuevas columnas a la tabla api_keys
y crear la tabla token_requests.

Este script actualiza la base de datos existente sin perder datos.
"""

import asyncio
from database import init_db, AsyncSessionLocal
from models import Base, TokenRequest
from sqlalchemy import text

async def migrate():
    """Ejecuta las migraciones necesarias para el sistema de gestión de tokens"""
    
    print("Iniciando migración de base de datos...")
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # Añadir columnas faltantes a ApiKey
        print("\nAñadiendo columnas a api_keys...")
        try:
            await session.execute(text('''
                ALTER TABLE api_keys ADD COLUMN purpose TEXT;
            '''))
            print("   Columna 'purpose' añadida")
        except Exception as e:
            print(f"   Columna 'purpose' ya existe o error: {e}")
        
        try:
            await session.execute(text('''
                ALTER TABLE api_keys ADD COLUMN expires_at DATE;
            '''))
            print("   Columna 'expires_at' añadida")
        except Exception as e:
            print(f"   Columna 'expires_at' ya existe o error: {e}")
        
        try:
            await session.execute(text('''
                ALTER TABLE api_keys ADD COLUMN last_used DATETIME;
            '''))
            print("   Columna 'last_used' añadida")
        except Exception as e:
            print(f"   Columna 'last_used' ya existe o error: {e}")
        
        try:
            await session.commit()
            print("   Cambios en api_keys confirmados")
        except Exception as e:
            print(f"   Error confirmando cambios: {e}")
            await session.rollback()
        
        # Crear tabla token_requests
        print("\nCreando tabla token_requests...")
        try:
            await session.execute(text('''
                CREATE TABLE IF NOT EXISTS token_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    email TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    requested_at DATETIME NOT NULL,
                    reviewed_at DATETIME,
                    reviewed_by TEXT,
                    notes TEXT
                )
            '''))
            await session.commit()
            print("   Tabla token_requests creada exitosamente")
        except Exception as e:
            print(f"   Error creando tabla token_requests: {e}")
            await session.rollback()
    
    print("\nMigración completada exitosamente!")
    print("\nIMPORTANTE: No olvides cambiar el ADMIN_TOKEN en token_endpoints.py")
    print("   Recomendación: Usa una variable de entorno ORQUESTA_ADMIN_TOKEN")

if __name__ == "__main__":
    asyncio.run(migrate())
