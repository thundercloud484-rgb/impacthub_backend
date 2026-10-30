import re
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import get_database
from app.core.security import get_current_user
from app.models.notification import Notification

router = APIRouter(prefix="/groups", tags=["groups"])


class CreateGroupBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)
    description: str = ""
    initial_members: list[str] = []
    is_official: bool = False
    is_community: bool = False


class AddMemberBody(BaseModel):
    user_id: str


class InvitationResponseBody(BaseModel):
    accept: bool


class GroupMessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


async def require_group_member(database, group_id: str, user_id: str):
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if not await has_group_content_access(database, group, user_id):
        raise HTTPException(status_code=403, detail="You must join this group to view its content")
    return group


async def has_group_content_access(database, group, user_id: str):
    group_admins = {str(value) for value in group.get("admins", [])}
    if str(group.get("creator_id")) == user_id or user_id in group_admins:
        return True

    if group.get("is_community"):
        affiliated_hub_ids = {
            str(value) for value in group.get("affiliated_hubs", [])
        }
        affiliated_hubs = await database.groups.find({
            "is_official": True,
            "is_community": {"$ne": True},
        }).to_list(length=1000)
        return any(
            str(hub["_id"]) in affiliated_hub_ids
            and (
                str(hub.get("creator_id")) == user_id
                or user_id in {str(value) for value in hub.get("admins", [])}
            )
            for hub in affiliated_hubs
        )

    member_ids = {str(member_id) for member_id in group.get("members", [])}
    if user_id in member_ids or await database.group_members.find_one({
        "group_id": str(group["_id"]),
        "user_id": user_id,
    }):
        return True

    hub_id = str(group["_id"])
    communities = await database.groups.find({"is_community": True}).to_list(length=1000)
    for community in communities:
        affiliated_hubs = {str(value) for value in community.get("affiliated_hubs", [])}
        if hub_id not in affiliated_hubs:
            continue
        community_admins = {str(value) for value in community.get("admins", [])}
        if str(community.get("creator_id")) == user_id or user_id in community_admins:
            return True
    return False


def group_response(document):
    members = document.get("members") or []
    return {
        "id": str(document["_id"]),
        "name": document.get("name", ""),
        "slug": document.get("slug", ""),
        "description": document.get("description", ""),
        "avatar_url": document.get("avatar_url", ""),
        "creator_id": str(document["creator_id"]) if document.get("creator_id") else None,
        "members_count": document.get("members_count", len(members)),
        "total_points": document.get("total_points", 0),
        "is_active": document.get("is_active", True),
        "is_official": bool(document.get("is_official", False)),
        "is_community": bool(document.get("is_community", False)),
    }


async def community_response(database, document):
    response = group_response(document)
    hub_ids = [
        ObjectId(hub_id)
        for hub_id in document.get("affiliated_hubs", [])
        if ObjectId.is_valid(str(hub_id))
    ]
    hubs = await database.groups.find({"_id": {"$in": hub_ids}}).to_list(length=100)
    response["affiliated_hubs"] = [str(hub["_id"]) for hub in hubs]
    response["affiliated_hubs_data"] = [group_response(hub) for hub in hubs]
    return response


@router.get("/me")
async def get_user_groups(user=Depends(get_current_user)):
    documents = await get_database().groups.find({
        "members": {"$in": [str(user.id), user.id]},
        "is_active": {"$ne": False},
    }).sort("created_at", -1).to_list(length=100)
    return {"success": True, "groups": [group_response(document) for document in documents]}


@router.get("/invitations/me")
async def get_user_invitations(user=Depends(get_current_user)):
    database = get_database()
    documents = await database.group_invitations.find({
        "invitee_id": str(user.id),
        "status": "pending",
    }).sort("created_at", -1).to_list(length=100)
    invitations = [
        {
            "id": str(document["_id"]),
            "group_id": document.get("group_id", ""),
            "group_name": document.get("group_name", ""),
            "slug": document.get("group_slug", ""),
            "inviter_name": document.get("inviter_name", ""),
        }
        for document in documents
    ]
    return {"success": True, "invitations": invitations}


