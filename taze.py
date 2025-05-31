import telebot
from telebot import types
import json
import os
import logging
import time
import flask

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or '8128882254:AAEZ_6OicThy8hlo-k4JShBlsatOyqzRhBY'
if TOKEN == '8128882254:AAEZ_6OicThy8hlo-k4JShBlsatOyqzRhBY':
    logging.error("Lütfen Telegram bot token'ınızı ayarlayın!")
    exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# Webhook settings
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_LISTEN = '0.0.0.0'

WEBHOOK_URL_PATH = f"/{TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_URL_PATH}" if WEBHOOK_HOST else None

# Flask app instance
app = flask.Flask(__name__)

# --- Constants and Data File ---
SUPER_ADMIN_ID = 7877979174  # KENDİ TELEGRAM ID'NİZİ BURAYA GİRİN (ÇOK ÖNEMLİ)
if SUPER_ADMIN_ID == 0:
    logging.error("Lütfen SUPER_ADMIN_ID'yi Telegram ID'niz ile ayarlayın!")
    exit(1)

DATA_FILE = 'channels.dat'

# Callback data constants
CB_SET_START_TEXT = "set_start_text"
CB_SET_CHANNEL_ANNOUNCE_TEXT = "set_channel_announce_text"
CB_VIEW_ADMINS = "view_admins"
CB_VIEW_CHANNELS = "view_channels"
CB_CREATE_SUPPORT_REQUEST = "create_support_request"

