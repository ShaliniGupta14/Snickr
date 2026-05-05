from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_connection
from dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_base_context(user_id: int, conn):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT w.workspace_id, w.name FROM Workspaces w
        JOIN WorkspaceMembers wm ON wm.workspace_id = w.workspace_id
        WHERE wm.user_id = %s AND wm.joined_at IS NOT NULL
          AND wm.removed_at IS NULL ORDER BY w.name
    """, (user_id,))
    workspaces = cursor.fetchall()
    cursor.execute(
        "SELECT username, nickname FROM Users WHERE user_id = %s", (user_id,)
    )
    me = cursor.fetchone()
    cursor.close()
    return {"workspaces": workspaces, "me": me}

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user_id: int = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT w.workspace_id, w.name, w.description
            FROM Workspaces w
            JOIN WorkspaceMembers wm ON wm.workspace_id = w.workspace_id
            WHERE wm.user_id = %s
              AND wm.joined_at IS NOT NULL
              AND wm.removed_at IS NULL
            ORDER BY w.name
        """, (user_id,))
        workspaces = cursor.fetchall()

        cursor.execute("""
            SELECT wi.invitation_id, w.name AS workspace_name,
                   u.username AS invited_by, wi.invited_at
            FROM WorkspaceInvitations wi
            JOIN Workspaces w ON w.workspace_id = wi.workspace_id
            JOIN Users u ON u.user_id = wi.invited_by
            JOIN Users me ON me.email = wi.invited_email
            WHERE me.user_id = %s AND wi.status = 'pending'
        """, (user_id,))
        invites = cursor.fetchall()

        cursor.execute(
            "SELECT username, nickname FROM Users WHERE user_id = %s",
            (user_id,)
        )
        me = cursor.fetchone()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "workspaces": workspaces,
            "invites": invites,
            "me": me,
            "active_workspace_id": None,
        })
    finally:
        cursor.close()
        conn.close()

@router.post("/workspaces/create")
def create_workspace(
    name: str = Form(...),
    description: str = Form(""),
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Workspaces (creator_id, name, description) "
            "VALUES (%s, %s, %s)",
            (user_id, name.strip(), description.strip()),
        )
        workspace_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO WorkspaceMembers
                (workspace_id, user_id, is_admin, invited_at, joined_at)
            VALUES (%s, %s, 1, NOW(), NOW())
        """, (workspace_id, user_id))
        conn.commit()
        return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
    except Exception:
        conn.rollback()
        return RedirectResponse("/dashboard", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.get("/workspaces/{workspace_id}", response_class=HTMLResponse)
def view_workspace(
    workspace_id: int,
    request: Request,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT is_admin FROM WorkspaceMembers
            WHERE workspace_id = %s AND user_id = %s
              AND joined_at IS NOT NULL AND removed_at IS NULL
        """, (workspace_id, user_id))
        membership = cursor.fetchone()
        if not membership:
            return RedirectResponse("/dashboard", status_code=303)

        cursor.execute(
            "SELECT * FROM Workspaces WHERE workspace_id = %s",
            (workspace_id,)
        )
        workspace = cursor.fetchone()

        cursor.execute("""
            SELECT c.channel_id, c.name, c.type
            FROM Channels c
            JOIN ChannelMembers cm
              ON cm.channel_id = c.channel_id AND cm.user_id = %s
            WHERE c.workspace_id = %s
              AND cm.joined_at IS NOT NULL AND cm.removed_at IS NULL
            ORDER BY c.type, c.name
        """, (user_id, workspace_id))
        channels = cursor.fetchall()

        cursor.execute("""
            SELECT c.channel_id, c.name
            FROM Channels c
            WHERE c.workspace_id = %s AND c.type = 'public'
              AND c.channel_id NOT IN (
                SELECT channel_id FROM ChannelMembers
                WHERE user_id = %s
                  AND joined_at IS NOT NULL AND removed_at IS NULL
              )
            ORDER BY c.name
        """, (workspace_id, user_id))
        joinable = cursor.fetchall()

        cursor.execute("""
            SELECT u.user_id, u.username, u.nickname, wm.is_admin
            FROM WorkspaceMembers wm
            JOIN Users u ON u.user_id = wm.user_id
            WHERE wm.workspace_id = %s
              AND wm.joined_at IS NOT NULL AND wm.removed_at IS NULL
            ORDER BY u.username
        """, (workspace_id,))
        members = cursor.fetchall()

        ctx = get_base_context(user_id, conn)
        return templates.TemplateResponse("workspace.html", {
            "request": request,
            "workspace": workspace,
            "channels": channels,
            "joinable": joinable,
            "members": members,
            "is_admin": membership["is_admin"],
            "active_workspace_id": workspace_id,
            **ctx,
        })
    finally:
        cursor.close()
        conn.close()

@router.post("/workspaces/{workspace_id}/invite")
def invite_to_workspace(
    workspace_id: int,
    email: str = Form(...),
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT is_admin FROM WorkspaceMembers
            WHERE workspace_id = %s AND user_id = %s
              AND joined_at IS NOT NULL AND removed_at IS NULL
        """, (workspace_id, user_id))
        m = cursor.fetchone()
        if not m or not m["is_admin"]:
            return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
        cursor.execute("""
            INSERT INTO WorkspaceInvitations
                (workspace_id, invited_email, invited_by, status)
            VALUES (%s, %s, %s, 'pending')
        """, (workspace_id, email.strip(), user_id))
        conn.commit()
        return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
    except Exception:
        conn.rollback()
        return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.post("/workspaces/{workspace_id}/remove/{target_user_id}")
def remove_member(
    workspace_id: int,
    target_user_id: int,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT is_admin FROM WorkspaceMembers
            WHERE workspace_id = %s AND user_id = %s
              AND joined_at IS NOT NULL AND removed_at IS NULL
        """, (workspace_id, user_id))
        m = cursor.fetchone()
        if not m or not m["is_admin"]:
            return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
        cursor.execute("""
            UPDATE WorkspaceMembers SET removed_at = NOW()
            WHERE workspace_id = %s AND user_id = %s
        """, (workspace_id, target_user_id))
        conn.commit()
        return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.post("/workspaces/{workspace_id}/promote/{target_user_id}")
def promote_member(
    workspace_id: int,
    target_user_id: int,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT is_admin FROM WorkspaceMembers
            WHERE workspace_id = %s AND user_id = %s
              AND joined_at IS NOT NULL AND removed_at IS NULL
        """, (workspace_id, user_id))
        m = cursor.fetchone()
        if not m or not m["is_admin"]:
            return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
        cursor.execute("""
            UPDATE WorkspaceMembers SET is_admin = 1
            WHERE workspace_id = %s AND user_id = %s
        """, (workspace_id, target_user_id))
        conn.commit()
        return RedirectResponse(f"/workspaces/{workspace_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()
