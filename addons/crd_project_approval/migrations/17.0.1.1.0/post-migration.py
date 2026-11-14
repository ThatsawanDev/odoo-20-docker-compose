def migrate(cr, version):
    cr.execute("""
        INSERT INTO project_approval_signoff_business_sponsor_rel (signoff_id, user_id)
        SELECT id, business_sponsor
        FROM project_approval_signoff
        WHERE business_sponsor IS NOT NULL
    """)
    cr.execute("ALTER TABLE project_approval_signoff DROP COLUMN IF EXISTS business_sponsor")

    # Records already sitting in wait_for_approval at upgrade time were never
    # touched by the new action_wait_for_approval logic, so their
    # approver_ids is empty and their existing pending 'waiting' history row
    # has user_id = NULL (it was created by the old single-approver code,
    # which never set user_id). Backfill both from the business_sponsor_ids
    # relation just populated above, so is_pending_sponsor_approver resolves
    # for the real sponsor instead of leaving the record permanently stuck.
    _migrate_pending_sponsor_approvals(cr)


def _migrate_pending_sponsor_approvals(cr):
    # approver_ids is a Many2many with no explicit relation/column names, so
    # Odoo auto-generated them from the sorted table names:
    # project_approval_signoff / res_users -> project_approval_signoff_res_users_rel
    # (column1 = project_approval_signoff_id, column2 = res_users_id).
    # Guarded with NOT EXISTS so this INSERT is safe to re-run.
    cr.execute("""
        INSERT INTO project_approval_signoff_res_users_rel
            (project_approval_signoff_id, res_users_id)
        SELECT bs.signoff_id, bs.user_id
        FROM project_approval_signoff_business_sponsor_rel bs
        JOIN project_approval_signoff s ON s.id = bs.signoff_id
        WHERE s.state = 'wait_for_approval'
          AND NOT EXISTS (
              SELECT 1 FROM project_approval_signoff_res_users_rel r
              WHERE r.project_approval_signoff_id = bs.signoff_id
                AND r.res_users_id = bs.user_id
          )
    """)

    # business_sponsor was a Many2one, so every record migrated above has
    # exactly one sponsor row here; the loop below still handles >1 sponsor
    # defensively in case this script is ever reused after business_sponsor_ids
    # becomes genuinely multi-valued.
    cr.execute("""
        SELECT s.id, array_agg(bs.user_id ORDER BY bs.user_id)
        FROM project_approval_signoff s
        JOIN project_approval_signoff_business_sponsor_rel bs ON bs.signoff_id = s.id
        WHERE s.state = 'wait_for_approval'
        GROUP BY s.id
    """)
    signoff_sponsors = cr.fetchall()

    for signoff_id, sponsor_ids in signoff_sponsors:
        if not sponsor_ids:
            # No business sponsor was ever set on this record -- nothing to
            # backfill; leaving it as-is is no worse than before this
            # migration (pre-existing data issue, out of scope here).
            continue

        cr.execute("""
            SELECT id, user_id
            FROM project_approval_history
            WHERE approval_id = %s
              AND row_type = 'waiting'
              AND status = 'pending'
            ORDER BY id
        """, (signoff_id,))
        pending_rows = cr.fetchall()
        null_user_rows = [row_id for row_id, user_id in pending_rows if user_id is None]
        existing_user_ids = {user_id for _, user_id in pending_rows if user_id is not None}

        first_sponsor, extra_sponsors = sponsor_ids[0], sponsor_ids[1:]

        if null_user_rows:
            # Legacy pending row from the old single-approver code: reuse it
            # for the first sponsor, keeping its existing detail/actor_id.
            cr.execute(
                "UPDATE project_approval_history SET user_id = %s WHERE id = %s",
                (first_sponsor, null_user_rows[0]),
            )
        elif not pending_rows:
            # No pending waiting row at all (unexpected -- e.g. history was
            # manually deleted). Synthesize one, mirroring the row shape
            # action_wait_for_approval creates for new records.
            cr.execute("""
                INSERT INTO project_approval_history
                    (approval_id, row_type, status, user_id, actor_id, detail, date)
                VALUES (%s, 'waiting', 'pending', %s, %s, %s, now() at time zone 'UTC')
            """, (
                signoff_id, first_sponsor, first_sponsor,
                'Business Sponsor Review and Approve (migrated)',
            ))
        # else: every pending waiting row already has a user_id (e.g. this
        # script ran before) -- nothing to backfill for the first sponsor.

        # Any sponsors beyond the first never had a corresponding legacy row
        # (the old flow only ever created one shared pending row), so they
        # need a brand-new row -- skip any that already have one (re-run safety).
        for sponsor_id in extra_sponsors:
            if sponsor_id in existing_user_ids:
                continue
            cr.execute("""
                INSERT INTO project_approval_history
                    (approval_id, row_type, status, user_id, actor_id, detail, date)
                VALUES (%s, 'waiting', 'pending', %s, %s, %s, now() at time zone 'UTC')
            """, (
                signoff_id, sponsor_id, sponsor_id,
                'Business Sponsor Review and Approve (migrated)',
            ))
