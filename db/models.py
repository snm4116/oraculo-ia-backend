# db/models.py
from sqlalchemy import Column, String, DateTime, func, Boolean
from .database import Base

# ... (la clase Game se mantiene igual arriba) ...
class Game(Base):
    __tablename__ = "games"
    id = Column(String, primary_key=True, index=True)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    commence_time = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())


# --- NUEVO MODELO PARA LA TABLA DE USUARIOS ---
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True) # Usaremos un ID único de texto
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())