from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, Message, CallbackQuery, InputMediaPhoto, BotCommand, BotCommandScope
from models import Base, Ad, LastAds, Settings
from pyrogram import Client, filters, enums
from sqlalchemy.orm import sessionmaker
import os, json, asyncio, pyrofix, time, re
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from datetime import datetime
from io import BytesIO

# 0 / 1
TESTMODE = 0

API_ID = 0
API_HASH = 'hash'

TOKEN = [
    'main bot token',
    'test bot token'
][TESTMODE]

CHAT_IDS = [
    [-100], # main
    [-100]  # test
][TESTMODE]

NAME = [
    "main",
    "test"
][TESTMODE]

ADMINS = [
    [], # basic
    []  # test
][TESTMODE]

MAX_ADS = 5

# SQLAlchemy setup
engine = create_engine(f'sqlite:///{NAME}.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

bot = Client(NAME, api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

user_states = {} 
lock = False

# region admin_only(func)
def admin_only(func):
    async def wrapper(client: Client, message: Message):
        if message.from_user.id in ADMINS:
            return await func(client, message)
        else:
            msg = await client.send_message(message.chat.id, "🚫 Admin only", reply_to_message_id=message.id)
            await asyncio.sleep(1)
            await msg.delete()
        await new_message(client, message)
    return wrapper

# region testmode_only(func)
def testmode_only(func):
    async def wrapper(client: Client, message: Message):
        if TESTMODE:
            return await func(client, message)
        else:
            msg = await client.send_message(message.chat.id, "🚫 In test only", reply_to_message_id=message.id)
            await asyncio.sleep(1)
            await msg.delete()
        await new_message(client, message)
    return wrapper

# region pm_only(func)
def pm_only(func):
    async def wrapper(client: Client, message: Message):
        if message.chat.type == enums.ChatType.PRIVATE:
            return await func(client, message)
        else:
            msg = await client.send_message(message.chat.id, "🚫 PM only", reply_to_message_id=message.id)
            await asyncio.sleep(1)
            await msg.delete()
        await new_message(client, message)
    return wrapper

# region send_ads()
async def send_ads():
    """Отправляет текущие объявления из базы данных в указанные чаты."""
    with SessionLocal() as db:
        ads_from_db = db.query(Ad).all()
        for CHAT_ID in CHAT_IDS:
            last_ads_in_chat = []
            for ad in ads_from_db:
                ad_buttons = []
                if ad.referrer:
                    if ad.referrer:
                        if ad.referrer.startswith("+"):
                            ref = ad.referrer[:5]+'*****'+ad.referrer[10:]
                        else:
                            ref = "@"+ad.referrer
                        ad_buttons.append([InlineKeyboardButton(f"✍️ Написать ({ref})", url=f"https://t.me/{ad.referrer}")])
                        if ad.referrer.startswith("+"):
                            ad_buttons.append([InlineKeyboardButton(f"📞 Позвонить ({ref})", url=f"https://t.me/{bot.me.username}?start=contact_ad_{ad.id}")])

                reply_markup = InlineKeyboardMarkup(ad_buttons) if ad_buttons else print("no refferer found, wtf")

                try:
                    if ad.photos:
                        media_group = [InputMediaPhoto(media=photo['file_id']) for photo in ad.photos]
                        if media_group:
                            media_group[0].caption = ad.text
                            sent_messages = await bot.send_media_group(chat_id=CHAT_ID, media=media_group)
                            if reply_markup and sent_messages:
                                await sent_messages[0].edit_reply_markup(reply_markup=reply_markup)
                            last_ads_in_chat.extend([msg.id for msg in sent_messages])
                    else:
                        sent_message = await bot.send_message(chat_id=CHAT_ID, text=ad.text, reply_markup=reply_markup)
                        last_ads_in_chat.append(sent_message.id)
                except Exception as e:
                    print(f"Ошибка при отправке объявления (ID: {ad.id}) в чат {CHAT_ID}: {e}")
                    raise
            
            last_ad_entry = db.query(LastAds).filter(LastAds.chat_id == CHAT_ID).first()
            if last_ad_entry:
                last_ad_entry.messages = last_ads_in_chat
            else:
                new_last_ad_entry = LastAds(chat_id=CHAT_ID, messages=last_ads_in_chat)
                db.add(new_last_ad_entry)
            db.commit()

# region delete_old_ads()
async def delete_old_ads():
    """Deletes previously sent ads from all tracked chats based on LastAds data."""
    with SessionLocal() as db:
        for CHAT_ID in CHAT_IDS:
            last_ads_entry = db.query(LastAds).filter(LastAds.chat_id == CHAT_ID).first()
            if last_ads_entry and last_ads_entry.messages:
                for message_id in last_ads_entry.messages:
                    try:
                        await bot.delete_messages(chat_id=CHAT_ID, message_ids=message_id)
                    except Exception as e:
                        print(f"Error deleting message {message_id} in chat {CHAT_ID}: {e}")
                db.delete(last_ads_entry)
                db.commit()

# region ADMINME
@bot.on_message(filters.command("adminme"))
@testmode_only
async def adminme(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        ADMINS.append(message.from_user.id)
        msg = await client.send_message(message.chat.id, "✅ Done", reply_to_message_id=message.id)
        await asyncio.sleep(2)
        await msg.delete()
    else:
        msg = await client.send_message(message.chat.id, "🚫 You already admin", reply_to_message_id=message.id)
        await asyncio.sleep(2)
        await msg.delete()
    await new_message(client, message)

# region UNADMINME
@bot.on_message(filters.command("unadminme"))
@testmode_only
@admin_only
async def unadminme(client: Client, message: Message):
    if message.from_user.id in ADMINS:
        ADMINS.remove(message.from_user.id)
        msg = await client.send_message(message.chat.id, "✅ Done", reply_to_message_id=message.id)
        await asyncio.sleep(2)
        await msg.delete()
    else:
        msg = await client.send_message(message.chat.id, "🚫 You are not an admin", reply_to_message_id=message.id)
        await asyncio.sleep(2)
        await msg.delete()
    await new_message(client, message)

# region DEL
@bot.on_message(filters.command("del"))
@admin_only
@pm_only
async def del_message_command(client: Client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            return await message.reply("Use: `del <chat_id> <msg_id>`")
        chat = int(parts[1])
        msg_id = int(parts[2])
    except (IndexError, ValueError):
        return await message.reply("Use: `del <chat_id> <msg_id>`")

    if chat not in CHAT_IDS:
        await message.reply(f"Chat `{chat}` not in `CHAT_IDS` list.")
        return
    try:
        await client.delete_messages(chat_id=chat, message_ids=msg_id)
        await message.reply("Message deleted.")
    except Exception as e:
        await message.reply(f"Error deleting message: {e}")

# region GET
@bot.on_message(filters.command("get"))
@pm_only
@admin_only
async def get_message_data_command(client: Client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            return await message.reply("Use: `get <chat_id> <msg_id>`")
        chat = int(parts[1])
        msg_id = int(parts[2])
    except (IndexError, ValueError):
        return await message.reply("Use: `get <chat_id> <msg_id>`")
    
    if chat not in CHAT_IDS:
        await message.reply(f"Chat `{chat}` not in `CHAT_IDS` list.")
        return

    try:
        target_message = await client.get_messages(chat, msg_id)
    except Exception as e:
        return await message.reply(f"No message with id: {e}")

    def serialize(obj):
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items() if not k.startswith("_")}
        elif hasattr(obj, "__dict__"):
            return serialize(obj.__dict__)
        else:
            try:
                return str(obj)  # fallback
            except:
                return "<unserializable>"

    clean_data = serialize(target_message)

    file_io = BytesIO()
    file_io.name = "get.json"
    file_io.write(json.dumps(clean_data, indent=2, ensure_ascii=False).encode("utf-8"))
    file_io.seek(0)

    await message.reply_document(file_io, caption=f"Message [#{msg_id}](https://t.me/c/{str(chat).lstrip('-100')}/{msg_id})")

# region START
@bot.on_message(filters.command("start"))
@pm_only
async def start_command(client: Client, message: Message):
    command_parts = message.command if message.command else []
    ad_id = -1
    if len(command_parts) > 1 and command_parts[0] == "start" and command_parts[1].startswith("contact_ad_"):
        try:
            ad_id = int(command_parts[1].split('_')[2])
            with SessionLocal() as db:
                ad = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad and ad.referrer and re.match(r"^\+7\d{10}$", ad.referrer):
                    response_text = f"Номер телефона для объявления \"__{ad.text.splitlines()[0]}__\": {ad.referrer}\n\n"
                    if ad.referrer_comment:
                        response_text += f"💬 Комментарий: __{ad.referrer_comment}__\n\n"
                    response_text += f"Вы можете нажать на номер телефона и написать/позвонить рекламодателю"

                    await message.reply(
                        response_text,
                        disable_web_page_preview=True
                    )
                else:
                    await message.reply("Не удалось найти объявление или контактную информацию.")
                user = message.from_user
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Открыть диалог", url=f"tg://user?id={user.id}")],
                    [InlineKeyboardButton("📃 Посмотреть объявление", callback_data=f'ad_view_{ad_id}')]
                ])
                for admin_id in ADMINS:
                    try:
                        st = str(ad.id)+' | __'+ad.text.splitlines()[0]+'__' if ad_id != -1 else ''
                        await client.send_message(admin_id, f"❗Пользователь отправил /start по обьявлению:\n{st}\n{'⭐ ' if user.is_premium else ''}{user.first_name} {user.last_name or ''}{' // @'+user.username+' // ' if user.username else ' // '}`{user.id}`", reply_markup=keyboard)
                    except Exception as e:
                        print(f"Could not send start message to admin {admin_id}: {e}")
            return
        except (ValueError, IndexError):
            await message.reply("Некорректная ссылка на объявление.")

    if message.from_user.id in ADMINS:
        await message.reply(f'Привет! Я бот для управления рекламными сообщениями.\n\n// Creator: @NoBanOnlyZXC')
    else:
        user = message.from_user
        await message.reply(f"🔑 Пользователь не является администратором, доступ ограничен.\n\n(ad) 🔥 Автоматическая реклама внизу чата за 200руб / день")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Открыть диалог", url=f"tg://user?id={user.id}")]
        ])
        for admin_id in ADMINS:
            try:
                await client.send_message(admin_id, f"❗Пользователь отправил /start\n{'⭐ ' if user.is_premium else ''}{user.first_name} {user.last_name or ''}{' // @'+user.username+' // ' if user.username else ' // '}`{user.id}`", reply_markup=keyboard)
            except Exception as e:
                print(f"Could not send start message to admin {admin_id}: {e}")

