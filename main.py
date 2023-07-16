import random

import telebot
import os
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


class Joke(Base):
    __tablename__ = "jokes"
    id = Column("id", Integer, primary_key=True, autoincrement=True)
    content = Column("content", String, nullable=False, unique=True)

    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return f"Joke №{self.id}: {self.content}"


engine = create_engine("sqlite:///database.db")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
session = Session()

API_KEY = os.environ["API_KEY"]
bot = telebot.TeleBot(API_KEY)

admin_id = ("1147111861",)


def is_admin(uid):
    if uid in admin_id:
        return True


@bot.message_handler(commands=["start"])
def start(message):
    message_to_send = f"Вітаю {message.from_user.first_name}!\n" \
                      f"Настав час справжніх жартів.\n" \
                      f"Натисніть /next_joke щоб отримати випадковий жарт.\n" \
                      f"Натисніть /rate_joke щоб оцінити жарт(Жарти з меншною оцінкою будуть випадати Вам рідше).\n" \
                      f"Команди тільки для адмінів:\n" \
                      f"Натисніть /add_joke щоб додати новий жарт.\n" \
                      f"Натисніть /edit_joke щоб редагувати жарт.\n" \
                      f"Натисніть /delete_joke щоб видалити жарт."
    bot.send_message(message.chat.id, f"{message_to_send}")


@bot.message_handler(commands=["next_joke"])
def next_joke(message):
    joke = random.choice(session.query(Joke).all())
    bot.send_message(message.chat.id, joke.content)


@bot.message_handler(commands=["add_joke"])
def add_joke(message):
    bot.send_message(message.chat.id, "Введіть ваш жарт:")
    bot.register_next_step_handler(message, add_joke_to_db)


def add_joke_to_db(message):
    joke = Joke(content=message.text)
    session.add(joke)
    session.commit()

    bot.reply_to(message, "Жарт успішно додано!")


bot.polling(none_stop=True)
