def migrate(cr, version):
    cr.execute("""
        INSERT INTO project_approval_signoff_assignee_rel (approval_id, user_id)
        SELECT id, assigne_user_id
        FROM project_approval_signoff
        WHERE assigne_user_id IS NOT NULL
    """)
    cr.execute("ALTER TABLE project_approval_signoff DROP COLUMN IF EXISTS assigne_user_id")