# region AD
@bot.on_message(filters.command("ad") & filters.reply)
@pm_only
@admin_only
async def add_ad_command(client: Client, message: Message):
    reply_to = message.reply_to_message
    if reply_to:
        photos = []
        text = ''
        
        if reply_to.media_group_id:
            mg = await reply_to.get_media_group()
            for pic in mg:
                photos.append({'file_id': pic.photo.file_id})
                text = pic.caption if pic.caption else (pic.text if pic.text else text)

        elif reply_to.photo:
            photo = reply_to.photo.file_id
            photos = [{'file_id': photo}]
            text = reply_to.caption if reply_to.caption else (reply_to.text if reply_to.text else text)
        elif reply_to.text:
            text = reply_to.text
        
        if not text and not photos:
            await message.reply("The replied message must contain text or a photo.")
            return

        referrer = None
        referrer_comment = None 
        original_text_lines = text.splitlines()

        if original_text_lines and original_text_lines[-2].strip().startswith("# "):
            referrer_comment = original_text_lines[-2].strip()[2:].strip()
            original_text_lines = original_text_lines[:-2]

        if original_text_lines:
            last_line = text.splitlines()[-1].strip()
            print(last_line)

            if last_line.startswith("@"):
                referrer = last_line[1:]
                original_text_lines = original_text_lines[:-1] # Remove username line from text
            elif last_line.startswith("+"):
                referrer = last_line

        text = "\n".join(original_text_lines).strip()

        with SessionLocal() as db:
            current_ads_count = db.query(Ad).count()
            if current_ads_count >= MAX_ADS:
                oldest_ad = db.query(Ad).order_by(Ad.date_added).first()
                if oldest_ad:
                    db.delete(oldest_ad)
                    db.commit()
            
            new_ad = Ad(
                text=text,
                photos=photos,
                referrer=referrer,
                referrer_comment=referrer_comment,
                admin_added=message.from_user.id
            )
            db.add(new_ad)
            db.commit()
            db.refresh(new_ad)

        await message.reply('Реклама добавлена')
        await send_ads()

