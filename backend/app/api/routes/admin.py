# app/api/routes/admin.py
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr
from beanie import PydanticObjectId
from beanie.operators import Or
from app.models.user import User
from app.models.post import Post
from app.models.event import Event
from app.core.security import get_admin_user, create_access_token
from app.core.database import get_database

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminLoginBody(BaseModel):
    email:    EmailStr
    password: str

class ResetPasswordBody(BaseModel):
    new_password: str


class GroupBulkDeleteBody(BaseModel):
    group_ids: list[str]


class UserBulkDeleteBody(BaseModel):
    user_ids: list[str]


def user_dict(u: User) -> dict:
    return {
        "id":              str(u.id),
        "name":            u.name,
        "username":        u.username,
        "email":           u.email,
        "avatar":          {"url": u.avatar.url, "public_id": u.avatar.public_id},
        "bio":             u.bio,
        "location":        u.location,
        "category":        u.category,
        "followers_count": u.followers_count,
        "following_count": u.following_count,
        "posts_count":     u.posts_count,
        "impact_score":    u.impact_score,
        "is_verified":     u.is_verified,
        "is_active":       u.is_active,
        "role":            u.role,
        "auth_provider":   u.auth_provider,
        "created_at":      u.created_at.isoformat(),
    }


# ── Admin Login ───────────────────────────────────────────────────────────────
@router.post("/login")
async def admin_login(body: AdminLoginBody):
    """Admin-only login endpoint"""
    user = await User.find_one(User.email == body.email.lower())
    if not user or user.role != "admin" or not user.verify_password(body.password):
        raise HTTPException(401, "Invalid admin credentials")
    
    return {
        "success": True,
        "token": create_access_token(str(user.id)),
        "user": user_dict(user)
    }


# ── Dashboard Stats ───────────────────────────────────────────────────────────
@router.get("/stats")
async def get_stats(admin: User = Depends(get_admin_user)):
    """Get dashboard statistics"""
    total_users  = await User.count()
    total_posts  = await Post.count()
    total_events = await Event.count()
    active_users = await User.find(User.is_active == True).count()
    
    return {
        "success": True,
        "stats": {
            "total_users":  total_users,
            "active_users": active_users,
            "total_posts":  total_posts,
            "total_events": total_events,
        }
    }


# ── User Management ───────────────────────────────────────────────────────────
@router.get("/users")
async def get_all_users(
    admin: User = Depends(get_admin_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
):
    """Get all users with pagination and filters"""
    skip = (page - 1) * limit
    
    query = {}
    if search:
        users = await User.find(
            Or(
                User.username.regex(search, "i"),
                User.name.regex(search, "i"),
                User.email.regex(search, "i")
            )
        ).skip(skip).limit(limit).to_list()
        total = await User.find(
            Or(
                User.username.regex(search, "i"),
                User.name.regex(search, "i"),
                User.email.regex(search, "i")
            )
        ).count()
    elif role:
        if role == "authority":
            users = await User.find(
                Or(User.role == role, User.category == "Authority")
            ).skip(skip).limit(limit).to_list()
            total = await User.find(
                Or(User.role == role, User.category == "Authority")
            ).count()
        else:
            users = await User.find(
                User.role == role,
                User.category != "Authority",
            ).skip(skip).limit(limit).to_list()
            total = await User.find(
                User.role == role,
                User.category != "Authority",
            ).count()
    else:
        users = await User.find_all().skip(skip).limit(limit).to_list()
        total = await User.count()
    
    return {
        "success": True,
        "users": [user_dict(u) for u in users],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        }
    }


