import unittest
from tools.calendar.google_calendar import GoogleCalendarTool
from scheduler.reminder import ReminderSystem
from agent.planner import Planner


class TestProductivityCapabilities(unittest.TestCase):
    """
    Verification of Tasks 161–170: Productivity & Personal Management.
    """

    def setUp(self):
        self.cal = GoogleCalendarTool()
        self.planner = Planner()
        self.reminders = ReminderSystem()

    def test_task_161_165_task_and_reminder_routing(self):
        """Tasks 161-165: Routing for reminders and calendar schedules."""
        prompt = self.planner.get_prompt("schedule a reminder for tomorrow")
        self.assertIn("calendar_create_event", prompt)
        self.assertIn("calendar_list_events", prompt)

    def test_task_162_reminder_manager(self):
        """Task 162: Reminder creation in local store."""
        msg = self.reminders.set_reminder(
            time_str="2026-11-22 10:00:00",
            message="Buy groceries",
        )
        self.assertTrue(msg.startswith("rem_"))
        all_rems = self.reminders.list_reminders()
        self.assertTrue(any(r["message"] == "Buy groceries" for r in all_rems))


if __name__ == "__main__":
    unittest.main()