# region ADS
@bot.on_message(filters.command("ads"))
@pm_only
@admin_only
async def ads_list_command(client: Client, message: Message):
    with SessionLocal() as db:
        ads_from_db = db.query(Ad).all()
        if len(ads_from_db) > 0:
            keyboard = InlineKeyboardMarkup([])
            for i, ad_item in enumerate(ads_from_db):
                marks = f'{"👤" if ad_item.referrer else ""}{"📝" if ad_item.referrer_comment else ""}{"🖼️"*len(ad_item.photos) if ad_item.photos else ""}'
                t = (ad_item.text[:27] + '...') if ad_item.text and len(ad_item.text) > 27 else (ad_item.text or "No text")
                button_text = f'{marks} {" | " if marks else ""} {t}'
                keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f'ad_view_{ad_item.id}')])
            await message.reply('**Активная реклама**\n👤 - Наличие реферера\n📝 - Наличие комментария\n🖼️ - Наличие картинок', reply_markup=keyboard)
        else:
            await message.reply('Нет рекламы.')

# region call:ad_view
@bot.on_callback_query(filters.regex(r"^ad_view_(\d+)$"))
async def ad_view_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[2])
    
    try:
        if not callback_query.message.text.startswith("❗️Пользователь отправил /start по обьявлению"):
            await callback_query.message.delete()
    except Exception as e:
        print(f"Не удалось удалить сообщение: {e}")
        await callback_query.answer("Не удалось удалить предыдущее сообщение.", show_alert=True)
        return

    with SessionLocal() as db:
        ad = db.query(Ad).filter(Ad.id == ad_id).first()
        if ad:
            kb1 = InlineKeyboardMarkup([
                [InlineKeyboardButton('❌ Удалить рекламу', callback_data=f'delete_ad_db_{ad_id}')],
                [InlineKeyboardButton('✏️ Изменить рекламу', callback_data=f'edit_ad_db_{ad_id}')],
                [InlineKeyboardButton('👤 Изменить реферала', callback_data=f'ref_ad_db_{ad_id}')],
                [InlineKeyboardButton('💬 Изменить комментарий', callback_data=f'edit_comment_ad_db_{ad_id}')]
            ])
            
            try:
                if ad.photos:
                    if isinstance(ad.photos, list) and ad.photos and 'file_id' in ad.photos[0]:
                        await client.send_photo(
                            chat_id=callback_query.message.chat.id,
                            photo=ad.photos[0]['file_id'],
                            caption=ad.text or "Без текста",
                            reply_markup=kb1
                        )
                    else:
                        await client.send_message(
                            chat_id=callback_query.message.chat.id,
                            text=ad.text or "Без текста (Ошибка с данными фото)",
                            reply_markup=kb1
                        )
                else:
                    await client.send_message(
                        chat_id=callback_query.message.chat.id,
                        text=ad.text or "Без текста",
                        reply_markup=kb1
                    )
            except Exception as e:
                print(f"Ошибка при отправке рекламы: {e}")
                await callback_query.answer("Не удалось отправить рекламу.")
                await client.send_message(
                    chat_id=callback_query.message.chat.id,
                    text=f"Произошла ошибка при отображении рекламы: {e}"
                )
        else:
            await callback_query.answer("Реклама не найдена.")

