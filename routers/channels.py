from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_connection
from dependencies import get_current_user
from routers.workspaces import get_base_context

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.post("/workspaces/{workspace_id}/channels/create")
def create_channel(
    workspace_id: int,
    name: str = Form(...),
    type: str = Form(...),
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 1 FROM WorkspaceMembers
            WHERE workspace_id = %s AND user_id = %s
              AND joined_at IS NOT NULL AND removed_at IS NULL
        """, (workspace_id, user_id))
        if not cursor.fetchone():
            return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
        if type not in ("public", "private", "direct"):
            return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
        cursor.execute("""
            INSERT INTO Channels (workspace_id, creator_id, name, type)
            VALUES (%s, %s, %s, %s)
        """, (workspace_id, user_id, name.strip(), type))
        channel_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO ChannelMembers
                (channel_id, user_id, invited_at, joined_at)
            VALUES (%s, %s, NOW(), NOW())
        """, (channel_id, user_id))
        conn.commit()
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)
    except Exception:
        conn.rollback()
        return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.post("/channels/{channel_id}/join")
def join_channel(
    channel_id: int,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT type, workspace_id FROM Channels WHERE channel_id = %s",
            (channel_id,)
        )
        ch = cursor.fetchone()
        if not ch or ch["type"] != "public":
            return RedirectResponse("/dashboard", status_code=303)
        cursor.execute("""
            SELECT 1 FROM WorkspaceMembers
            WHERE workspace_id = %s AND user_id = %s
              AND joined_at IS NOT NULL AND removed_at IS NULL
        """, (ch["workspace_id"], user_id))
        if not cursor.fetchone():
            return RedirectResponse("/dashboard", status_code=303)
        cursor.execute("""
            INSERT INTO ChannelMembers
                (channel_id, user_id, invited_at, joined_at)
            VALUES (%s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE joined_at = NOW(), removed_at = NULL
        """, (channel_id, user_id))
        conn.commit()
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.get("/channels/{channel_id}", response_class=HTMLResponse)
def view_channel(
    channel_id: int,
    request: Request,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 1 FROM ChannelMembers
            WHERE channel_id = %s AND user_id = %s
              AND joined_at IS NOT NULL AND removed_at IS NULL
        """, (channel_id, user_id))
        if not cursor.fetchone():
            return RedirectResponse("/dashboard", status_code=303)
        cursor.execute("""
            SELECT c.*, w.name AS workspace_name, w.workspace_id
            FROM Channels c
            JOIN Workspaces w ON w.workspace_id = c.workspace_id
            WHERE c.channel_id = %s
        """, (channel_id,))
        channel = cursor.fetchone()
        cursor.execute("""
            SELECT m.message_id, m.body, m.posted_at, u.username
            FROM Messages m
            JOIN Users u ON u.user_id = m.user_id
            WHERE m.channel_id = %s
            ORDER BY m.posted_at ASC
        """, (channel_id,))
        messages = cursor.fetchall()
        cursor.execute("""
            SELECT u.username, u.nickname
            FROM ChannelMembers cm
            JOIN Users u ON u.user_id = cm.user_id
            WHERE cm.channel_id = %s
              AND cm.joined_at IS NOT NULL AND cm.removed_at IS NULL
        """, (channel_id,))
        members = cursor.fetchall()
        ctx = get_base_context(user_id, conn)
        return templates.TemplateResponse("channel.html", {
            "request": request,
            "channel": channel,
            "messages": messages,
            "members": members,
            "active_workspace_id": channel["workspace_id"],
            **ctx,
        })
    finally:
        cursor.close()
        conn.close()

@router.post("/channels/{channel_id}/invite")
def invite_to_channel(
    channel_id: int,
    username: str = Form(...),
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT type, workspace_id FROM Channels WHERE channel_id = %s",
            (channel_id,)
        )
        ch = cursor.fetchone()
        if not ch or ch["type"] == "public":
            return RedirectResponse(f"/channels/{channel_id}", status_code=303)
        cursor.execute("""
            SELECT u.user_id FROM Users u
            JOIN WorkspaceMembers wm ON wm.user_id = u.user_id
            WHERE u.username = %s AND wm.workspace_id = %s
              AND wm.joined_at IS NOT NULL AND wm.removed_at IS NULL
        """, (username.strip(), ch["workspace_id"]))
        target = cursor.fetchone()
        if not target:
            return RedirectResponse(f"/channels/{channel_id}", status_code=303)
        cursor.execute("""
            INSERT INTO ChannelMembers
                (channel_id, user_id, invited_by, invited_at)
            VALUES (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE invited_at = NOW(), removed_at = NULL
        """, (channel_id, target["user_id"], user_id))
        conn.commit()
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.post("/channels/{channel_id}/accept-invite")
def accept_channel_invite(
    channel_id: int,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE ChannelMembers SET joined_at = NOW()
            WHERE channel_id = %s AND user_id = %s
              AND joined_at IS NULL AND removed_at IS NULL
        """, (channel_id, user_id))
        conn.commit()
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.post("/workspaces/{workspace_id}/direct")
def create_direct_channel(
    workspace_id: int,
    target_username: str = Form(...),
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT user_id FROM Users WHERE username = %s",
            (target_username.strip(),)
        )
        target = cursor.fetchone()
        if not target or target["user_id"] == user_id:
            return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
        cursor.execute("""
            SELECT c.channel_id FROM Channels c
            JOIN ChannelMembers cm1
              ON cm1.channel_id = c.channel_id AND cm1.user_id = %s
            JOIN ChannelMembers cm2
              ON cm2.channel_id = c.channel_id AND cm2.user_id = %s
            WHERE c.workspace_id = %s AND c.type = 'direct'
              AND cm1.joined_at IS NOT NULL AND cm2.joined_at IS NOT NULL
        """, (user_id, target["user_id"], workspace_id))
        existing = cursor.fetchone()
        if existing:
            return RedirectResponse(
                f"/channels/{existing['channel_id']}", status_code=303
            )
        name = f"dm-{user_id}-{target['user_id']}"
        cursor.execute("""
            INSERT INTO Channels (workspace_id, creator_id, name, type)
            VALUES (%s, %s, %s, 'direct')
        """, (workspace_id, user_id, name))
        channel_id = cursor.lastrowid
        for uid in [user_id, target["user_id"]]:
            cursor.execute("""
                INSERT INTO ChannelMembers
                    (channel_id, user_id, invited_at, joined_at)
                VALUES (%s, %s, NOW(), NOW())
            """, (channel_id, uid))
        conn.commit()
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)
    except Exception:
        conn.rollback()
        return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()