@router.post("/create")
async def create_group(
    body: CreateGroupBody,
    user=Depends(get_current_user),
):
    slug = re.sub(r"\s+", "_", body.slug.strip().lower())
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug):
        raise HTTPException(
            status_code=400,
            detail="Handle can contain only lowercase letters, numbers, underscores, and hyphens",
        )

    database = get_database()
    if body.is_official and getattr(user, "category", "") != "Authority":
        raise HTTPException(
            status_code=403,
            detail="Only authorities can create official hubs",
        )
    if body.is_community and getattr(user, "category", "") != "Authority":
        raise HTTPException(
            status_code=403,
            detail="Only authorities can create communities",
        )
    if await database.groups.find_one({"slug": slug}):
        raise HTTPException(status_code=409, detail="This handle is already in use")
    group_name = body.name.strip()
    if body.is_community and await database.groups.find_one({
        "is_community": True,
        "name": {"$regex": f"^{re.escape(group_name)}$", "$options": "i"},
    }):
        raise HTTPException(status_code=409, detail="This community name is already in use")

    member_ids = {str(user.id)}
    for member_id in body.initial_members:
        if ObjectId.is_valid(member_id):
            member_ids.add(member_id)

    group = {
        "name": group_name,
        "slug": slug,
        "description": body.description.strip(),
        "creator_id": str(user.id),
        "members": list(member_ids),
        "members_count": len(member_ids),
        "is_official": body.is_official,
        "is_community": body.is_community,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "total_points": 0,
    }
    result = await database.groups.insert_one(group)

    await database.group_members.insert_many([
        {
            "group_id": str(result.inserted_id),
            "user_id": member_id,
            "role": "admin" if member_id == str(user.id) else "member",
            "contributed_points": 0,
            "joined_at": group["created_at"],
        }
        for member_id in member_ids
    ])

    group["_id"] = result.inserted_id
    return {"success": True, "group": group_response(group)}


