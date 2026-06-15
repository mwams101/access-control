from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.access.models import Blacklist

from . import services
from .models import CheckInEvent, VisitRequest

User = get_user_model()


def make_visit(host, **overrides):
    now = timezone.now()
    defaults = dict(
        full_name="Test Visitor",
        id_number="123456/10/1",
        phone="0977000000",
        email="visitor@example.com",
        host=host,
        purpose="Meeting",
        expected_start=now,
        expected_end=now + timedelta(hours=2),
    )
    defaults.update(overrides)
    return VisitRequest.objects.create(**defaults)


class PassWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", role="ADMIN", email="a@x.com")
        self.guard = User.objects.create_user("guard", role="SECURITY")
        self.host = User.objects.create_user("host", role="ADMIN", email="h@x.com",
                                             first_name="Host", last_name="Person")

    def test_approve_issues_valid_pass(self):
        visit = make_visit(self.host)
        access_pass = services.approve_visit(visit, self.admin)
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.APPROVED)
        result = services.verify_pass(access_pass.token)
        self.assertTrue(result.allowed)

    def test_tampered_token_is_rejected(self):
        visit = make_visit(self.host)
        access_pass = services.approve_visit(visit, self.admin)
        result = services.verify_pass(access_pass.token + "x")
        self.assertFalse(result.allowed)

    def test_expired_window_is_rejected(self):
        past = timezone.now() - timedelta(days=2)
        visit = make_visit(self.host, expected_start=past,
                           expected_end=past + timedelta(hours=1))
        access_pass = services.approve_visit(visit, self.admin)
        result = services.verify_pass(access_pass.token)
        self.assertFalse(result.allowed)
        self.assertIn("window", result.reason)

    def test_single_entry_pass_cannot_be_reused(self):
        visit = make_visit(self.host)
        access_pass = services.approve_visit(visit, self.admin)
        services.check_in(access_pass, self.guard)
        result = services.verify_pass(access_pass.token)
        self.assertFalse(result.allowed)
        self.assertIn("already", result.reason)

    def test_blacklisted_visitor_is_denied_with_event(self):
        Blacklist.objects.create(id_number="123456/10/1", reason="Test",
                                 added_by=self.admin)
        visit = make_visit(self.host)
        access_pass = services.approve_visit(visit, self.admin)
        result = services.verify_pass(access_pass.token, actor=self.guard)
        self.assertFalse(result.allowed)
        self.assertTrue(result.alert)
        self.assertTrue(
            CheckInEvent.objects.filter(pass_obj=access_pass,
                                        kind=CheckInEvent.Kind.DENIED).exists()
        )

    def test_check_in_and_out_lifecycle(self):
        visit = make_visit(self.host)
        access_pass = services.approve_visit(visit, self.admin)
        services.check_in(access_pass, self.guard, gate="Main Gate")
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.CHECKED_IN)
        services.check_out(access_pass, self.guard)
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.CHECKED_OUT)

    def test_walk_in_blacklist_blocked(self):
        Blacklist.objects.create(full_name="Bad Actor", reason="Test",
                                 added_by=self.admin)
        visit = make_visit(self.host, full_name="Bad Actor", status="PENDING")
        result = services.register_walk_in(visit, self.guard)
        self.assertFalse(result.allowed)
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.DENIED)
