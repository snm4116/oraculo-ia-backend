# main.py
import os
import httpx
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
from typing import List
from datetime import datetime, timedelta, timezone # Asegúrate que datetime esté importado

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db.database import engine, get_db
from db import models as db_models
from schemas import GameFromDB, GameAnalysis
import auth

# ... (el resto de la configuración inicial se mantiene igual hasta el endpoint predict_game) ...
# ... (omitiendo el código que no cambia por brevedad) ...

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
                    commence_time=datetime.fromisoformat(game_data['commence_time'].replace("Z", "+00:00")),
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

@app.get("/")
def read_root():
    return {"message": "Bienvenido al motor de El Oráculo IA."}

@app.get("/games", response_model=List[GameFromDB])
async def get_games(db: Session = Depends(get_db)):
    print("-> [CACHE] Revisando la base de datos para partidos...")
    first_game = db.query(db_models.Game).first()
    cache_duration = timedelta(hours=1)
    
    if first_game and first_game.updated_at and (datetime.now(timezone.utc) - first_game.updated_at) < cache_duration:
        print("-> [CACHE] Sirviendo desde caché.")
        return db.query(db_models.Game).all()
    
    print("-> [CACHE] Caché expirada. Obteniendo datos frescos.")
    return await _fetch_and_cache_games_from_api(db)


@app.get("/predict/{game_id}", response_model=GameAnalysis)
async def predict_game(game_id: str, db: Session = Depends(get_db)):
    game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
    if not game:
        await _fetch_and_cache_games_from_api(db)
        game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail=f"Partido con ID {game_id} no encontrado.")

    team_home = game.home_team
    team_away = game.away_team
    current_year = datetime.now().year # Obtenemos el año actual

    # --- PROMPT MEJORADO CON ANCLAJE TEMPORAL ---
    prompt = f"""
    Actúa como un analista experto en deportes de la NFL. El año actual es {current_year}. Basa tu análisis en las plantillas y el estado de forma más recientes de los equipos.

    Tu tarea es analizar el próximo partido entre {team_away} y {team_home}.
    Proporciona un análisis conciso pero experto y utiliza la herramienta 'GameAnalysis' para estructurar tu respuesta, rellenando TODOS los campos.
    1.  **summary**: Un resumen general del enfrentamiento.
    2.  **key_factors**: De 3 a 5 factores o estadísticas clave que serán decisivos en el partido. Para cada factor, explica brevemente tu razonamiento.
    3.  **prediction**: Tu predicción final clara, incluyendo el equipo ganador (winner), un marcador final estimado (final_score) y un nivel de confianza (confidence) de 0.0 a 1.0.
    """

    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", tools=[GameAnalysis])
        response = await model.generate_content_async(prompt, tool_config={'function_calling_config': 'ANY'})
        
        if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            analysis_args = response.candidates[0].content.parts[0].function_call.args
            
            if all(key in analysis_args for key in ["summary", "key_factors", "prediction"]):
                 return analysis_args

        print("-> [ERROR] La respuesta de Gemini no tuvo el formato esperado.")
        raise HTTPException(status_code=500, detail="La IA no pudo generar un análisis estructurado. Inténtalo de nuevo.")

    except Exception as e:
        print(f"Error al llamar a la API de Gemini o procesar su respuesta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al generar el análisis de la IA.")