from sqlalchemy import Column, Integer, String, Date, JSON, Boolean, Float, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    genero = Column(String) # 'M' or 'F'
    es_siervo = Column(Boolean, default=False)
    
    # Role capabilities (flags)
    can_president = Column(Boolean, default=False)
    can_pray = Column(Boolean, default=False)
    can_conduct = Column(Boolean, default=False)
    can_read = Column(Boolean, default=False)
    
    metadata_json = Column(JSON, name="metadata")

class AssignmentHistory(Base):
    __tablename__ = "assignment_history"
    id = Column(Integer, primary_key=True, index=True)
    semana = Column(Date, index=True)
    role = Column(String, index=True)
    person_id = Column(Integer)
    resultado = Column(String)  # 'aceptada','rechazada','corrigida'
    feedback = Column(JSON)     # info adicional
    created_at = Column(Date)

class ModelWeights(Base):
    __tablename__ = "model_weights"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)  # e.g., 'default_v1'
    weights = Column(JSON)              # { "role::skill_weight": 1.2, ... }
    updated_at = Column(Date)

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    owner = Column(String) # Nombre del usuario o servicio (e.g. "App Movil", "Admin")
    is_active = Column(Boolean, default=True)
    created_at = Column(Date)
