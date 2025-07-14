from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, InputMediaPhoto
from pyrogram.enums import ChatType
from models import Base, Ad, LastAds, Settings
from pyrogram import Client, filters, enums
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound
from sqlalchemy import create_engine
import json, asyncio, pyrofix, re
from io import BytesIO
import time

# 0 / 1
TESTMODE = 0

API_ID = 1234
API_HASH = 'your hash'

TOKEN = [
    'main',
    'test'
][TESTMODE]

NAME = [
    "main",
    "test"
][TESTMODE]

engine = create_engine(f'sqlite:///{NAME}.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

bot = Client(NAME, api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

user_states = {}
lock = {}

MAX_ADS = 5

last_resend_time = 0
RESEND_COOLDOWN = 10

def get_setting(key, default_value=None):
    with SessionLocal() as db:
        try:
            setting = db.query(Settings).filter(Settings.key == key).one()
            if isinstance(setting.value, str):
                try:
                    return json.loads(setting.value)
                except json.JSONDecodeError:
                    pass
            return setting.value
        except NoResultFound:
            return default_value
        except Exception as e:
            print(f"Error getting setting {key}: {e}")
            return default_value

def set_setting(key, value):
    with SessionLocal() as db:
        try:
            setting = db.query(Settings).filter(Settings.key == key).one()
            if isinstance(value, (list, dict)):
                setting.value = json.dumps(value)
            else:
                setting.value = value
        except NoResultFound:
            if isinstance(value, (list, dict)):
                new_setting = Settings(key=key, value=json.dumps(value))
            else:
                new_setting = Settings(key=key, value=value)
            db.add(new_setting)
        db.commit()

all_chats_db = get_setting('all_chats')
active_chats_db = get_setting('active_chats')

if all_chats_db is None or active_chats_db is None:
    CHAT_IDS_INITIAL = [
        [],
        []
    ][TESTMODE]
    set_setting('all_chats', CHAT_IDS_INITIAL)
    set_setting('active_chats', CHAT_IDS_INITIAL)
    print("Инициализировал настройки чатов из хардкода.")

CHAT_IDS = get_setting('all_chats')
ACTIVE_CHAT_IDS = get_setting('active_chats')

admins_db = get_setting('admins')
test_admins_db = get_setting('test_admins')

if admins_db is None:
    set_setting('admins', [])
if test_admins_db is None:
    set_setting('test_admins', [])
    print("Инициализировал списки админов из хардкода.")

ADMINS = get_setting('admins' if TESTMODE == 0 else 'test_admins')

lock = {cid: False for cid in ACTIVE_CHAT_IDS}
print(f"Админы: {ADMINS}")
print(f"Активные чаты: {ACTIVE_CHAT_IDS}")
print(f"Все чаты: {CHAT_IDS}")

def admin_only(func):
    async def wrapper(client: Client, message: Message):
        if message.from_user.id in ADMINS:
            return await func(client, message)
        else:
            await message.reply("🚫 Admin only", quote=True)
            return
    return wrapper

def admin_only_callback(func):
    async def wrapper(client: Client, callback_query: CallbackQuery):
        if callback_query.from_user.id in ADMINS:
            return await func(client, callback_query)
        else:
            await callback_query.answer("🚫 Admin only")
    return wrapper

def testmode_only(func):
    async def wrapper(client: Client, message: Message):
        if TESTMODE:
            return await func(client, message)
        else:
            await message.reply("🚫 In test only", quote=True)
            return
    return wrapper

def pm_only(func):
    async def wrapper(client: Client, message: Message):
        if message.chat.type == enums.ChatType.PRIVATE:
            return await func(client, message)
        else:
            await message.reply("🚫 PM only", quote=True)
            return
    return wrapper

async def send_ads(CHAT_ID):
    with SessionLocal() as db:
        ads_from_db = db.query(Ad).all()
        last_ads_in_chat = []
        for ad in ads_from_db:
            ad_buttons = []
            if ad.referrer:
                if ad.referrer.startswith("+"):
                    ref = ad.referrer[:5]+'*****'+ad.referrer[10:]
                else:
                    ref = "@"+ad.referrer
                ad_buttons.append([InlineKeyboardButton(f"✍️ Написать ({ref})", url=f"https://t.me/{ad.referrer}")])
                if ad.referrer.startswith("+"):
                    ad_buttons.append([InlineKeyboardButton(f"📞 Позвонить ({ref})", url=f"https://t.me/{bot.me.username}?start=contact_ad_{ad.id}")])

            reply_markup = InlineKeyboardMarkup(ad_buttons) if ad_buttons else None
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

async def delete_old_ads(CHAT_ID):
    with SessionLocal() as db:
        last_ads_entry = db.query(LastAds).filter(LastAds.chat_id == CHAT_ID).first()
        if last_ads_entry and last_ads_entry.messages:
            for message_id in last_ads_entry.messages:
                try:
                    await bot.delete_messages(chat_id=CHAT_ID, message_ids=message_id)
                except Exception as e:
                    print(f"Error deleting message {message_id} in chat {CHAT_ID}: {e}")
            db.delete(last_ads_entry)
            db.commit()

@bot.on_message(filters.command("admin") & filters.private)
@admin_only
async def add_admin_command(client: Client, message: Message):
    global ADMINS
    try:
        user_id = int(message.command[1])
        if user_id not in ADMINS:
            ADMINS.append(user_id)
            set_setting('admins' if TESTMODE == 0 else 'test_admins', ADMINS)
            await message.reply(f"✅ Пользователь с ID `{user_id}` успешно добавлен в админы.")
        else:
            await message.reply(f"🚫 Пользователь с ID `{user_id}` уже является админом.")
    except (IndexError, ValueError):
        await message.reply("Используйте: `/admin <user_id>`")

@bot.on_message(filters.command("unadmin") & filters.private)
@admin_only
async def remove_admin_command(client: Client, message: Message):
    global ADMINS
    try:
        user_id = int(message.command[1])
        if user_id in ADMINS:
            ADMINS.remove(user_id)
            set_setting('admins' if TESTMODE == 0 else 'test_admins', ADMINS)
            await message.reply(f"✅ Пользователь с ID `{user_id}` успешно удален из админов.")
        else:
            await message.reply(f"🚫 Пользователь с ID `{user_id}` не является админом.")
    except (IndexError, ValueError):
        await message.reply("Используйте: `/unadmin <user_id>`")

@bot.on_message(filters.command("adminme"))
@testmode_only
async def adminme(client: Client, message: Message):
    global ADMINS
    if message.from_user.id not in ADMINS:
        ADMINS.append(message.from_user.id)
        set_setting('admins' if TESTMODE == 0 else 'test_admins', ADMINS)
        await message.reply("✅ Done", quote=True)
    else:
        await message.reply("🚫 You are already an admin", quote=True)

@bot.on_message(filters.command("unadminme"))
@testmode_only
@admin_only
async def unadminme(client: Client, message: Message):
    global ADMINS
    if message.from_user.id in ADMINS:
        ADMINS.remove(message.from_user.id)
        set_setting('admins' if TESTMODE == 0 else 'test_admins', ADMINS)
        await message.reply("✅ Done", quote=True)
    else:
        await message.reply("🚫 You are not an admin", quote=True)

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
                return str(obj)
            except:
                return "<unserializable>"

    clean_data = serialize(target_message)
    file_io = BytesIO()
    file_io.name = "get.json"
    file_io.write(json.dumps(clean_data, indent=2, ensure_ascii=False).encode("utf-8"))
    file_io.seek(0)
    await message.reply_document(file_io, caption=f"Message [#{msg_id}](https://t.me/c/{str(chat).lstrip('-100')}/{msg_id})")

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
                original_text_lines = original_text_lines[:-1]
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

        for chat in ACTIVE_CHAT_IDS:
            await delete_old_ads(chat)
            await asyncio.sleep(0.5)
            await send_ads(chat)
        await message.reply('Реклама добавлена')


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
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔄️ Переотправить рекламу", callback_data='resend_ads')])
            await message.reply('**Активная реклама**\n👤 Наличие реферера\n📝 Наличие комментария\n🖼️ Наличие картинок', reply_markup=keyboard)
        else:
            await message.reply('Нет рекламы.')

async def update_chats_message(client: Client, query_object):
    is_callback = isinstance(query_object, CallbackQuery)
    message = query_object.message if is_callback else query_object

    temp_message = message if not is_callback else None
    
    if is_callback:
        await query_object.answer("Обновляю список чатов...")
    else:
        temp_message = await message.reply("Получаю информацию о чатах...")

    keyboard_buttons = []
    
    all_chats_db = get_setting('all_chats', [])
    active_chats_db = get_setting('active_chats', [])
    
    if not all_chats_db:
        if temp_message: await temp_message.edit_text("Список управляемых чатов пуст.")
        return
    
    for chat_id in all_chats_db:
        try:
            chat = await client.get_chat(chat_id)
            chat_name = chat.title if chat.title else chat.first_name
            chat_type_display = chat.type.name.capitalize()
            
            is_active = chat.id in active_chats_db
            status_text = "🟢 Активен" if is_active else "🔴 Неактивен"
            # action_text = "Деактивировать" if is_active else "Активировать"
            callback_data = f"togglechat_{chat.id}"
            
            row_actions = []
            if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                row_actions.append(InlineKeyboardButton("Покинуть", callback_data=f"leavechat_{chat.id}"))
            
            row_actions.append(InlineKeyboardButton(status_text, callback_data=callback_data))
            
            keyboard_buttons.append([InlineKeyboardButton(f"{chat_name} (ID: {chat.id} | Тип: {chat_type_display})", callback_data="ignore")])
            # keyboard_buttons.append([InlineKeyboardButton(status_text, callback_data="ignore")])
            keyboard_buttons.append(row_actions)
            
        except Exception as e:
            keyboard_buttons.append([InlineKeyboardButton(f"Недоступный чат (ID: {chat_id})", callback_data="ignore")])
            keyboard_buttons.append([InlineKeyboardButton("Удалить из списка", callback_data=f"remove_from_all_{chat_id}")])
            print(f"Ошибка при получении информации о чате {chat_id}: {e}")

    if not keyboard_buttons:
        if temp_message: await temp_message.edit_text("Не удалось получить информацию ни по одному чату из списка.")
        return

    if is_callback:
        await message.edit_text("Список управляемых чатов:", reply_markup=InlineKeyboardMarkup(keyboard_buttons))
    else:
        await temp_message.edit_text("Список управляемых чатов:", reply_markup=InlineKeyboardMarkup(keyboard_buttons))

@bot.on_message(filters.command("chats"))
@pm_only
@admin_only
async def chatslist(client: Client, message: Message):
    await update_chats_message(client, message)

@bot.on_message(filters.new_chat_members)
async def new_chat_members_handler(client: Client, message: Message):
    global CHAT_IDS, ACTIVE_CHAT_IDS
    for member in message.new_chat_members:
        if member.id == client.me.id:
            chat_id = message.chat.id
            
            all_chats_db = get_setting('all_chats', [])
            if chat_id not in all_chats_db:
                all_chats_db.append(chat_id)
                set_setting('all_chats', all_chats_db)
                CHAT_IDS = all_chats_db
            
            print(f"Бот добавлен в новый чат! ID: {chat_id}, Название: {message.chat.title}")
            for admin_id in ADMINS:
                try:
                    await client.send_message(admin_id, f"Бот добавлен в новый чат\nID: {chat_id}\nНазвание: {message.chat.title}")
                except Exception as e:
                    print(f"Could not send start message to admin {admin_id}: {e}")
            await message.reply(f"Спасибо, что добавили меня в чат!\nЭтот чат был автоматически добавлен в список неактивных.")

@bot.on_callback_query(filters.regex(r"^ad_view_(\d+)$"))
async def ad_view_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[2])
    try:
        if not callback_query.message.text.startswith("❗Пользователь отправил /start по обьявлению"):
            await callback_query.message.delete()
    except Exception as e:
        print(f"Не удалось удалить предыдущее сообщение: {e}")
        await callback_query.answer("Не удалось удалить предыдущее сообщение.")
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

@bot.on_callback_query(filters.regex(r"^delete_ad_db_(\d+)$"))
async def delete_ad_db_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[3])
    with SessionLocal() as db:
        ad_to_delete = db.query(Ad).filter(Ad.id == ad_id).first()
        if ad_to_delete:
            db.delete(ad_to_delete)
            db.commit()
            for chat in ACTIVE_CHAT_IDS:
                await delete_old_ads(chat)
                await send_ads(chat)
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
                keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔄️ Переотправить рекламу", callback_data='resend_ads')])
                await callback_query.message.reply('**Активная реклама**\n👤 - Наличие реферера\n📝 - Наличие комментария\n🖼️ - Наличие картинок', reply_markup=keyboard)
            else:
                await callback_query.message.reply('Нет рекламы.')
        else:
            await callback_query.answer("Реклама не найдена.")
            await callback_query.message.delete()