@router.patch("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: str,
    admin: User = Depends(get_admin_user)
):
    """Toggle user active status"""
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise HTTPException(404, "User not found")
    
    if user.role == "admin":
        raise HTTPException(403, "Cannot deactivate admin users")
    
    user.is_active = not user.is_active
    await user.save()
    
    return {
        "success": True,
        "user": user_dict(user)
    }


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str = Query(..., regex="^(user|admin)$"),
    admin: User = Depends(get_admin_user)
):
    """Update user role"""
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise HTTPException(404, "User not found")
    
    user.role = role
    await user.save()
    
    return {
        "success": True,
        "user": user_dict(user)
    }


@router.patch("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    body: ResetPasswordBody,
    admin: User = Depends(get_admin_user)
):
    """Reset user password (admin only)"""
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise HTTPException(404, "User not found")
    
    if len(body.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    
    user.set_password(body.new_password)
    await user.save()
    
    return {
        "success": True,
        "message": "Password reset successfully"
    }


async def delete_user_data(database, user: User) -> None:
    user_id = str(user.id)
    user_object_id = user.id
    await Post.find(Post.author_id == user_object_id).delete()
    await Event.find(Event.organizer_id == user_object_id).delete()
    await database.follows.delete_many({
        "$or": [{"follower_id": user_id}, {"following_id": user_id},
                {"follower_id": user_object_id}, {"following_id": user_object_id}]
    })
    await database.likes.delete_many({
        "$or": [{"user_id": user_id}, {"user_id": user_object_id}]
    })
    await database.comments.delete_many({
        "$or": [{"author_id": user_id}, {"author_id": user_object_id},
                {"user_id": user_id}, {"user_id": user_object_id}]
    })
    await database.notifications.delete_many({
        "$or": [{"user_id": user_id}, {"user_id": user_object_id},
                {"sender_id": user_id}, {"sender_id": user_object_id}]
    })
    await database.group_members.delete_many({
        "$or": [{"user_id": user_id}, {"user_id": user_object_id}]
    })
    await database.group_messages.delete_many({
        "$or": [{"sender_id": user_id}, {"sender_id": user_object_id}]
    })
    await user.delete()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(get_admin_user)
):
    """Permanently delete a user and their directly owned content."""
    if not PydanticObjectId.is_valid(user_id):
        raise HTTPException(404, "User not found")
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise HTTPException(404, "User not found")
    
    if user.role == "admin":
        raise HTTPException(403, "Cannot delete admin users")
    await delete_user_data(get_database(), user)

    return {"success": True, "message": "User permanently deleted"}


@router.post("/users/bulk-delete")
async def bulk_delete_users(
    body: UserBulkDeleteBody,
    admin: User = Depends(get_admin_user),
):
    deleted_count = 0
    skipped_users = []
    for user_id in body.user_ids:
        if not PydanticObjectId.is_valid(user_id):
            skipped_users.append({"id": user_id, "reason": "Invalid user ID"})
            continue
        user = await User.get(PydanticObjectId(user_id))
        if not user:
            skipped_users.append({"id": user_id, "reason": "User not found"})
            continue
        if user.role == "admin":
            skipped_users.append({"id": user_id, "reason": "Admin users cannot be deleted"})
            continue
        await delete_user_data(get_database(), user)
        deleted_count += 1
    return {
        "success": True,
        "deleted_count": deleted_count,
        "skipped_users": skipped_users,
        "message": f"Deleted {deleted_count} users",
    }


