from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from models import Base
from config import DATABASE_URL
import asyncio

# Configuración optimizada del engine para evitar idle timeouts
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Cambiado a False para reducir ruido en logs
    poolclass=NullPool,  # Evita pool de conexiones - crea nueva cada vez
    connect_args={
        "server_settings": {
            "jit": "off",
            "idle_in_transaction_session_timeout": "30000",  # 30 segundos
        },
        "command_timeout": 10,  # Timeout para comandos individuales
        "timeout": 10,  # Timeout de conexión
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
