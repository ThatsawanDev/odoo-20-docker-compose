def migrate(cr, version):
    cr.execute("""
        INSERT INTO project_approval_signoff_business_owner_rel (signoff_id, user_id)
        SELECT id, business_owner
        FROM project_approval_signoff
        WHERE business_owner IS NOT NULL
    """)
    cr.execute("ALTER TABLE project_approval_signoff DROP COLUMN IF EXISTS business_owner")