@bot.on_callback_query(filters.regex(r"^edit_ad_db_(\d+)$"))
@admin_only_callback
async def edit_ad_db_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[3])
    user_id = callback_query.from_user.id
    await callback_query.answer()
    user_states[user_id] = {"action": "edit_ad", "ad_id": ad_id, "message_id": callback_query.message.id}
    await callback_query.message.reply("Отправьте новое сообщение, которое будет использоваться как реклама. Вы можете отправить текст или фото с подписью.")

@bot.on_callback_query(filters.regex(r"^ref_ad_db_(\d+)$"))
@admin_only_callback
async def ref_ad_db_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[3])
    user_id = callback_query.from_user.id
    await callback_query.answer()
    user_states[user_id] = {"action": "edit_referrer", "ad_id": ad_id, "message_id": callback_query.message.id}
    await callback_query.message.reply("Отправьте @username или номер телефона (+7ХХХХХХХХХХ), который будет новым рефералом для этой рекламы. Или отправьте `/clear` для удаления реферала.")

@bot.on_callback_query(filters.regex(r"^edit_comment_ad_db_(\d+)$"))
@admin_only_callback
async def edit_referrer_comment_callback(client: Client, callback_query: CallbackQuery):
    ad_id = int(callback_query.data.split('_')[4])
    user_id = callback_query.from_user.id
    await callback_query.answer("Пожалуйста, отправьте новый комментарий для реферала. Начните сообщение с символа \"# \", например: # Мой новый комментарий")
    user_states[user_id] = {"action": "edit_referrer_comment", "ad_id": ad_id, "message_id": callback_query.message.id}
    await callback_query.message.reply_text("Отправьте новый комментарий к рефералу. Он будет отображаться вместе с номером телефона.\nНачните сообщение с символа \"# \".")

