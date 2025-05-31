import telebot
from telebot import types
import json
import os
import logging
import time
import flask

# Logging ayarları
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # __name__ KULLANILDI

# --- Yapılandırma ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or '8128882254:AAEZ_6OicThy8hlo-k4JShBlsatOyqzRhBY' # Token'ınızı buraya girin
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# Webhook ayarları
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_LISTEN = '0.0.0.0'

WEBHOOK_URL_PATH = f"/{TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_URL_PATH}" if WEBHOOK_HOST else None

# Flask app instance
app = flask.Flask(__name__) # __name__ KULLANILDI

# --- Sabitler ve Veri Dosyası ---
SUPER_ADMIN_ID = 7877979174 # KENDİ TELEGRAM ID'NİZİ GİRİN! (ÇOK ÖNEMLİ)
DATA_FILE = 'channels.dat'

# Callback data sabitleri (basitleştirilmiş)
CB_SET_START_TEXT = "set_start_text"
CB_SET_CHANNEL_ANNOUNCE_TEXT = "set_channel_announce_text"
CB_VIEW_ADMINS = "view_admins"
CB_VIEW_CHANNELS = "view_channels"
CB_CREATE_SUPPORT_REQUEST = "create_support_request"

# --- Veri Yönetimi ---
def load_data():
    default_start_text = "👋 Hoş geldin {user_name}\\!\n\n📣 VPN KODUNU ALMAK İSTİYORSANIZ AŞAĞIDA GÖSTERİLEN SPONSOR KANALLARA ABONE OLUNUZ\\:"
    default_channel_announce_text = (
        "*🔥 PUBG İÇİN YARIP GEÇEN VPN KODU GELDİ\\! 🔥*\n\n"
        "⚡️ *30 \\- 40 PING* veren efsane kod botumuzda sizleri bekliyor\\!\n\n"
        "🚀 Hemen aşağıdaki butona tıklayarak veya [bota giderek](https://t.me/{bot_username}?start=pubgcode) kodu kapın\\!\n\n"
        "✨ _Aktif ve değerli üyelerimiz için özel\\!_ ✨"
    )

    if not os.path.exists(DATA_FILE):
        initial_data = {
            "channels": [],
            "success_message": "KOD: ",
            "users": [],
            "admins": [SUPER_ADMIN_ID] if SUPER_ADMIN_ID != 0 else [],
            "start_message_text": default_start_text,
            "channel_announcement_text": default_channel_announce_text,
            "bot_operational_status": "active"
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(initial_data, file, ensure_ascii=False, indent=4)
        logger.info(f"{DATA_FILE} oluşturuldu.")
        return initial_data
    else:
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise json.JSONDecodeError("Data is not a dictionary", "", 0)

            updated = False
            # Temel anahtarlar
            for key, default_value in [
                ("channels", []), ("success_message", "KOD: "), ("users", []),
                ("admins", [SUPER_ADMIN_ID] if SUPER_ADMIN_ID != 0 else []),
                ("start_message_text", default_start_text),
                ("channel_announcement_text", default_channel_announce_text),
                ("bot_operational_status", "active")
            ]:
                if key not in data:
                    data[key] = default_value
                    updated = True
            
            # Admin listesinde SUPER_ADMIN_ID kontrolü
            if SUPER_ADMIN_ID != 0 and SUPER_ADMIN_ID not in data.get("admins", []):
                 data.setdefault("admins", []).append(SUPER_ADMIN_ID)
                 updated = True
            
            # Eski resimle ilgili anahtarları kaldır (isteğe bağlı temizlik)
            for old_key in ["start_message_type", "start_message_image_id", 
                            "channel_announcement_type", "channel_announcement_image_id"]:
                if old_key in data:
                    del data[old_key]
                    updated = True

            if updated:
                save_data(data) 
            return data
        except json.JSONDecodeError as e:
            logger.error(f"{DATA_FILE} bozuk. Yeniden oluşturuluyor. Hata: {e}")
            # ... (önceki yedekleme ve yeniden oluşturma mantığı aynı kalabilir) ...
            initial_data_on_error = {
                "channels": [], "success_message": "KOD: ", "users": [], 
                "admins": [SUPER_ADMIN_ID] if SUPER_ADMIN_ID != 0 else [],
                "start_message_text": default_start_text,
                "channel_announcement_text": default_channel_announce_text,
                "bot_operational_status": "active"
            }
            with open(DATA_FILE, 'w', encoding='utf-8') as file:
                json.dump(initial_data_on_error, file, ensure_ascii=False, indent=4)
            return initial_data_on_error
        except Exception as e: # Diğer tüm hatalar
            logger.error(f"{DATA_FILE} yüklenirken beklenmedik genel hata: {e}")
            # En kötü durumda varsayılan bir yapı döndür
            return {"channels": [], "success_message": "KOD: ", "users": [], 
                    "admins": [SUPER_ADMIN_ID] if SUPER_ADMIN_ID != 0 else [],
                    "start_message_text": default_start_text, 
                    "channel_announcement_text": default_channel_announce_text,
                    "bot_operational_status": "active"}


def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        logger.info(f"Veri {DATA_FILE} dosyasına kaydedildi.")
    except Exception as e:
        logger.error(f"{DATA_FILE} dosyasına kaydederken hata: {e}")

def add_user_if_not_exists(user_id):
    data = load_data()
    if user_id not in data.get("users", []):
        data.setdefault("users", []).append(user_id) # setdefault daha güvenli
        save_data(data)
        logger.info(f"Yeni kullanıcı eklendi: {user_id}")

def escape_markdown_v2(text):
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join([f'\\{char}' if char in escape_chars else char for char in text])

# --- Güvenli Mesaj Gönderme Yardımcısı (Basitleştirilmiş) ---
def send_with_markdown_v2_fallback(bot_method, chat_id_or_message, text_content, reply_markup=None):
    """MarkdownV2 ile göndermeyi dener, ayrıştırma hatasında düz metin olarak veya Markdown'sız dener."""
    chat_id = chat_id_or_message.chat.id if hasattr(chat_id_or_message, 'chat') else chat_id_or_message
    is_reply = hasattr(chat_id_or_message, 'message_id') and bot_method == bot.reply_to

    args = [chat_id_or_message if is_reply else chat_id, text_content]
    kwargs_md = {"reply_markup": reply_markup, "parse_mode": "MarkdownV2"}
    kwargs_plain = {"reply_markup": reply_markup}

    try:
        bot_method(*args, **kwargs_md)
        return True
    except telebot.apihelper.ApiTelegramException as e:
        markdown_errors = ["can't parse entities", "unclosed token", "can't find end of the entity", "expected an entity after `[`", "wrong string"]
        if any(err_str in str(e).lower() for err_str in markdown_errors):
            logger.warning(f"MarkdownV2 ayrıştırma hatası (chat {chat_id}): {e}. Düz metin/Markdown'sız deneniyor.")
            try:
                # Önce escape edilmiş MarkdownV2 ile deneyelim
                escaped_text = escape_markdown_v2(text_content)
                args_escaped = [chat_id_or_message if is_reply else chat_id, escaped_text]
                bot_method(*args_escaped, **kwargs_md)
                return True
            except telebot.apihelper.ApiTelegramException as e2:
                logger.warning(f"Escaped MarkdownV2 ile gönderme de başarısız oldu (chat {chat_id}): {e2}. Parse_mode olmadan deneniyor.")
                try:
                    bot_method(*args, **kwargs_plain) # parse_mode yok
                    return True
                except Exception as e3:
                    logger.error(f"Düz metin/Markdown'sız gönderme son denemesi de başarısız oldu (chat {chat_id}): {e3}")
                    return False
        else: 
            logger.error(f"Başka bir API Hatası (chat {chat_id}): {e}")
            raise 
    except Exception as ex: 
        logger.error(f"Mesaj gönderilirken beklenmedik genel hata (chat {chat_id}): {ex}")
        return False

# --- Yetkilendirme ve Durum Kontrolü ---
def is_admin_check(user_id):
    data = load_data()
    return user_id in data.get("admins", [])

def is_super_admin_check(user_id):
    return user_id == SUPER_ADMIN_ID

def is_bot_active_for_user(user_id):
    data = load_data()
    if data.get("bot_operational_status") == "admin_only":
        return is_admin_check(user_id)
    return True

# --- Admin Paneli (Basitleştirilmiş) ---
def get_admin_panel_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📢 Kanallara Genel Duyuru", callback_data="admin_public_channels"), # Sadece metin
        types.InlineKeyboardButton("🗣️ Kullanıcılara Duyuru", callback_data="admin_alert_users"),     # Sadece metin
        types.InlineKeyboardButton("➕ Kanal Ekle", callback_data="admin_add_channel"),
        types.InlineKeyboardButton("➖ Kanal Sil", callback_data="admin_delete_channel_prompt"),
        types.InlineKeyboardButton("🔑 VPN Kodunu Değiştir", callback_data="admin_change_vpn"),
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="admin_stats"),
        types.InlineKeyboardButton("➕ Admin Ekle", callback_data="admin_add_admin_prompt"),
        types.InlineKeyboardButton("➖ Admin Sil", callback_data="admin_remove_admin_prompt"),
        types.InlineKeyboardButton("✍️ Başlangıç Msj Ayarla", callback_data=CB_SET_START_TEXT),
        types.InlineKeyboardButton("✍️ Genel Kanal Dyr Ayarla", callback_data=CB_SET_CHANNEL_ANNOUNCE_TEXT),
        types.InlineKeyboardButton("📜 Adminleri Gör", callback_data=CB_VIEW_ADMINS),
        types.InlineKeyboardButton("📜 Kanalları Gör", callback_data=CB_VIEW_CHANNELS),
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user_id = message.from_user.id
    if not is_admin_check(user_id):
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return
    send_with_markdown_v2_fallback(bot.send_message, message.chat.id, "🤖 *Admin Paneli*\nLütfen bir işlem seçin:", reply_markup=get_admin_panel_markup())

