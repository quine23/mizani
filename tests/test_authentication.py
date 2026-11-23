from database import db_connection as db
from modules import authentication
from modules.errors import AuthenticationError, ValidationError
from tests.base import FinanceTestCase


class AuthenticationTests(FinanceTestCase):
    def test_register_and_login(self):
        user = authentication.login_user("alice@example.com", "Passw0rd1")
        self.assertEqual(user.user_id, self.alice.user_id)
        self.assertEqual(user.first_name, "Alice")

    def test_email_is_case_insensitive(self):
        self.assertEqual(authentication.login_user("ALICE@Example.com", "Passw0rd1").email, "alice@example.com")

    def test_duplicate_email_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_user("Other Alice", "Alice@Example.com")
        self.assertIn("email", ctx.exception.errors)

    def test_wrong_password_and_unknown_email_give_same_message(self):
        with self.assertRaises(AuthenticationError) as a:
            authentication.login_user("alice@example.com", "wrong-pass1")
        with self.assertRaises(AuthenticationError) as b:
            authentication.login_user("nobody@example.com", "Passw0rd1")
        self.assertEqual(str(a.exception), str(b.exception))

    def test_password_is_stored_as_hash(self):
        row = db.query_one("SELECT password_hash FROM users WHERE email = ?", ("alice@example.com",))
        self.assertNotIn("Passw0rd1", row["password_hash"])
        self.assertTrue(row["password_hash"].startswith("pbkdf2:"))

    def test_user_object_does_not_expose_hash(self):
        self.assertNotIn("pbkdf2", repr(self.alice))
        self.assertFalse(hasattr(self.alice, "password_hash"))

    def test_registration_validation(self):
        bad_inputs = [
            ("", "a@b.com", "Passw0rd1", "Passw0rd1", "full_name"),
            ("Jo Doe", "not-an-email", "Passw0rd1", "Passw0rd1", "email"),
            ("Jo Doe", "jo@b.com", "short1", "short1", "password"),
            ("Jo Doe", "jo@b.com", "onlyletters", "onlyletters", "password"),
            ("Jo Doe", "jo@b.com", "Passw0rd1", "Different1", "confirm_password"),
        ]
        for name, email, pw, confirm, field in bad_inputs:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as ctx:
                    authentication.register_user(name, email, pw, confirm)
                self.assertIn(field, ctx.exception.errors)
