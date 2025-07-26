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

# --- Configuración Segura ---
ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not ODDS_API_KEY or not GEMINI_API_KEY:
    raise RuntimeError("THE_ODDS_API_KEY y GEMINI_API_KEY deben estar definidas.")

genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(
    title="El Oráculo IA API",
    description="El motor de IA para predicciones deportivas.",
    version="1.1.0", # Version incrementada
)

# --- Configuración de CORS ---
origins = [
    "http://localhost:3000",
    "https://oraculo-ia-frontend.vercel.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex='https://oraculo-ia-frontend-.*-samuels-projects-97aaae46\\.vercel\\.app',
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])

# --- Lógica de la API ---

async def _fetch_and_cache_games_from_api(db: Session):
    API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events"
    params = {"apiKey": ODDS_API_KEY}
    print("-> [API] Obteniendo partidos frescos...")
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
                    commence_time=datetime.fromisoformat(game_data['commence_time'].replace("Z", "+00:00")),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(db_game)
            db.commit()
            print("-> [DB] Base de datos actualizada.")
            return db.query(db_models.Game).all()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno al procesar los partidos: {e}")

@app.get("/")
def read_root():
    return {"message": "Bienvenido al motor de El Oráculo IA."}

@app.get("/games", response_model=List[GameFromDB])
async def get_games(db: Session = Depends(get_db)):
    first_game = db.query(db_models.Game).first()
    cache_duration = timedelta(hours=1)
    if first_game and first_game.updated_at and (datetime.now(timezone.utc) - first_game.updated_at) < cache_duration:
        return db.query(db_models.Game).all()
    return await _fetch_and_cache_games_from_api(db)

@app.get("/predict/{game_id}", response_model=GameAnalysis)
async def predict_game(game_id: str, db: Session = Depends(get_db)):
    game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail=f"Partido con ID {game_id} no encontrado.")

    team_home = game.home_team
    team_away = game.away_team
    
    # --- IMPLEMENTACIÓN DEL PROMPT MAESTRO V3 ---
    current_year = datetime.now().year
    prompt = f"""
    Actúa como El Oráculo, un analista experto en deportes de la NFL con un conocimiento enciclopédico. El año actual es {current_year}. Basa todo tu análisis en las plantillas, estadísticas y estado de forma más recientes de los equipos para la temporada {current_year}. Ignora por completo las plantillas o situaciones de años anteriores.

    Tu tarea es analizar en profundidad el próximo partido entre los {team_away} (visitantes) y los {team_home} (locales).

    Primero, realiza un análisis interno que cubra los siguientes puntos clave:
    1.  **Análisis Ofensivo y Defensivo:** Evalúa las fortalezas y debilidades de la ofensiva y defensiva de cada equipo. Menciona jugadores clave (Quarterback, un receptor principal, un corredor, y un jugador defensivo destacado).
    2.  **Enfrentamientos Clave (Matchups):** Identifica uno o dos enfrentamientos individuales o de unidades que serán decisivos para el resultado del partido.
    3.  **Estado de Forma y Lesiones:** Considera el rendimiento reciente de ambos equipos y el impacto de cualquier lesión importante confirmada para el partido.

    Finalmente, utiliza la herramienta 'GameAnalysis' para estructurar tu conclusión final. Debes rellenar TODOS los campos de la herramienta con la información de tu análisis:
    - **summary**: Un resumen narrativo general de tu análisis, justificando tu predicción.
    - **key_factors**: Una lista de 2 a 3 de los factores más importantes de tu análisis.
    - **prediction**: Tu predicción final, incluyendo el ganador, el marcador exacto y tu nivel de confianza.
    """
    # --- FIN DEL PROMPT ---

    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", tools=[GameAnalysis])
        response = await model.generate_content_async(prompt, tool_config={'function_calling_config': 'ANY'})
        
        if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            analysis_args = response.candidates[0].content.parts[0].function_call.args
            if all(key in analysis_args for key in ["summary", "key_factors", "prediction"]):
                 return analysis_args

        raise HTTPException(status_code=500, detail="La IA no pudo generar un análisis estructurado.")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error interno al generar el análisis de la IA: {e}")
