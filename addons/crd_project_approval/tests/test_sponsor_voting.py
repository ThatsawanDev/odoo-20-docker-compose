# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSponsorVoting(TransactionCase):
    """Multi-approver Business Sponsor voting: approver_ids assignment,
    per-user project.approval.history rows, and _evaluate_sponsor_votes
    majority/tie tally logic.
    """

    def setUp(self):
        super().setUp()
        approver_group = self.env.ref('crd_project_approval.group_project_approver')

        self.sponsor1 = self._create_user('sponsor1', approver_group)
        self.sponsor2 = self._create_user('sponsor2', approver_group)
        self.sponsor3 = self._create_user('sponsor3', approver_group)
        self.outsider = self._create_user('outsider', approver_group)
        self.it_head = self._create_user('it_head', approver_group)

        self.env['ir.config_parameter'].sudo().set_str(
            'crd_project_approval.auto_assign_it_head_user_id', str(self.it_head.id)
        )
        # Voting tests don't assert on notifications; disable them so a vote
        # cast as a non-superuser sponsor can't fail on an unrelated mail/
        # Teams-webhook side effect of the state transition.
        for key in ('send_assignment_email', 'send_assignment_teams', 'send_requester_notification'):
            self.env['ir.config_parameter'].sudo().set_str('crd_project_approval.%s' % key, 'False')

        self.project_size = self.env['project.size'].create({'name': 'M'})
        self.related_system = self.env['project.related.system'].create({'name': 'Test System'})
        self.dependency = self.env['project.dependency'].create({'name': 'Test Dependency'})

    def _create_user(self, key, group):
        user = self.env['res.users'].create({
            'name': 'Test %s' % key,
            'login': '%s_voting_test@ofm.test' % key,
            'email': '%s@ofm.test' % key,
        })
        user.groups_id = [(4, group.id)]
        return user

    def _make_signoff(self, sponsors, requester=None):
        """Create a signoff with every field action_wait_for_approval requires,
        then advance it from draft -> in_review -> wait_for_approval so
        approver_ids/history rows are populated for the given sponsors.

        `requester` lets the "non-approver" tests give a user read/write
        access to the record (via the requester_id clause of the
        rule_project_approval_read_own record rule) without adding them to
        approver_ids, so the assertion reaches the intended UserError instead
        of failing earlier on an AccessError.
        """
        vals = {
            'project_name': 'Test Voting Project',
            'project_objective': 'Test objective',
            'scope_pain_points': 'Test scope',
            'business_sponsor_ids': [(6, 0, sponsors.ids)],
            'technical_impact': 'Test technical impact',
            'related_system_ids': [(6, 0, [self.related_system.id])],
            'dependency_ids': [(6, 0, [self.dependency.id])],
            'estimated_effort': '10',
            'date_timeline_start': '2026-01-01',
            'date_timeline_end': '2026-02-01',
            'project_size_id': self.project_size.id,
            'feature_impact_ids': [(0, 0, {'name': 'Test Feature'})],
            'business_impact_ids': [(0, 0, {'change_impact_description': 'Test Impact'})],
        }
        if requester is not None:
            vals['requester_id'] = requester.id
        signoff = self.env['project.approval.signoff'].create(vals)
        signoff.action_submit()
        signoff.action_wait_for_approval()
        return signoff

    def test_pending_rows_created_and_close_individually(self):
        """Right after action_wait_for_approval, each approver has their own
        pending waiting row; voting closes only the voter's own row."""
        sponsors = self.sponsor1 + self.sponsor2 + self.sponsor3
        signoff = self._make_signoff(sponsors)

        for sponsor in sponsors:
            row = signoff.history_ids.filtered(
                lambda h, s=sponsor: h.row_type == 'waiting'
                and h.status == 'pending'
                and h.user_id.id == s.id
            )
            self.assertEqual(len(row), 1, "Expected one pending row for %s" % sponsor.name)

        signoff.with_user(self.sponsor1).action_sponsor_approve()

        row1 = signoff.history_ids.filtered(
            lambda h: h.row_type == 'waiting' and h.user_id.id == self.sponsor1.id
        )
        self.assertEqual(row1.status, 'done', "sponsor1's own row should close on vote")

        for sponsor in (self.sponsor2, self.sponsor3):
            row = signoff.history_ids.filtered(
                lambda h, s=sponsor: h.row_type == 'waiting'
                and h.status == 'pending'
                and h.user_id.id == s.id
            )
            self.assertEqual(len(row), 1, "%s's row should remain pending" % sponsor.name)

    def test_all_approve_advances_to_wait_it_head_approval(self):
        sponsors = self.sponsor1 + self.sponsor2 + self.sponsor3
        signoff = self._make_signoff(sponsors)

        signoff.with_user(self.sponsor1).action_sponsor_approve()
        signoff.with_user(self.sponsor2).action_sponsor_approve()
        signoff.with_user(self.sponsor3).action_sponsor_approve()

        self.assertEqual(signoff.state, 'wait_it_head_approval')

    def test_majority_approve_two_vs_one_advances(self):
        sponsors = self.sponsor1 + self.sponsor2 + self.sponsor3
        signoff = self._make_signoff(sponsors)

        signoff.with_user(self.sponsor1).action_sponsor_approve()
        signoff.with_user(self.sponsor2).action_sponsor_approve()
        signoff.with_user(self.sponsor3).action_sponsor_reject()

        self.assertEqual(signoff.state, 'wait_it_head_approval')

    def test_majority_reject_two_vs_one_goes_draft(self):
        sponsors = self.sponsor1 + self.sponsor2 + self.sponsor3
        signoff = self._make_signoff(sponsors)

        signoff.with_user(self.sponsor1).action_sponsor_approve()
        signoff.with_user(self.sponsor2).action_sponsor_reject()
        signoff.with_user(self.sponsor3).action_sponsor_reject()

        self.assertEqual(signoff.state, 'draft')

    def test_tie_two_approvers_stays_pending(self):
        sponsors = self.sponsor1 + self.sponsor2
        signoff = self._make_signoff(sponsors)

        signoff.with_user(self.sponsor1).action_sponsor_approve()
        signoff.with_user(self.sponsor2).action_sponsor_reject()

        self.assertEqual(
            signoff.state, 'wait_for_approval',
            "A tied vote should not advance the state (deferred tie-break rule)",
        )

    def test_non_approver_raises_user_error_on_approve(self):
        sponsors = self.sponsor1 + self.sponsor2 + self.sponsor3
        # requester=outsider grants the outsider read/write access to the
        # record (via the record rule's requester_id clause) without putting
        # them in approver_ids, so the assertion below reaches the intended
        # business-logic UserError rather than an unrelated AccessError.
        signoff = self._make_signoff(sponsors, requester=self.outsider)

        with self.assertRaises(UserError):
            signoff.with_user(self.outsider).action_sponsor_approve()

    def test_non_approver_raises_user_error_on_reject(self):
        sponsors = self.sponsor1 + self.sponsor2 + self.sponsor3
        signoff = self._make_signoff(sponsors, requester=self.outsider)

        with self.assertRaises(UserError):
            signoff.with_user(self.outsider).action_sponsor_reject()