# --- BAKIM MODU KOMUTLARI ---
@bot.message_handler(commands=['durdur'])
def stop_bot_command(message):
    if not is_admin_check(message.from_user.id):
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return
    data = load_data()
    data["bot_operational_status"] = "admin_only"
    save_data(data)
    bot.reply_to(message, "🤖 Bot bakım moduna alındı. Sadece adminler komut kullanabilir.")

@bot.message_handler(commands=['baslat'])
def start_bot_command(message):
    if not is_admin_check(message.from_user.id):
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return
    data = load_data()
    data["bot_operational_status"] = "active"
    save_data(data)
    bot.reply_to(message, "🤖 Bot aktif moda alındı. Tüm kullanıcılar komut kullanabilir.")

# --- Genel Kullanıcı Komutları ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if not is_bot_active_for_user(user_id):
        bot.reply_to(message, "ℹ️ Bot şu anda bakım modundadır. Lütfen daha sonra tekrar deneyin.")
        return

    user_name_raw = message.from_user.first_name or "Kullanıcı"
    user_name_escaped = escape_markdown_v2(user_name_raw)
    logger.info(f"Kullanıcı {user_id} ({user_name_raw}) /start komutunu kullandı.")
    add_user_if_not_exists(user_id)

    data = load_data()
    start_message_text_template = data.get("start_message_text", "👋 Hoş geldin {user_name}\\!")
    final_start_text = start_message_text_template.replace("{user_name}", user_name_escaped)
    send_with_markdown_v2_fallback(bot.send_message, message.chat.id, final_start_text)
    
    channels = data.get("channels", [])
    if channels:
        markup_channels = types.InlineKeyboardMarkup(row_width=1)
        text_for_channels = "📣 VPN KODUNU ALMAK İSTİYORSANIZ AŞAĞIDA GÖSTERİLEN SPONSOR KANALLARA ABONE OLUNUZ\\:"
        for index, channel_link in enumerate(channels, 1):
            channel_username = channel_link.strip('@')
            if channel_username:
                display_name = escape_markdown_v2(channel_link)
                button = types.InlineKeyboardButton(f"🔗 Kanal {index}: {display_name}", url=f"https://t.me/{channel_username}")
                markup_channels.add(button)
        button_check = types.InlineKeyboardButton("✅ ABONE OLDUM / KODU AL", callback_data="check_subscription")
        markup_channels.add(button_check)
        send_with_markdown_v2_fallback(bot.send_message, message.chat.id, text_for_channels, reply_markup=markup_channels)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    user_id = call.from_user.id
    if not is_bot_active_for_user(user_id):
        bot.answer_callback_query(call.id, "ℹ️ Bot bakımda.", show_alert=True)
        return
    bot.answer_callback_query(call.id, "🔄 Abonelikleriniz kontrol ediliyor...", show_alert=False)
    data = load_data()
    channels = data.get("channels", [])
    success_message_text = data.get("success_message", "KOD: ")
    if not channels:
        try: bot.edit_message_text("📢 Şu anda kontrol edilecek zorunlu kanal bulunmamaktadır.", call.message
