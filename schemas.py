# schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict
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
    model_config = ConfigDict(from_attributes=True)

class GameAnalysis(BaseModel):
    predicted_winner: str
    predicted_score: str
    confidence_level: float
    analysis_summary: str

# -------------------
# Schemas para Users y Autenticación
# -------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: int
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

# -------------------
# Schemas para Tokens (JWT)
# -------------------

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None