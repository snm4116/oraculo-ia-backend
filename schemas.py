# schemas.py
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime

# --- Modelos para el Análisis de la IA (Estructura Avanzada) ---
class KeyFactor(BaseModel):
    factor: str = Field(description="Un factor o duelo clave que será decisivo en el partido.")
    impact: str = Field(description="Una explicación concisa de cómo este factor impactará el resultado.")

class Prediction(BaseModel):
    winner: str = Field(description="El nombre completo del equipo que se predice que ganará.")
    confidence: float = Field(description="Un valor entre 0.0 y 1.0 que representa la confianza en la predicción.")
    final_score: str = Field(description="El marcador final predicho, en formato '27-24'.")
    reasoning: str = Field(description="El resumen final y la justificación principal de por qué ganará ese equipo.")

class GameAnalysis(BaseModel):
    historical_context: str = Field(description="Un breve análisis de los enfrentamientos pasados y la rivalidad histórica.")
    current_form_analysis: str = Field(description="Análisis del rendimiento reciente de ambos equipos, incluyendo su estado de forma y lesiones clave.")
    key_factors: List[KeyFactor] = Field(description="Una lista de 2 a 3 factores o duelos clave que influirán en el resultado.")
    prediction: Prediction = Field(description="La predicción final y detallada del resultado del partido.")


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