# --- Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Data Management ---
def load_data():
    default_start_text = "👋 Hoş geldin {user_name}!\n\n📣 VPN KODUNU ALMAK İSTİYORSANIZ AŞAĞIDA GÖSTERİLEN SPONSOR KANALLARA ABONE OLUNUZ:"
    default_channel_announce_text = (
        "*🔥 PUBG İÇİN YARIP GEÇEN VPN KODU GELDİ! 🔥*\n\n"
        "⚡️ *30 - 40 PING* veren efsane kod botumuzda sizleri bekliyor!\n\n"
        "🚀 Hemen aşağıdaki butona tıklayarak veya [bota giderek](https://t.me/{bot_username}?start=pubgcode) kodu kapın!\n\n"
        "✨ _Aktif ve değerli üyelerimiz için özel!_ ✨"
    )

    if not os.path.exists(DATA_FILE):
        initial_data = {
            "channels": [],
            "success_message": "KOD: ",
            "users": [],
            "admins": [SUPER_ADMIN_ID],
            "start_message_text": default_start_text,
            "channel_announcement_text": default_channel_announce_text,
            "bot_operational_status": "active"
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(initial_data, file, ensure_ascii=False, indent=4)
        logger.info(f"{DATA_FILE} oluşturuldu.")
        return initial_data
    
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        if not isinstance(data, dict):
            raise ValueError(f"{DATA_FILE} içeriği bir sözlük olmalı.")

        # Gerekli tüm anahtarların var olduğundan emin olun
        required_keys = {
            "channels": [],
            "success_message": "KOD: ",
            "users": [],
            "admins": [SUPER_ADMIN_ID],
            "start_message_text": default_start_text,
            "channel_announcement_text": default_channel_announce_text,
            "bot_operational_status": "active"
        }
        
        updated = False
        for key, default_value in required_keys.items():
            if key not in data:
                data[key] = default_value
                updated = True
        
        # SUPER_ADMIN'in adminler içinde olduğundan emin olun
        if SUPER_ADMIN_ID not in data["admins"]:
            data["admins"].append(SUPER_ADMIN_ID)
            updated = True
            
        if updated:
            save_data(data)
            
        return data
        
    except FileNotFoundError:
        logger.warning(f"{DATA_FILE} bulunamadı. Varsayılan verilerle oluşturuluyor.")
        initial_data = {
            "channels": [],
            "success_message": "KOD: ",
            "users": [],
            "admins": [SUPER_ADMIN_ID],
            "start_message_text": default_start_text,
            "channel_announcement_text": default_channel_announce_text,
            "bot_operational_status": "active"
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(initial_data, file, ensure_ascii=False, indent=4)
        return initial_data
    
    except json.JSONDecodeError as e:
        logger.error(f"{DATA_FILE} bozuk. Yeniden oluşturuluyor. Hata: {e}")
        # Eski dosyayı yedekle
        if os.path.exists(DATA_FILE):
            try:
                backup_name = f"{DATA_FILE}.bak.{int(time.time())}"
                os.rename(DATA_FILE, backup_name)
                logger.info(f"Yedek oluşturuldu: {backup_name}")
            except Exception as backup_error:
                logger.error(f"Yedek oluşturulamadı: {backup_error}")
        
        # Varsayılan verilerle yeni dosya oluştur
        initial_data = required_keys
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(initial_data, file, ensure_ascii=False, indent=4)
        return initial_data
        
    except Exception as e:
        logger.error(f"{DATA_FILE} yüklenirken beklenmeyen hata: {e}")
        return required_keys

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        logger.info(f"Veri {DATA_FILE} dosyasına kaydedildi.")
    except Exception as e:
        logger.error(f"{DATA_FILE} dosyasına kaydederken hata: {e}")

def add_user_if_not_exists(user_id):
    data = load_data()
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)
        logger.info(f"Yeni kullanıcı eklendi: {user_id}")

def escape_markdown_v2(text):
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join([f'\\{char}' if char in escape_chars else char for char in text])

# --- Message Sending Helper ---
def send_with_markdown_v2_fallback(bot_method, chat_id_or_message, text_content, reply_markup=None):
    """MarkdownV2 ile göndermeyi dene, hatada düz metne geri dön."""

    chat_id = chat_id_or_message.chat.id if hasattr(chat_id_or_message, 'chat') else chat_id_or_message
    is_reply = hasattr(chat_id_or_message, 'message_id') and bot_method == bot.reply_to

    args = [chat_id_or_message] if is_reply else [chat_id]
    args.append(text_content)
    
    kwargs_md = {"reply_markup": reply_markup, "parse_mode": "MarkdownV2"}
    kwargs_plain = {"reply_markup": reply_markup}

    try:
        if is_reply:
            bot.reply_to(*args, **kwargs_md)
        else:
            bot.send_message(*args, **kwargs_md)
        return True
    except telebot.apihelper.ApiTelegramException as e:
        markdown_errors = ["can't parse entities", "unclosed token", "can't find end of the entity", 
                          "expected an entity after `[`", "wrong string"]
        if any(err_str in str(e).lower() for err_str in markdown_errors):
            logger.warning(f"MarkdownV2 ayrıştırma hatası (sohbet {chat_id}): {e}. Düz metin deneniyor.")
            try:
                # Önce kaçışlı Markdown ile dene
                escaped_text = escape_markdown_v2(text_content)
                if is_reply:
                    bot.reply_to(chat_id_or_message, escaped_text, **kwargs_md)
                else:
                    bot.send_message(chat_id, escaped_text, **kwargs_md)
                return True
            except telebot.apihelper.ApiTelegramException:
                try:
                    # Düz metne geri dön
                    if is_reply:
                        bot.reply_to(chat_id_or_message, text_content, **kwargs_plain)
                    else:
                        bot.send_message(chat_id, text_content, **kwargs_plain)
                    return True
                except Exception as e3:
                    logger.error(f"Düz metin gönderme de başarısız (sohbet {chat_id}): {e3}")
                    return False
        else:
            logger.error(f"Diğer API Hatası (sohbet {chat_id}): {e}")
            raise
    except Exception as ex:
        logger.error(f"Mesaj gönderirken beklenmeyen hata (sohbet {chat_id}): {ex}")
        return False

# --- Authorization and Status Checks ---
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

# --- Admin Panel ---
def get_admin_panel_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📢 Kanallara Genel Duyuru", callback_data="admin_public_channels"),
        types.InlineKeyboardButton("🗣️ Kullanıcılara Duyuru", callback_data="admin_alert_users"),
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
    send_with_markdown_v2_fallback(bot.send_message, message.chat.id, 
                                 "🤖 *Admin Paneli*\nLütfen bir işlem seçin:", 
                                 reply_markup=get_admin_panel_markup())

# --- Maintenance Mode Commands ---
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

# --- User Commands ---
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
    start_message_text_template = data.get("start_message_text", "👋 Hoş geldin {user_name}!")
    final_start_text = start_message_text_template.replace("{user_name}", user_name_escaped)
    
    # Başlangıç mesajını gönder
    send_with_markdown_v2_fallback(bot.send_message, message.chat.id, final_start_text)
    
    # Kanallar varsa kanal butonlarını gönder
    channels = data.get("channels", [])
    if channels:
        markup_channels = types.InlineKeyboardMarkup(row_width=1)
        text_for_channels = "📣 VPN KODUNU ALMAK İSTİYORSANIZ AŞAĞIDA GÖSTERİLEN SPONSOR KANALLARA ABONE OLUNUZ:"
        
        for index, channel_link in enumerate(channels, 1):
            channel_username = channel_link.lstrip('@')
            display_name = escape_markdown_v2(channel_link)
            button = types.InlineKeyboardButton(
                f"🔗 Kanal {index}: {display_name}", 
                url=f"https://t.me/{channel_username}"
            )
            markup_channels.add(button)
            
        button_check = types.InlineKeyboardButton(
            "✅ ABONE OLDUM / KODU AL", 
            callback_data="check_subscription"
        )
        markup_channels.add(button_check)
        
        send_with_markdown_v2_fallback(
            bot.send_message, 
            message.chat.id, 
            text_for_channels, 
            reply_markup=markup_channels
        )

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    user_id = call.from_user.id
    if not is_bot_active_for_user(user_id):
        bot.answer_callback_query(call.id, "ℹ️ Bot bakımda.", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, "🔄 Abonelikleriniz kontrol ediliyor...", show_alert=False)
    
    data = load_data()
    channels = data.get("channels", [])
    success_message_text = data.
