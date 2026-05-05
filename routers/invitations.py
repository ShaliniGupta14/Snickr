from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from database import get_connection
from dependencies import get_current_user

router = APIRouter()

@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(
    invitation_id: int,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT wi.workspace_id, wi.invited_email, wi.invited_by
            FROM WorkspaceInvitations wi
            JOIN Users u ON u.email = wi.invited_email
            WHERE wi.invitation_id = %s
              AND u.user_id = %s
              AND wi.status = 'pending'
        """, (invitation_id, user_id))
        inv = cursor.fetchone()
        if not inv:
            return RedirectResponse("/dashboard", status_code=303)
        cursor.execute("""
            UPDATE WorkspaceInvitations SET status = 'accepted'
            WHERE invitation_id = %s
        """, (invitation_id,))
        cursor.execute("""
            INSERT INTO WorkspaceMembers
                (workspace_id, user_id, invited_by, is_admin,
                 invited_at, joined_at)
            VALUES (%s, %s, %s, 0, NOW(), NOW())
            ON DUPLICATE KEY UPDATE joined_at = NOW(), removed_at = NULL
        """, (inv["workspace_id"], user_id, inv["invited_by"]))
        conn.commit()
        return RedirectResponse(
            f"/workspaces/{inv['workspace_id']}", status_code=303
        )
    except Exception:
        conn.rollback()
        return RedirectResponse("/dashboard", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.post("/invitations/{invitation_id}/decline")
def decline_invitation(
    invitation_id: int,
    user_id: int = Depends(get_current_user),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            UPDATE WorkspaceInvitations wi
            JOIN Users u ON u.email = wi.invited_email
            SET wi.status = 'declined'
            WHERE wi.invitation_id = %s
              AND u.user_id = %s
              AND wi.status = 'pending'
        """, (invitation_id, user_id))
        conn.commit()
        return RedirectResponse("/dashboard", status_code=303)
    finally:
        cursor.close()
        conn.close()