@bot.on_callback_query(filters.regex(r"^togglechat_(\-?\d+)$"))
@admin_only_callback
async def toggle_chat_callback(client: Client, callback_query: CallbackQuery):
    global ACTIVE_CHAT_IDS, lock
    chat_id = int(callback_query.matches[0].group(1))
    active_chats_db = get_setting('active_chats', [])

    if chat_id in active_chats_db:
        active_chats_db.remove(chat_id)
        message = f"Чат `{chat_id}` деактивирован."
        await delete_old_ads(chat_id) 
    else:
        active_chats_db.append(chat_id)
        message = f"Чат `{chat_id}` активирован."
        await delete_old_ads(chat_id)
        await asyncio.sleep(0.5)
        await send_ads(chat_id)

    set_setting('active_chats', active_chats_db)
    ACTIVE_CHAT_IDS = active_chats_db
    lock = {cid: False for cid in ACTIVE_CHAT_IDS}

    await callback_query.answer(message)
    await update_chats_message(client, callback_query)

@bot.on_callback_query(filters.regex(r"^leavechat_(\-?\d+)$"))
@admin_only_callback
async def leave_chat_callback(client: Client, callback_query: CallbackQuery):
    global CHAT_IDS, ACTIVE_CHAT_IDS, lock
    chat_id = int(callback_query.matches[0].group(1))
    
    try:
        await client.leave_chat(chat_id)
        
        all_chats_db = get_setting('all_chats', [])
        if chat_id in all_chats_db:
            all_chats_db.remove(chat_id)
            set_setting('all_chats', all_chats_db)
            CHAT_IDS = all_chats_db

        active_chats_db = get_setting('active_chats', [])
        if chat_id in active_chats_db:
            active_chats_db.remove(chat_id)
            set_setting('active_chats', active_chats_db)
            ACTIVE_CHAT_IDS = active_chats_db
            
        lock = {cid: False for cid in ACTIVE_CHAT_IDS}
        
        await callback_query.answer(f"Успешно покинул чат: {chat_id} и удалил его из списка.")
        await update_chats_message(client, callback_query)

    except Exception as e:
        await callback_query.answer(f"Ошибка при попытке покинуть чат: {e}")
        
