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

from db.database import engine, get_db
from db import models as db_models
from schemas import GameFromDB, GameAnalysis
import auth

db_models.Base.metadata.create_all(bind=engine)
load_dotenv()

ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not ODDS_API_KEY or not GEMINI_API_KEY:
    raise RuntimeError("Las claves de API deben estar definidas.")

genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="El Oráculo IA API", version="2.0.0")

origins = ["http://localhost:3000", "https://oraculo-ia-frontend.vercel.app"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex='https://oraculo-ia-frontend-.*-samuels-projects-97aaae46\\.vercel\\.app',
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])

async def _fetch_and_cache_games_from_api(db: Session):
    API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events"
    params = {"apiKey": ODDS_API_KEY}
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, params=params)
        response.raise_for_status()
        api_games = response.json()
        db.query(db_models.Game).delete()
        for game_data in api_games:
            db_game = db_models.Game(
                id=game_data['id'],
                home_team=game_data['home_team'],
                away_team=game_data['away_team'],
                commence_time=datetime.fromisoformat(game_data['commence_time'].replace("Z", "+00:00")),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(db_game)
        db.commit()
        return db.query(db_models.Game).all()

@app.get("/games", response_model=List[GameFromDB])
async def get_games(db: Session = Depends(get_db)):
    first_game = db.query(db_models.Game).first()
    if first_game and first_game.updated_at and (datetime.now(timezone.utc) - first_game.updated_at) < timedelta(hours=1):
        return db.query(db_models.Game).all()
    return await _fetch_and_cache_games_from_api(db)

@app.get("/predict/{game_id}", response_model=GameAnalysis)
async def predict_game(game_id: str, db: Session = Depends(get_db)):
    game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail=f"Partido con ID {game_id} no encontrado.")

    team_home = game.home_team
    team_away = game.away_team
    current_year = datetime.now().year

    # --- PROMPT MAESTRO V4: CADENA DE PENSAMIENTO ---
    prompt = f"""
    Actúa como El Oráculo, un analista de élite de la NFL. El año actual es {current_year}. Tu análisis debe ser profundo, incisivo y basado en los datos más recientes.

    **Tarea:** Realiza un análisis para el partido entre {team_away} (visitantes) y {team_home} (locales).

    **Proceso de Análisis (Cadena de Pensamiento):**
    1.  **Análisis Histórico (Pasado):** Primero, considera la rivalidad histórica y los resultados de enfrentamientos directos recientes. ¿Hay alguna tendencia psicológica o táctica?
    2.  **Análisis de Forma Actual (Presente):** Luego, evalúa el rendimiento de ambos equipos en los últimos 3-4 partidos de la temporada {current_year}. Analiza sus fortalezas y debilidades ofensivas y defensivas, mencionando jugadores clave actuales. Considera el impacto de lesiones confirmadas.
    3.  **Duelos Decisivos (Futuro en el Partido):** Finalmente, identifica 2 o 3 duelos específicos (ej. receptor estrella vs. esquinero top, línea ofensiva vs. línea defensiva) que determinarán el resultado del partido.

    **Salida Final:**
    Una vez completado tu análisis interno, usa la herramienta 'GameAnalysis' para estructurar tu conclusión. Rellena TODOS los campos con la mayor precisión posible.
    """

    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", tools=[GameAnalysis])
        response = await model.generate_content_async(prompt, tool_config={'function_calling_config': 'ANY'})
        
        if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            analysis_args = response.candidates[0].content.parts[0].function_call.args
            if all(key in analysis_args for key in ["historical_context", "current_form_analysis", "key_factors", "prediction"]):
                 return analysis_args

        raise HTTPException(status_code=500, detail="La IA no pudo generar un análisis estructurado.")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error interno al generar el análisis de la IA: {e}")