# region call:delete_ad
@bot.on_callback_query(filters.regex(r"^delete_ad_db_(\d+)$"))
async def delete_ad_db_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[3])
    with SessionLocal() as db:
        ad_to_delete = db.query(Ad).filter(Ad.id == ad_id).first()
        if ad_to_delete:
            db.delete(ad_to_delete)
            db.commit()
            await delete_old_ads()
            await send_ads()
            await callback_query.answer("Реклама удалена")
            await callback_query.message.delete()
            
            ads_from_db = db.query(Ad).all()
            if len(ads_from_db) > 0:
                keyboard = InlineKeyboardMarkup([])
                for i, ad_item in enumerate(ads_from_db):
                    marks = f'{"👤" if ad_item.referrer else ""}{"📝" if ad_item.referrer_comment else ""}{"🖼️"*len(ad_item.photos) if ad_item.photos else ""}'
                    t = (ad_item.text[:27] + '...') if ad_item.text and len(ad_item.text) > 27 else (ad_item.text or "No text")
                    button_text = f'{marks} {" | " if marks else ""} {t}'
                    keyboard.inline_keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f'ad_view_{ad_item.id}')])
                await callback_query.message.reply('**Активная реклама**\n👤 - Наличие реферера\n📝 - Наличие комментария\n🖼️ - Наличие картинок', reply_markup=keyboard)
            else:
                await callback_query.message.reply('Нет рекламы.')
        else:
            await callback_query.answer("Реклама не найдена.", show_alert=True)
            await callback_query.message.delete()

