# schemas.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# -------------------
# Schemas para Games
# -------------------

class GameBase(BaseModel):
    id: str
    home_team: str
    away_team: str
    commence_time: datetime

class GameFromDB(GameBase):
    updated_at: datetime

    class Config:
        orm_mode = True # En Pydantic v2, se usa from_attributes = True

class GameAnalysis(BaseModel):
    predicted_winner: str
    predicted_score: str
    confidence_level: float
    analysis_summary: str

# -------------------
# Schemas para Users y Autenticación
# -------------------

# Schema para la creación de un usuario (lo que se recibe en el endpoint de registro)
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Schema para leer un usuario desde la BD (nunca debe exponer la contraseña)
class User(BaseModel):
    id: int
    email: EmailStr

    class Config:
        orm_mode = True # En Pydantic v2, se usa from_attributes = True

# -------------------
# Schemas para Tokens (JWT)
# -------------------

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None