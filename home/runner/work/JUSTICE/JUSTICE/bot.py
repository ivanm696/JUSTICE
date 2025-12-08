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
safety_settings = Config.SAFETY_SETTINGS
main_chat = Config.MAIN_CHAT

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
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


def find_strings():  # TODO: handle other strings but a `find_draw_strings()`
    pass


def find_prompt(text):
    data = text.replace('/addprompt ', '')
    data = data.replace('/addprompt@neuro_gemini_bot ', '')
    data = data.split('|', maxsplit=3)
    command = data[0]
    name = data[1]
    description = data[2]
    prompt = data[3]
    return command, name, description, prompt


def is_banned(id):
    with get_db() as db:
        user = db.get(User, id)
        if user:
            return user.banned


def is_admin(id):
    with get_db() as db:
        user = db.get(User, id)
        if user:
            return user.admin


def replace_links(match):
    url = match.group(0)
    return get_article(url)


def get_article(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    main_content = soup.find('article', class_='tl_article_content')
    main_text = ''
    for element in main_content.find_all(['p']):
        main_text += element.get_text() + '\n'
    return main_text


def read_telegraph(text):
    pattern = r'(?:https:\/\/)?telegra\.ph\/[a-zA-Z0-9_-]+'
    return re.sub(pattern, replace_links, text)



def is_user(id):
    with get_db() as db:
        user = db.query(User).filter_by(id=id).first()
        if user:
            return True
        else:
            return False


def sets_msg(id):
    with get_db() as db:
        user = db.query(User).filter_by(id=id).first()
        sets = json.loads(user.settings)
    reset = types.InlineKeyboardButton(text='Кнопки сброса диалога:', callback_data='reset')
    reset_on = types.InlineKeyboardButton(text='✅', callback_data='reset_on')
    reset_off = types.InlineKeyboardButton(text='❎', callback_data='reset_off')
    pictures_in_chat = types.InlineKeyboardButton(text='Генерация картинок в диалоге:',
                                                  callback_data='pictures_in_dialog')
    pictures_on = types.InlineKeyboardButton(text='✅', callback_data='pictures_on')
    pictures_off = types.InlineKeyboardButton(text='❎', callback_data='pictures_off')
    pictures_count = types.InlineKeyboardButton(text='Количество картинок в /sd:', callback_data='pictures_count')
    pictures_count_1 = types.InlineKeyboardButton(text='1️⃣', callback_data='pictures_count_1')
    pictures_count_2 = types.InlineKeyboardButton(text='2️⃣', callback_data='pictures_count_2')
    pictures_count_3 = types.InlineKeyboardButton(text='3️⃣', callback_data='pictures_count_3')
    pictures_count_4 = types.InlineKeyboardButton(text='4️⃣', callback_data='pictures_count_4')
    pictures_count_5 = types.InlineKeyboardButton(text='5️⃣', callback_data='pictures_count_5')
    imageai = types.InlineKeyboardButton(text='Нейросеть для генерации картинок в диалоге:', callback_data='imageai')
    imageai_sd = types.InlineKeyboardButton(text='SD', callback_data='imageai_sd')
    imageai_flux = types.InlineKeyboardButton(text='Flux', callback_data='imageai_flux')
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [reset],
            [reset_on, reset_off],
            [pictures_in_chat],
            [pictures_on, pictures_off],
            [pictures_count],
            [pictures_count_1, pictures_count_2, pictures_count_3, pictures_count_4, pictures_count_5],
            [imageai],
            [imageai_sd, imageai_flux]
        ]
    )
    if sets["reset"]:
        reset_status = "включено"
    else:
        reset_status = "выключено"
    if sets["pictures_in_dialog"]:
        pictures_status = "включено"
    else:
        pictures_status = "выключено"
    msg = (f'Настройки:\n\n'
           f'Кнопки сброса диалога: {reset_status}\n'
           f'Картинки в диалоге: {pictures_status}\n'
           f'Количество картинок: {sets["pictures_count"]}\n'
           f'Нейросеть для генерации картинок в диалоге: {sets["imageai"]}')
    return msg, markup


def edit_sets(id, setting_name, value):
    with get_db() as db:
        user = db.query(User).filter_by(id=id).first()
        sets = json.loads(user.settings)
        sets[setting_name] = value
        user.settings = json.dumps(sets)
        db.commit()


def split_message(text):
    max_len = 4096
    if len(text) <= max_len:
        return [text]
    
    messages = []
    current_message = ''
    words = text.split()
    
    for word in words:
        if len(current_message) + len(word) + 1 <= max_len:
            if current_message:
                current_message += ' '
            current_message += word
        else:
            # Если текущее слово превышает max_len, разбиваем его на части
            if len(word) > max_len:
                for i in range(0, len(word), max_len):
                    part = word[i:i + max_len]
                    if current_message:
                        messages.append(current_message)
                        current_message = part
                    else:
                        messages.append(part)
            else:
                messages.append(current_message)
                current_message = word
    
    if current_message:
        messages.append(current_message)
    
    return messages


async def prompt_string(command):
    with get_db() as db:
        prompt = db.query(Prompt).filter_by(command=command).first()
        author = db.query(User).filter_by(id=prompt.author).first()
        prompt_admins = []
        for prompt_admin in json.loads(prompt.admins):
            prompt_admins.append(f'{db.query(User).filter_by(id=prompt_admin).first().get_object().mention_markdown()} (`{prompt_admin}`)')
    return (f'`/addprompt {prompt.command}|{prompt.name}|{prompt.description}|{prompt.content}`\n\n'
        f'Создатель: {author.get_object().mention_markdown()} (`{prompt.author}`)\n'
        f'Админы: {', '.join(prompt_admins) if prompt_admins else 'отсутствуют'}')


