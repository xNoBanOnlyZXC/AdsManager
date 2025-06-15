from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    Message, 
    CallbackQuery, 
    InputMediaPhoto,
)
import os, json, asyncio, pyrofix

# 0 / 1
TESTMODE = 0

API_ID = 0
API_HASH = 'hash'

TOKEN = [
    'main bot token',
    'test bot token'
][TESTMODE]

CHAT_ID = [
    -100, # main chat
    -100  # tests chat
][TESTMODE]

NAME = [
    "main",
    "test"
][TESTMODE]

ADMINS = []
ADS_FILE = 'ads.json'
LAST_FILE = 'last.dict'
MAX_ADS = 3

bot = Client(NAME, api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

def load_ads():
    if os.path.exists(ADS_FILE):
        with open(ADS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_ads(ads):
    with open(ADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(ads, f, indent=4, ensure_ascii=False)

def load_last():
    if os.path.exists(LAST_FILE):
        with open(LAST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_last(last_ad_message_ids):
    with open(LAST_FILE, 'w', encoding='utf-8') as f:
        json.dump(last_ad_message_ids, f, indent=4, ensure_ascii=False)

ads = load_ads()
last_ad_message_ids = load_last()
lock = False

def admin_only(func):
    async def wrapper(client: Client, message: Message):
        if message.from_user.id in ADMINS:
            return await func(client, message)
        else:
            await message.react("👎")
    return wrapper

def pm_only(func):
    async def wrapper(client: Client, message: Message):
        if message.chat.type == enums.ChatType.PRIVATE:
            return await func(client, message)
        else:
            await message.react("👎")
    return wrapper

@bot.on_message(filters.command("del") & filters.private)
@admin_only
async def delmessage(client: Client, message: Message):
    m = await client.get_messages(CHAT_ID, int(message.text.split()[1]))
    await m.delete()
    await message.reply("deleted")

@bot.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    if message.from_user.id in ADMINS:
        await message.reply(f'Привет! Я бот для управления рекламными сообщениями.\nМои команды:\n\n/ad (в ответ на сообщение) - добавить рекламное сообщение (максимум 1 картинка)\n/ads - список реклам (максимум - {MAX_ADS})\n/this (в ответ на сообщение) - отправит this.txt с полными данными сообщения на которое ответили\n\nБот создан @NoBanOnlyZXC')
    else:
        user = message.from_user
        await message.reply(f"🔑 Пользователь не является администратором, доступ ограничен.\n")
        for admin in ADMINS:
            await client.send_message(admin, f"❗ Пользователь нажал /start\n{'⭐ ' if user.is_premium else ''}{user.first_name} {user.last_name}\n{'@'+user.username if user.username else 'No username'}\nid: {user.id}")

@bot.on_message(filters.command("ad") & filters.private & filters.reply)
@admin_only
async def ad(client: Client, message: Message):
    reply_to = message.reply_to_message
    if reply_to:
        photos = []
        text = ''
        if reply_to.media_group_id:
            mg = await reply_to.get_media_group()
            for pic in mg:
                photos.append({'file_id': pic.photo.file_id})
                text = pic.caption if pic.caption else (pic.text if pic.text else text)

        else:
            if reply_to.photo:
                photo = reply_to.photo.file_id
                photos = [{'file_id': photo}]
                text = reply_to.caption if reply_to.caption else (reply_to.text if reply_to.text else text)

        ad_data = {
            'text': text,
            'photos': photos,
            'refferer': None
        }
        ads.append(ad_data)
        if len(ads) > MAX_ADS:
            ads.pop(0)
        save_ads(ads)
        await message.reply_text('Реклама добавлена!')
        await send_ads()

@bot.on_message(filters.command("ads") & filters.private)
@admin_only
async def ads_command(client: Client, message: Message):
    if len(ads) > 0:
        keyboard = InlineKeyboardMarkup([])
        for i, ad in enumerate(ads):
            button_text = (ad['text'][:27] + '...') if len(ad['text']) > 27 else ad['text']
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text or "No text", callback_data=f'ad_{i}')])
        await message.reply_text('Выберите рекламу:', reply_markup=keyboard)
    else:
        await message.reply_text('Нет рекламы')

async def send_ads():
    global last_ad_message_ids
    last_ad_message_ids.clear()

    for ad in ads:
        if ad['photos']:
            media_group = [InputMediaPhoto(media=photo['file_id']) for photo in ad['photos']]
            media_group[0].caption=ad['text']
            sent_messages = await bot.send_media_group(chat_id=CHAT_ID, media=media_group)
            last_ad_message_ids.extend([msg.id for msg in sent_messages])
        else:
            sent_message = await bot.send_message(chat_id=CHAT_ID, text=ad['text'])
            last_ad_message_ids.append(sent_message.id)
    save_last(last_ad_message_ids)

async def delete_old_ads():
    global last_ad_message_ids
    for message_id in last_ad_message_ids:
        try:
            await bot.delete_messages(chat_id=CHAT_ID, message_ids=message_id)
        except Exception as e:
            print(f"Error deleting message {message_id}: {e}")

@bot.on_callback_query(filters.regex(r"^ad_(\d+)$"))
async def ad_callback(client: Client, callback_query: CallbackQuery):
    ad_index = int(callback_query.data.split('_')[1])
    ad = ads[ad_index]
    kb1 = InlineKeyboardMarkup([
        [InlineKeyboardButton('Удалить рекламу', callback_data=f'delete_ad_{ad_index}')],
        [InlineKeyboardButton('Изменить рекламу', callback_data=f'edit_ad_{ad_index}')],
        [InlineKeyboardButton('Изменить реферала', callback_data=f'ref_ad_{ad_index}')]
    ])
    if ad['photos']:
        await callback_query.edit_message_media(
            media=InputMediaPhoto(media=ad['photos'][0]['file_id'], caption=ad['text'] or "No text"),
            reply_markup=kb1
        )
    else:
        await callback_query.edit_message_text(text=ad['text'] or "No text", reply_markup=kb1)

@bot.on_callback_query(filters.regex(r"^delete_ad_(\d+)$"))
async def delete_ad_callback(client: Client, callback_query: CallbackQuery):
    ad_index = int(callback_query.data.split('_')[2])
    ads.pop(ad_index)
    save_ads(ads)
    await delete_old_ads()
    await send_ads()
    await callback_query.answer("Реклама удалена!")
    await callback_query.message.delete()
    if len(ads) > 0:
        keyboard = InlineKeyboardMarkup([])
        for i, ad in enumerate(ads):
            button_text = (ad['text'][:27] + '...') if len(ad['text']) > 27 else ad['text']
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f'ad_{i}')])
        await callback_query.message.reply_text('Выберите рекламу:', reply_markup=keyboard)
    else:
        await callback_query.message.reply_text('Нет рекламы')

@bot.on_message(filters.chat(CHAT_ID) & (filters.text | filters.photo | filters.audio | filters.video | filters.document | filters.sticker | filters.animation | filters.voice))
async def new_message(client: Client, message: Message):
    global lock
    if not lock:
        lock = True
        await delete_old_ads()
        await asyncio.sleep(0.5)
        await send_ads()
        lock = False

if __name__ == '__main__':
    bot.run()
