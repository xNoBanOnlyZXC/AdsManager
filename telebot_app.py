from telebot import TeleBot, types
import io, time, os, json

TOKEN = 'token'
CHAT_ID = -100
ADMINS = []
ADS_FILE = 'ads.json'
LAST_FILE = 'last.dict'
MAX_ADS = 3

bot = TeleBot(TOKEN)

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

def save_last():
    with open(LAST_FILE, 'w', encoding='utf-8') as f:
        json.dump(last_ad_message_ids, f, indent=4, ensure_ascii=False)

ads = load_ads()
last_ad_message_ids = load_last()

def admin_only(func):
    def wrapper(message: types.Message):
        if message.from_user.id in ADMINS:
            return func(message)
        else:
            bot.set_message_reaction(message.chat.id, message.id, [types.ReactionTypeEmoji('👎')], is_big=False)
    return wrapper

def pm_only(func):
    def wrapper(message: types.Message):
        if message.chat.type == 'private':
            return func(message)
        else:
            bot.set_message_reaction(message.chat.id, message.id, [types.ReactionTypeEmoji('👎')], is_big=False)
    return wrapper

@bot.message_handler(commands=['start'])
@pm_only
def start(message: types.Message):
    if message.from_user.id in ADMINS:
        bot.send_message(message.chat.id, f'Привет! Я бот для управления рекламными сообщениями.\nМои команды:\n\n/ad (в ответ на сообщение) - добавить рекламное сообщение (максимум 1 картинка)\n/ads - список реклам (максимум - {MAX_ADS})\n/this (в ответ на сообщение) - отправит this.txt с полными данными сообщения на которое ответили\n\nБот создан @NoBanOnlyZXC')
    else:
        user = message.from_user
        bot.send_message(message.chat.id, f"🔑 Пользователь не является администратором, доступ ограничен.\n")
        for admin in ADMINS:
            bot.send_message(admin, f"❗ Пользователь нажал /start\n{'⭐ ' if user.is_premium else ''}{user.first_name} {user.last_name}\n{'@'+user.username if user.username else 'No username'}\nid: {user.id}")

@bot.message_handler(commands=['fp'])
@admin_only
def firstpic(message: types.Message):
    m = message.reply_to_message
    m.photo.reverse()
    bot.send_photo(message.chat.id, m.photo[0].file_id)

def otod(obj):
    if hasattr(obj, "__dict__"):
        return {k: otod(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [otod(i) for i in obj]
    else:
        return obj
    
def otod2(obj):
    if hasattr(obj, "__dict__"):
        return {
            k: otod2(v) 
            for k, v in obj.__dict__.items() 
            if v is not None
        }
    elif isinstance(obj, list):
        return [otod2(i) for i in obj]
    else:
        return obj

@bot.message_handler(commands=['this'])
@admin_only
def this(message: types.Message):
    if message.reply_to_message:
        if '-f' in message.text:
            make = otod
        else:
            make = otod2
        file_io = io.StringIO(json.dumps(make(message.reply_to_message), indent=4, ensure_ascii=False))
        bot.send_document(
            message.chat.id,
            document=io.BytesIO(file_io.getvalue().encode('utf-8')),
            visible_file_name=f'{message.reply_to_message.content_type}.txt'
        )
    else:
        bot.send_message(message.chat.id, "Эта команда должна быть ответом на сообщение.")

@bot.message_handler(commands=['del'])
@admin_only
@pm_only
def deletemessage(message: types.Message):
    id = message.text.split()[1]
    if id:
        bot.delete_message(CHAT_ID, int(id.strip()))
        bot.send_message(message.chat.id, f"Сообщение {id} удалено")

def get_media_group(message: types.Message):
    mgi = message.media_group_id
    if not mgi:
        return False
    
    bot.get_message()

@bot.message_handler(commands=['ad'])
@admin_only
@pm_only
def ad(message: types.Message):
    reply_to = message.reply_to_message
    if reply_to: # and reply_to.content_type == 'photo'
        photos = []
        get_media_group(reply_to)
        # for photo in reply_to.photo:
        #     photos.append({
        #         'file_id': photo.file_id,
        #         'file_unique_id': photo.file_unique_id
        #     })
        if reply_to.photo:
            reply_to.photo.reverse()
            photo = reply_to.photo[0]
            photos = [{'file_id': photo.file_id}]
        ad_data = {
            'text': reply_to.caption if reply_to.caption else (reply_to.text if reply_to.text else ''),
            'photos': photos,
            'refferer': None
        }
        ads.append(ad_data)
        if len(ads) > MAX_ADS:
            ads.pop(0)
        save_ads(ads)
        bot.send_message(message.chat.id, 'Реклама добавлена!')
        send_ads()

@bot.message_handler(commands=['ads'])
@admin_only
@pm_only
def ads_command(message: types.Message):
    if len(ads) > 0:
        keyboard = types.InlineKeyboardMarkup()
        for i, ad in enumerate(ads):
            button_text = (ad['text'][:27] + '...') if len(ad['text']) > 27 else ad['text']
            keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=f'ad_{i}'))
        bot.send_message(message.chat.id, 'Выберите рекламу:', reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, 'Нет рекламы')

