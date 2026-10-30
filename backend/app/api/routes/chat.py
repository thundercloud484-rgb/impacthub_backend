import re
from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel
from typing import Optional, List, Dict
from dotenv import load_dotenv
from google.genai import types

# Load the variables from the .env file
load_dotenv()
router = APIRouter()

# --- CONFIGURATION ---

from app.core.ai import generate_content_with_fallback
from app.core.database import get_database
from app.core.security import get_optional_user
router = APIRouter()

# FIX 1: Defined MODEL_NAME properly so /detect doesn't crash
MODEL_NAME = "gemini-3.5-flash-lite"
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


APP_KNOWLEDGE = """
CivicImpact rules:
- The home feed shows posts from the current user and accounts they follow.
- Public posts can be discovered in the Posts/Explore section.
- Official Hubs and Communities can be created only by Authorities.
- A user can join only one Official Hub at a time.
- Community chat is available only to the Community creator/admins and admins of affiliated Official Hubs.
- Normal users cannot join Communities or access private group chat.
- Smart Lens scans waste and users must record disposal verification before earning points.
- Aura tiers are Seed (0-100), Sprout (101-500), Guardian (501-2000), and Civic Legend (2000+).
"""


def query_terms(query: str) -> set[str]:
    return {
        term for term in re.findall(r"[a-z0-9]{3,}", query.lower())
        if term not in {"what", "where", "when", "which", "how", "does", "can", "the", "and"}
    }


def relevance(text: str, terms: set[str]) -> int:
    haystack = text.lower()
    return sum(haystack.count(term) for term in terms)


def needs_retrieval(message: str) -> bool:
    terms = query_terms(message)
    return bool(terms & {
        "points", "profile", "events", "event", "groups", "group", "hub",
        "community", "post", "posts", "following", "followers", "smart",
        "lens", "scan", "rules", "available", "upcoming", "near", "where",
    })


def wants_category(terms: set[str], category: str) -> bool:
    category_terms = {
        "groups": {"group", "groups", "hub", "community", "communities"},
        "events": {"event", "events", "upcoming", "volunteer"},
        "posts": {"post", "posts", "caption", "impact", "tag"},
    }
    return bool(terms & category_terms[category])


async def retrieve_context(message: str, user) -> str:
    database = get_database()
    terms = query_terms(message)
    snippets = [APP_KNOWLEDGE.strip()]

    if user:
        snippets.append(
            f"Current user profile: name={user.name}; username=@{user.username}; "
            f"category={user.category}; location={user.location or 'not provided'}; "
            f"impact_points={user.impact_score}; following_count={user.following_count}; "
            f"followers_count={user.followers_count}."
        )

    search_pattern = "|".join(re.escape(term) for term in terms)

    if wants_category(terms, "groups"):
        group_filter = {
            "is_active": {"$ne": False},
            "is_community": {"$ne": True},
            "$or": [
                {"name": {"$regex": search_pattern, "$options": "i"}},
                {"slug": {"$regex": search_pattern, "$options": "i"}},
                {"description": {"$regex": search_pattern, "$options": "i"}},
            ],
        }
        groups = await database.groups.find(group_filter).sort(
            "total_points", -1
        ).limit(3).to_list()
        snippets.extend(
            f"Public group: {group.get('name', '')} (@{group.get('slug', '')}); "
            f"members={group.get('members_count', 0)}; "
            f"points={group.get('total_points', 0)}."
            for group in groups
        )

    if wants_category(terms, "events"):
        event_filter = {
            "status": "upcoming",
            "$or": [
                {"title": {"$regex": search_pattern, "$options": "i"}},
                {"description": {"$regex": search_pattern, "$options": "i"}},
                {"location": {"$regex": search_pattern, "$options": "i"}},
            ],
        }
        events = await database.events.find(event_filter).sort(
            "event_date", 1
        ).limit(3).to_list()
        snippets.extend(
            f"Upcoming event: {event.get('title', '')}; "
            f"location={event.get('location', '')}; "
            f"date={event.get('event_date', '')}."
            for event in events
        )

    if wants_category(terms, "posts"):
        post_filter = {
            "is_archived": False,
            "$or": [
                {"caption": {"$regex": search_pattern, "$options": "i"}},
                {"location": {"$regex": search_pattern, "$options": "i"}},
                {"impact_tags": {"$regex": search_pattern, "$options": "i"}},
            ],
        }
        posts = await database.posts.find(post_filter).sort(
            "created_at", -1
        ).limit(3).to_list()
        snippets.extend(
            f"Public post: caption={post.get('caption', '')[:160]}; "
            f"location={post.get('location', '')}; "
            f"tags={', '.join(post.get('impact_tags', []))}."
            for post in posts
        )

    return "\n".join(snippets)


@router.post("/query")
async def chat_gemini(request: ChatRequest, user=Depends(get_optional_user)):
    try:
        retrieved_context = (
            await retrieve_context(request.message, user)
            if needs_retrieval(request.message)
            else APP_KNOWLEDGE
        )
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

RETRIEVED CIVICIMPACT CONTEXT:
{retrieved_context}

RAG RULES:
- Use retrieved context when it answers the question.
- Never invent app data, events, group members, private messages, or restricted content.
- If the context does not contain the answer, say that you do not have that information.
- Do not reveal private data or claim that a normal user can access private group content.
"""

        # 2. Format History for the new SDK (types.Content)
        # We must convert your history list into the specific 'Content' objects Gemini expects
        formatted_history = []
        for m in (request.history or [])[-4:]:
            formatted_history.append(
                types.Content(
                    role=m.get("role", "user"), 
                    parts=[types.Part(text=m.get("content", ""))]
                )
            )

        # 3. Use the new SDK Client syntax
        # We use 'system_instruction' instead of adding it to every prompt for better AI logic
        response = await generate_content_with_fallback(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=persona,
                temperature=0.7,
            ),
            contents=formatted_history + [
                types.Content(
                    role="user",
                    parts=[types.Part(text=request.message)],
                )
            ],
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
