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
origins = [
    "http://localhost:3000",
    "https://legendary-space-bassoon-g4pgjxg59ppqfg9q-3000.app.github.dev",
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

# --- Endpoints de la API ---

@app.get("/")
def read_root():
    return {"message": "Bienvenido al motor de El Oráculo IA."}

@app.get("/games", response_model=List[GameFromDB])
async def get_games(db: Session = Depends(get_db)):
    print("-> [CACHE] Revisando la base de datos para partidos...")
    first_game = db.query(db_models.Game).first()
    
    cache_duration = timedelta(hours=1)
    
    now_utc = datetime.now(timezone.utc)
    if first_game and first_game.updated_at and (now_utc - first_game.updated_at) < cache_duration:
        print("-> [CACHE] Partidos frescos encontrados en la base de datos. Sirviendo desde caché.")
        return db.query(db_models.Game).all()
    
    print("-> [CACHE] Caché vacía o expirada. Obteniendo datos frescos de la API.")
    return await _fetch_and_cache_games_from_api(db)

@app.get("/predict/{game_id}", response_model=GameAnalysis)
async def predict_game(game_id: str, db: Session = Depends(get_db)):
    game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
    if not game:
        print(f"-> [PREDICT] Partido {game_id} no encontrado en caché, buscando en la API...")
        await _fetch_and_cache_games_from_api(db)
        game = db.query(db_models.Game).filter(db_models.Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail=f"Partido con ID {game_id} no encontrado.")

    team_home = game.home_team
    team_away = game.away_team

    # --- INICIO DEL PROMPT MAESTRO ---
    prompt = f"""
    Actúa como El Oráculo, un analista experto en deportes de la NFL con un conocimiento enciclopédico de equipos, jugadores, estadísticas y estrategias. Tu tono es sabio, confiado y analítico.

    Analiza el próximo partido de la NFL entre los {team_away} (visitantes) y los {team_home} (locales).

    Realiza un análisis profundo que cubra los siguientes puntos clave:
    1.  **Análisis Ofensivo y Defensivo:** Evalúa las fortalezas y debilidades de la ofensiva y defensiva de cada equipo. Menciona jugadores clave (Quarterback, receptores principales, corredores, línea defensiva, etc.).
    2.  **Enfrentamientos Clave (Matchups):** Identifica uno o dos enfrentamientos individuales o de unidades que serán decisivos para el resultado del partido (por ejemplo, el receptor estrella de un equipo contra el esquinero principal del otro).
    3.  **Estado de Forma y Lesiones:** Considera el rendimiento reciente de ambos equipos (racha de victorias/derrotas) y el impacto de cualquier lesión importante en jugadores clave.
    4.  **Veredicto y Resumen:** Basado en todo tu análisis, proporciona un resumen conciso que justifique tu predicción.

    Después de tu análisis, utiliza la herramienta 'GameAnalysis' para estructurar tu conclusión final con los siguientes elementos:
    - **predicted_winner:** El nombre completo del equipo que crees que ganará.
    - **predicted_score:** Tu predicción del marcador final (ej. "27-24").
    - **confidence_level:** Un número entre 0.0 y 1.0 que represente tu nivel de confianza en la predicción.
    - **analysis_summary:** El texto de tu veredicto y resumen.
    """
    # --- FIN DEL PROMPT MAESTRO ---

    # --- INICIO DEL BLOQUE TRY/EXCEPT CORREGIDO ---
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", tools=[GameAnalysis])
        response = await model.generate_content_async(prompt, tool_config={'function_calling_config': 'ANY'})
        
        if response.candidates and response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
            analysis_args = response.candidates[0].content.parts[0].function_call.args
            
            if all(key in analysis_args for key in ["predicted_winner", "predicted_score", "confidence_level", "analysis_summary"]):
                 return analysis_args

        print("-> [ERROR] La respuesta de Gemini no tuvo el formato esperado.")
        raise HTTPException(status_code=500, detail="La IA no pudo generar un análisis estructurado. Inténtalo de nuevo.")

    except Exception as e:
        print(f"Error al llamar a la API de Gemini o procesar su respuesta: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Error interno al generar el análisis de la IA.")
    # --- FIN DEL BLOQUE TRY/EXCEPT CORREGIDO ---