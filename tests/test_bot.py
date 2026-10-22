import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from telebot import types
from main import PointsStore, RollLimiter, create_bot, points_word


class StorageTests(unittest.TestCase):
    def test_new_user_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'users.db'
            store = PointsStore(path)
            self.assertEqual(store.balance(123), 0)
            store.add(123, 6)
            self.assertEqual(PointsStore(path).balance(123), 6)
            self.assertEqual(store.balance(456), 0)

    def test_promo_only_once_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'users.db'
            store = PointsStore(path)
            self.assertTrue(store.redeem_promo(123))
            self.assertFalse(PointsStore(path).redeem_promo(123))
            self.assertEqual(store.balance(123), 20)
            self.assertTrue(store.redeem_promo(456))

    def test_sliding_limit_and_user_isolation(self):
        now = [0]
        limiter = RollLimiter(lambda: now[0])
        for second in [0, 10, 20]:
            now[0] = second
            self.assertEqual(limiter.remaining(123), 0)
            limiter.record(123)
        self.assertEqual(limiter.remaining(123), 40)
        self.assertEqual(limiter.remaining(456), 0)
        now[0] = 60
        self.assertEqual(limiter.remaining(123), 0)
        limiter.record(123)
        self.assertEqual(limiter.remaining(123), 10)

    def test_points_grammar(self):
        for value, word in [(0,'балів'), (1,'бал'), (4,'бали'), (9,'балів'),
                            (11,'балів'), (14,'балів'), (21,'бал'), (24,'бали'), (111,'балів')]:
            with self.subTest(value=value):
                self.assertEqual(points_word(value), word)


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / 'users.db'
        # This token is a deliberately fake value, never used for a request.
        self.bot = create_bot('123:TEST', self.database, self.root / 'photos')
        self.bot.send_message = Mock()
        self.bot.send_photo = Mock()
        self.bot.send_dice = Mock(return_value=SimpleNamespace(dice=SimpleNamespace(value=6)))

    def send(self, text=None, content_type='text', user_id=123):
        payload = {'message_id':1, 'date':0,
                   'chat':{'id':user_id, 'type':'private'},
                   'from':{'id':user_id, 'is_bot':False, 'first_name':'Test'}}
        if content_type == 'text':
            payload['text'] = text
        else:
            payload['sticker'] = {'file_id':'test', 'file_unique_id':'test', 'type':'regular',
                                  'width':1, 'height':1, 'is_animated':False, 'is_video':False}
        self.bot.process_new_messages([types.Message.de_json(payload)])

    def test_start_and_counter_for_new_user(self):
        self.send('/start')
        self.assertIn('reply_markup', self.bot.send_message.call_args.kwargs)
        self.send('🧮Лічильник')
        self.assertIn('0 балів', self.bot.send_message.call_args.args[1])

    def test_dice_limit(self):
        for _ in range(4):
            self.send('🎲Кубік')
        self.assertEqual(self.bot.send_dice.call_count, 3)
        self.assertEqual(PointsStore(self.database).balance(123), 18)
        self.assertIn('Зачекайте', self.bot.send_message.call_args.args[1])

    def test_promo_through_handler(self):
        self.send('промік')
        self.send('ПРОМІК')
        self.assertEqual(PointsStore(self.database).balance(123), 20)

    def test_missing_and_empty_photos(self):
        self.send('🖼️Фото')
        self.assertIn('Фото поки немає', self.bot.send_message.call_args.args[1])
        (self.root / 'photos').mkdir()
        (self.root / 'photos' / 'README.md').write_text('Not an image')
        self.send('🖼️Фото')
        self.bot.send_photo.assert_not_called()

    def test_photo_bonus(self):
        (self.root / 'photos').mkdir()
        # Network is mocked, so image decoding is not part of this test.
        (self.root / 'photos' / '2.jpg').write_bytes(b'test image')
        self.send('🖼️Фото')
        self.bot.send_photo.assert_called_once()
        self.assertEqual(PointsStore(self.database).balance(123), 10)
        self.assertTrue(self.bot.send_photo.call_args.args[1].closed)

    def test_menus_unknown_input_and_restart(self):
        for text in ['🎮Ігри', '◀️Назад', 'ℹ️Про бот', '🌴Розваги', '⚽Футбол', 'unknown', '/start']:
            with self.subTest(text=text):
                self.send(text)
                self.assertTrue(self.bot.send_message.called)
                self.bot.send_message.reset_mock()
        self.send(content_type='sticker')
        self.assertTrue(self.bot.send_message.called)


if __name__ == '__main__':
    unittest.main()
