import os
from fastapi import APIRouter, HTTPException

from pydantic import BaseModel
from typing import Optional, List
from google import genai  # NEW: Modern SDK
from dotenv import load_dotenv
from typing import Optional, List, Dict
from google.genai import types

# Load the variables from the .env file
load_dotenv()
router = APIRouter()

# --- CONFIGURATION ---


from pydantic import BaseModel
from typing import Optional, List, Dict
from google import genai  # NEW: Modern SDK
from google.genai import types
from app.core.config import settings
from dotenv import load_dotenv
load_dotenv()
router = APIRouter()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEYY")
client = genai.Client(api_key=GEMINI_API_KEY)

# FIX 1: Defined MODEL_NAME properly so /detect doesn't crash
MODEL_NAME = "gemini-2.5-flash-lite"
# ✅ Enhanced Professional System Prompt
CIVIC_AURA_IDENTITY = """
You are the "Civic Assistant," the heart of CivicAura in Lucknow. 
Your tone is encouraging, tech-savvy, and deeply committed to a cleaner city.

CORE KNOWLEDGE:
1. SMART LENS: Users MUST scan trash AND record a video of disposal to earn points. (YOLOv8 AI verified).
2. REWARDS: Points are "Aura Points." Higher points = higher status in Lucknow.
3. TIERS: 
   - 🌱 Seed (0-100)
   - 🌿 Sprout (101-500) 
   - 🛡️ Guardian (501-2000)
   - 👑 Civic Legend (2000+)
4. MISSION: Reward citizens for cleaning, reporting 'Black Spots', and joining community drives at BBDU and across Lucknow.

GUIDELINES:
- If a user is a 'Seed', motivate them to reach 'Sprout'.
- If a user mentions a dirty area, tell them to "Report a Black Spot" in the app.
- Keep responses concise (under 3-4 sentences) so they look good in the chat bubble.
"""

class ChatMessage(BaseModel):
    role: str # "user" or "model"
    content: str

class ChatRequest(BaseModel):
    message: str
    user_name: Optional[str] = "Citizen"
    user_points: Optional[float] = 0.0
    history: Optional[List[Dict[str, str]]] = [] # Pass history from frontend

@router.post("/query")
async def chat_gemini(request: ChatRequest):
    try:
        # 1. Build the Persona Header
        persona = f"""{CIVIC_AURA_IDENTITY}

CURRENT USER CONTEXT:
Name: {request.user_name}
Aura Points: {request.user_points}
Tier: {get_tier(request.user_points)}

IMPORTANT:
- Use EXACT Aura Points given above
- Do NOT assume or change points
- Always base tier on given points only
"""

        # 2. Format History for the new SDK (types.Content)
        # We must convert your history list into the specific 'Content' objects Gemini expects
        formatted_history = []
        for m in (request.history or []):
            formatted_history.append(
                types.Content(
                    role=m.get("role", "user"), 
                    parts=[types.Part(text=m.get("content", ""))]
                )
            )

        # 3. Use the new SDK Client syntax
        # We use 'system_instruction' instead of adding it to every prompt for better AI logic
        response = client.models.generate_content(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=persona,
                temperature=0.7,
            ),
            # Send the history + the new message
            contents=formatted_history + [types.Content(role="user", parts=[types.Part(text=request.message)])]
        )

        return {
            "reply": response.text.strip(),
            "status": "success"
        }

    except Exception as e:
        print(f"AI Error: {e}")
        # Raising the detail so you can see the error in the frontend/logs
        raise HTTPException(status_code=500, detail=str(e))

def get_tier(points: float) -> str:
    if points <= 100: return "Seed"
    if points <= 500: return "Sprout"
    if points <= 2000: return "Guardian"
    return "Civic Legend"