def send_ads():
    global last_ad_sent_time, last_ad_message_ids
    last_ad_message_ids.clear()
    save_last()

    ref_kb = types.InlineKeyboardMarkup([
                    [types.InlineKeyboardButton('✏️ Написать', )],
             ])

    for ad in ads:
        if ad['photos']:
            media_group = []
            for photo in ad['photos']:
                media_group.append(types.InputMediaPhoto(media=photo['file_id']))
            if ad['text']:
                media_group[0].caption = ad['text']
            sent_messages = bot.send_media_group(chat_id=CHAT_ID, media=media_group)
            last_ad_message_ids.extend([msg.message_id for msg in sent_messages])
            save_last()
        else:
            sent_message = bot.send_message(chat_id=CHAT_ID, text=ad['text'])
            last_ad_message_ids.append(sent_message.message_id)
            save_last()

def delete_old_ads():
    global last_ad_message_ids
    for message_id in last_ad_message_ids:
        try:
            bot.delete_message(chat_id=CHAT_ID, message_id=message_id)
        except:
            pass

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: types.CallbackQuery):
    try:
        if call.data.startswith('ad_'):
            ad_index = int(call.data.split('_')[1])
            kb1 = types.InlineKeyboardMarkup([
                    [types.InlineKeyboardButton('Удалить рекламу', callback_data=f'delete_ad_{ad_index}')],
                    [types.InlineKeyboardButton('Изменить рекламу', callback_data=f'edit_ad_{ad_index}')],
                    [types.InlineKeyboardButton('Изменить реферала', callback_data=f'ref_ad_{ad_index}')]
                ])
            ad = ads[ad_index]
            if ad['photos']:
                bot.edit_message_media(media=types.InputMediaPhoto(media=ad['photos'][0]['file_id'], caption=ad['text']), chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb1)
            else:
                bot.edit_message_text(text=ad['text'], chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb1)
        elif call.data.startswith('delete_ad_'):
            ad_index = int(call.data.split('_')[2])
            ads.pop(ad_index)
            save_ads(ads)
            delete_old_ads()
            send_ads()
            bot.answer_callback_query(call.id, "Реклама удалена!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
        elif call.data.startswith('edit_ad_'):
            ad_index = int(call.data.split('_')[2])
            bot.send_message(call.message.chat.id, f'Отправьте новое сообщение для рекламы {ad_index + 1}:')
            bot.register_next_step_handler(call.message, edit_ad, ad_index)
        elif call.data.startswith('ref_ad_'):
            ad_index = int(call.data.split('_')[2])
            bot.send_message(call.message.chat.id, f'Отправьте юзернейм реферала для рекламы {ad_index + 1}:')
            bot.register_next_step_handler(call.message, edit_ad, ad_index, True)

    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

def edit_ad(message: types.Message, ad_index: int, ref: bool):
    reply_to = message.reply_to_message
    if reply_to and reply_to.content_type == 'photo':
        photos = []
        for photo in reply_to.photo:
            photos.append({
                'file_id': photo.file_id,
                'file_unique_id': photo.file_unique_id
            })
        old_ad_data = ads[ad_index]
        ad_data = {
            'text': reply_to.caption if reply_to.caption else "",
            'photos': photos,
            'refferer': message.text if ref else old_ad_data.get("refferer", None)
        }
        ads[ad_index] = ad_data
        save_ads(ads)
        delete_old_ads()
        send_ads()
        bot.send_message(message.chat.id, 'Реклама изменена!')

lock = False

@bot.message_handler(func=lambda message: message.chat.id == CHAT_ID, content_types=['text', 'photo', 'audio', 'video', 'document', 'sticker', 'animation'])
def new_message(message: types.Message):
    global lock
    if not lock:
        lock = True
        delete_old_ads()
        time.sleep(.5)
        send_ads()
        lock = False

if __name__ == '__main__':
    bot.polling(none_stop=True)