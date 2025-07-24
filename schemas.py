# schemas.py
from pydantic import BaseModel
from typing import List, Optional

# Define la estructura de un equipo
class Team(BaseModel):
    id: int
    name: str
    logo: str

# Define la estructura del objeto que contiene los equipos local y visitante
class Teams(BaseModel):
    home: Team
    away: Team

# Define la estructura del objeto de estado del partido
# Hacemos los campos opcionales para manejar datos nulos de la API
class GameStatus(BaseModel):
    long: Optional[str] = None
    short: Optional[str] = None

# Define la estructura principal de un partido
class Game(BaseModel):
    id: int
    date: str
    time: str
    timezone: str
    status: GameStatus
    teams: Teams
