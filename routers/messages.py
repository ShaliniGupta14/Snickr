from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_connection
from dependencies import get_current_user
from routers.workspaces import get_base_context

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.post("/channels/{channel_id}/post")
def post_message(
    channel_id: int,
    body: str = Form(...),
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
        cursor.execute(
            "INSERT INTO Messages (channel_id, user_id, body) "
            "VALUES (%s, %s, %s)",
            (channel_id, user_id, body.strip()),
        )
        conn.commit()
        return RedirectResponse(f"/channels/{channel_id}", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    q: str = "",
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    results = []
    try:
        if q.strip():
            cursor.execute("""
                SELECT m.message_id, m.body, m.posted_at,
                       u.username AS author,
                       c.name AS channel_name, c.type AS channel_type,
                       c.channel_id, w.name AS workspace_name
                FROM Messages m
                JOIN Channels c ON c.channel_id = m.channel_id
                JOIN Workspaces w ON w.workspace_id = c.workspace_id
                JOIN Users u ON u.user_id = m.user_id
                JOIN WorkspaceMembers wm
                  ON wm.workspace_id = c.workspace_id
                  AND wm.user_id = %s
                JOIN ChannelMembers cm
                  ON cm.channel_id = m.channel_id
                  AND cm.user_id = %s
                WHERE m.body LIKE %s
                  AND wm.joined_at IS NOT NULL AND wm.removed_at IS NULL
                  AND cm.joined_at IS NOT NULL AND cm.removed_at IS NULL
                ORDER BY m.posted_at DESC
            """, (user_id, user_id, f"%{q.strip()}%"))
            results = cursor.fetchall()
        ctx = get_base_context(user_id, conn)
        return templates.TemplateResponse("search.html", {
            "request": request,
            "q": q,
            "results": results,
            **ctx,
        })
    finally:
        cursor.close()
        conn.close()