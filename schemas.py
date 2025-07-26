# schemas.py
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime

# --- Modelos para el Análisis de la IA (Respuesta de Gemini) ---
class KeyFactor(BaseModel):
    factor: str = Field(description="Un factor clave o estadística comparativa relevante para la predicción.")
    reasoning: str = Field(description="Una breve explicación de por qué este factor es importante para el partido.")

class Prediction(BaseModel):
    winner: str = Field(description="El nombre del equipo que se predice que ganará.")
    confidence: float = Field(description="Un valor entre 0.0 y 1.0 que representa la confianza en la predicción.")
    final_score: str = Field(description="El marcador final predicho, en formato '27-24'.")

class GameAnalysis(BaseModel):
    summary: str = Field(description="Un resumen narrativo general del análisis del partido.")
    key_factors: List[KeyFactor] = Field(description="Una lista de 3 a 5 factores clave que influyen en el resultado.")
    prediction: Prediction = Field(description="La predicción final del resultado del partido.")


# --- Modelos para la Base de Datos y la API de Juegos ---
class GameBase(BaseModel):
    id: str
    home_team: str
    away_team: str
    commence_time: datetime

class GameFromDB(GameBase):
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Modelos para Autenticación de Usuarios ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: int
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None