"""Telegram entertainment bot with SQLite points and optional local photos."""

import math
import os
import random
import sqlite3
import time
from collections import deque
from pathlib import Path

import telebot
from telebot import types

BASE_DIR = Path(__file__).resolve().parent


class PointsStore:
    def __init__(self, path):
        self.path = str(path)
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS users '
                         '(user_id INTEGER PRIMARY KEY, points INTEGER NOT NULL DEFAULT 0)')
            conn.execute('CREATE TABLE IF NOT EXISTS promo_users (user_id INTEGER PRIMARY KEY)')

    def balance(self, user_id):
        with sqlite3.connect(self.path) as conn:
            row = conn.execute('SELECT points FROM users WHERE user_id = ?', (user_id,)).fetchone()
            return row[0] if row else 0

    def add(self, user_id, amount):
        with sqlite3.connect(self.path) as conn:
            conn.execute('INSERT OR IGNORE INTO users VALUES (?, 0)', (user_id,))
            conn.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (amount, user_id))

    def redeem_promo(self, user_id):
        # Award points and record redemption together in one transaction.
        with sqlite3.connect(self.path) as conn:
            result = conn.execute('INSERT OR IGNORE INTO promo_users VALUES (?)', (user_id,))
            if result.rowcount == 0:
                return False
            conn.execute('INSERT OR IGNORE INTO users VALUES (?, 0)', (user_id,))
            conn.execute('UPDATE users SET points = points + 20 WHERE user_id = ?', (user_id,))
            return True


class RollLimiter:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.rolls = {}

    def remaining(self, user_id):
        now = self.clock()
        rolls = self.rolls.setdefault(user_id, deque())
        while rolls and now - rolls[0] >= 60:
            rolls.popleft()
        return max(1, math.ceil(60 - (now - rolls[0]))) if len(rolls) >= 3 else 0

    def record(self, user_id):
        self.rolls.setdefault(user_id, deque()).append(self.clock())


def points_word(points):
    if 11 <= points % 100 <= 14:
        return 'балів'
    if points % 10 == 1:
        return 'бал'
    if 2 <= points % 10 <= 4:
        return 'бали'
    return 'балів'


def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('🌴Розваги', '🧮Лічильник')
    keyboard.row('🎮Ігри', 'ℹ️Про бот')
    return keyboard


def games_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('🎲Кубік', '🖼️Фото', '⚽Футбол')
    keyboard.row('◀️Назад')
    return keyboard


def create_bot(token, database_path=None, photos_path=None):
    # Serial handlers avoid overlapping game requests; each DB operation owns its connection.
    bot = telebot.TeleBot(token, threaded=False)
    store = PointsStore(database_path if database_path is not None else BASE_DIR / 'users.db')
    photos = Path(photos_path) if photos_path is not None else BASE_DIR / 'photos'
    limiter = RollLimiter()

    @bot.message_handler(commands=['start', 'help'])
    def start(message):
        bot.send_message(message.chat.id, 'Привіт! Обери, що тобі потрібно.',
                         reply_markup=main_keyboard())

    @bot.message_handler(content_types=['text'])
    def handle_message(message):
        text = (message.text or '').strip()
        user_id = message.from_user.id
        chat_id = message.chat.id

        if text == '🌴Розваги':
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(types.InlineKeyboardButton('YouTube', url='https://www.youtube.com/'))
            keyboard.row(types.InlineKeyboardButton('Аніме англійською', url='https://zoro.to/home'),
                         types.InlineKeyboardButton('Манґа англійською', url='https://mangareader.to/home'))
            keyboard.row(types.InlineKeyboardButton('Mangalib', url='https://mangalib.me/?section=home-updates'),
                         types.InlineKeyboardButton('Jut.su', url='https://jut.su/anime/'))
            bot.send_message(chat_id, 'Відпочивай!', reply_markup=keyboard)
        elif text == 'ℹ️Про бот':
            bot.send_message(chat_id, 'Навчальний бот: ігри, бали та випадкові фото.')
        elif text == '🧮Лічильник':
            points = store.balance(user_id)
            bot.send_message(chat_id, f'У вас {points} {points_word(points)}!')
        elif text == '🎮Ігри':
            bot.send_message(chat_id, 'У що зіграєш?', reply_markup=games_keyboard())
        elif text == '◀️Назад':
            start(message)
        elif text.lower() == 'промік':
            reply = 'Вам додано 20 балів' if store.redeem_promo(user_id) else 'Ви вже використали цей промокод'
            bot.send_message(chat_id, reply)
        elif text == '🎲Кубік':
            remaining = limiter.remaining(user_id)
            if remaining:
                bot.send_message(chat_id, f'Зачекайте {remaining} секунд. Ліміт: 3 кидки за 60 секунд.')
                return
            result = bot.send_dice(chat_id)
            limiter.record(user_id)
            value = result.dice.value
            store.add(user_id, value)
            bot.send_message(chat_id, f'Вам додано {value} {points_word(value)}!')
        elif text == '🖼️Фото':
            choices = sorted(p for p in photos.iterdir()
                             if p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png'}) if photos.is_dir() else []
            if not choices:
                bot.send_message(chat_id, 'Фото поки немає. Додайте JPG або PNG у папку photos.')
                return
            photo = random.choice(choices)
            with photo.open('rb') as image:
                bot.send_photo(chat_id, image)
            if photo.name == '2.jpg':
                store.add(user_id, 10)
                bot.send_message(chat_id, 'Вам додано 10 балів')
        elif text == '⚽Футбол':
            bot.send_message(chat_id, 'Футбол поки недоступний.')
        else:
            bot.send_message(chat_id, 'Оберіть дію на клавіатурі або введіть /start.',
                             reply_markup=main_keyboard())

    @bot.message_handler(content_types=['photo', 'sticker', 'document', 'video', 'voice',
                                        'audio', 'animation', 'location', 'contact', 'dice'])
    def handle_other(message):
        bot.send_message(message.chat.id, 'Скористайтеся кнопками меню або введіть /start.')

    return bot


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    if not token or token == 'YOUR_BOT_TOKEN':
        raise SystemExit('Set TELEGRAM_BOT_TOKEN to your bot token before starting.')
    bot = create_bot(token)
    print('Bot started. Press Ctrl+C to stop.')
    bot.infinity_polling(allowed_updates=['message'])


if __name__ == '__main__':
    main()
