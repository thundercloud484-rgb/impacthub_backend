import os
import json
from typing import Optional, List

from dotenv import load_dotenv

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from beanie import PydanticObjectId
from google import genai
from google.genai import types

from dotenv import load_dotenv

from app.core.config import settings


from app.models.user import User, AvatarEmbed
from app.models.follow import Follow
from app.core.security import get_current_user, get_optional_user
from app.core import cloudinary as cld
from app.api.routes.auth import user_dict

# Load the variables from the .env file
load_dotenv()


load_dotenv()

# prefix="/users" matches your main.py app.include_router(users_router, prefix="/api")
# Resulting in: /api/users/...
router = APIRouter(prefix="/users", tags=["users"])
# --- GEMINI CONFIGURATION ---

GEMINI_API_KEY = os.getenv("GEMINI_API_KEYY")
client = genai.Client(api_key=GEMINI_API_KEY)

# FIX 1: Defined MODEL_NAME properly so /detect doesn't crash
MODEL_NAME = "gemini-2.5-flash-lite"

# --- REGISTRY ---
GARBAGE_REGISTRY = {
    "aluminum can": {"category": "Metal", "points": 10},
    "garbage": {"category": "Waste", "points": 0.1},
    "waste": {"category": "Waste", "points": 0.1},
    "soda can": {"category": "Metal", "points": 10},
    "crushed soda can": {"category": "Metal", "points": 10},
    "wooden stir stick": {"category": "Wood", "points": 3},
    "napkin": {"category": "Paper", "points": 2},
    "waste coffee cup": {"category": "Paper", "points": 5},
    "empty cup": {"category": "Paper", "points": 5},
    "red bull can": {"category": "Metal", "points": 10},
    "waste sugar sachet": {"category": "Paper", "points": 2},
    "monster energy can": {"category": "Metal", "points": 10},
    "crushed beverage can": {"category": "Metal", "points": 10},
    "crushed energy drink can": {"category": "Metal", "points": 10},
    "crushed can": {"category": "Metal", "points": 10},
    "empty blister pack": {"category": "Medical", "points": 5},
    "empty medicine blister pack": {"category": "Medical", "points": 5},
    "popped blister pack": {"category": "Medical", "points": 5},
    "empty food packaging": {"category": "Plastic", "points": 3},
    "empty chip bag": {"category": "Plastic", "points": 4},
    "tin can": {"category": "Metal", "points": 12},
    "plastic bottle": {"category": "Plastic", "points": 8},
    "water bottle": {"category": "Plastic", "points": 8},
    "glass bottle": {"category": "Glass", "points": 15},
    "blister pack": {"category": "Medical", "points": 5},
    "empty pill blister pack": {"category": "Medical", "points": 5},
    "pill blister pack": {"category": "Medical", "points": 5},
    "cardboard box": {"category": "Paper", "points": 12},
    "paper sheet": {"category": "Paper", "points": 2},
    "plastic wrapper": {"category": "Plastic", "points": 3},
    "chip bag": {"category": "Plastic", "points": 4},
    "battery": {"category": "Electronic", "points": 25},
}

# --- Pydantic Models ---
class ClaimRequest(BaseModel):
    amount: float

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class GarbageItem(BaseModel):
    class_name: str 
    count: int
    confidence: float

class DetectionResponse(BaseModel):
    items: list[GarbageItem]

def mini(u: User) -> dict:
    return {
        "id": str(u.id), "name": u.name, "username": u.username,
        "avatar": {"url": u.avatar.url, "public_id": u.avatar.public_id},
        "category": u.category, "is_verified": u.is_verified, "impact_score": u.impact_score,
    }

# ==========================================
# NEW ENDPOINTS: SMART LENS AI INTEGRATION
# ==========================================

@router.post("/detect")
async def detect_garbage(
    file: UploadFile = File(...), 
    video: Optional[UploadFile] = File(None),
    targets: Optional[str] = Form(None),
    custom_objects: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    try:
        image_content = await file.read()
        contents = [types.Part.from_bytes(data=image_content, mime_type=file.content_type)]

        custom_instr = ""
        if custom_objects:
            custom_instr = f"Additionally, the user has identified these specific items as waste: {custom_objects}. Please ensure you detect them if present."

        waste_rules = (
            "STRICT RULE: Only detect items that are clearly WASTE or GARBAGE. "
            f"{custom_instr} "
            "Check for these 'Waste Signs': Cans must be crushed, dented, or opened. "
            "Blister packs must be empty or popped. "
            "If a can looks full, brand new, or is on a supermarket shelf, CATEGORIZE it as 'Non-Waste'. "
        )

        if video:
            video_content = await video.read()
            contents.append(types.Part.from_bytes(data=video_content, mime_type=video.content_type))
            target_text = f"The user has specifically selected these items for disposal: {targets}." if targets else ""
            
            prompt = (
                f"{waste_rules} "
                f"STRICT RULE: Ignore all background objects, furniture, people, and walls. {target_text} "
                "1. Identify the garbage items from the photo. "
                "2. Watch the video and verify if the items selected by the user are thrown into a dustbin. "
                "Only return the items in JSON if the disposal action is successfully seen in the video."
            )
        else:
            prompt = (
                f"{waste_rules} "
                f"Ignore everything except garbage/waste items. "
                "Detect garbage items: name, quantity, confidence (0-1)."
            )
        
        contents.append(prompt)
        
        # FIX: Changed from undefined CURRENT_MODEL to MODEL_NAME
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DetectionResponse,
            )
        )

        if response.parsed:
            formatted_items = [
                {"class": i.class_name, "count": i.count, "confidence": i.confidence} 
                for i in response.parsed.items
            ]
            return {
                "items": formatted_items,
                "total_objects": sum(i['count'] for i in formatted_items)
            }
        return {"items": [], "total_objects": 0}

    except Exception as e:
        print(f"Error in /detect: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calculate_points")
