# main.py
import os
import httpx
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from typing import List

from fastapi.middleware.cors import CORSMiddleware
from schemas import Game, GameAnalysis

load_dotenv()

# --- Configuración Segura ---
ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not ODDS_API_KEY:
    raise RuntimeError("THE_ODDS_API_KEY debe estar definida.")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY debe estar definida.")

genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(
    title="El Oráculo IA API",
    description="El motor de IA para predicciones deportivas.",
    version="0.1.0",
)

# --- Configuración de CORS ---
# Lista de orígenes permitidos.
origins = [
    "http://localhost:3000",
    "https://legendary-space-bassoon-g4pgjxg59ppqfg9q-3000.app.github.dev", # Tu frontend de Codespaces
    "https://oraculo-ia-frontend.vercel.app", # Tu frontend de Vercel
    # Si Vercel te da otras URLs de vista previa, también se pueden añadir aquí.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Usamos nuestra lista específica
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Capa de Servicio / Funciones de Ayuda ---

async def _fetch_games_from_odds_api():
    """
    Función interna que llama a The Odds API para obtener los partidos de la NFL.
    """
    API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events"
    params = {
        "apiKey": ODDS_API_KEY,
    }
    async with httpx.AsyncClient() as client:
        try:
            # The Odds API devuelve los próximos 8 días de eventos
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Error al contactar The Odds API: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error de conexión con The Odds API: {e}")

async def get_game_by_id(game_id: str):
    """
    Función de ayuda para obtener los datos de un solo partido por su ID.
    """
    all_games = await _fetch_games_from_odds_api()
    for game in all_games:
        if game['id'] == game_id:
            return game
    return None

# --- Endpoints de la API ---

@app.get("/")
def read_root():
    return {"message": "Bienvenido al motor de El Oráculo IA."}

@app.get("/games", response_model=List[Game])
async def get_games():
    """
    Endpoint público para obtener la lista de partidos de The Odds API.
    """
    return await _fetch_games_from_odds_api()

@app.get("/predict/{game_id}", response_model=GameAnalysis)
async def predict_game(game_id: str):
    """
    Genera un análisis y predicción para un partido específico usando Gemini.
    """
    game_data = await get_game_by_id(game_id)
    if not game_data:
        raise HTTPException(status_code=404, detail=f"Partido con ID {game_id} no encontrado.")

    team_home = game_data['home_team']
    team_away = game_data['away_team']

    prompt = f"""
    Actúa como un analista experto en deportes de la NFL. Tu tarea es analizar el próximo partido entre {team_away} y {team_home}.
    Proporciona un análisis conciso pero experto que cubra los siguientes puntos:
    1.  Un resumen general del enfrentamiento.
    2.  De 3 a 5 factores o estadísticas clave que serán decisivos en el partido. Para cada factor, explica brevemente tu razonamiento.
    3.  Una predicción final clara, incluyendo el equipo ganador, un marcador final estimado y un nivel de confianza (de 0.0 a 1.0) en tu predicción.
    Basa tu análisis en el conocimiento general de la NFL, el rendimiento reciente de los equipos, enfrentamientos históricos y cualquier otro dato relevante que consideres.
    """

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            tools=[GameAnalysis] 
        )
        response = await model.generate_content_async(prompt, tool_config={'function_calling_config': 'ANY'})
        analysis = response.candidates[0].content.parts[0].function_call.args
        return analysis
    except Exception as e:
        print(f"Error al llamar a la API de Gemini: {e}")
        raise HTTPException(status_code=500, detail="Error al generar el análisis de la IA.")