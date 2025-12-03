from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from models import Base
from config import DATABASE_URL
import asyncio

# Configuración optimizada del engine para Leapcell
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verifica conexiones antes de usarlas
    pool_recycle=300,  # Recicla conexiones cada 5 min
    connect_args={
        "server_settings": {
            "jit": "off",
        },
        "command_timeout": 30,  # Aumentado para cold starts
        "timeout": 20,  # Timeout de conexión aumentado
    }
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

async def init_db():
    """Inicializa la base de datos con reintentos y manejo de timeouts"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"[DB Init] Intento {attempt + 1}/{max_retries}...")
            async with engine.begin() as conn:
                await asyncio.wait_for(
                    conn.run_sync(Base.metadata.create_all),
                    timeout=15.0
                )
            print("[DB Init] Tablas creadas exitosamente")
            return
        except asyncio.TimeoutError:
            print(f"[DB Init] Timeout en intento {attempt + 1}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                print("[DB Init] Continuando sin verificar tablas...")
                return
        except Exception as e:
            print(f"[DB Init] Error en intento {attempt + 1}: {str(e)[:100]}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                print("[DB Init] Continuando sin verificar tablas...")
                return

async def get_db():
    """Dependency para obtener sesión de DB con manejo de errores"""
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception as e:
        await session.rollback()
        print(f"[DB Session] Error en sesión: {str(e)[:100]}")
        raise
    finally:
        await session.close()