@dp.message(Command(commands=['start']))
async def start(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        with get_db() as db:
            user_id = message.from_user.id

            existing_user = db.query(User).filter(User.id == user_id).first()

            if existing_user:
                existing_user.set_object(message.from_user)
            else:
                new_user = User(id=user_id)
                new_user.set_object(message.from_user)
                db.add(new_user)

            db.commit()
        await message.reply('Привет!\nПомощь - /help')


@dp.message(Command(commands=['online']))
async def online(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        try:
            prompt = message.text.replace('/online ', '')
            prompt = prompt.replace('/online@neuro_gemini_bot ', '')
            response = await generate.onlinegen(prompt)
            await message.reply(response)
        except Exception as e:
            await message.reply(f'Ошибка: {e}')


@dp.message(Command(commands=['sd']))
async def sd(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        prompt = message.text.replace('/sd ', '')
        prompt = prompt.replace('/sd@neuro_gemini_bot ', '')
        wait_msg = await message.reply('Рисую...')
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=message.from_user.id).first()
                sets = json.loads(user.settings)
            photos = []
            for i in range(sets['pictures_count']):
                request = await generate.sdgen(prompt)
                photos.append(types.InputMediaPhoto(media=request))
            if len(photos) == 1:
                await message.reply_photo(photos[0].media)
            else:
                await message.reply_media_group(photos)
            await wait_msg.delete()
        except Exception as e:
            await message.reply(f'Ошибка при генерации изображения: {e}')
            await wait_msg.delete()


@dp.message(Command(commands=['flux']))
async def flux(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        prompt = message.text.replace('/flux ', '')
        prompt = prompt.replace('/flux@neuro_gemini_bot ', '')
        wait_msg = await message.reply('Рисую...')
        try:
            with get_db() as db:
                user = db.query(User).filter_by(id=message.from_user.id).first()
                sets = json.loads(user.settings)
            photos = []
            for i in range(sets['pictures_count']):
                request = await generate.fluxgen(prompt)
                photos.append(types.InputMediaPhoto(media=request))
            if len(photos) == 1:
                await message.reply_photo(photos[0].media)
            else:
                await message.reply_media_group(photos)
            await wait_msg.delete()
        except Exception as e:
            await message.reply(f'Ошибка при генерации изображения: {e}')
            await wait_msg.delete()


@dp.message(Command(commands=['help']))
async def help(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        help_message = ('Команды:\n/start - начать\n/online - онлайн\n/sd <запрос> - cгенерировать картинку в SD\n'
                        '/prompts - список промптов\n/reset - очистить контекст\n/help - помощь\n/settings - настройки'
                        '\n/unicode - посмотреть символы unicode\n/support - отправить сообщение админу\n/stats - '
                        'статистика\n/profile - профиль')
        with get_db() as db:
            admin = db.query(User).filter(User.admin==True, User.id==message.from_user.id).first()
        if admin or message.from_user.id == creator:
            help_message += ('\n/addprompt <команда>|<название>|<описание>|<промпт> - добавить/изменить промпт\n'
                             '/delprompt <команда> - удалить промпт\n/getprompt <команда> - просмотреть промпт\n'
                             '/myprompts - просмотреть свои промпты\n/addadmin <команда> - добавить админа к промпту\n'
                             '/deladmin <команда> - удалить админа промпта')
        if message.from_user.id == creator:
            help_message += ('\n/admin - назначить админа\n/unadmin - снять админа\n/ban - забанить пользователя\n'
                             '/unban - разбанить пользователя\n/bans - список забаненых\n/admins - список админов\n'
                             '/yourprompts - просмотреть чьи-то промпты\n/restart - перезапуск бота\n/stop - остановка '
                             'бота\n/your_profile - просмотреть чей-то профиль')
        await message.reply(help_message)


@dp.message(Command(commands=['settings']))
async def settings(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        msg = sets_msg(message.from_user.id)
        await message.reply(msg[0], reply_markup=msg[1])


@dp.message(Command(commands=['stats']))
async def stats(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        with get_db() as db:
            prompts = db.query(Prompt).all()
        prompts_count = len(prompts)

        with get_db() as db:
            bans = db.query(User).filter(User.banned==True).all()
        bans_count = len(bans)

        with get_db() as db:
            admins = db.query(User).filter(User.admin==True).all()
        admins_count = len(admins)

        with get_db() as db:
            users = db.query(User).all()
        users_count = len(users)
        
        await message.reply(
            f'Статистика:\n\nПромпты: {prompts_count}\nБаны: {bans_count}\nАдмины: {admins_count}\nПользователи: {users_count}')


@dp.message(Command(commands=['profile']))
async def profile(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        with get_db() as db:
            user = db.query(User).filter(User.id==message.from_user.id).first()

        if user.admin == True:
            user_admin_status = 'да'
        else:
            user_admin_status = 'нет'

        await message.reply(f'Админ: {user_admin_status}',
                            parse_mode=ParseMode.HTML)


@dp.message(Command(commands=['your_profile']))
async def your_profile(message: Message):
    if message.from_user.id == creator:
        with get_db() as db:
            user = db.query(User).filter(User.id==message.reply_to_message.from_user.id).first()

        if user.admin == True:
            user_admin_status = 'да'
        else:
            user_admin_status = 'нет'

        if user.banned == True:
            user_ban_status = 'да'
        else:
            user_ban_status = 'нет'

        await message.reply(f'Админ: {user_admin_status}\nЗабанен: {user_ban_status}',
                            parse_mode=ParseMode.HTML)


@dp.message(Command(commands=['reset']))  # TODO: work with `name` of prompt
async def reset(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        with open('contexts.json') as f:
            contexts = json.load(f)
        contexts_to_del = []
        for context in contexts:
            if context.startswith(str(message.from_user.id)):
                contexts_to_del.append(context)
        for context in contexts_to_del:
            del contexts[context]
        with open('contexts.json', 'w') as f:
            json.dump(contexts, f, ensure_ascii=False, indent=4)
        await message.reply('Весь контекст удалён')


@dp.message(Command(commands=['unicode']))
async def unicode(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        await message.reply('Эта функция предоставляет символы Unicode (их могут использовать админы для создания ASCII'
                            '-картинок или кастомизированных меню в своих промптах):\n'
                            '֎ ֍ \n█ ▓ ▒ ░ ▄ ▀ ▌ ▐ \n■ □ ▬ ▲ ► ▼ ◄ \n◊ ○ ◌ ● ◘ ◙ ◦ ☻ \n☼ ♀ ♂ ♪ ♫ ♯ \n'
                            '┌─┬┐  ╒═╤╕\n│ ││  │ ││\n├─┼┤  ╞═╪╡\n└─┴┘  ╘═╧╛\n╓─╥╖  ╔═╦╗\n║ ║║  ║ ║║\n╟─╫╢  ╠═╬╣\n'
                            '╙─╨╜  ╚═╩╝\nΩ ₪ ← ↑ → ↓ ∆ ∏ ∑ \n√ ∞ ∟ ∩ ≈ ≠ ≡ ≤ ≥ ⌂ ⌐ \n➀➁➂➃➄➅➆➇➈➉\n⓿❶❷❸❹❺❻❼❽❾❿\n'
                            '➊➋➌➍➎➏➐➑➒➓\n⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴\n⓵⓶⓷⓸⓹⓺⓻⓼⓽⓾\n⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽\n⑾⑿⒀⒁⒂⒃⒄⒅⒆⒇\n'
                            '⒈⒉⒊⒋⒌⒍⒎⒏⒐⒑\n⒒⒓⒔⒕⒖⒗⒘⒙⒚⒛\n①②③④⑤⑥⑦⑧⑨⑩\n⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳\n♳♴♵♶♷♸♹♺\n♼♽✓\n♩♪♫♬\n'
                            '▁▂▃▄▅▆▇█ \n▊\n▋\n▌\n▍\n▎\n▏\n\n▔\n')


@dp.message(Command(commands=['addkey']))
async def addkey(message: Message):
    data = message.text.replace('/addkey ', '')
    data = data.replace('/addkey@neuro_gemini_bot ', '')
    try:
        await gemini.gemini_gen('hi', data)
        with get_db() as db:
            key = APIKey(key=data, creator=message.from_user.id)
            db.add(key)
            db.commit()
        await message.reply('Ключ добавлен.')
    except Exception as e:
        await message.reply(f'Ключ неактивен. Попробуйте снова чуть позже. \nОшибка: {e}')


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
        except Exception as e:
            continue
    try:
        await message.reply(f'Ключ неактивен. Попробуйте снова чуть позже. \nОшибка: {e}')
    except Exception as e:
        await message.reply('Кончился лимит!')


@dp.message(Command(commands=['support']))
async def send(message: Message, state: FSMContext):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        await state.set_state(MessageToAdmin.text_message)
        await message.reply('Связь с админом.\nНапишите сообщение, для отмены напишите: "отмена":')


@dp.message(MessageToAdmin.text_message)
async def message_to_admin(message: Message, state: FSMContext):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        await state.update_data(text_message=message.text)
        if message.text.lower() == 'отмена':
            await state.clear()
            await message.reply('Отмена.')
        else:
            await state.clear()
            await message.reply('Сообщение отправлено.\nОбсуждение бота в группе @neuro_opensource')
            await bot.send_message(support_chat,
                                   f'Сообщение от пользователя @{message.from_user.username}, {message.from_user.id}, {message.from_user.mention_html()}:',
                                   parse_mode=ParseMode.HTML)
            await message.forward(support_chat)


@dp.message(Command(commands=['addprompt']))
async def addprompt(message: Message):
    with get_db() as db:
        user = db.query(User).filter(User.id==message.from_user.id).first()
        data = find_prompt(message.text)
        prompt = db.query(Prompt).filter_by(command=data[0]).first()
        if prompt:
            prompt_admins = json.loads(prompt.admins)
            prompt_creator = db.query(User).filter_by(id=prompt.author).first()

    if user.admin or message.from_user.id == creator:
        if message.from_user.id == creator:
            status = add_or_update_prompt(data[0], data[1], data[2], data[3], creator)
            with get_db() as db:
                prompt = db.query(Prompt).filter_by(command=data[0]).first()
                prompt_admins = json.loads(prompt.admins)
                prompt_creator = db.query(User).filter_by(id=prompt.author).first()
        
        elif user.admin and prompt:
            if prompt.author == message.from_user.id or message.from_user.id in prompt_admins:
                status = add_or_update_prompt(data[0], data[1], data[2], data[3], message.from_user.id)
                with get_db() as db:
                    prompt = db.query(Prompt).filter_by(command=data[0]).first()
                    prompt_admins = json.loads(prompt.admins)
                    prompt_creator = db.query(User).filter_by(id=prompt.author).first()
            else:
                await message.reply('Куда полез? Тебе сюда нельзя.')
                return

        elif user.admin and not prompt:
            status = add_or_update_prompt(data[0], data[1], data[2], data[3], message.from_user.id)
            with get_db() as db:
                prompt = db.query(Prompt).filter_by(command=data[0]).first()
                prompt_admins = json.loads(prompt.admins)
                prompt_creator = db.query(User).filter_by(id=prompt.author).first()
        
        else:
            await message.reply('Куда полез? Тебе сюда нельзя.')
            return

        if status == True:
            await message.reply(f'Промпт /{data[0]} изменён.')
        else:
            await message.reply(f'Промпт /{data[0]} добавлен.')
    
    else:
        if prompt:
            if prompt.author == message.from_user.id or message.from_user.id in prompt_admins:
                status = add_or_update_prompt(data[0], data[1], data[2], data[3], prompt_creator)
                with get_db() as db:
                    prompt = db.query(Prompt).filter_by(command=data[0]).first()
                    prompt_admins = json.loads(prompt.admins)
                    prompt_creator = db.query(User).filter_by(id=prompt.author).first()
                await message.reply(f'Промпт /{data[0]} изменён.')
            else:
                await message.reply('Куда полез? Тебе сюда нельзя.')
                return
        else:
            await message.reply('Куда полез? Тебе сюда нельзя.')
            return

    await bot.send_message(prompts_channel, f'/addprompt {data[0]}|{data[1]}|{data[2]}|{data[3]}\n\n'
                                            f'Создатель: {prompt_creator.get_object().mention_markdown()} (`{prompt_creator.id}`)\n'
                                            f'Админы: {prompt_admins}', parse_mode=ParseMode.MARKDOWN)


@dp.message(Command(commands=['delprompt']))
async def delprompt(message: Message):
    command = message.text.replace('/delprompt ', '')
    command = command.replace('/delprompt@neuro_gemini_bot ', '')
    with get_db() as db:
        prompt = db.query(Prompt).filter_by(command=command).first()
    try:
        prompt_creator = prompt.author
    except AttributeError:
        await message.reply('Такого промпта нет')
        return
    if prompt_creator == message.from_user.id or message.from_user.id == creator:
        btn1 = types.InlineKeyboardButton(text='Нет', callback_data=f'false_delprompt_{message.from_user.id}')
        btn2 = types.InlineKeyboardButton(text='Да', callback_data=f'true__delprompt__{prompt.command}__{message.from_user.id}')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        await message.reply(f'Ты уверен?', reply_markup=markup)
    else:
        await message.reply('Куда полез? Тебе сюда нельзя')


@dp.message(Command(commands=['getprompt']))
async def getprompt(message: Message):
    key = message.text.replace('/getprompt ', '')
    key = key.replace('/getprompt@neuro_gemini_bot ', '')
    with get_db() as db:
        prompt = db.query(Prompt).filter_by(command=key).first()
    if not prompt:
        await message.reply('Такого промпта нет')
        return
    if prompt.author == message.from_user.id or message.from_user.id == creator or message.from_user.id in json.loads(prompt.admins):
        string = await prompt_string(key)
        btn1 = types.InlineKeyboardButton(text='❌ Скрыть', callback_data=f'del_{message.from_user.id}')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1]])
        await message.reply(string, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply('Куда полез? Тебе сюда нельзя')


@dp.message(Command(commands=['gdelprompt']))
async def gdelprompt(message: Message):
    prompt_command = message.text.replace('/gdelprompt ', '')
    prompt_command = prompt_command.replace('/gdelprompt@neuro_gemini_bot ', '')
    with get_db() as db:
        prompt = db.query(Prompt).filter_by(command=prompt_command).first()
    if not prompt:
        await message.reply('Такого промпта нет')
        return
    if prompt.author == message.from_user.id or message.from_user.id == creator:
        with get_db() as db:
            user = db.query(User).filter(User.id==message.from_user.id).first()
        string = await prompt_string(prompt_command)
        await message.reply(string, parse_mode=ParseMode.MARKDOWN)
        btn1 = types.InlineKeyboardButton(text='Нет', callback_data=f'false_delprompt_{message.from_user.id}')
        btn2 = types.InlineKeyboardButton(text='Да',
                                          callback_data=f'true__delprompt__{prompt_command}__{message.from_user.id}')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        await message.reply(f'Ты уверен?', reply_markup=markup)
    else:
        await message.reply('Куда полез? Тебе сюда нельзя.')


@dp.message(Command(commands=['addadmin']))
async def addadmin(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
        return
    data = message.text.replace('/addadmin ', '')
    data = data.replace('/addadmin@neuro_gemini_bot ', '')

    with get_db() as db:
        user = db.query(User).filter(User.id==message.from_user.id).first()
        reply_user = db.query(User).filter(User.id==message.reply_to_message.from_user.id).first()
        prompt = db.query(Prompt).filter_by(command=data).first()

        if message.from_user.id == creator or message.from_user.id == prompt.author:
            if reply_user.admin:
                admins = json.loads(prompt.admins)
                admins.append(message.reply_to_message.from_user.id)
                prompt.admins = json.dumps(admins)
                db.commit()
            else:
                await message.reply('Целевой пользователь не админ.')
                return
        else:
            await message.reply('Ты не админ.')
            return
    await message.reply(f'Админ к /{data} добавлен.')


@dp.message(Command(commands=['deladmin']))
async def deladmin(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
        return
    data = message.text.replace('/deladmin ', '')
    data = data.replace('/deladmin@neuro_gemini_bot ', '')

    with get_db() as db:
        user = db.query(User).filter(User.id==message.from_user.id).first()
        reply_user = db.query(User).filter(User.id==message.reply_to_message.from_user.id).first()
        prompt = db.query(Prompt).filter_by(command=data).first()

        if message.from_user.id == creator or message.from_user.id == prompt.author:
            if reply_user.admin:
                admins = json.loads(prompt.admins)
                admins.remove(message.reply_to_message.from_user.id)
                prompt.admins = json.dumps(admins)
                #prompts[data]['admins'].remove(message.reply_to_message.from_user.id)
                db.commit()
            else:
                await message.reply('Целевой пользователь не админ.')
                return
    await message.reply(f'Админ к /{data} удалён.')


@dp.message(Command(commands=['myprompts']))
async def myprompts(message: Message):
    with get_db() as db:
        user_prompts = db.query(Prompt).filter_by(author=message.from_user.id).all()
    message_prompts = ''
    for prompt in user_prompts:
        message_prompts += '/' + prompt.command + ' "' + prompt.name + '" ' + prompt.description + '\n'
    try:
        await message.reply(message_prompts)
    except aiogram.exceptions.TelegramBadRequest:
        await message.reply('У вас нет ни одного созданного промпта.')


@dp.message(Command(commands=['yourprompts']))
async def yourprompts(message: Message):
    if message.from_user.id == creator:
        with get_db() as db:
            user_prompts = db.query(Prompt).filter_by(author=message.from_user.id).all()
        message_prompts = ''
        for prompt in prompts:
            message_prompts += '/' + prompt.command + ' "' + prompt.name + '" ' + prompt.description + '\n'
        try:
            await message.reply(message_prompts)
        except aiogram.exceptions.TelegramBadRequest:
            await message.reply(f'У {message.reply_to_message.from_user.first_name} нет ни одного созданного промпта')


@dp.message(Command(commands=['prompts']))
async def prompts(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        with get_db() as db:
            prompts = db.query(Prompt).all()
        list_prompts = []
        for prompt in prompts:
            message_prompt = '/' + prompt.command + ' "' + prompt.name + '" ' + prompt.description + '\n'
            list_prompts.append(message_prompt)
        btn1 = types.InlineKeyboardButton(text='❌ Скрыть', callback_data='del')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1]])
        i = len(list_prompts)
        y = [0, 10]
        while True:
            message_prompts = ''
            for msg in list_prompts[y[0]:y[1]]:
                message_prompts += msg
            await message.reply(message_prompts, reply_markup=markup)
            if y[1] >= i:
                break
            y[0] += 10
            y[1] += 10


@dp.message(Command(commands=['ban']))
async def ban(message: Message):
    if message.from_user.id == creator:
        data = message.text.split()

        if len(data) == 2:
            user_id = int(data[1])
        else:
            user_id = message.reply_to_message.from_user.id

        with get_db() as db:
            user = db.get(User, user_id)
            if not user:
                new_user = User(id=user_id, object='{}')
                db.add(new_user)
            user = db.get(User, user_id)
            user.banned = True
            db.commit()

        await message.reply('Пользователь забанен')
    else:
        await message.reply('Вы не админ')


@dp.message(Command(commands=['unban']))
async def unban(message: Message):
    if message.from_user.id == creator:
        data = message.text.split()

        if len(data) == 2:
            user_id = int(data[1])
        else:
            user_id = message.reply_to_message.from_user.id

        with get_db() as db:
            user = db.get(User, user_id)
            user.banned = False
            db.commit()

        await message.reply('Пользователь разбанен')
    else:
        await message.reply('Вы не админ')


@dp.message(Command(commands=['deluser']))
async def deluser(message: Message):
    if message.from_user.id == creator:
        data = message.text.split()

        if data[1]:
            user_id = int(data[1])
        else:
            user_id = message.reply_to_message.from_user.id

        with get_db() as db:
            user = db.get(User, user_id)
            db.delete(user)
            db.commit()

        await message.reply('Пользователь удалён')
    else:
        await message.reply('Вы не админ')


@dp.message(Command(commands=['admin']))
async def admin(message: Message):
    if message.from_user.id == creator:
        user_id = message.reply_to_message.from_user.id

        with get_db() as db:
            user = db.get(User, user_id)
            user.admin = True
            db.commit()

        await message.reply(f'{message.reply_to_message.from_user.first_name} теперь админ')
    else:
        await message.reply('Вы не админ')


@dp.message(Command(commands=['unadmin']))
async def unadmin(message: Message):
    if message.from_user.id == creator:
        user_id = message.reply_to_message.from_user.id

        with get_db() as db:
            user = db.get(User, user_id)
            user.admin = False
            db.commit()

        await message.reply(f'{message.reply_to_message.from_user.first_name} больше не админ')
    else:
        await message.reply('Вы не админ')


@dp.message(Command(commands=['admins']))
async def admins(message: Message):
    if message.from_user.id == creator:
        with get_db() as db:
            admins = db.query(User).filter(User.admin==True).all()
        admins_message = 'Админы:\n'
        for admin in admins:
            admins_message += f'{admin.get_object().mention_markdown()} (`{admin.id}`)\n'
        btn1 = types.InlineKeyboardButton(text='❌ Скрыть', callback_data=f'del_{message.from_user.id}')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1]])
        if admins_message == 'Админы:\n':
            await message.reply('Админов нет')
            return
        await message.reply(admins_message, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply('Вы не админ')


@dp.message(Command(commands=['bans']))
async def bans(message: Message):
    if message.from_user.id == creator:
        with get_db() as db:
            bans = db.query(User).filter(User.banned==True).all()
        bans_message = 'Забаненные пользователи:\n'
        for ban in bans:
            bans_message += f'{ban.get_object().mention_markdown() if ban.object != '{}' else 'Имя отсутствует'} (`{ban.id}`)\n'
        btn1 = types.InlineKeyboardButton(text='❌ Скрыть', callback_data=f'del_{message.from_user.id}')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1]])
        if bans_message == 'Забаненные пользователи:\n':
            await message.reply('Забаненных пользователей нет')
            return
        await message.reply(bans_message, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply('Вы не админ')


@dp.message(Command(commands=['stop']))
async def stop(message: Message):
    if message.from_user.id == creator:
        await message.reply('Бот остановлен')
        await dp.stop_polling()


@dp.message(Command(commands=['restart']))
async def restart(message: Message):
    if message.from_user.id == creator:
        await message.reply('Временно недоступно.')


@dp.message(F.caption.startswith('/'), F.photo)
async def command_response(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    elif message.caption[0] == '/':
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        buffer = io.BytesIO()
        buffer.seek(0)
        await bot.download_file(file_path, buffer)

        command = message.caption.split()[0].replace('/', '')
        command = command.split()[0].replace('@neuro_gemini_bot', '')
        prompt = message.caption.replace(message.caption.split()[0], '')
        prompt = prompt.replace('@neuro_gemini_bot ', '')
        prompt = read_telegraph(prompt)
        if prompt == '':
            prompt = ' '

        with open('contexts.json') as f:
            contexts = json.load(f)
        try:
            with get_db() as db:
                prompt_obj = db.query(Prompt).filter_by(command=command).first()
            system_prompt = read_telegraph(prompt_obj.content)
        except AttributeError:
            return
        with get_db() as db:
            keys = db.query(APIKey).all()
        wait_msg = await message.reply('Думаю...')
        if f'{message.from_user.id}-{command}' not in contexts:
            contexts[f'{message.from_user.id}-{command}'] = []
        context = contexts[f'{message.from_user.id}-{command}']
        for key in keys:
            try:
                request = await gemini.gemini_gen(prompt, key.key, context, system_prompt, image_bytes_io=buffer)
                break
            except Exception as e:
                continue
        try:
            await message.reply(f'Ошибка при генерации: {e}\n Вы можете сообщить о ней по команде /send')
            await wait_msg.delete()
            return
        except:
            pass
        response = find_draw_strings(request[0])
        btn1 = types.InlineKeyboardButton(text='Сброс всего', callback_data='delall_context')
        btn2 = types.InlineKeyboardButton(text='Сброс', callback_data=f'delcontext__{command}')
        with get_db() as db:
            user = db.query(User).filter_by(id=message.from_user.id).first()
            sets = json.loads(user.settings)
        if sets['reset']:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        else:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[])
        i = len(response[1])
        x = [0, 4096]
        ids1 = []
        while True:
            msg = await message.reply(response[1][x[0]:x[1]], reply_markup=markup)
            ids1.append(msg.message_id)
            if x[1] >= i:
                break
            x[0] += 4096
            x[1] += 4096
        await wait_msg.delete()
        context = request[1]
        with open('prompts_message_ids.json') as f:
            ids = json.load(f)
        if f'{command}' not in ids:
            ids[f'{command}'] = []
        for id in ids1:
            ids[f'{command}'].append(id)
        contexts[f'{str(message.from_user.id)}-{command}'] = context
        with open('prompts_message_ids.json', 'w') as f:
            json.dump(ids, f, indent=4)
        with open('contexts.json', 'w') as f:
            json.dump(contexts, f, ensure_ascii=False, indent=4)
        photos = []
        if sets['pictures_in_dialog']:
            for prompt in response[0]:
                request = await generate.sdgen(prompt) if sets["imageai"] == 'sd' else await generate.fluxgen(prompt) if sets["imageai"] == 'flux' else None
                photos.append(types.InputMediaPhoto(media=request, caption=prompt))
            if len(photos) == 0:
                pass
            elif len(photos) == 1:
                await message.reply_photo(photos[0].media)
            else:
                await message.reply_media_group(photos)
        buffer.close()


@dp.message(F.reply_to_message.from_user.id == 7487465375, F.photo)
async def reply_response(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        buffer = io.BytesIO()
        buffer.seek(0)
        await bot.download_file(file_path, buffer)

        with open('prompts_message_ids.json') as f:
            ids = json.load(f)
        for prompt_ids in ids:
            if message.reply_to_message.message_id in ids[prompt_ids]:
                command = prompt_ids
                break
        else:
            return
        prompt = message.caption if message.caption else ' '
        prompt = read_telegraph(prompt)

        with open('contexts.json') as f:
            contexts = json.load(f)
        if f'{message.from_user.id}-{command}' not in contexts:
            contexts[f'{message.from_user.id}-{command}'] = []
        context = contexts[f'{message.from_user.id}-{command}']
        with get_db() as db:
            prompt_obj = db.query(Prompt).filter_by(command=command).first()
        system_prompt = read_telegraph(prompt_obj.content)
        with get_db() as db:
            keys = db.query(APIKey).all()
        wait_msg = await message.reply('Думаю...')
        for key in keys:
            try:
                request = await gemini.gemini_gen(prompt, key.key, context, system_prompt, image_bytes_io=buffer)
                break
            except Exception as e:
                continue
        try:
            await message.reply(f'Ошибка при генерации: {e}\n Вы можете сообщить о ней по команде /send')
            await wait_msg.delete()
            return
        except:
            pass
        response = find_draw_strings(request[0])
        with get_db() as db:
            user = db.query(User).filter_by(id=message.from_user.id).first()
            sets = json.loads(user.settings)
        btn1 = types.InlineKeyboardButton(text='Сброс всего', callback_data='delall_context')
        btn2 = types.InlineKeyboardButton(text='Сброс', callback_data=f'delcontext__{command}')
        if sets['reset']:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        else:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[])
        i = len(response[1])
        x = [0, 4096]
        ids1 = []
        while True:
            msg = await message.reply(response[1][x[0]:x[1]], reply_markup=markup)
            ids1.append(msg.message_id)
            if x[1] >= i:
                break
            x[0] += 4096
            x[1] += 4096
        await wait_msg.delete()
        context = request[1]
        for id in ids1:
            ids[f'{command}'].append(id)
        contexts[f'{str(message.from_user.id)}-{command}'] = context
        with open('prompts_message_ids.json', 'w') as f:
            json.dump(ids, f, indent=4)
        with open('contexts.json', 'w') as f:
            json.dump(contexts, f, ensure_ascii=False, indent=4)
        photos = []
        if sets['pictures_in_dialog']:
            for prompt in response[0]:
                request = await generate.sdgen(prompt) if sets["imageai"] == 'sd' else await generate.fluxgen(prompt) if sets["imageai"] == 'flux' else None
                photos.append(types.InputMediaPhoto(media=request, caption=prompt))
            if len(photos) == 0:
                pass
            elif len(photos) == 1:
                await message.reply_photo(photos[0].media, caption=photos[0].caption)
            else:
                await message.reply_media_group(photos)
        buffer.close()


@dp.message(F.text.startswith('/'))
async def command_response(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    elif message.text[0] == '/':
        command = message.text.split()[0].replace('/', '')
        command = command.split()[0].replace('@neuro_gemini_bot', '')
        prompt = message.text.replace(message.text.split()[0], '')
        prompt = prompt.replace('@neuro_gemini_bot ', '')
        prompt = read_telegraph(prompt)
        if prompt == '':
            prompt = ' '

        with open('contexts.json') as f:
            contexts = json.load(f)
        try:
            with get_db() as db:
                prompt_obj = db.query(Prompt).filter_by(command=command).first()
            system_prompt = read_telegraph(prompt_obj.content)
        except AttributeError:
            return
        with get_db() as db:
            keys = db.query(APIKey).all()
        wait_msg = await message.reply('Думаю...')
        if f'{message.from_user.id}-{command}' not in contexts:
            contexts[f'{message.from_user.id}-{command}'] = []
        context = contexts[f'{message.from_user.id}-{command}']
        for key in keys:
            try:
                request = await gemini.gemini_gen(prompt, key.key, context, system_prompt)
                break
            except Exception as e:
                continue
        try:
            await message.reply(f'Ошибка при генерации: {e}\n Вы можете сообщить о ней по команде /send')
            await wait_msg.delete()
            return
        except:
            pass
        response = find_draw_strings(request[0])
        btn1 = types.InlineKeyboardButton(text='Сброс всего', callback_data='delall_context')
        btn2 = types.InlineKeyboardButton(text='Сброс', callback_data=f'delcontext__{command}')
        with get_db() as db:
            user = db.query(User).filter_by(id=message.from_user.id).first()
            sets = json.loads(user.settings)
        if sets['reset']:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        else:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[])
        i = len(response[1])
        x = [0, 4096]
        ids1 = []
        while True:
            msg = await message.reply(response[1][x[0]:x[1]], reply_markup=markup)
            ids1.append(msg.message_id)
            if x[1] >= i:
                break
            x[0] += 4096
            x[1] += 4096
        await wait_msg.delete()
        context = request[1]
        with open('prompts_message_ids.json') as f:
            ids = json.load(f)
        if f'{command}' not in ids:
            ids[f'{command}'] = []
        for id in ids1:
            ids[f'{command}'].append(id)
        contexts[f'{str(message.from_user.id)}-{command}'] = context
        with open('prompts_message_ids.json', 'w') as f:
            json.dump(ids, f, indent=4)
        with open('contexts.json', 'w') as f:
            json.dump(contexts, f, ensure_ascii=False, indent=4)
        photos = []
        if sets['pictures_in_dialog']:
            for prompt in response[0]:
                request = await generate.sdgen(prompt) if sets["imageai"] == 'sd' else await generate.fluxgen(prompt) if sets["imageai"] == 'flux' else None
                photos.append(types.InputMediaPhoto(media=request, caption=prompt))
            if len(photos) == 0:
                pass
            elif len(photos) == 1:
                await message.reply_photo(photos[0].media)
            else:
                await message.reply_media_group(photos)


@dp.message(F.reply_to_message.from_user.id == 7487465375)
async def reply_response(message: Message):
    if is_banned(message.from_user.id):
        await message.reply('Вы забанены.')
    else:
        with open('prompts_message_ids.json') as f:
            ids = json.load(f)
        for prompt_ids in ids:
            if message.reply_to_message.message_id in ids[prompt_ids]:
                command = prompt_ids
                break
        else:
            return
        prompt = message.text
        prompt = read_telegraph(prompt)

        with open('contexts.json') as f:
            contexts = json.load(f)
        if f'{message.from_user.id}-{command}' not in contexts:
            contexts[f'{message.from_user.id}-{command}'] = []
        context = contexts[f'{message.from_user.id}-{command}']
        with get_db() as db:
            prompt_obj = db.query(Prompt).filter_by(command=command).first()
        system_prompt = read_telegraph(prompt_obj.content)
        with get_db() as db:
            keys = db.query(APIKey).all()
        wait_msg = await message.reply('Думаю...')
        for key in keys:
            try:
                request = await gemini.gemini_gen(prompt, key.key, context, system_prompt)
                break
            except Exception as e:
                continue
        try:
            await message.reply(f'Ошибка при генерации: {e}\n Вы можете сообщить о ней по команде /send')
            await wait_msg.delete()
            return
        except:
            pass
        response = find_draw_strings(request[0])
        with get_db() as db:
            user = db.query(User).filter_by(id=message.from_user.id).first()
            sets = json.loads(user.settings)
        btn1 = types.InlineKeyboardButton(text='Сброс всего', callback_data='delall_context')
        btn2 = types.InlineKeyboardButton(text='Сброс', callback_data=f'delcontext__{command}')
        if sets['reset']:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        else:
            markup = types.InlineKeyboardMarkup(inline_keyboard=[])
        i = len(response[1])
        x = [0, 4096]
        ids1 = []
        while True:
            msg = await message.reply(response[1][x[0]:x[1]], reply_markup=markup)
            ids1.append(msg.message_id)
            if x[1] >= i:
                break
            x[0] += 4096
            x[1] += 4096
        await wait_msg.delete()
        context = request[1]
        for id in ids1:
            ids[f'{command}'].append(id)
        contexts[f'{str(message.from_user.id)}-{command}'] = context
        with open('prompts_message_ids.json', 'w') as f:
            json.dump(ids, f, indent=4)
        with open('contexts.json', 'w') as f:
            json.dump(contexts, f, ensure_ascii=False, indent=4)
        photos = []
        if sets['pictures_in_dialog']:
            for prompt in response[0]:
                request = await generate.sdgen(prompt) if sets["imageai"] == 'sd' else await generate.fluxgen(prompt) if sets["imageai"] == 'flux' else None
                photos.append(types.InputMediaPhoto(media=request, caption=prompt))
            if len(photos) == 0:
                pass
            elif len(photos) == 1:
                await message.reply_photo(photos[0].media, caption=photos[0].caption)
            else:
                await message.reply_media_group(photos)


@dp.callback_query()
async def callback(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer('Ты забанен.', show_alert=True)
        return
    if call.data == 'delall_context':
        btn1 = types.InlineKeyboardButton(text='Нет', callback_data=f'false_delall_context_{call.from_user.id}')
        btn2 = types.InlineKeyboardButton(text='Да', callback_data=f'true_delall_context_{call.from_user.id}')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        await call.message.reply(f'{call.from_user.mention_html()}, ты уверен, что хочешь сбросить весь контекст?',
                                 parse_mode=ParseMode.HTML, reply_markup=markup)
        await call.answer()

    elif call.data.startswith('true_delall_context'):
        data = call.data.split('_')
        if str(call.from_user.id) == data[3]:
            with open('contexts.json') as f:
                contexts = json.load(f)
            contexts_to_del = []
            for context in contexts:
                if context.startswith(str(call.from_user.id)):
                    contexts_to_del.append(context)
            for context in contexts_to_del:
                del contexts[context]
            with open('contexts.json', 'w') as f:
                json.dump(contexts, f, ensure_ascii=False, indent=4)
            await call.message.delete()
            await call.answer('Весь контекст удалён', show_alert=True)
        else:
            await call.answer('Отставить! Это не твоя кнопка!')

    elif call.data.startswith('false_delall_context'):
        data = call.data.split('_')
        if str(call.from_user.id) == data[3]:
            await call.message.delete()
            await call.answer('Хорошо, я не буду удалять весь контекст.')
        else:
            await call.answer('Отставить! Это не твоя кнопка!')

    elif call.data.startswith('delcontext__'):
        data = call.data.split('__')
        btn1 = types.InlineKeyboardButton(text='Нет', callback_data=f'false_delcontext_{call.from_user.id}')
        btn2 = types.InlineKeyboardButton(text='Да', callback_data=f'true__delcontext__{data[1]}__{call.from_user.id}')
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn1, btn2]])
        await call.message.reply(f'{call.from_user.mention_html()}, ты уверен, что хочешь сбросить контекст?',
                                 parse_mode=ParseMode.HTML, reply_markup=markup)
        await call.answer()

    elif call.data.startswith('true__delcontext__'):
        data = call.data.split('__')
        if str(call.from_user.id) == data[3]:
            key = f'{data[2]}_{data[3]}'
            with open('contexts.json') as f:
                contexts = json.load(f)
            contexts.pop(key, 'Не найдено')
            with open('contexts.json', 'w') as f:
                json.dump(contexts, f, ensure_ascii=False, indent=4)
            await call.message.delete()
            await call.answer('Контекст удалён', show_alert=True)
        else:
            await call.answer('Отставить! Это не твоя кнопка!')

    elif call.data.startswith('false_delcontext'):
        data = call.data.split('_')
        if str(call.from_user.id) == data[2]:
            await call.message.delete()
            await call.answer('Хорошо, я не буду удалять контекст.')
        else:
            await call.answer('Отставить! Это не твоя кнопка!')

    elif call.data.startswith('true__delprompt__'):
        data = call.data.split('__')
        if str(call.from_user.id) == data[3]:
            string = await prompt_string(data[2])
            with get_db() as db:
                user = db.query(User).filter(User.id==call.from_user.id).first()
                prompt = db.query(Prompt).filter_by(command=data[2]).first()
                db.delete(prompt)
                db.commit()
            await call.message.edit_text(f'Промпт /{prompt.command} удалён.')
            await bot.send_message(prompts_channel, string, parse_mode=ParseMode.MARKDOWN)
        else:
            await call.answer('Отставить! Это не твоя кнопка!')

    elif call.data.startswith('false_delprompt'):
        data = call.data.split('_')
        if str(call.from_user.id) == data[2]:
            await call.message.delete()
            await call.answer('Хорошо, я не буду удалять промпт.')
        else:
            await call.answer('Отставить! Это не твоя кнопка!')

    elif call.data == 'del':
        await call.message.delete()

    elif call.data.startswith('del_'):
        data = call.data.split('_')
        if str(call.from_user.id) == data[1]:
            await call.message.delete()
        else:
            await call.answer('Отставить! Это не твоя кнопка!')

    elif call.data == 'reset':
        await call.answer('Кнопки сброса диалога')

    elif call.data.startswith('reset'):
        data = call.data.split('_')
        await call.message.edit_text('Загрузка... Подождите.')

        if data[1] == 'on':
            edit_sets(call.from_user.id, 'reset', True)
            await call.answer(f'Кнопки сброса диалога включены', show_alert=True)
        elif data[1] == 'off':
            edit_sets(call.from_user.id, 'reset', False)
            await call.answer(f'Кнопки сброса диалога отключены', show_alert=True)

        msg = sets_msg(call.from_user.id)
        await call.message.edit_text(msg[0], reply_markup=msg[1])

    elif call.data == 'pictures_count':
        await call.answer('Количество генерируемых картинок')

    elif call.data.startswith('pictures_count_'):
        await call.message.edit_text('Загрузка... Подождите.')
        data = call.data.split('_')
        edit_sets(call.from_user.id, 'pictures_count', int(data[2]))
        await call.answer(f'Количество генерируемых картинок изменено на {data[2]}', show_alert=True)
        msg = sets_msg(call.from_user.id)
        await call.message.edit_text(msg[0], reply_markup=msg[1])

    elif call.data == 'pictures_in_chat':
        await call.answer('Генерация картинок в диалоге')

    elif call.data.startswith('pictures_'):
        await call.message.edit_text('Загрузка... Подождите.')
        data = call.data.split('_')
        if data[1] == 'on':
            edit_sets(call.from_user.id, 'pictures_in_dialog', True)
            await call.answer(f'Картинки в диалоге включены', show_alert=True)
        elif data[1] == 'off':
            edit_sets(call.from_user.id, 'pictures_in_dialog', False)
            await call.answer(f'Картинки в диалоге отключены', show_alert=True)
        
        msg = sets_msg(call.from_user.id)
        await call.message.edit_text(msg[0], reply_markup=msg[1])

    elif call.data == 'imageai':
        await call.answer('Нейросеть для генерации картинок в диалоге')

    elif call.data.startswith('imageai_'):
        await call.message.edit_text('Загрузка... Подождите.')
        data = call.data.split('_')
        edit_sets(call.from_user.id, 'imageai', data[1])
        await call.answer(f'Нейросеть для генерации картинок в диалоге изменена на {data[1]}')
        msg = sets_msg(call.from_user.id)
        await call.message.edit_text(msg[0], reply_markup=msg[1])


if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot))