# ── Post Management ───────────────────────────────────────────────────────────
@router.get("/posts")
async def get_all_posts(
    admin: User = Depends(get_admin_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Get all posts with pagination"""
    skip = (page - 1) * limit
    posts = await Post.find_all().sort("-created_at").skip(skip).limit(limit).to_list()
    total = await Post.count()
    
    # Populate author info
    result = []
    for post in posts:
        author = await User.get(post.author_id)
        result.append({
            "id": str(post.id),
            "content": post.caption,
            "media": [media.model_dump() for media in post.media],
            "likes_count": post.likes_count,
            "comments_count": post.comments_count,
            "created_at": post.created_at.isoformat(),
            "author": {
                "id": str(author.id),
                "name": author.name,
                "username": author.username,
                "avatar": {"url": author.avatar.url}
            } if author else None
        })
    
    return {
        "success": True,
        "posts": result,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        }
    }


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    admin: User = Depends(get_admin_user)
):
    """Delete a post"""
    post = await Post.get(PydanticObjectId(post_id))
    if not post:
        raise HTTPException(404, "Post not found")
    
    # Update author's post count
    author = await User.get(post.author_id)
    if author:
        author.posts_count = max(0, author.posts_count - 1)
        await author.save()
    
    await post.delete()
    return {"success": True, "message": "Post deleted"}


# ── Event Management ──────────────────────────────────────────────────────────
@router.get("/events")
async def get_all_events(
    admin: User = Depends(get_admin_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Get all events with pagination"""
    skip = (page - 1) * limit
    events = await Event.find_all().sort("-created_at").skip(skip).limit(limit).to_list()
    total = await Event.count()
    
    # Populate organizer info
    result = []
    for event in events:
        organizer = await User.get(event.organizer_id)
        result.append({
            "id": str(event.id),
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "date": event.date.isoformat() if event.date else None,
            "attendees_count": event.attendees_count,
            "created_at": event.created_at.isoformat(),
            "organizer": {
                "id": str(organizer.id),
                "name": organizer.name,
                "username": organizer.username,
                "avatar": {"url": organizer.avatar.url}
            } if organizer else None
        })
    
    return {
        "success": True,
        "events": result,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        }
    }


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    admin: User = Depends(get_admin_user)
):
    """Delete an event"""
    event = await Event.get(PydanticObjectId(event_id))
    if not event:
        raise HTTPException(404, "Event not found")
    
    await event.delete()
    return {"success": True, "message": "Event deleted"}


@router.get("/groups")
async def get_all_groups(
    admin: User = Depends(get_admin_user),
    limit: int = Query(200, ge=1, le=500),
):
    database = get_database()
    groups = await database.groups.find({}).sort("created_at", -1).to_list(length=limit)
    return {
        "success": True,
        "groups": [
            {
                "_id": str(group["_id"]),
                "id": str(group["_id"]),
                "name": group.get("name", ""),
                "slug": group.get("slug", ""),
                "description": group.get("description", ""),
                "is_official": bool(group.get("is_official", False)),
                "is_community": bool(group.get("is_community", False)),
                "is_active": group.get("is_active", True),
                "member_count": group.get("members_count", len(group.get("members") or [])),
                "total_points": group.get("total_points", 0),
            }
            for group in groups
        ],
    }


@router.patch("/groups/{group_id}/toggle-active")
async def toggle_group_active(
    group_id: str,
    admin: User = Depends(get_admin_user),
):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(404, "Group not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(404, "Group not found")

    is_active = not group.get("is_active", True)
    await database.groups.update_one(
        {"_id": group["_id"]},
        {"$set": {"is_active": is_active}},
    )
    return {
        "success": True,
        "group": {
            "id": str(group["_id"]),
            "is_active": is_active,
        },
    }


async def delete_group_data(database, group_ids: list[str]) -> int:
    valid_ids = [ObjectId(group_id) for group_id in group_ids if ObjectId.is_valid(group_id)]
    if not valid_ids:
        return 0
    string_ids = [str(group_id) for group_id in valid_ids]
    for collection in ("group_members", "group_messages", "group_invitations"):
        await database[collection].delete_many({
            "$or": [{"group_id": {"$in": string_ids}},
                    {"group_id": {"$in": valid_ids}}]
        })
    result = await database.groups.delete_many({"_id": {"$in": valid_ids}})
    return result.deleted_count


@router.post("/groups/bulk-delete")
async def bulk_delete_groups(
    body: GroupBulkDeleteBody,
    admin: User = Depends(get_admin_user),
):
    database = get_database()
    deleted_count = await delete_group_data(database, body.group_ids)
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} groups",
    }
