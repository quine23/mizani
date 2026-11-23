from modules import categories, expenses
from modules.errors import NotFoundError, ValidationError
from tests.base import FinanceTestCase


class CategoryTests(FinanceTestCase):
    def test_default_categories_exist_for_everyone(self):
        names = {c.name for c in categories.list_categories(self.alice.user_id, "expense")}
        self.assertTrue({"Food", "Rent", "Transport"} <= names)
        self.assertIn("Salary", {c.name for c in categories.list_categories(self.bob.user_id, "income")})

    def test_custom_categories_are_private(self):
        mine = categories.add_category(self.alice.user_id, "Pet care", "expense")
        self.assertNotIn(mine.category_id, [c.category_id for c in categories.list_categories(self.bob.user_id)])
        with self.assertRaises(NotFoundError):
            categories.get_category(self.bob.user_id, mine.category_id)

    def test_duplicates_rejected_including_defaults(self):
        categories.add_category(self.alice.user_id, "Pet care", "expense")
        for name, kind in [("pet CARE", "expense"), ("food", "expense")]:
            with self.assertRaises(ValidationError):
                categories.add_category(self.alice.user_id, name, kind)
        categories.add_category(self.alice.user_id, "Pet care", "income")  # other type is fine

    def test_rename_and_delete_custom_only(self):
        mine = categories.add_category(self.alice.user_id, "Pet care", "expense")
        self.assertEqual(categories.rename_category(self.alice.user_id, mine.category_id, "Pets").name, "Pets")
        with self.assertRaises(ValidationError):
            categories.rename_category(self.alice.user_id, self.expense_cat, "Meals")
        with self.assertRaises(ValidationError):
            categories.delete_category(self.alice.user_id, self.expense_cat)
        categories.delete_category(self.alice.user_id, mine.category_id)

    def test_cannot_delete_category_in_use(self):
        mine = categories.add_category(self.alice.user_id, "Pet care", "expense")
        expenses.add_expense(self.alice.user_id, 100, "2026-11-01", mine.category_id)
        with self.assertRaises(ValidationError):
            categories.delete_category(self.alice.user_id, mine.category_id)

    def test_other_user_cannot_rename_or_delete(self):
        mine = categories.add_category(self.alice.user_id, "Pet care", "expense")
        with self.assertRaises(NotFoundError):
            categories.rename_category(self.bob.user_id, mine.category_id, "Hacked")
        with self.assertRaises(NotFoundError):
            categories.delete_category(self.bob.user_id, mine.category_id)