# region call:edit_ad
@bot.on_callback_query(filters.regex(r"^edit_ad_db_(\d+)$"))
@admin_only
async def edit_ad_db_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[3])
    user_id = callback_query.from_user.id

    await callback_query.answer()
    user_states[user_id] = {"action": "edit_ad", "ad_id": ad_id, "message_id": callback_query.message.id}
    
    await callback_query.message.reply("Отправьте новое сообщение, которое будет использоваться как реклама. Вы можете отправить текст или фото с подписью.")

# region call:ref_ad
@bot.on_callback_query(filters.regex(r"^ref_ad_db_(\d+)$"))
async def ref_ad_db_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[3])
    user_id = callback_query.from_user.id

    await callback_query.answer()
    
    user_states[user_id] = {"action": "edit_referrer", "ad_id": ad_id, "message_id": callback_query.message.id}

    await callback_query.message.reply("Отправьте @username или номер телефона (+7ХХХХХХХХХХ), который будет новым рефералом для этой рекламы. Или отправьте `/clear` для удаления реферала.")

# region call:edit_comment
@bot.on_callback_query(filters.regex(r"^edit_comment_ad_db_(\d+)$"))
@admin_only
async def edit_referrer_comment_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[4]) # Обратите внимание на индекс 4
    user_id = callback_query.from_user.id

    await callback_query.answer("Пожалуйста, отправьте новый комментарий для реферала. Начните сообщение с символа #, например: #Мой новый комментарий", show_alert=True)
    
    user_states[user_id] = {"action": "edit_referrer_comment", "ad_id": ad_id, "message_id": callback_query.message.id}
    
    await callback_query.message.reply_text("Отправьте новый комментарий к рефералу. Он будет отображаться вместе с номером телефона.\nНачните сообщение с символа `#`.")

# region Chats watchdog
@bot.on_message(filters.chat(CHAT_IDS) & (filters.text | filters.photo | filters.audio | filters.video | filters.document | filters.sticker | filters.animation | filters.voice))
async def new_message(client: Client, message: Message):
    global lock
    if message.chat.id in CHAT_IDS:
        if not lock:
            lock = True
            print(f"New message detected in {message.chat.id}. Deleting old ads and sending new ones.")
            await delete_old_ads()
            await asyncio.sleep(0.5)
            await send_ads()
            lock = False
        else:
            print(f"Lock is active, skipping ad cycle for message in {message.chat.id}.")

