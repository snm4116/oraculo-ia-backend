# main.py
import os
import httpx
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
from typing import List
from datetime import datetime, timedelta, timezone

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Importaciones de DB, Schemas y Auth
from db.database import engine, get_db
from db import models as db_models
from schemas import GameFromDB, GameAnalysis
import auth

db_models.Base.metadata.create_all(bind=engine)
load_dotenv()

# --- Configuración Segura ---
ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not ODDS_API_KEY or not GEMINI_API_KEY:
    raise RuntimeError("THE_ODDS_API_KEY y GEMINI_API_KEY deben estar definidas.")

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
    "https://oraculo-ia-frontend.vercel.app", # Tu frontend de Vercel principal
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex='https://oraculo-ia-frontend-.*-samuels-projects-97aaae46\\.vercel\\.app', # Permite subdominios de Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluimos el router de autenticación en nuestra app principal
app.include_router(auth.router, prefix="/auth", tags=["auth"])


# --- Capa de Servicio / Funciones de Ayuda ---

async def _fetch_and_cache_games_from_api(db: Session):
    API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events"
    params = {"apiKey": ODDS_API_KEY}
    
    print("-> [API] Obteniendo partidos frescos desde The Odds API...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
            api_games = response.json()

            print("-> [DB] Actualizando la base de datos...")
            db.query(db_models.Game).delete()
            
            for game_data in api_games:
                db_game = db_models.Game(
                    id=game_data['id'],
                    home_team=game_data['home_team'],
                    away_team=game_data['away_team'],
                    commence_time=datetime.fromisoformat(game_data['commence_time']),
                    updated_at=datetime.now(timezone.utc) 
                )
                db.add(db_game)
            
            db.commit()
            print("-> [DB] Base de datos actualizada con éxito.")
            return db.query(db_models.Game).all()

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Error al contactar The Odds API: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error de conexión con The Odds API: {e}")

# --- Endpoints de la API ---

@app.get("/")
def read_root():
    return {"message": "Bienvenido al motor de El Oráculo IA."}

@app.get("/games", response_model=List[GameFromDB])
async def get_games(db: Session = Depends(get_db)):
    """
    Endpoint para obtener la lista de partidos.
    Implementa una lógica de caché de 1 hora.
    """
    print("-> [CACHE] Revisando la base de datos para partidos...")
    first_game = db.query(db_models.Game).first()
    
    cache_duration = timedelta(hours=1)
    
    if first_game and first_game.updated_at and (datetime.now(timezone.utc) - first_game.updated_at) < cache_duration:
        print("-> [CACHE] Partidos frescos encontrados en la base de datos. Sirviendo desde caché.")
        return db.query(db_models.Game).all()
    
    print("-> [CACHE] Caché vacía o expirada. Obteniendo datos frescos de la API.")
    return await _fetch_and_cache_games_from_api(db)

@app.get("/predict/{game_id}", response_model=GameAnalysis)
async def predict_game(game_id: str, db: Session = Depends(get_db)):
    """
    Genera un análisis y predicción para un partido específico usando Gemini.
    """
    game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
    if not game:
        print(f"-> [PREDICT] Partido {game_id} no encontrado en caché, buscando en la API...")
        await _fetch_and_cache_games_from_api(db)
        game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail=f"Partido con ID {game_id} no encontrado.")

    team_home = game.home_team
    team_away = game.away_team

    prompt = f"Actúa como un analista experto en deportes de la NFL. Analiza el próximo partido entre {team_away} y {team_home} y proporciona un análisis detallado..." # Prompt acortado

    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", tools=[GameAnalysis])
        response = await model.generate_content_async(prompt, tool_config={'function_calling_config': 'ANY'})
        analysis = response.candidates[0].content.parts[0].function_call.args
        return analysis
    except Exception as e:
        print(f"Error al llamar a la API de Gemini: {e}")
        raise HTTPException(status_code=500, detail="Error al generar el análisis de la IA.")