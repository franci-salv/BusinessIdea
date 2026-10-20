import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
import main_bot as bot


class ArcadeNamesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = bot.UserDB(os.path.join(self.tmp.name, "users.db"))
        self.db.add_user(1, "private_telegram_handle")
        self.db.add_user(2, "another_private_handle")
        bot.pending_arcade_name.clear()
        self.addCleanup(bot.pending_arcade_name.clear)
        self.db_patch = patch.object(bot, "user_db", self.db, create=True)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_signup_prompts_and_normalizes_letters(self):
        with patch.object(bot, "send_message") as send:
            bot.handle_start(1, 1, "private_telegram_handle")
            self.assertIn(1, bot.pending_arcade_name)
            bot.handle_arcade_name_input(1, 1, " ace ")
        self.assertEqual(self.db.get_arcade_name(1), "ACE")
        self.assertNotIn(1, bot.pending_arcade_name)
        self.assertNotIn("private_telegram_handle", str(send.call_args_list))

    def test_rejects_invalid_tags(self):
        with patch.object(bot, "send_message"):
            for tag in ("A1B", "AB", "ABCD", "<A>", "éab"):
                bot.handle_arcade_name_input(1, 1, tag)
                self.assertIsNone(self.db.get_arcade_name(1))

    def test_blocked_tags_rejected_by_handler_and_database(self):
        bot.pending_arcade_name.add(1)
        for tag in bot.BLOCKED_ARCADE_NAMES:
            with self.subTest(tag=tag), patch.object(bot, "send_message") as send:
                candidate = f" {tag.lower()} "
                self.assertFalse(self.db.set_arcade_name(1, candidate))
                bot.handle_arcade_name_input(1, 1, candidate)
                self.assertIsNone(self.db.get_arcade_name(1))
                self.assertIn(1, bot.pending_arcade_name)
                self.assertNotIn("✅", str(send.call_args_list))

    def test_rejected_change_preserves_current_tag(self):
        self.assertTrue(self.db.set_arcade_name(1, "ACE"))
        with patch.object(bot, "send_message") as send:
            bot.handle_arcade_name_input(1, 1, "aSs")
        self.assertIn("isn't allowed", send.call_args.args[1])
        self.assertEqual(self.db.get_arcade_name(1), "ACE")

    def test_ascii_only_and_safe_tags(self):
        for tag in ("aſs", "ßa", "ＡＣＥ", "F A G", "F4G"):
            with self.subTest(tag=tag):
                self.assertFalse(self.db.set_arcade_name(1, tag))
                with patch.object(bot, "send_message"):
                    bot.handle_arcade_name_input(1, 1, tag)
                self.assertIsNone(self.db.get_arcade_name(1))
        for tag in ("ACE", "MAX", "ZAP", "CAT", "PIC"):
            with self.subTest(tag=tag):
                self.assertTrue(self.db.set_arcade_name(1, tag))

    def test_startup_retires_existing_blocked_tags_and_preserves_scores(self):
        self.db.set_arcade_name(2, "ACE")
        self.db.record_answer(1, "today", 0, "answer", True)
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute("UPDATE users SET arcade_name = ' aSs ' WHERE user_id = 1")
        self.db.init_db()
        self.db.init_db()  # Safe to repeat on each restart.
        self.assertIsNone(self.db.get_arcade_name(1))
        self.assertEqual(self.db.get_arcade_name(2), "ACE")
        self.assertEqual(self.db.get_today_leaderboard("today")[0][1:3], ("???", 1))
        with patch.object(bot, "send_message"):
            bot.handle_start(1, 1, "private_telegram_handle")
        self.assertIn(1, bot.pending_arcade_name)

    def test_final_answer_sends_full_menu_after_completion(self):
        quiz = {"date": "today", "questions": [
            {"question": "Test?", "options": ["Yes", "No"], "correct_answer": "Yes"}
        ]}
        self.addCleanup(bot.processed_polls.clear)
        self.addCleanup(bot.poll_question_map.clear)
        for answer in (0, 1):
            with self.subTest(answer=answer):
                self.db.set_user_progress(1, 0, "today")
                bot.poll_question_map[(1, f"final-{answer}")] = 0
                with patch.object(bot, "load_quiz", return_value=quiz), patch.object(bot.time, "sleep"), patch.object(bot, "send_message") as send, patch.object(bot, "send_poll") as poll:
                    bot.handle_poll_answer(1, f"final-{answer}", answer)
                self.assertIn("completed all 1 questions", send.call_args_list[-2].args[1])
                menu = send.call_args_list[-1]
                self.assertEqual(menu.args[0], 1)
                self.assertIn("What would you like to do next?", menu.args[1])
                actions = {button["callback_data"] for row in menu.kwargs["reply_markup"]["inline_keyboard"] for button in row}
                self.assertEqual(actions, {"stats", "leaderboard", "start_quiz", "change_tag", "unsubscribe"})
                poll.assert_not_called()

    def test_duplicate_claims_are_atomic(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda uid: self.db.set_arcade_name(uid, "ACE"), (1, 2)))
        self.assertEqual(sorted(results), [False, True])

    def test_failed_save_keeps_prompt_pending(self):
        bot.pending_arcade_name.add(1)
        with patch.object(self.db, "set_arcade_name", return_value=False), patch.object(bot, "send_message") as send:
            bot.handle_arcade_name_input(1, 1, "ACE")
        self.assertIn(1, bot.pending_arcade_name)
        self.assertNotIn("✅", str(send.call_args_list))

    def test_leaderboard_uses_tags_and_private_fallback(self):
        self.assertTrue(self.db.set_arcade_name(1, "ACE"))
        for uid in (1, 2):
            self.db.record_answer(uid, "today", 0, "answer", True)
        with patch.object(bot, "load_quiz", return_value={"date": "today", "questions": [{}]}), patch.object(bot, "send_message") as send:
            bot.show_leaderboard(1, 1)
        output = str(send.call_args_list)
        self.assertIn("ACE", output)
        self.assertIn("???", output)
        self.assertNotIn("private_handle", output)
        self.assertNotIn("private_telegram_handle", output)
        self.assertTrue(self.db.set_arcade_name(1, "ZAP"))
        self.assertEqual(self.db.get_today_leaderboard("today")[0][1], "ZAP")


if __name__ == "__main__":
    unittest.main()
