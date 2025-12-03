from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models import Base
from config import DATABASE_URL
import asyncio

# Configuración mejorada del engine con timeouts y pool
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,  # Verifica conexiones antes de usar
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Recicla conexiones cada hora
    connect_args={
        "server_settings": {"jit": "off"},
        "command_timeout": 60,
        "timeout": 30,
    }
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Inicializa la base de datos con reintentos"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"[DB Init] Intento {attempt + 1}/{max_retries}...")
            async with engine.begin() as conn:
                await asyncio.wait_for(
                    conn.run_sync(Base.metadata.create_all),
                    timeout=10.0
                )
            print("[DB Init] Tablas creadas exitosamente")
            return
        except asyncio.TimeoutError:
            print(f"[DB Init] ✗ Timeout en intento {attempt + 1}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                print("[DB Init] Continuando sin verificar tablas...")
                # No fallar el startup, solo advertir
                return
        except Exception as e:
            print(f"[DB Init] Error en intento {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                print("[DB Init] Continuando sin verificar tablas...")
                return

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session