@bot.on_callback_query(filters.regex(r"^remove_from_all_(\-?\d+)$"))
@admin_only_callback
async def remove_from_all_callback(client: Client, callback_query: CallbackQuery):
    global CHAT_IDS, ACTIVE_CHAT_IDS
    chat_id = int(callback_query.matches[0].group(1))
    
    all_chats_db = get_setting('all_chats', [])
    if chat_id in all_chats_db:
        all_chats_db.remove(chat_id)
        set_setting('all_chats', all_chats_db)
        CHAT_IDS = all_chats_db
    
    active_chats_db = get_setting('active_chats', [])
    if chat_id in active_chats_db:
        active_chats_db.remove(chat_id)
        set_setting('active_chats', active_chats_db)
        ACTIVE_CHAT_IDS = active_chats_db

    await callback_query.answer(f"Чат {chat_id} удален из списка всех чатов.")
    await update_chats_message(client, callback_query)

@bot.on_callback_query(filters.regex("^resend_ads$"))
@admin_only_callback
async def resend_ads_callback(client: Client, callback_query: CallbackQuery):
    global last_resend_time, RESEND_COOLDOWN
    current_time = time.time()

    if current_time - last_resend_time < RESEND_COOLDOWN:
        remaining_time = int(RESEND_COOLDOWN - (current_time - last_resend_time))
        await callback_query.answer(f"Пожалуйста, подождите {remaining_time} секунд перед повторной отправкой.", show_alert=True)
        return

    last_resend_time = current_time

    await callback_query.answer("Переотправляю рекламу во все активные чаты...")
    for chat in ACTIVE_CHAT_IDS:
        await delete_old_ads(chat)
        await asyncio.sleep(0.5)
        await send_ads(chat)
    await callback_query.message.reply("Реклама переотправлена во все активные чаты.")

