# main.py
import os
import httpx
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from typing import List

# Importa el middleware de CORS
from fastapi.middleware.cors import CORSMiddleware

# Importa los modelos que acabamos de crear
from schemas import Game

# Carga las variables de entorno desde un archivo .env
load_dotenv()

# --- Configuración Segura ---
API_KEY = os.getenv("RAPIDAPI_KEY")
API_HOST = os.getenv("RAPIDAPI_HOST")
API_URL = f"https://{API_HOST}/games"

if not API_KEY or not API_HOST:
    raise RuntimeError("Las variables de entorno RAPIDAPI_KEY y RAPIDAPI_HOST deben estar definidas.")

app = FastAPI(
    title="El Oráculo IA API",
    description="El motor de IA para predicciones deportivas.",
    version="0.1.0",
)

# --- Configuración de CORS ---
# Lista de orígenes permitidos.
# Le decimos explícitamente al backend que confíe en estas direcciones.
origins = [
    "http://localhost:3000",
    "https://legendary-space-bassoon-g4pgjxg59ppqfg9q-3000.app.github.dev", # Tu frontend de Codespaces
    "https://oraculo-ia-frontend.vercel.app", # Tu frontend de Vercel
    # Si Vercel te da otras URLs de vista previa, también se pueden añadir aquí.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Usamos nuestra lista específica en lugar de "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints de la API ---

@app.get("/")
def read_root():
    """
    Endpoint de bienvenida.
    """
    return {"message": "Bienvenido al motor de El Oráculo IA."}


@app.get("/games", response_model=List[Game])
async def get_games(season: int = 2023, league: int = 1):
    """
    Obtiene la lista de partidos de la NFL y la transforma para que coincida
    con nuestro modelo de datos interno.
    """
    headers = {
        "x-rapidapi-key": API_KEY,
        "x-rapidapi-host": API_HOST
    }
    params = {
        "league": str(league),
        "season": str(season)
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(API_URL, headers=headers, params=params)
            response.raise_for_status()
            
            api_data = response.json()
            raw_games = api_data.get("response", [])

            # --- CAPA DE TRADUCCIÓN ---
            # Transformamos la respuesta de la API a nuestra estructura deseada (Game)
            formatted_games = []
            for raw_game in raw_games:
                game_details = raw_game.get("game", {})
                game_date_info = game_details.get("date", {})
                
                formatted_game = {
                    "id": game_details.get("id"),
                    "date": game_date_info.get("date"),
                    "time": game_date_info.get("time"),
                    "timezone": game_date_info.get("timezone"),
                    "status": game_details.get("status"),
                    "teams": raw_game.get("teams")
                }
                formatted_games.append(formatted_game)
            
            return formatted_games

        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Error al contactar la API de deportes: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, 
                detail=f"Error de conexión con la API de deportes: {e}"
            )
