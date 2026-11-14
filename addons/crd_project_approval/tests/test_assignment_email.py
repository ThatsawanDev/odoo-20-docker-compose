# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAssignmentEmail(TransactionCase):

    def setUp(self):
        super().setUp()
        self.reviewer = self.env['res.users'].create({
            'name': 'Test Reviewer',
            'login': 'reviewer_email_test@ofm.test',
            'email': 'reviewer@ofm.test',
        })
        self.project_size = self.env['project.size'].create({'name': 'M'})
        self.related_system = self.env['project.related.system'].create({'name': 'Test System'})
        self.dependency = self.env['project.dependency'].create({'name': 'Test Dependency'})
        self.signoff = self.env['project.approval.signoff'].create({
            'project_name': 'Test IT Project',
            'project_objective': 'Test objective',
            'scope_pain_points': 'Test scope',
            'business_sponsor_ids': [(6, 0, [self.reviewer.id])],
            # Minimal values required by action_wait_for_approval's validation
            # block (technical_impact, related_system_ids, dependency_ids,
            # estimated_effort, date_timeline_start/end, project_size_id,
            # feature_impact_ids, business_impact_ids) so tests that call
            # action_wait_for_approval() can reach the code path being tested.
            'technical_impact': 'Test technical impact',
            'related_system_ids': [(6, 0, [self.related_system.id])],
            'dependency_ids': [(6, 0, [self.dependency.id])],
            'estimated_effort': '10',
            'date_timeline_start': '2026-01-01',
            'date_timeline_end': '2026-02-01',
            'project_size_id': self.project_size.id,
            'feature_impact_ids': [(0, 0, {'name': 'Test Feature'})],
            'business_impact_ids': [(0, 0, {'change_impact_description': 'Test Impact'})],
        })

    def test_config_send_assignment_email_default_true(self):
        """send_assignment_email reads as True when param not yet configured."""
        settings = self.env['project.approval.settings'].create({})
        self.assertTrue(
            settings.send_assignment_email,
            "send_assignment_email should default to True when param absent",
        )

    def test_config_send_assignment_teams_default_true(self):
        """send_assignment_teams reads as True when param not yet configured."""
        settings = self.env['project.approval.settings'].create({})
        self.assertTrue(
            settings.send_assignment_teams,
            "send_assignment_teams should default to True when param absent",
        )

    def test_template_in_review_exists(self):
        """Email template for in_review state is loadable."""
        template = self.env.ref(
            'crd_project_approval.email_template_assignment_in_review',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(template, "email_template_assignment_in_review must exist")

    def test_template_wait_approval_exists(self):
        """Email template for wait_for_approval state is loadable."""
        template = self.env.ref(
            'crd_project_approval.email_template_assignment_wait_approval',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(template, "email_template_assignment_wait_approval must exist")

    def _set_email_config(self, enabled):
        """Helper: set send_assignment_email ir.config_parameter."""
        self.env['ir.config_parameter'].sudo().set_str(
            'crd_project_approval.send_assignment_email', str(enabled),
        )

    def test_send_assignment_email_creates_mail_when_enabled(self):
        """_send_assignment_email creates a mail.mail record when config is True."""
        self._set_email_config(True)
        self.signoff.assigne_user_id = self.reviewer
        before = self.env['mail.mail'].sudo().search_count([])
        self.signoff._send_assignment_email(
            'crd_project_approval.email_template_assignment_in_review'
        )
        after = self.env['mail.mail'].sudo().search_count([])
        self.assertGreater(after, before, "Expected a mail.mail record to be created")

    def test_send_assignment_email_skips_when_disabled(self):
        """_send_assignment_email does nothing when config is False."""
        self._set_email_config(False)
        self.signoff.assigne_user_id = self.reviewer
        before = self.env['mail.mail'].sudo().search_count([])
        self.signoff._send_assignment_email(
            'crd_project_approval.email_template_assignment_in_review'
        )
        after = self.env['mail.mail'].sudo().search_count([])
        self.assertEqual(before, after, "Expected no mail.mail record when disabled")

    def test_action_submit_sends_email(self):
        """action_submit triggers email notification when config is True."""
        self._set_email_config(True)
        self.env['ir.config_parameter'].sudo().set_str(
            'crd_project_approval.auto_assign_user_id', str(self.reviewer.id)
        )
        before = self.env['mail.mail'].sudo().search_count([])
        self.signoff.action_submit()
        after = self.env['mail.mail'].sudo().search_count([])
        self.assertGreater(after, before, "action_submit should trigger email")

    def test_action_wait_for_approval_sends_email(self):
        """action_wait_for_approval triggers email notification when config is True."""
        self._set_email_config(True)
        self.signoff.action_submit()
        self.signoff.business_sponsor_ids = [(6, 0, [self.reviewer.id])]
        before = self.env['mail.mail'].sudo().search_count([])
        self.signoff.action_wait_for_approval()
        after = self.env['mail.mail'].sudo().search_count([])
        self.assertGreater(after, before, "action_wait_for_approval should trigger email")