@bot.on_message((filters.group) & (filters.text | filters.photo | filters.audio | filters.video | filters.document | filters.sticker | filters.animation | filters.voice))
async def new_message(client: Client, message: Message):
    global lock, ACTIVE_CHAT_IDS
    chat_id = message.chat.id
    
    if chat_id not in ACTIVE_CHAT_IDS:
        return

    if not lock.get(chat_id, False):
        lock[chat_id] = True
        print(f"New message detected in {chat_id}. Deleting old ads and sending new ones.")
        try:
            await delete_old_ads(chat_id)
            await asyncio.sleep(0.5)
            await send_ads(chat_id)
        except Exception as e:
            print(f"Error in ad cycle for chat {chat_id}: {e}")
        finally:
            lock[chat_id] = False
    else:
        print(f"Lock is active, skipping ad cycle for message in {chat_id}.")

@bot.on_message(filters.private & ~filters.command(["start", "ads", "ad", "get", "del", "adminme", "unadminme", "clear", "admin", "unadmin", "chats"]))
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
                    if referrer is not None: ad_to_update.referrer = referrer
                    if referrer_comment is not None: ad_to_update.referrer_comment = referrer_comment
                    db.commit()
                    await message.reply("Реклама успешно изменена!")
                    for chat in ACTIVE_CHAT_IDS:
                        await delete_old_ads(chat)
                        await send_ads(chat)
                else:
                    await message.reply("Ошибка: Реклама не найдена.")
            del user_states[user_id]
            try:
                if original_message_id: await client.delete_messages(chat_id=message.chat.id, message_ids=original_message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение с кнопками: {e}")

        elif action == "edit_referrer":
            new_referrer = message.text.strip()
            if new_referrer == "/clear": new_referrer = None
            elif new_referrer.startswith("@"): new_referrer = new_referrer[1:]
            elif not re.match(r"^\+7\d{10}$", new_referrer):
                await message.reply("Неверный формат реферала. Используйте @username, +7ХХХХХХХХХХ, или /clear.")
                return
            with SessionLocal() as db:
                ad_to_update = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad_to_update:
                    ad_to_update.referrer = new_referrer
                    db.commit()
                    await message.reply(f"Реферер успешно изменен на: {new_referrer if new_referrer else 'нет'}")
                    for chat in ACTIVE_CHAT_IDS:
                        await delete_old_ads(chat)
                        await send_ads(chat)
                else:
                    await message.reply("Ошибка: Реклама не найдена.")
            del user_states[user_id]
            try:
                if original_message_id: await client.delete_messages(chat_id=message.chat.id, message_ids=original_message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение с кнопками: {e}")
        elif action == "edit_referrer_comment":
            new_comment_text = message.text.strip()
            if not new_comment_text.startswith("#"):
                await message.reply_text("Комментарий должен начинаться с символа #. Попробуйте еще раз.")
                return
            new_comment = new_comment_text[1:].strip()
            with SessionLocal() as db:
                ad_to_update = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad_to_update:
                    ad_to_update.referrer_comment = new_comment
                    db.commit()
                    await message.reply_text("Комментарий успешно обновлен!")
                    for chat in ACTIVE_CHAT_IDS:
                        await delete_old_ads(chat)
                        await send_ads(chat)
                else:
                    await message.reply_text("Ошибка: Реклама не найдена.")
            del user_states[user_id]
            try:
                if original_message_id: await client.delete_messages(chat_id=message.chat.id, message_ids=original_message_id)
            except Exception as e:
                print(f"Не удалось удалить сообщение с кнопками: {e}")
    else:
        await message.reply("Нет активных команд. Используйте `/ads` для просмотра рекламы или `/chats` для управления чатами.", quote=True)


@bot.on_message(filters.command("clear") & filters.private)
@admin_only
async def clear_state_command(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_states:
        state = user_states[user_id]
        if state.get("action") == "edit_referrer" and message.text == "/clear":
            ad_id = state.get("ad_id")
            with SessionLocal() as db:
                ad_to_update = db.query(Ad).filter(Ad.id == ad_id).first()
                if ad_to_update:
                    ad_to_update.referrer = None
                    db.commit()
                    await message.reply("Реферер для этой рекламы успешно удален.")
                    for chat in ACTIVE_CHAT_IDS:
                        await delete_old_ads(chat)
                        await send_ads(chat)
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

if __name__ == '__main__':
    bot.run()