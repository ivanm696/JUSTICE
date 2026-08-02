# Правильная ссылка на CI/CD badge
[![Bot CI/CD Workflow](https://github.com/ivanm696/JUSTICE/actions/workflows/deploy.yml/badge.svg)](https://github.com/ivanm696/JUSTICE/actions/workflows/deploy.yml)

import asyncio
import json
import math
import os
import re
from enum import Enum
import io

import aiogram
import google.generativeai as genai
import requests
from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from bs4 import BeautifulSoup

from funcs_for_resp import *
import generate
from config import Config
from aiohttp import ClientSession
import aiohttp
from ai import gemini
from db import get_db, create_tables
from db.user import User
from db.api_key import APIKey
from db.prompt import Prompt
from utils.prompts import add_or_update_prompt

create_tables()

token = Config.BOT_TOKEN
bot = Bot(token=token)
dp = Dispatcher()

creator = Config.CREATOR
prompts_channel = Config.PROMPTS_CHANNEL
log_chat = Config.LOG_CHAT
support_chat = Config.SUPPORT_CHAT
main_chat = Config.MAIN_CHAT

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

class MessageToAdmin(StatesGroup):
    text_message = State()

class Permissions(str, Enum):
    CREATE_PROMPTS = 'create_prompts'
    BAN_USERS = 'ban_users'
    ADMIN_USERS = 'admin_users'
    VIEW_OTHER = 'view_other'
    BOT_CONTROL = 'bot_control'

def find_draw_strings(text):
    draw_strings = re.findall(r'{{{(.*?)}}}', text, re.DOTALL)
    new_draw_strings = []
    for string in draw_strings:
        escaped_string = re.escape(string)
        text = re.sub(escaped_string, '', text, flags=re.DOTALL)
        text = re.sub(r'{{{', '', text, flags=re.DOTALL)
        text = re.sub(r'}}}', '', text, flags=re.DOTALL)
        string = re.sub(r'\n', '', string)
        string = re.sub(r'%', '', string)
        new_draw_strings.append(string)
    return new_draw_strings, text

def find_prompt(text):
    data = text.replace('/addprompt ', '').replace('/addprompt@neuro_gemini_bot ', '')
    parts = data.split('|', maxsplit=3)
    if len(parts) < 4:
        raise ValueError("Неверный формат команды. Нужно: /addprompt команда|название|описание|промпт")
    return parts[0], parts[1], parts[2], parts[3]

def is_banned(id):
    with get_db() as db:
        user = db.get(User, id)
        return user.banned if user else False

def is_admin(id):
    with get_db() as db:
        user = db.get(User, id)
        return user.admin if user else False

def get_article(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    main_content = soup.find('article', class_='tl_article_content')
    if not main_content:
        return "Статья не найдена."
    main_text = ''
    for element in main_content.find_all(['p']):
        main_text += element.get_text() + '\n'
    return main_text

def read_telegraph(text):
    pattern = r'(?:https:\/\/)?telegra\.ph\/[a-zA-Z0-9_-]+'
    return re.sub(pattern, lambda m: get_article(m.group(0)), text)

def sets_msg(id):
    with get_db() as db:
        user = db.query(User).filter_by(id=id).first()
        sets = json.loads(user.settings) if user and user.settings else {
            "reset": False, "pictures_in_dialog": False, "pictures_count": 1, "imageai": "SD"
        }
    reset_status = "включено" if sets.get("reset") else "выключено"
    pictures_status = "включено" if sets.get("pictures_in_dialog") else "выключено"
    msg = (f'Настройки:\n\n'
           f'Кнопки сброса диалога: {reset_status}\n'
           f'Картинки в диалоге: {pictures_status}\n'
           f'Количество картинок: {sets.get("pictures_count",1)}\n'
           f'Нейросеть для генерации картинок в диалоге: {sets.get("imageai","SD")}')
    # клавиатура оставлена как в оригинале
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text='Кнопки сброса диалога:', callback_data='reset')],
        [types.InlineKeyboardButton(text='✅', callback_data='reset_on'),
         types.InlineKeyboardButton(text='❎', callback_data='reset_off')],
        [types.InlineKeyboardButton(text='Генерация картинок в диалоге:', callback_data='pictures_in_dialog')],
        [types.InlineKeyboardButton(text='✅', callback_data='pictures_on'),
         types.InlineKeyboardButton(text='❎', callback_data='pictures_off')],
        [types.InlineKeyboardButton(text='Количество картинок в /sd:', callback_data='pictures_count')],
        [types.InlineKeyboardButton(text='1️⃣', callback_data='pictures_count_1'),
         types.InlineKeyboardButton(text='2️⃣', callback_data='pictures_count_2'),
         types.InlineKeyboardButton(text='3️⃣', callback_data='pictures_count_3'),
         types.InlineKeyboardButton(text='4️⃣', callback_data='pictures_count_4'),
         types.InlineKeyboardButton(text='5️⃣', callback_data='pictures_count_5')],
        [types.InlineKeyboardButton(text='Нейросеть для генерации картинок в диалоге:', callback_data='imageai')],
        [types.InlineKeyboardButton(text='SD', callback_data='imageai_sd'),
         types.InlineKeyboardButton(text='Flux', callback_data='imageai_flux')]
    ])
    return msg, markup

# исправленный test
@dp.message(Command(commands=['test']))
async def test(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
        return
    with get_db() as db:
        keys = db.query(APIKey).all()
    for key in keys:
        try:
            response = await gemini.gemini_gen('Привет!', key.key)
            await message.reply(response[0])
            return
        except Exception:
            continue
    await message.reply('Ключи неактивны или закончился лимит.')

# исправленный addadmin
@dp.message(Command(commands=['addadmin']))
async def addadmin(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
        return
    if not message.reply_to_message:
        await message.reply("Эта команда должна быть вызвана в ответ на сообщение.")
        return
    data = message.text.replace('/addadmin ', '').replace('/addadmin@neuro_gemini_bot ', '')
    with get_db() as db:
        reply_user = db.query(User).filter(User.id==message.reply_to_message.from_user.id).first()
        prompt = db.query(Prompt).filter_by(command=data).first()
        if not prompt:
            await message.reply("Такого промпта нет.")
            return
        if message.from_user.id == creator or message.from_user.id == prompt.author:
            if reply_user and reply_user.admin:
                admins = json.loads(prompt.admins)
                if message.reply_to_message.from_user.id not in admins:
                    admins.append(message.reply_to_message.from_user.id)
                    prompt.admins = json.dumps(admins)
                    db.commit()
                await message.reply(f'Админ к /{data} добавлен.')
            else:
                await message.reply('Целевой пользователь не админ.')
        else:
            await message.reply('Ты не админ.')

# исправленный deladmin
@dp.message(Command(commands=['deladmin']))
async def deladmin(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
        return
    if not message.reply_to_message:
        await message.reply("Эта команда должна быть вызвана в ответ на сообщение.")
        return
    data = message.text.replace('/deladmin ', '').replace('/deladmin@neuro_gemini_bot ', '')
    with get_db() as db:
        prompt = db.query(Prompt).filter_by(command=data).first()
        if not prompt     
