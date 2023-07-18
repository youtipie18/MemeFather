import random

import sqlalchemy.exc
import telebot
from telebot import types
import os
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


class Joke(Base):
    __tablename__ = "joke"
    joke_id = Column("joke_id", Integer, primary_key=True, autoincrement=True)
    content = Column("content", String, nullable=False)
    rating = Column("rating", Integer, nullable=False, default=0)

    def __repr__(self):
        return f"Joke №{self.id}: {self.content}"


class User(Base):
    __tablename__ = "user"
    user_id = Column("user_id", Integer, primary_key=True)
    admin_status = Column("is_admin", String, nullable=False, default="None")
    full_name = Column("full_name", String, nullable=False)

    def __init__(self, user_id, full_name):
        self.user_id = user_id
        self.full_name = full_name

    def __repr__(self):
        return f"User №{self.user_id}"


engine = create_engine("sqlite:///database.db")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
session = Session()

API_KEY = os.environ["API_KEY"]
bot = telebot.TeleBot(API_KEY)


def is_admin(uid, admin_type="all"):
    return session.query(User).filter(User.user_id == uid).one().admin_status in \
           ["Admin", "MAIN_ADMIN"] if admin_type == "all" else admin_type


def for_admin(func):
    def wrapper(*args):
        message = args[0]
        if type(message) == telebot.types.Message:
            if is_admin(message.from_user.id):
                func(message)
            else:
                bot.send_message(message.chat.id, "Ця команда тільки для адмінів.\n"
                                                  "Якщо ви хочете бути адміном, то натисніть /send_admin_request")
        else:
            raise ValueError(f"Invalid arg type. Got: {type(message)}, expected: {telebot.types.Message}")

    return wrapper


def for_main_admin(func):
    def wrapper(*args):
        message = args[0]
        if type(message) == telebot.types.Message:
            if is_admin(message.from_user.id, admin_type="MAIN_ADMIN"):
                func(message)
            else:
                bot.send_message(message.chat.id, "Ця команда тільки для головного адміна.\n"
                                                  "Зв'яжіться з іним головним адміном, щоб отримати права доступу.")
        else:
            raise ValueError(f"Invalid arg type. Got: {type(message)}, expected: {telebot.types.Message}")

    return wrapper


@bot.message_handler(commands=["start"])
def start(message):
    user = User(message.from_user.id, f"{message.from_user.first_name} {message.from_user.last_name}")
    if not session.query(User).filter(User.user_id == message.from_user.id).scalar():
        session.add(user)
        session.commit()
    else:
        print("User already registered. Updating their name")
        existing_user = session.query(User).filter(User.user_id == message.from_user.id)
        existing_user.full_name = user.full_name
        session.commit()
    msg = f"Вітаю {message.from_user.first_name}!\n" \
          f"Настав час справжніх жартів.\n" \
          f"Натисніть /next_joke щоб отримати випадковий жарт.\n" \
          f"{'Натисніть /add_joke щоб додати новий жарт(Тільки для адмінів).' if is_admin(message.from_user.id) else ''}\n" \
          f"{'Натисніть /show_requests щоб переглянути запити на адмін права.' if is_admin(message.from_user.id, admin_type='MAIN_ADMIN') else ''}\n" \
          f"{'Натисніть /show_admins щоб переглянути дійсних адмінів .' if is_admin(message.from_user.id, admin_type='MAIN_ADMIN') else ''}"
    bot.send_message(message.chat.id, f"{msg}")


@bot.message_handler(commands=["send_admin_request"])
def send_admin_request(message):
    try:
        user = session.query(User).filter(User.user_id == message.from_user.id).one()
        if user.admin_status == "Pending":
            bot.send_message(message.chat.id, "Ви вже надсилали запит, очікуйте згоди головного адміна😡")
        elif user.admin_status in ["Admin", "MAIN_ADMIN"]:
            bot.send_message(message.chat.id, "Ви вже маєте статус адміна!")
        else:
            user.admin_status = "Pending"
            session.commit()
            bot.send_message(message.chat.id,
                             "Запит надіслано! Коли головний адмін роздивиться вашу заявку та погодить її, ви зможете редагувати та видаляти жарти.")
    except sqlalchemy.orm.exc.NoResultFound:
        bot.send_message(message.chat.id, "Користувача не знайдено. Можливо ви не зареєстровані, натисніть /start")


@bot.message_handler(commands=["show_admins"])
@for_main_admin
def show_admins(message):
    admins = session.query(User).filter(
        sqlalchemy.and_(User.admin_status.in_(["MAIN_ADMIN", "Admin"]), User.user_id != message.from_user.id)).all()
    if admins:
        for admin in admins:
            delete_admin_markup = types.InlineKeyboardMarkup(row_width=1)
            delete_admin_markup.add(
                types.InlineKeyboardButton("Позбавити адмін-прав❌", callback_data=f"delete_admin*{admin.user_id}"))
            bot.send_message(message.chat.id,
                             f"Id:{admin.user_id}; Name: {admin.full_name}; {'MAIN_ADMIN' if admin.admin_status == 'MAIN_ADMIN' else ''}",
                             reply_markup=delete_admin_markup)
    else:
        bot.send_message(message.chat.id, "Адмінів поки немає💤")