# region User states manager
@bot.on_message(filters.private & ~filters.command(["start", "ads", "ad", "get", "del", "adminme", "unadminme", "clear"]))
async def handle_user_state_message(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in user_states:
        state = user_states[user_id]
        action = state.get("action")
        ad_id = state.get("ad_id")
        original_message_id = state.get("message_id")

        if action == "edit_ad":
            photos_data = []
            text = ''

            if message.photo:
                photos_data = [{'file_id': message.photo.file_id}]
                text = message.caption if message.caption else ''
            elif message.text:
                text = message.text
            
            if not text and not photos_data:
                await message.reply("Не удалось распознать текст или фото. Попробуйте еще раз.")
                return

            referrer = None
            referrer_comment = None
            processed_text_lines = []

            original_text_lines = text.splitlines()
            
            if original_text_lines and original_text_lines[-1].strip().startswith("#"):
                referrer_comment = original_text_lines[-1].strip()[1:].strip()
                original_text_lines = original_text_lines[:-1]

            if original_text_lines:
                last_line = original_text_lines[-1].strip()

                if last_line.startswith("@"):
                    referrer = last_line[1:]
                    original_text_lines = original_text_lines[:-1]
                elif re.match(r"^\+7\d{10}$", last_line):
                    referrer = last_line

            text = "\n".join(original_text_lines).strip()

            with SessionLocal() as db:
                ad_to_update = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad_to_update:
                    ad_to_update.text = text
                    ad_to_update.photos = photos_data
                    if referrer is not None: 
                        ad_to_update.referrer = referrer
                    if referrer_comment is not None: 
                        ad_to_update.referrer_comment = referrer_comment
                    
                    db.commit()
                    await message.reply("Реклама успешно изменена!")
                    await delete_old_ads()
                    await send_ads()
                else:
                    await message.reply("Ошибка: Реклама не найдена.")

            del user_states[user_id]
            try:
                if original_message_id:
                    await client.delete_messages(chat_id=message.chat.id, message_ids=original_message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение с кнопками: {e}")

        elif action == "edit_referrer":
            new_referrer = message.text.strip()
            
            if new_referrer == "/clear":
                new_referrer = None
                await message.reply("Реферер успешно удален.")
            elif new_referrer.startswith("@"):
                new_referrer = new_referrer[1:]
                await message.reply(f"Реферер успешно изменен на: @{new_referrer}")
            elif re.match(r"^\+7\d{10}$", new_referrer):
                await message.reply(f"Реферер успешно изменен на: {new_referrer}")
            else:
                await message.reply("Неверный формат реферала. Используйте @username или +7ХХХХХХХХХХ, или /clear.")
                return

            with SessionLocal() as db:
                ad_to_update = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad_to_update:
                    ad_to_update.referrer = new_referrer
                    db.commit()
                    await delete_old_ads()
                    await send_ads()
                else:
                    await message.reply("Ошибка: Реклама не найдена.")
            
            del user_states[user_id]
            try:
                if original_message_id:
                    await client.delete_messages(chat_id=message.chat.id, message_ids=original_message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение с кнопками: {e}")
        elif action == "edit_referrer_comment":
            new_comment_text = message.text.strip()
            if not new_comment_text.startswith("#"):
                await message.reply_text("Комментарий должен начинаться с символа #. Попробуйте еще раз или используйте /clear для отмены.")
                return
            new_comment = new_comment_text[2:].strip()

            with SessionLocal() as db:
                ad_to_update = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad_to_update:
                    ad_to_update.referrer_comment = new_comment
                    db.commit()
                    await message.reply_text("Комментарий успешно обновлен!")
                    await delete_old_ads()
                    await send_ads()
                else:
                    await message.reply_text("Ошибка: Реклама не найдена.")
            
            del user_states[user_id]
            try:
                if original_message_id:
                    await client.delete_messages(chat_id=message.chat.id, message_ids=original_message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение с кнопками: {e}")
    pass

# region CLEAR
@bot.on_message(filters.command("clear") & filters.private)
@admin_only
async def clear_state_command(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_states:
        state = user_states[user_id]
        if state.get("action") == "edit_referrer":
            ad_id = state.get("ad_id")
            with SessionLocal() as db:
                ad_to_update = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad_to_update:
                    ad_to_update.referrer = None
                    db.commit()
                    await message.reply("Реферер для этой рекламы успешно удален.")
                    await delete_old_ads()
                    await send_ads()
                else:
                    await message.reply("Ошибка: Реклама не найдена.")
        else:
            await message.reply("Ваше текущее действие было сброшено.")
        del user_states[user_id]
        try:
            if state.get("message_id"):
                await client.delete_messages(chat_id=message.chat.id, message_ids=state["message_id"])
        except Exception as e:
            print(f"Не удалось удалить сообщение с кнопками при /clear: {e}")
    else:
        await message.reply("Нет активных действий для сброса.")

# region bot.run()
if __name__ == '__main__':
    bot.run()