async def calculate_points(selected_items: List[dict], current_user: User = Depends(get_current_user)):
    total_score = 0
    breakdown = []

    for item in selected_items:
        raw_name = item.get("class") or item.get("class_name") or ""
        name_lower = raw_name.lower().strip()
        count = item.get("count", 1)

        match_found = None
        for valid_item in GARBAGE_REGISTRY:
            if valid_item == name_lower:
                match_found = valid_item
                break
        
        if match_found:
            data = GARBAGE_REGISTRY[match_found]
            points_for_this = data["points"] * count
            total_score += points_for_this
            breakdown.append({
                "item": match_found,
                "category": data["category"],
                "count": count,
                "total": points_for_this
            })
        else:
            breakdown.append({
                "item": raw_name,
                "category": "REJECTED / NON-WASTE",
                "count": count,
                "total": 0
            })

    return {"total_points": total_score, "breakdown": breakdown}

# ==========================================
# EXISTING ENDPOINTS (Profile, Leaderboard)
# ==========================================

@router.post("/claim-points")
async def claim_points(request: ClaimRequest, current_user: User = Depends(get_current_user)):
    pts = request.amount
    original_score = current_user.impact_score
    current_user.do_claim() 
    current_user.impact_score = original_score + pts
    await current_user.save()
    
    return {
        "success": True,
        "message": f"Added {pts} impact points!",
        "points_awarded": pts,
        "new_score":      current_user.impact_score,
        "streak":         current_user.claim_streak,
        "can_claim_today": False,
    }

@router.get("/leaderboard")
async def leaderboard():
    users = await User.find(User.is_active == True).sort(-User.impact_score).limit(20).to_list()
    return {"success": True, "users": [mini(u) for u in users]}

@router.get("/search")
async def search_users(q: str = ""):
    if len(q.strip()) < 2:
        return {"success": True, "users": []}
    users = await User.find(
        {"$or": [{"username": {"$regex": q, "$options": "i"}}, {"name": {"$regex": q, "$options": "i"}}]}
    ).limit(20).to_list()
    return {"success": True, "users": [mini(u) for u in users]}

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    if not current_user.verify_password(request.current_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(request.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    current_user.set_password(request.new_password)
    await current_user.save()
    return {"success": True, "message": "Password changed successfully"}

@router.put("/update-profile")
async def update_profile(
    name:       Optional[str] = Form(None),
    bio:        Optional[str] = Form(None),
    location:   Optional[str] = Form(None),
    website:    Optional[str] = Form(None),
    category:   Optional[str] = Form(None),
    skills:     Optional[str] = Form(None),
    interests:  Optional[str] = Form(None),
    avatar:     Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
):
    if name     is not None: current_user.name      = name
    if bio      is not None: current_user.bio       = bio
    if location is not None: current_user.location  = location
    if website  is not None: current_user.website   = website
    if category is not None: current_user.category  = category
    if skills   is not None: current_user.skills    = [s.strip() for s in skills.split(",") if s.strip()]
    if interests is not None: current_user.interests = [i.strip() for i in interests.split(",") if i.strip()]

    if avatar:
        data = await avatar.read()
        result = await cld.upload_avatar(data)
        if current_user.avatar.public_id:
            cld.delete_media(current_user.avatar.public_id)
        current_user.avatar = AvatarEmbed(url=result["url"], public_id=result["public_id"])

    await current_user.save()
    return {"success": True, "message": "Profile updated", "user": user_dict(current_user)}

@router.get("/{username}")
async def get_profile(username: str, current_user: Optional[User] = Depends(get_optional_user)):
    user = await User.find_one(User.username == username.lower())
    if not user:
        raise HTTPException(404, "User not found")
    is_following = False
    if current_user:
        is_following = bool(await Follow.find_one(Follow.follower_id == current_user.id, Follow.following_id == user.id))
    return {"success": True, "user": user_dict(user), "isFollowing": is_following}

@router.get("/{user_id}/followers")
async def get_followers(user_id: str):
    oid = PydanticObjectId(user_id)
    follows = await Follow.find(Follow.following_id == oid).to_list()
    result = []
    for f in follows:
        u = await User.get(f.follower_id)
        if u: result.append(mini(u))
    return {"success": True, "followers": result}

@router.get("/{user_id}/following")
async def get_following(user_id: str):
    oid = PydanticObjectId(user_id)
    follows = await Follow.find(Follow.follower_id == oid).to_list()
    result = []
    for f in follows:
        u = await User.get(f.following_id)
        if u: result.append(mini(u))
    return {"success": True, "following": result}