@bot.callback_query_handler(func=lambda call: "delete_admin*" in call.data)
def delete_admin(call):
    try:
        admin_to_delete = session.query(User).filter(User.user_id == int(call.data.split("*")[-1])).one()
        admin_to_delete.admin_status = "None"
        session.commit()
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=types.InlineKeyboardMarkup())
        bot.send_message(call.message.chat.id, f"Користувача {admin_to_delete.full_name} позбавлено адмін-прав!")
    except sqlalchemy.exc.NoResultFound:
        bot.send_message(call.message.chat.id,
                         "Користувача не знайдено, можливо його прийняв уже інший головний адмін?")


@bot.message_handler(commands=["show_requests"])
@for_main_admin
def show_requests(message):
    requests = session.query(User).filter(User.admin_status == "Pending").all()
    if requests:
        for user in requests:
            status_markup = types.InlineKeyboardMarkup(row_width=1)
            accept_button = types.InlineKeyboardButton("Прийняти запит✅",
                                                       callback_data=f"admin_request_accept*{user.user_id}")
            reject_button = types.InlineKeyboardButton("Вдімовити запит❌",
                                                       callback_data=f"admin_request_reject*{user.user_id}")
            status_markup.add(accept_button, reject_button)
            bot.send_message(message.chat.id, f"Id:{user.user_id}; Name: {user.full_name}", reply_markup=status_markup)
    else:
        bot.send_message(message.chat.id, "На даний момент запитів немає💤")


@bot.callback_query_handler(func=lambda call: "admin_request_" in call.data)
def admin_request_callback(call):
    data = call.data.split("*")[0]
    try:
        user_to_change = session.query(User).filter(User.user_id == int(call.data.split("*")[-1])).one()
        if data == "admin_request_accept":
            user_to_change.admin_status = "Admin"
            bot.send_message(call.message.chat.id, f"Права адміна користувачу {user_to_change.full_name} видано!")
        elif data == "admin_request_reject":
            user_to_change.admin_status = "None"
            bot.send_message(call.message.chat.id, f"Права адміна користувачу {user_to_change.full_name} відмовлено!")
        session.commit()
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=types.InlineKeyboardMarkup())
    except sqlalchemy.exc.NoResultFound:
        bot.send_message(call.message.chat.id,
                         "Користувача не знайдено, можливо його прийняв уже інший головний адмін?")


@bot.message_handler(commands=["next_joke"])
def next_joke(message):
    if len(session.query(Joke).all()):
        joke = random.choices(session.query(Joke).all(),
                              cum_weights=[joke[0] for joke in session.query(Joke.joke_id).all()])[0]
        markup = types.InlineKeyboardMarkup(row_width=1)
        rate_button = types.InlineKeyboardButton("Оцінити жарт💯", callback_data=f"rate_joke*{joke.joke_id}")
        if is_admin(message.from_user.id):
            edit_button = types.InlineKeyboardButton("Редагувати жарт🛠", callback_data=f"edit_joke*{joke.joke_id}")
            delete_button = types.InlineKeyboardButton("Видалити жарт⚰", callback_data=f"delete_joke*{joke.joke_id}")
            markup.add(rate_button, edit_button, delete_button)
        else:
            markup.add(rate_button)
        bot.send_message(message.chat.id, f"Жарт №{joke.joke_id}\n" + joke.content, reply_markup=markup)
    else:
        bot.send_message(message.chat.id,
                         "На жаль жартів не існує, йди поплач або скажи адміну нехай додасть новий жарт!")


@bot.callback_query_handler(func=lambda call: "_joke*" in call.data)
def change_joke(call):
    data = call.data.split("*")[0]
    try:
        joke_to_edit = session.query(Joke).filter(Joke.joke_id == int(call.data.split("*")[-1])).one()
        if data == "rate_joke":
            rate_markup = types.InlineKeyboardMarkup(row_width=2)
            rate_positive_button = types.InlineKeyboardButton("+1",
                                                              callback_data=f"rate_positive*{joke_to_edit.joke_id}")
            rate_negative_button = types.InlineKeyboardButton("-1",
                                                              callback_data=f"rate_negative*{joke_to_edit.joke_id}")
            rate_markup.add(rate_positive_button, rate_negative_button)
            bot.send_message(call.message.chat.id, "Оцініть жарт:", reply_markup=rate_markup)
        elif data == "edit_joke" and is_admin(call.message.chat.id):
            bot.send_message(call.message.chat.id, "Введіть новий текст для цього жарту:")
            bot.register_next_step_handler(call.message, edit_content_joke, joke_to_edit)
        elif data == "delete_joke" and is_admin(call.message.chat.id):
            delete_joke(joke_to_edit)
            bot.send_message(call.message.chat.id, "Жарт успішно видалено!")
    except sqlalchemy.exc.NoResultFound:
        bot.send_message(call.message.chat.id,
                         "Жарту не знайдено. Можливо такий жарт було щойно видалено Вами або іншим адміном?")


@bot.callback_query_handler(func=lambda call: "rate_" in call.data)
def rate_joke(call):
    data = call.data.split("*")[0]
    try:
        joke_to_rate = session.query(Joke).filter(Joke.joke_id == int(call.data.split("*")[-1])).one()
        if data == "rate_positive":
            joke_to_rate.rating += 1
        elif data == "rate_negative":
            joke_to_rate.rating -= 1
        session.commit()
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=types.InlineKeyboardMarkup())
        bot.send_message(call.message.chat.id, "Оцінку успішно змінено!\n"
                                               "Жарти з меншною оцінкою будуть випадати Вам рідше")
    except sqlalchemy.exc.NoResultFound:
        bot.send_message(call.message.chat.id,
                         "Жарту не знайдено. Можливо такий жарт було щойно видалено Вами або іншим адміном?")


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