@router.post("/{group_id}/members/add")
async def add_group_member(
    group_id: str,
    body: AddMemberBody,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(group_id) or not ObjectId.is_valid(body.user_id):
        raise HTTPException(status_code=404, detail="Group or user not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    invitee = await database.users.find_one({"_id": ObjectId(body.user_id)})
    if not group or not invitee:
        raise HTTPException(status_code=404, detail="Group or user not found")

    is_admin = str(group.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in group.get("admins", [])
    }
    is_member = str(user.id) in {str(member_id) for member_id in group.get("members", [])}
    if not is_member:
        is_member = bool(await database.group_members.find_one({
            "group_id": group_id,
            "user_id": str(user.id),
        }))
    if group.get("is_official"):
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only Official Hub admins can invite members")
    elif not is_admin and not is_member:
        raise HTTPException(status_code=403, detail="Only group members can invite members")

    member_ids = {str(member_id) for member_id in group.get("members", [])}
    if body.user_id in member_ids:
        raise HTTPException(status_code=409, detail="User is already a member")

    existing = await database.group_invitations.find_one({
        "group_id": group_id,
        "invitee_id": body.user_id,
        "status": "pending",
    })
    if existing:
        return {"success": True, "action": "requested", "invite_id": str(existing["_id"])}

    invitation = {
        "group_id": group_id,
        "group_name": group.get("name", ""),
        "group_slug": group.get("slug", ""),
        "invitee_id": body.user_id,
        "inviter_id": str(user.id),
        "inviter_name": user.name,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    result = await database.group_invitations.insert_one(invitation)
    return {"success": True, "action": "requested", "invite_id": str(result.inserted_id)}


@router.post("/{group_id}/join")
async def request_to_join_group(
    group_id: str,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=404, detail="Group not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group or group.get("is_active") is False:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.get("is_community"):
        raise HTTPException(
            status_code=403,
            detail="Communities are managed by authorities and cannot be joined by regular users",
        )

    user_id = str(user.id)
    if group.get("is_official"):
        existing_group = await database.groups.find_one({
            "is_official": True,
            "is_community": {"$ne": True},
            "members": {"$in": [user_id, user.id]},
            "is_active": {"$ne": False},
        })
        if existing_group:
            raise HTTPException(status_code=409, detail="You can only join one Official Hub")
    member_ids = {str(member_id) for member_id in group.get("members", [])}
    if user_id in member_ids:
        raise HTTPException(status_code=409, detail="You are already a member")

    pending_ids = {str(request_id) for request_id in group.get("pending_requests", [])}
    if user_id in pending_ids:
        return {"success": True, "message": "Join request is already pending"}

    await database.groups.update_one(
        {"_id": group["_id"]},
        {"$addToSet": {"pending_requests": user_id}},
    )
    return {"success": True, "message": "Request sent! Awaiting admin approval."}


@router.post("/{community_id}/invite-hub/{hub_id}")
async def invite_hub_to_community(
    community_id: str,
    hub_id: str,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(community_id) or not ObjectId.is_valid(hub_id):
        raise HTTPException(status_code=404, detail="Community or hub not found")
    database = get_database()
    community = await database.groups.find_one({"_id": ObjectId(community_id)})
    hub = await database.groups.find_one({"_id": ObjectId(hub_id)})
    if not community or not community.get("is_community") or not hub or not hub.get("is_official"):
        raise HTTPException(status_code=404, detail="Community or hub not found")
    is_admin = str(community.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in community.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only community admins can invite hubs")
    pending = hub.get("pending_community_invites", [])
    if any(str(invite.get("community_id")) == community_id for invite in pending):
        return {"success": True, "message": "Invitation already sent"}
    await database.groups.update_one(
        {"_id": hub["_id"]},
        {"$push": {"pending_community_invites": {
            "community_id": community_id,
            "name": community.get("name", ""),
            "slug": community.get("slug", ""),
            "avatar_url": community.get("avatar_url", ""),
            "created_at": datetime.utcnow(),
        }}},
    )
    existing_notification = await database.notifications.find_one({
        "recipient_id": ObjectId(str(hub["creator_id"])),
        "sender_id": user.id,
        "type": "community_invite",
        "entity_type": "Community",
        "entity_id": community["_id"],
        "is_read": False,
    })
    if not existing_notification:
        await Notification(
            recipient_id=ObjectId(str(hub["creator_id"])),
            sender_id=user.id,
            type="community_invite",
            entity_type="Community",
            entity_id=community["_id"],
            message=f'{community.get("name", "A community")} invited your Official Hub to join its network.',
        ).insert()
    return {"success": True, "message": "Invitation sent"}


@router.get("/{hub_id}/community-invites")
async def get_community_invites(hub_id: str, user=Depends(get_current_user)):
    if not ObjectId.is_valid(hub_id):
        raise HTTPException(status_code=404, detail="Hub not found")
    database = get_database()
    hub = await database.groups.find_one({"_id": ObjectId(hub_id)})
    if not hub or not hub.get("is_official"):
        raise HTTPException(status_code=404, detail="Hub not found")
    is_admin = str(hub.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in hub.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only hub admins can view invitations")
    for invite in hub.get("pending_community_invites", []):
        community_id = str(invite.get("community_id", ""))
        if not ObjectId.is_valid(community_id):
            continue
        community = await database.groups.find_one({"_id": ObjectId(community_id)})
        if not community or not ObjectId.is_valid(str(community.get("creator_id"))):
            continue
        sender_id = ObjectId(str(community["creator_id"]))
        existing_notification = await database.notifications.find_one({
            "recipient_id": ObjectId(str(hub["creator_id"])),
            "sender_id": sender_id,
            "type": "community_invite",
            "entity_type": "Community",
            "entity_id": ObjectId(community_id),
            "is_read": False,
        })
        if not existing_notification:
            await Notification(
                recipient_id=ObjectId(str(hub["creator_id"])),
                sender_id=sender_id,
                type="community_invite",
                entity_type="Community",
                entity_id=ObjectId(community_id),
                message=f'{community.get("name", "A community")} invited your Official Hub to join its network.',
            ).insert()
    return {"success": True, "invites": [
        {"id": invite.get("community_id"), **invite}
        for invite in hub.get("pending_community_invites", [])
    ]}


@router.post("/{hub_id}/community-invites/{community_id}/respond")
async def respond_to_community_invite(
    hub_id: str,
    community_id: str,
    body: InvitationResponseBody,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(hub_id) or not ObjectId.is_valid(community_id):
        raise HTTPException(status_code=404, detail="Community or hub not found")
    database = get_database()
    hub = await database.groups.find_one({"_id": ObjectId(hub_id)})
    community = await database.groups.find_one({"_id": ObjectId(community_id)})
    if not hub or not community or not hub.get("is_official") or not community.get("is_community"):
        raise HTTPException(status_code=404, detail="Community or hub not found")
    is_admin = str(hub.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in hub.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only hub admins can respond to invitations")
    if body.accept:
        await database.groups.update_one(
            {"_id": community["_id"]},
            {"$addToSet": {"affiliated_hubs": hub_id}},
        )
    await database.groups.update_one(
        {"_id": hub["_id"]},
        {"$pull": {"pending_community_invites": {"community_id": community_id}}},
    )
    return {"success": True, "message": "Invitation accepted" if body.accept else "Invitation declined"}


@router.get("/{group_id}/pending")
async def get_pending_group_requests(
    group_id: str,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=404, detail="Group not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    is_admin = str(group.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in group.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only group admins can view requests")

    request_ids = [
        ObjectId(request_id)
        for request_id in group.get("pending_requests", [])
        if ObjectId.is_valid(str(request_id))
    ]
    users = []
    async for requested_user in database.users.find({"_id": {"$in": request_ids}}):
        avatar = requested_user.get("avatar") or {}
        users.append({
            "id": str(requested_user["_id"]),
            "name": requested_user.get("name", ""),
            "username": requested_user.get("username", ""),
            "avatar": avatar,
        })
    return {"success": True, "requests": users}


@router.post("/{group_id}/approve/{user_id}")
async def approve_group_request(
    group_id: str,
    user_id: str,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(group_id) or not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="Group or user not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    requested_user = await database.users.find_one({"_id": ObjectId(user_id)})
    if not group or not requested_user:
        raise HTTPException(status_code=404, detail="Group or user not found")

    is_admin = str(group.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in group.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only group admins can approve requests")
    if user_id not in {str(request_id) for request_id in group.get("pending_requests", [])}:
        raise HTTPException(status_code=404, detail="Join request not found")

    await database.group_members.update_one(
        {"group_id": group_id, "user_id": user_id},
        {
            "$setOnInsert": {
                "group_id": group_id,
                "user_id": user_id,
                "role": "member",
                "contributed_points": 0,
                "joined_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    await database.groups.update_one(
        {"_id": group["_id"]},
        {
            "$addToSet": {"members": user_id},
            "$pull": {"pending_requests": user_id},
            "$inc": {"members_count": 1},
        },
    )
    return {"success": True, "message": "Join request approved"}


@router.post("/{group_id}/reject/{user_id}")
async def reject_group_request(
    group_id: str,
    user_id: str,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(group_id) or not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="Group or user not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    is_admin = str(group.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in group.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only group admins can reject requests")

    await database.groups.update_one(
        {"_id": group["_id"]},
        {"$pull": {"pending_requests": user_id}},
    )
    return {"success": True, "message": "Join request rejected"}


@router.post("/invitations/{invite_id}/respond")
async def respond_to_group_invitation(
    invite_id: str,
    body: InvitationResponseBody,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(invite_id):
        raise HTTPException(status_code=404, detail="Invitation not found")

    database = get_database()
    invitation = await database.group_invitations.find_one({
        "_id": ObjectId(invite_id),
        "invitee_id": str(user.id),
        "status": "pending",
    })
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if body.accept:
        group = await database.groups.find_one({"_id": ObjectId(invitation["group_id"])})
        if not group or group.get("is_active") is False:
            raise HTTPException(status_code=404, detail="Group not found")
        if group.get("is_official"):
            existing_group = await database.groups.find_one({
                "_id": {"$ne": group["_id"]},
                "is_official": True,
                "is_community": {"$ne": True},
                "members": {"$in": [str(user.id), user.id]},
                "is_active": {"$ne": False},
            })
            if existing_group:
                raise HTTPException(status_code=409, detail="You can only join one Official Hub")
        await database.group_members.update_one(
            {"group_id": invitation["group_id"], "user_id": str(user.id)},
            {
                "$setOnInsert": {
                    "group_id": invitation["group_id"],
                    "user_id": str(user.id),
                    "role": "member",
                    "contributed_points": 0,
                    "joined_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )
        await database.groups.update_one(
            {"_id": group["_id"]},
            {"$addToSet": {"members": str(user.id)}, "$inc": {"members_count": 1}},
        )

    await database.group_invitations.update_one(
        {"_id": invitation["_id"]},
        {"$set": {"status": "accepted" if body.accept else "declined"}},
    )
    return {"success": True, "accepted": body.accept}


@router.get("/slug/{slug}")
async def get_group_by_slug(slug: str, user=Depends(get_current_user)):
    database = get_database()
    document = await database.groups.find_one({
        "slug": slug,
        "is_active": {"$ne": False},
    })
    if not document:
        return {"success": False, "group": None}
    response = (
        await community_response(database, document)
        if document.get("is_community")
        else group_response(document)
    )
    response["community_access"] = await has_group_content_access(
        database, document, str(user.id)
    )
    return {"success": True, "group": response}


@router.get("/{group_id}/members")
async def get_group_members(group_id: str, user=Depends(get_current_user)):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=404, detail="Group not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    member_records = await database.group_members.find(
        {"group_id": group_id}
    ).to_list(length=1000)
    member_ids = [record.get("user_id") for record in member_records if record.get("user_id")]
    users = {}
    async for member in database.users.find({"_id": {"$in": [
        ObjectId(member_id) for member_id in member_ids if ObjectId.is_valid(member_id)
    ]}}):
        users[str(member["_id"])] = member

    members = []
    for record in member_records:
        member = users.get(str(record["user_id"]))
        if not member:
            continue
        avatar = member.get("avatar") or {}
        members.append({
            "id": str(member["_id"]),
            "name": member.get("name", ""),
            "username": member.get("username", ""),
            "avatar": avatar,
            "role": record.get("role", "member"),
            "points_since_joining": record.get("contributed_points", 0),
        })
    return {"success": True, "members": members}


@router.delete("/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: str,
    user_id: str,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(group_id) or not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="Group or user not found")
    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    is_admin = str(group.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in group.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only group admins can remove members")
    if user_id == str(group.get("creator_id")):
        raise HTTPException(status_code=400, detail="The group creator cannot be removed")
    membership = await database.group_members.find_one_and_delete({
        "group_id": group_id,
        "user_id": user_id,
    })
    if membership:
        await database.groups.update_one(
            {"_id": group["_id"]},
            {
                "$pull": {"members": user_id},
                "$inc": {
                    "members_count": -1,
                    "total_points": -float(membership.get("contributed_points", 0)),
                },
            },
        )
    return {"success": True}


@router.delete("/{group_id}/leave")
async def leave_group(group_id: str, user=Depends(get_current_user)):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=404, detail="Group not found")
    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if str(group.get("creator_id")) == str(user.id):
        raise HTTPException(status_code=400, detail="The group creator cannot leave")
    membership = await database.group_members.find_one_and_delete({
        "group_id": group_id,
        "user_id": str(user.id),
    })
    if membership:
        await database.groups.update_one(
            {"_id": group["_id"]},
            {
                "$pull": {"members": str(user.id)},
                "$inc": {
                    "members_count": -1,
                    "total_points": -float(membership.get("contributed_points", 0)),
                },
            },
        )
    return {"success": True}


@router.get("/{group_id}/messages")
async def get_group_messages(group_id: str, user=Depends(get_current_user)):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=404, detail="Group not found")

    database = get_database()
    group = await require_group_member(database, group_id, str(user.id))

    messages = []
    async for message in database.group_messages.find(
        {"group_id": group_id}
    ).sort("created_at", 1).limit(200):
        messages.append({
            "_id": str(message["_id"]),
            "sender_id": str(message.get("sender_id", "")),
            "sender_name": message.get("sender_name", ""),
            "text": message.get("text", ""),
            "created_at": message.get("created_at"),
        })
    return {"success": True, "messages": messages}


@router.post("/{group_id}/messages")
async def send_group_message(
    group_id: str,
    body: GroupMessageBody,
    user=Depends(get_current_user),
):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=404, detail="Group not found")

    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group or group.get("is_active") is False:
        raise HTTPException(status_code=404, detail="Group not found")

    if not await has_group_content_access(database, group, str(user.id)):
        raise HTTPException(status_code=403, detail="Only group members can send messages")

    message = {
        "group_id": group_id,
        "sender_id": user_id,
        "sender_name": user.name,
        "text": body.text.strip(),
        "created_at": datetime.utcnow(),
    }
    if not message["text"]:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    result = await database.group_messages.insert_one(message)
    message["_id"] = result.inserted_id
    return {
        "success": True,
        "message": {
            "_id": str(message["_id"]),
            "sender_id": message["sender_id"],
            "sender_name": message["sender_name"],
            "text": message["text"],
            "created_at": message["created_at"],
        },
    }


@router.post("/{group_id}/reset-points")
async def reset_group_points(group_id: str, user=Depends(get_current_user)):
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=404, detail="Group not found")
    database = get_database()
    group = await database.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    is_admin = str(group.get("creator_id")) == str(user.id) or str(user.id) in {
        str(admin_id) for admin_id in group.get("admins", [])
    }
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only group admins can reset points")
    await database.group_members.update_many(
        {"group_id": group_id},
        {"$set": {"contributed_points": 0}},
    )
    await database.groups.update_one(
        {"_id": group["_id"]},
        {"$set": {"total_points": 0}},
    )
    return {"success": True, "message": "Group points reset successfully"}


@router.get("/leaderboard/list")
async def group_leaderboard(
    group_type: str = Query(default="group", alias="groupType"),
    search: str = Query(default=""),
    state: str = Query(default=""),
    city: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
):
    database = get_database()
    filters = {"is_active": {"$ne": False}}
    if group_type == "official":
        filters.update({"is_official": True, "is_community": {"$ne": True}})
    elif group_type == "community":
        filters["is_community"] = True
    else:
        filters.update({
            "is_official": {"$ne": True},
            "is_community": {"$ne": True},
        })

    if search.strip():
        pattern = re.escape(search.strip())
        filters["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"slug": {"$regex": pattern, "$options": "i"}},
        ]

    documents = await database.groups.find(filters).sort(
        "total_points", -1
    ).to_list(length=1000)

    if state or city:
        creator_ids = [
            ObjectId(str(document["creator_id"]))
            for document in documents
            if ObjectId.is_valid(str(document.get("creator_id")))
        ]
        location_pattern = ", ".join(
            part for part in (city, state) if part
        )
        creators = await database.users.find({
            "_id": {"$in": creator_ids},
            **({
                "location": {
                    "$regex": re.escape(location_pattern),
                    "$options": "i",
                }
            } if location_pattern else {}),
        }).to_list(length=1000)
        allowed_creator_ids = {str(creator["_id"]) for creator in creators}
        documents = [
            document for document in documents
            if str(document.get("creator_id")) in allowed_creator_ids
        ]

    total = len(documents)
    groups = [
        {
            **group_response(document),
            "rank": index + 1,
        }
        for index, document in enumerate(documents[skip:skip + limit], start=skip)
    ]
    return {"success": True, "groups": groups, "total": total}


@router.get("/discover/{group_type}")
async def discover_groups(
    group_type: str,
    q: Optional[str] = Query(default=None),
):
    if group_type not in {"normal", "official", "community"}:
        return {"success": False, "groups": []}

    filters = {}
    if group_type == "official":
        filters = {"is_official": True, "is_community": {"$ne": True}}
    elif group_type == "community":
        filters = {"is_community": True}
    else:
        filters = {
            "is_official": {"$ne": True},
            "is_community": {"$ne": True},
        }

    if q and q.strip():
        pattern = re.escape(q.strip())
        filters["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"slug": {"$regex": pattern, "$options": "i"}},
        ]

    filters["is_active"] = {"$ne": False}
    documents = await get_database().groups.find(filters).sort("created_at", -1).to_list(length=100)
    groups = []
    for document in documents:
        groups.append(group_response(document))

    return {"success": True, "groups": groups}
