# schemas.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

# --- Modelo para los datos que vienen de The Odds API ---
class GameFromAPI(BaseModel):
    id: str
    sport_key: str
    sport_title: str
    commence_time: str
    home_team: str
    away_team: str

# --- Modelo para los datos que leemos DESDE nuestra base de datos ---
class GameFromDB(BaseModel):
    id: str
    home_team: str
    away_team: str
    commence_time: datetime

    # Esto le dice a Pydantic que puede leer datos desde un objeto de SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

# --- Modelos para el Análisis de la IA (Respuesta de Gemini) ---
class KeyFactor(BaseModel):
    factor: str = Field(description="Un factor clave o estadística comparativa relevante para la predicción.")
    reasoning: str = Field(description="Una breve explicación de por qué este factor es importante para el partido.")

class Prediction(BaseModel):
    winner: str = Field(description="El nombre del equipo que se predice que ganará.")
    confidence: float = Field(description="Un valor entre 0.0 y 1.0 que representa la confianza en la predicción.")
    final_score: str = Field(description="El marcador final predicho, en formato '27 - 24'.")

class GameAnalysis(BaseModel):
    summary: str = Field(description="Un resumen narrativo general del análisis del partido.")
    key_factors: List[KeyFactor] = Field(description="Una lista de 3 a 5 factores clave que influyen en el resultado.")
    prediction: Prediction = Field(description="La predicción final del resultado del partido.")

# --- Modelos para Usuarios y Autenticación ---
class UserCreate(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: str
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
# --- NUEVOS SCHEMAS PARA USUARIOS Y AUTENTICACIÓN ---

# Molde para los datos que un usuario envía al registrarse
class UserCreate(BaseModel):
    email: str
    password: str

# Molde para leer los datos de un usuario desde la base de datos
class User(BaseModel):
    id: str
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

# Molde para el token de acceso
class Token(BaseModel):
    access_token: str
    token_type: str

# Molde para los datos dentro del token
class TokenData(BaseModel):
    email: Optional[str] = None