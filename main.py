import random

import sqlalchemy.exc
import telebot
from telebot import types
import os
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


class Joke(Base):
    __tablename__ = "jokes"
    id = Column("id", Integer, primary_key=True, autoincrement=True)
    content = Column("content", String, nullable=False)
    rating = Column("rating", Integer, nullable=False)

    def __init__(self, content, rating=0):
        self.content = content
        self.rating = rating

    def __repr__(self):
        return f"Joke №{self.id}: {self.content}"


engine = create_engine("sqlite:///database.db")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
session = Session()

API_KEY = os.environ["API_KEY"]
bot = telebot.TeleBot(API_KEY)

admin_id = (1147111861,)


def is_admin(uid):
    if uid in admin_id:
        return True


def for_admin(func):
    def wrapper(*args):
        message = args[0]
        if type(message) == telebot.types.Message:
            if message.from_user.id in admin_id:
                func(message)
            else:
                bot.send_message(message.chat.id, "Ця команда тільки для адмінів.")
        else:
            raise ValueError(f"Invalid arg type. Got: {type(message)}, expected: {telebot.types.Message}")

    return wrapper


@bot.message_handler(commands=["start"])
def start(message):
    message_to_send = f"Вітаю {message.from_user.first_name}!\n" \
                      f"Настав час справжніх жартів.\n" \
                      f"Натисніть /next_joke щоб отримати випадковий жарт.\n" \
                      f"Натисніть /add_joke щоб додати новий жарт(Тільки для адмінів).\n"
    bot.send_message(message.chat.id, f"{message_to_send}")


@bot.message_handler(commands=["next_joke"])
def next_joke(message):
    if len(session.query(Joke).all()):
        joke = random.choices(session.query(Joke).all(), cum_weights=[joke[0] for joke in session.query(Joke.id).all()])[0]
        markup = types.InlineKeyboardMarkup(row_width=1)
        rate_button = types.InlineKeyboardButton("Оцінити жарт💯", callback_data=f"rate_joke*{joke.id}")
        edit_button = types.InlineKeyboardButton("Редагувати жарт🛠", callback_data=f"edit_joke*{joke.id}")
        delete_button = types.InlineKeyboardButton("Видалити жарт⚰", callback_data=f"delete_joke*{joke.id}")
        markup.add(rate_button, edit_button, delete_button)
        bot.send_message(message.chat.id, f"Жарт №{joke.id}\n" + joke.content, reply_markup=markup)
    else:
        bot.send_message(message.chat.id,
                         "На жаль жартів не існує, йди поплач або скажи адміну нехай додасть новий жарт!")


@bot.callback_query_handler(func=lambda call: True)
def change_joke(call):
    data = call.data.split("*")[0]
    try:
        joke_to_edit = session.query(Joke).filter(Joke.id == int(call.data.split("*")[-1])).one()
        if data == "rate_joke":
            bot.send_message(call.message.chat.id, "Введіть нову оцінку(Від 0 до 10):")
            bot.register_next_step_handler(call.message, rate_joke, joke_to_edit)
        elif data == "edit_joke":
            bot.send_message(call.message.chat.id, "Введіть новий текст для цього жарту:")
            bot.register_next_step_handler(call.message, edit_content_joke, joke_to_edit)
        elif data == "delete_joke":
            delete_joke(joke_to_edit)
            bot.send_message(call.message.chat.id, "Жарт успішно видалено!")
    except sqlalchemy.exc.NoResultFound:
        bot.send_message(call.message.chat.id,
                         "Жарту не знайдено. Можливо такий жарт було щойно видалено Вами або іншим адміном?")


def rate_joke(message, joke_to_rate):
    try:
        user_rating = int(message.text)
        if user_rating in range(0, 11):
            joke_to_rate.rating = user_rating
            session.commit()
            bot.send_message(message.chat.id, "Оцінку успішно змінено!\n"
                                              "Жарти з меншною оцінкою будуть випадати Вам рідше")
        else:
            bot.send_message(message.chat.id, "Оцінка повинна бути цілим числом від 0 до 10. Введіть оцінку знову:")
            bot.register_next_step_handler(message, rate_joke, joke_to_rate)
    except ValueError:
        bot.send_message(message.chat.id, "Оцінка повинна бути цілим числом від 0 до 10. Введіть оцінку знову:")
        bot.register_next_step_handler(message, rate_joke, joke_to_rate)


def edit_content_joke(message, joke_to_rate):
    joke_to_rate.content = message.text
    session.commit()
    bot.send_message(message.chat.id, "Жарт успішно змінено!")


def delete_joke(joke_to_edit):
    session.delete(joke_to_edit)
    session.commit()


@bot.message_handler(commands=["add_joke"])
@for_admin
def add_joke(message):
    bot.send_message(message.chat.id, "Введіть ваш жарт:")
    bot.register_next_step_handler(message, add_joke_to_db)


def add_joke_to_db(message):
    joke = Joke(content=message.text)
    session.add(joke)
    session.commit()

    bot.reply_to(message, "Жарт успішно додано!")


bot.polling(none_stop=True)
