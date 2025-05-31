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
logger = logging.getLogger(__name__) # DÜZELTİLDİ: name -> __name__

# --- Yapılandırma ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or '8150737858:AAGBk5gcGJNJf2iR1-G7w8vuIaBzM4Ds4mU' # Token'ınızı buraya girin
bot = telebot.TeleBot(TOKEN, parse_mode=None) # parse_mode'u daha sonra özel olarak ayarlayacağız

# Webhook ayarları (Render.com için)
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_LISTEN = '0.0.0.0' # Genellikle '0.0.0.0' kullanılır

WEBHOOK_URL_PATH = f"/{TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_URL_PATH}" if WEBHOOK_HOST else None # WEBHOOK_HOST yoksa None ata

# Flask app instance
app = flask.Flask(__name__) # DÜZELTİLDİ: name -> __name__

# --- Sabitler ve Veri Dosyası ---
SUPER_ADMIN_ID = 7877979174 # Bu ID'yi kendi Telegram ID'niz ile değiştirin!
DATA_FILE = 'channels.dat' # Veri dosyası adı .dat olarak değiştirildi

# --- Veri Yönetimi ---
def load_data():
    """channels.dat dosyasını yükler veya oluşturur."""
    if not os.path.exists(DATA_FILE):
        initial_data = {
            "channels": [],
            "success_message": "KOD: ",
            "users": [],
            "admins": [SUPER_ADMIN_ID] # Süper admin başlangıçta eklenir
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(initial_data, file, ensure_ascii=False, indent=4)
        logger.info(f"{DATA_FILE} oluşturuldu.")
        return initial_data
    else:
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as file:
                data = json.load(file)
            if not isinstance(data, dict): # Veri bozuksa veya beklenen formatta değilse
                raise json.JSONDecodeError("Data is not a dictionary", "", 0)

            # Gerekli anahtarların varlığını kontrol et ve yoksa ekle
            if "channels" not in data: data["channels"] = []
            if "success_message" not in data: data["success_message"] = "KOD: "
            if "users" not in data: data["users"] = []
            if "admins" not in data:
                data["admins"] = [SUPER_ADMIN_ID]
            elif SUPER_ADMIN_ID not in data["admins"]: # Süper admin her zaman listede olmalı
                 data["admins"].append(SUPER_ADMIN_ID)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"{DATA_FILE} bozuk. Yeniden oluşturuluyor. Hata: {e}")
            backup_file = f"{DATA_FILE}.bak_{int(time.time())}"
            try:
                if os.path.exists(DATA_FILE): # Sadece var olan dosya yedeklenir
                    os.rename(DATA_FILE, backup_file)
                    logger.info(f"{DATA_FILE} şuraya yedeklendi: {backup_file}")
            except OSError as err:
                logger.error(f"{DATA_FILE} yedeklenemedi: {err}")
            # initial_data fonksiyonun başında tanımlı, onu doğrudan return edebiliriz.
            # Ancak load_data() tekrar çağrıldığında initial_data'yı oluşturacak.
            # Bu döngüye girmemesi için doğrudan default bir yapı döndürmek daha güvenli olabilir
            # VEYA initial_data'yı burada yeniden tanımlayıp kaydetmek
            initial_data_on_error = {
                "channels": [], "success_message": "KOD: ", "users": [], "admins": [SUPER_ADMIN_ID]
            }
            with open(DATA_FILE, 'w', encoding='utf-8') as file: # Bozuk dosyayı varsayılanla üzerine yaz
                json.dump(initial_data_on_error, file, ensure_ascii=False, indent=4)
            logger.info(f"{DATA_FILE} yeniden oluşturuldu (bozuk olduğu için).")
            return initial_data_on_error
        except Exception as e:
            logger.error(f"{DATA_FILE} yüklenirken beklenmedik hata: {e}")
            return {"channels": [], "success_message": "KOD: ", "users": [], "admins": [SUPER_ADMIN_ID]}

def save_data(data):
    """Veriyi channels.dat dosyasına kaydeder."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        logger.info(f"Veri {DATA_FILE} dosyasına kaydedildi.")
    except Exception as e:
        logger.error(f"{DATA_FILE} dosyasına kaydederken hata: {e}")

def add_user_if_not_exists(user_id):
    """Yeni kullanıcı ID'sini (varsa) listeye ekler."""
    data = load_data()
    if user_id not in data.get("users", []):
        data["users"].append(user_id)
        save_data(data)
        logger.info(f"Yeni kullanıcı eklendi: {user_id}")

def escape_markdown_v2(text):
    """MarkdownV2 için özel karakterleri escape eder."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join([f'\\{char}' if char in escape_chars else char for char in str(text)])

# --- Yetkilendirme ---
def is_admin_check(user_id):
    """Kullanıcının admin olup olmadığını kontrol eder."""
    data = load_data()
    return user_id in data.get("admins", [])

def is_super_admin_check(user_id):
    """Kullanıcının süper admin olup olmadığını kontrol eder."""
    return user_id == SUPER_ADMIN_ID

# --- Admin Paneli ---
def get_admin_panel_markup():
    """Admin paneli butonlarını oluşturur."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📢 Kanallara Duyuru Yap", callback_data="admin_public_channels"),
        types.InlineKeyboardButton("🗣️ Kullanıcılara Duyuru Yap", callback_data="admin_alert_users"),
        types.InlineKeyboardButton("➕ Kanal Ekle", callback_data="admin_add_channel"),
        types.InlineKeyboardButton("➖ Kanal Sil", callback_data="admin_delete_channel_prompt"),
        types.InlineKeyboardButton("🔑 VPN Kodunu Değiştir", callback_data="admin_change_vpn"),
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="admin_stats"),
        types.InlineKeyboardButton("➕ Admin Ekle", callback_data="admin_add_admin_prompt"), # Sadece Süper Admin
        types.InlineKeyboardButton("➖ Admin Sil", callback_data="admin_remove_admin_prompt") # Sadece Süper Admin
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user_id = message.from_user.id
    if not is_admin_check(user_id):
        bot.reply_to(message, "⛔ Bu komutu kullanma yetkiniz yok.")
        return
    
    bot.send_message(message.chat.id, "🤖 *Admin Paneli*\nLütfen bir işlem seçin:",
                     reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")

# --- Genel Kullanıcı Komutları ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user_name = escape_markdown_v2(message.from_user.first_name or "Kullanıcı")
    logger.info(f"Kullanıcı {user_id} ({user_name}) /start komutunu kullandı.")
    add_user_if_not_exists(user_id)

    data = load_data()
    channels = data.get("channels", [])
    markup = types.InlineKeyboardMarkup(row_width=1)

    if not channels:
        text = f"👋 Hoş geldin {user_name}\\!\n\n📣 Şu anda sponsor kanal bulunmamaktadır\\."
        bot.send_message(message.chat.id, text, parse_mode="MarkdownV2")
    else:
        text = (
            f"👋 Hoş geldin {user_name}\\!\n\n"
            f"📣 VPN KODUNU ALMAK İSTİYORSANIZ AŞAĞIDA GÖSTERİLEN SPONSOR KANALLARA ABONE OLUNUZ\\:"
        )
        for index, channel_link in enumerate(channels, 1):
            channel_username = channel_link.strip('@')
            if channel_username:
                try:
                    # Kanal adını almak için get_chat kullanabiliriz (opsiyonel ama hata verebilir)
                    # chat_info = bot.get_chat(f"@{channel_username}") # @ eklemek önemli
                    # display_name = escape_markdown_v2(chat_info.title or channel_link)
                    display_name = escape_markdown_v2(channel_link) # Şimdilik sadece kullanıcı adını gösterelim
                    button = types.InlineKeyboardButton(f"🔗 Kanal {index}: {display_name}", url=f"https://t.me/{channel_username}")
                    markup.add(button)
                except Exception as e:
                    logger.warning(f"Kanal bilgisi alınamadı (@{channel_username}): {channel_link} - Hata: {e}")
                    button = types.InlineKeyboardButton(f"🔗 Kanal {index}: {escape_markdown_v2(channel_link)}", url=f"https://t.me/{channel_username}")
                    markup.add(button)
            else:
                logger.warning(f"Veritabanında geçersiz kanal formatı: '{channel_link}'")
        
        button_check = types.InlineKeyboardButton("✅ ABONE OLDUM / KODU AL", callback_data="check_subscription")
        markup.add(button_check)
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="MarkdownV2")

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    user_id = call.from_user.id
    logger.info(f"Kullanıcı {user_id} abonelik kontrolünü tetikledi.")
    bot.answer_callback_query(call.id, "🔄 Abonelikleriniz kontrol ediliyor...", show_alert=False)

    data = load_data() # DÜZELTİLDİ: data burada yüklenmeli
    channels = data.get("channels", [])
    success_message_text = data.get("success_message", "KOD: ")

    if not channels:
        try:
            bot.edit_message_text("📢 Şu anda kontrol edilecek zorunlu kanal bulunmamaktadır.", call.message.chat.id, call.message.message_id)
        except telebot.apihelper.ApiTelegramException as e:
            if "message to edit not found" in str(e).lower():
                logger.warning("Düzenlenecek 'kanal yok' mesajı bulunamadı, muhtemelen silinmiş.")
                bot.send_message(call.message.chat.id, "📢 Şu anda kontrol edilecek zorunlu kanal bulunmamaktadır.")
            else:
                raise e
        return

    all_subscribed = True
    failed_channels_list = []

    for channel_link in channels:
        # Kanalların başında @ yoksa bile get_chat_member çalışması için @ eklenmeli
        # Ancak kullanıcı veritabanına @ ile giriyorsa bu gereksiz olabilir.
        # Mevcut kodunuzda channel_link'in doğrudan kullanıldığı varsayılıyor.
        # Eğer kanal ID'si ise (sayısal), o zaman @ eklenmemeli.
        # Eğer kullanıcı adı ise (@kanaladi), o zaman doğru.
        # Eğer kanal adı (kanaladi) ise, @ eklenmeli.
        # Şimdilik gelen formatın doğru (@kanaladi veya ID) olduğunu varsayalım.
        effective_channel_id = channel_link 
        if isinstance(channel_link, str) and not channel_link.startswith("@") and not channel_link.lstrip('-').isdigit():
             effective_channel_id = f"@{channel_link}"


        try:
            member = bot.get_chat_member(chat_id=effective_channel_id, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                all_subscribed = False
                failed_channels_list.append(channel_link) # Orijinal linki listeye ekle
                logger.info(f"Kullanıcı {user_id}, {effective_channel_id} kanalına abone değil (durum: {member.status}).")
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"API Hatası: Kullanıcı {user_id}, kanal {effective_channel_id}. Hata: {e}")
            if "chat not found" in str(e).lower() or "bot is not a member" in str(e).lower() or "user not found" in str(e).lower() or "PEER_ID_INVALID" in str(e).upper() or "BOT_IS_NOT_PARTICIPANT" in str(e).upper() :
                 bot.send_message(SUPER_ADMIN_ID, f"⚠️ Uyarı: Bot {effective_channel_id} kanalına erişemiyor, kanal bulunamadı veya bot üye değil. Lütfen kontrol edin. (Kullanıcı: {user_id})")
            all_subscribed = False # Hata durumunda abone olmadığını varsay
            failed_channels_list.append(channel_link)
        except Exception as e:
            logger.error(f"Beklenmedik hata ({effective_channel_id}): Kullanıcı {user_id}, kanal {channel_link}. Hata: {e}")
            all_subscribed = False
            failed_channels_list.append(channel_link)
    
    if all_subscribed:
        try:
            bot.edit_message_text(
                success_message_text, 
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None,
                parse_mode="MarkdownV2"
            )
            logger.info(f"Kullanıcı {user_id} tüm kanallara abone. Başarı mesajı gönderildi.")
        except telebot.apihelper.ApiTelegramException as e:
            if "message to edit not found" in str(e).lower():
                 logger.warning("Düzenlenecek başarı mesajı bulunamadı, muhtemelen silinmiş.")
                 bot.send_message(call.message.chat.id, success_message_text, parse_mode="MarkdownV2")
            elif "message is not modified" in str(e).lower():
                 logger.info("Mesaj zaten aynı içerikte (başarı), düzenleme yapılmadı.")
                 bot.answer_callback_query(call.id, "✅ Zaten tüm kanallara abonesiniz ve kodunuz gösteriliyor.", show_alert=False)
            else:
                 logger.error(f"Başarı mesajı gönderilirken Markdown hatası: {e}. Mesaj: {success_message_text}")
                 try:
                     bot.edit_message_text(
                        escape_markdown_v2(success_message_text) + "\n\n_(Mesaj formatında bir sorun olabilir, admin ile iletişime geçin\\.)_",
                        call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode="MarkdownV2")
                 except Exception as e2:
                     logger.error(f"Fallback başarı mesajı da gönderilemedi: {e2}")
                     bot.send_message(call.message.chat.id, escape_markdown_v2(success_message_text) + "\n\n_(Mesaj formatında bir sorun olabilir, admin ile iletişime geçin\\.)_", parse_mode="MarkdownV2")


    else:
        error_text = "❌ Lütfen aşağıdaki kanalların hepsine abone olduğunuzdan emin olun ve tekrar deneyin:\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        # DÜZELTİLDİ: Aşağıdaki for döngüsü ve içindeki mantık doğru girintilendi.
        for index, channel_link_original in enumerate(channels, 1): # Tüm kanalları tekrar listele
            channel_username = channel_link_original.strip('@')
            is_failed = channel_link_original in failed_channels_list
            prefix = "❗️" if is_failed else "➡️"
            
            if channel_username:
                # Burada da /start komutundaki gibi dinamik kanal adı alınabilir, şimdilik link kullanılıyor
                button = types.InlineKeyboardButton(f"{prefix} Kanal: {escape_markdown_v2(channel_link_original)}", url=f"https://t.me/{channel_username}")
                markup.add(button)
        
        button_check = types.InlineKeyboardButton("🔄 TEKRAR KONTROL ET", callback_data="check_subscription")
        markup.add(button_check)
        
        try:
            bot.edit_message_text(
                error_text, # Bu bizim tarafımızdan oluşturuldu, escape edilmesine gerek yok (içinde Markdown yok)
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="MarkdownV2" # error_text'i MarkdownV2 olarak göndermek için. escape_markdown_v2(error_text) yapılabilir.
                                         # ancak error_text'in kendisi Markdown içermiyorsa gerek yok. Bizimki içermiyor.
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message to edit not found" in str(e).lower():
                 logger.warning("Düzenlenecek 'abone olmama' mesajı bulunamadı.")
                 bot.send_message(call.message.chat.id, error_text, reply_markup=markup, parse_mode="MarkdownV2")
            elif "message is not modified" in str(e).lower():
                 logger.info("Mesaj zaten aynı içerikte (hata), düzenleme yapılmadı.")
                 # Kullanıcıya bir geri bildirim vermek iyi olabilir.
                 bot.answer_callback_query(call.id, "❗️ Lütfen belirtilen kanallara abone olun.", show_alert=False)

            else:
                logger.error(f"Abone olmama mesajı düzenlenirken hata: {e}")
        logger.info(f"Kullanıcı {user_id} tüm kanallara abone değil. Hata mesajı gösterildi.")

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id
    base_help = (
        "🤖 *BOT KOMUTLARI* 🤖\n\n"
        "👤 *Genel Kullanıcı Komutları:*\n"
        "/start \\- Botu başlatır ve abonelik kanallarını gösterir\\.\n"
        "/help \\- Bu yardım mesajını gösterir\\.\n"
    )
    admin_help = ""
    if is_admin_check(user_id):
        admin_help = (
            "\n👑 *Admin Komutları:*\n"
            "/admin \\- Admin yönetim panelini açar\\.\n"
        )
    
    full_help_text = base_help + admin_help
        
    bot.reply_to(message, full_help_text, parse_mode="MarkdownV2")

# --- Admin Panel Callback İşleyicileri ---

# KANAL EKLEME
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_channel")
def admin_add_channel_prompt_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg_text = ("➕ Eklenecek kanal\\(lar\\)ın kullanıcı adlarını girin \\(örneğin: `@kanal1 @kanal2` veya her biri yeni satırda\\)\\. "
                "Lütfen botun bu kanallarda *yönetici olduğundan* veya *mesaj gönderme izni olduğundan* emin olun\\.")
    
    # Önceki mesajı düzenle
    try:
        sent_msg = bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Kanal ekleme istemi mesajı düzenlenemedi: {e}")
        sent_msg = bot.send_message(call.message.chat.id, msg_text, parse_mode="MarkdownV2") # Yeni mesaj gönder

    bot.register_next_step_handler(sent_msg, process_add_multiple_channels, call.message.message_id)


def process_add_multiple_channels(message, original_message_id): # original_message_id eklendi
    if not is_admin_check(message.from_user.id): return

    channel_inputs = message.text.split() 
    added_channels = []
    failed_channels = []
    already_exists_channels = []
    data = load_data()

    for ch_input in channel_inputs:
        new_channel = ch_input.strip()
        if not new_channel: continue # Boş girdileri atla

        if not new_channel.startswith("@"):
            # Sayısal ID'ler @ ile başlamaz, onları da kabul et
            if not new_channel.lstrip('-').isdigit():
                failed_channels.append(f"{new_channel} (Geçersiz format: '@' ile başlamalı veya sayısal ID olmalı)")
                continue
        
        # Kanalın varlığını ve botun erişimini kontrol etmeyeceğiz, adminin sorumluluğunda.
        # Ancak, temel bir get_chat denemesi yapılabilir.
        try:
            # bot.get_chat(new_channel) # Bu, botun kanalda olmasına gerek duymaz, sadece varlığını kontrol eder.
            # Daha iyi bir test, bot.get_chat_administrators(new_channel) olabilir, ama bot yönetici olmalı.
            # Şimdilik bu kontrolü atlıyoruz.
            pass
        except telebot.apihelper.ApiTelegramException as e:
            # if "chat not found" in str(e).lower():
            #     failed_channels.append(f"{new_channel} (Kanal bulunamadı veya bot erişemiyor)")
            #     continue
            logger.warning(f"Kanal eklerken {new_channel} için get_chat denemesi başarısız (bu bir hata olmayabilir): {e}")


        if new_channel not in data["channels"]:
            data["channels"].append(new_channel)
            added_channels.append(new_channel)
        else:
            already_exists_channels.append(new_channel)
    
    if added_channels:
        save_data(data)

    # DÜZELTİLDİ: response_message bloğunun girintisi
    response_message = ""
    if added_channels:
        response_message += f"✅ Başarıyla eklenen kanallar:\n" + "\n".join(added_channels) + "\n\n"
    if failed_channels:
        response_message += f"❌ Eklenemeyen veya geçersiz formatlı kanallar:\n" + "\n".join(failed_channels) + "\n\n"
    if already_exists_channels:
        response_message += f"ℹ️ Zaten listede bulunan kanallar:\n" + "\n".join(already_exists_channels) + "\n"
    
    if not response_message:
        response_message = "Hiçbir kanal adı girilmedi veya işlem yapılacak geçerli kanal bulunamadı."

    bot.reply_to(message, response_message)
    
    # Kullanıcının girdiği mesajı sil (opsiyonel)
    try: bot.delete_message(message.chat.id, message.message_id)
    except Exception as e: logger.debug(f"Kullanıcı mesajı silinemedi: {e}")

    # Admin panelini orijinal mesajda göster
    try:
        bot.edit_message_text("🤖 *Admin Paneli*\nLütfen bir işlem seçin:", message.chat.id, original_message_id,
                              reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Admin paneli process_add_multiple_channels içinde düzenlenemedi: {e}")
        # Yeni bir panel gönder
        admin_panel_command(message) # Bu yeni bir mesaj gönderir, dikkat.


# KANAL SİLME
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_channel_prompt")
def admin_delete_channel_prompt_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    data = load_data()
    channels = data.get("channels", [])

    if not channels:
        try:
            bot.edit_message_text("➖ Silinecek kayıtlı kanal bulunmuyor.", call.message.chat.id, call.message.message_id,
                                  reply_markup=get_admin_panel_markup()) # Paneli tekrar göster
        except telebot.apihelper.ApiTelegramException: pass # Mesaj zaten buysa veya silinmişse
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        markup.add(types.InlineKeyboardButton(f"🗑️ Sil: {escape_markdown_v2(ch)}", callback_data=f"admin_del_ch_confirm:{ch}"))
    markup.add(types.InlineKeyboardButton("↩️ Geri", callback_data="admin_panel_back"))
    try:
        bot.edit_message_text("➖ Silmek istediğiniz kanalı seçin:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException: pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_del_ch_confirm:"))
def admin_delete_channel_confirm_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    
    channel_to_remove = call.data.split(":", 1)[1]
    data = load_data()

    if channel_to_remove in data["channels"]:
        data["channels"].remove(channel_to_remove)
        save_data(data)
        bot.answer_callback_query(call.id, f"✅ {escape_markdown_v2(channel_to_remove)} başarıyla silindi.")
        admin_delete_channel_prompt_callback(call) 
    else:
        bot.answer_callback_query(call.id, f"ℹ️ {escape_markdown_v2(channel_to_remove)} listede bulunamadı.", show_alert=True)
        admin_delete_channel_prompt_callback(call)

# VPN KODU DEĞİŞTİRME
@bot.callback_query_handler(func=lambda call: call.data == "admin_change_vpn")
def admin_change_vpn_prompt_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    data = load_data()
    current_vpn_code_raw = data.get("success_message", "KOD: ")
    # Markdown'ı ekranda düzgün göstermek için escape edelim, ama kullanıcıya Markdown kullanabileceğini belirtelim.
    current_vpn_code_display = escape_markdown_v2(current_vpn_code_raw)

    msg_text = (f"🔑 Yeni VPN kodunu \\(başarı mesajını\\) girin\\.\n"
                f"*Mevcut kod \\(önizleme\\):*\n`{current_vpn_code_raw}`\n\n" # Ham halini backtick içinde göster
                f"Markdown formatını kullanabilirsiniz \\(örn: *kalın*, [link](url)\\)\\.")
    try:
        sent_msg = bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"VPN kodu değiştirme istemi mesajı düzenlenemedi: {e}")
        sent_msg = bot.send_message(call.message.chat.id, msg_text, parse_mode="MarkdownV2")

    bot.register_next_step_handler(sent_msg, process_change_vpn_code, call.message.message_id)

def process_change_vpn_code(message, original_message_id): 
    if not is_admin_check(message.from_user.id): return
    
    new_message_text = message.text.strip()
    
    # Kullanıcının girdiği mesajı silelim (opsiyonel)
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    if not new_message_text:
        bot.reply_to(message, "❌ VPN kodu boş olamaz. İşlem iptal edildi.") # reply_to yerine send_message daha iyi olabilir
        # Admin panelini orjinal mesajda göster
        try:
            bot.edit_message_text("🤖 *Admin Paneli*\nLütfen bir işlem seçin:", message.chat.id, original_message_id,
                                  reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
        except telebot.apihelper.ApiTelegramException: # Eğer mesaj bulunamazsa yeni panel gönder
             admin_panel_command(message) # Bu yeni mesaj gönderir
        return

    data = load_data()
    data["success_message"] = new_message_text
    save_data(data)
    # bot.reply_to(message, "✅ VPN kodu başarıyla güncellendi.") # Bu, silinen mesaja yanıt vermeye çalışır, hata verir.
    bot.send_message(message.chat.id, "✅ VPN kodu başarıyla güncellendi.") # Yeni mesaj olarak gönder

    # Admin panelini orjinal mesajda göster
    try:
        bot.edit_message_text("🤖 *Admin Paneli*\nLütfen bir işlem seçin:", message.chat.id, original_message_id,
                              reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException:
        admin_panel_command(message) # Yeni mesaj olarak panel


# KULLANICILARA DUYURU
@bot.callback_query_handler(func=lambda call: call.data == "admin_alert_users")
def admin_alert_users_prompt_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg_text = "🗣️ Tüm bot kullanıcılarına göndermek istediğiniz mesajı yazın \\(Markdown kullanabilirsiniz\\):"
    try:
        sent_msg = bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Kullanıcılara duyuru istemi mesajı düzenlenemedi: {e}")
        sent_msg = bot.send_message(call.message.chat.id, msg_text, parse_mode="MarkdownV2")
    bot.register_next_step_handler(sent_msg, process_alert_users_message, call.message.message_id)

def process_alert_users_message(message, original_message_id):
    if not is_admin_check(message.from_user.id): return

    alert_text = message.text 
    data = load_data()
    users = data.get("users", [])

    # Kullanıcının mesajını sil (isteğe bağlı)
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    if not users:
        bot.send_message(message.chat.id, "ℹ️ Mesaj gönderilecek kayıtlı kullanıcı bulunmuyor.")
        try:
            bot.edit_message_text("🤖 *Admin Paneli*\nLütfen bir işlem seçin:", message.chat.id, original_message_id,
                                  reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
        except telebot.apihelper.ApiTelegramException:
            admin_panel_command(message)
        return

    status_text = f"📢 {len(users)} kullanıcıya duyuru gönderiliyor..."
    try:
        status_msg = bot.edit_message_text(status_text, message.chat.id, original_message_id, parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException as e:
        logger.warning(f"Duyuru durum mesajı düzenlenemedi: {e}")
        status_msg = bot.send_message(message.chat.id, status_text, parse_mode="MarkdownV2") # Yeni durum mesajı gönder
    
    success_count = 0
    failed_count = 0
    blocked_users = []

    for user_id_to_send in users:
        try:
            bot.send_message(user_id_to_send, alert_text, parse_mode="MarkdownV2")
            success_count += 1
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"Kullanıcı {user_id_to_send} için duyuru gönderilemedi: {e}")
            if "bot was blocked by the user" in str(e).lower() or "user is deactivated" in str(e).lower() or "chat not found" in str(e).lower():
                blocked_users.append(user_id_to_send)
            failed_count += 1
        except Exception as e:
            logger.error(f"Kullanıcı {user_id_to_send} için duyuru gönderilirken beklenmedik hata: {e}")
            failed_count += 1
        time.sleep(0.1) 

    # Engellenen kullanıcıları veritabanından sil (opsiyonel)
    if blocked_users:
        data = load_data() # Veriyi tekrar yükle, arada değişmiş olabilir
        updated_users = [u for u in data.get("users", []) if u not in blocked_users]
        if len(updated_users) < len(data.get("users",[])): # Eğer kullanıcı silindiyse
            data["users"] = updated_users
            save_data(data)
            logger.info(f"{len(blocked_users)} engellenmiş kullanıcı veritabanından silindi.")


    report = (f"✅ Duyuru gönderme tamamlandı:\n\n"
              f"Başarılı: {success_count}\n"
              f"Başarısız: {failed_count}")
    if blocked_users:
        report += f"\nEngellemiş/Deaktif Kullanıcılar (silindi): {len(blocked_users)}"
    
    try:
        bot.edit_message_text(report, status_msg.chat.id, status_msg.message_id, 
                              reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2") # Rapor Markdown içerebilir
    except telebot.apihelper.ApiTelegramException as e:
        logger.warning(f"Duyuru raporu düzenlenemedi: {e}")
        bot.send_message(status_msg.chat.id, report, reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")


# KANALLARA DUYURU (ÖN TANIMLI MESAJ)
@bot.callback_query_handler(func=lambda call: call.data == "admin_public_channels")
def admin_public_to_channels_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, "İşleniyor...")
    data = load_data()
    channels_to_send = data.get("channels", [])

    if not channels_to_send:
        try:
            bot.edit_message_text("ℹ️ Duyuru yapılacak kayıtlı kanal bulunmuyor.", 
                                  call.message.chat.id, call.message.message_id, 
                                  reply_markup=get_admin_panel_markup())
        except telebot.apihelper.ApiTelegramException: pass
        return

    try:
        bot_info = bot.get_me()
        bot_username = bot_info.username
    except Exception as e:
        logger.error(f"Bot kullanıcı adı alınamadı: {e}")
        try:
            bot.edit_message_text("❌ Bot bilgileri alınamadı, lütfen tekrar deneyin.",
                                  call.message.chat.id, call.message.message_id,
                                  reply_markup=get_admin_panel_markup())
        except telebot.apihelper.ApiTelegramException: pass
        return

    text_to_send = (
        "*🔥 PUBG İÇİN YARIP GEÇEN VPN KODU GELDİ\\! 🔥*\n\n"
        f"⚡️ *30 \\- 40 PING* veren efsane kod botumuzda sizleri bekliyor\\!\n\n"
        f"🚀 Hemen aşağıdaki butona tıklayarak veya [bota giderek](https://t.me/{bot_username}?start=pubgcode) kodu kapın\\!\n\n"
        f"✨ _Aktif ve değerli üyelerimiz için özel\\!_ ✨"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1) 
    markup.add(types.InlineKeyboardButton("🤖 KODU ALMAK İÇİN TIKLA 🤖", url=f"https://t.me/{bot_username}?start=getCode")) # start parametresi isteğe bağlı

    status_text = f"📢 {len(channels_to_send)} kanala duyuru gönderiliyor..."
    try:
        status_msg = bot.edit_message_text(status_text, call.message.chat.id, call.message.message_id, parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException as e:
        logger.warning(f"Kanallara duyuru durum mesajı düzenlenemedi: {e}")
        status_msg = bot.send_message(call.message.chat.id, status_text, parse_mode="MarkdownV2")
    
    success_count = 0
    failed_count = 0

    for channel_item in channels_to_send:
        try:
            bot.send_message(channel_item, text_to_send, reply_markup=markup, parse_mode="MarkdownV2")
            success_count += 1
        except Exception as e:
            logger.error(f"Kanal {channel_item} için duyuru gönderilemedi: {e}")
            failed_count += 1
        time.sleep(0.2) 

    report = (f"✅ Kanallara duyuru gönderme tamamlandı:\n\n"
              f"Başarılı: {success_count}\n"
              f"Başarısız: {failed_count}")
    try:
        bot.edit_message_text(report, status_msg.chat.id, status_msg.message_id, 
                              reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException as e:
        logger.warning(f"Kanallara duyuru raporu düzenlenemedi: {e}")
        bot.send_message(status_msg.chat.id, report, reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")


# İSTATİSTİKLER
@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats_callback(call):
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    data = load_data()
    num_users = len(data.get("users", []))
    num_channels = len(data.get("channels", []))
    num_admins = len(data.get("admins", []))

    stats_text = (
        f"📊 *Bot İstatistikleri*\n\n"
        f"👤 Toplam Kayıtlı Kullanıcı: {num_users}\n"
        f"📢 Yönetilen Kanal Sayısı: {num_channels}\n"
        f"👑 Yönetici Sayısı: {num_admins}\n\n"
        f"_Veriler {escape_markdown_v2(time.strftime('%Y-%m-%d %H:%M:%S %Z'))} itibariyle günceldir\\._" # Saat dilimi eklendi
    )
    try:
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id,
                              reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException: pass


# ADMIN EKLEME (Sadece Süper Admin)
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_admin_prompt")
def admin_add_admin_prompt_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_super_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Bu işlemi sadece Süper Admin yapabilir.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    msg_text = "➕ Admin olarak eklemek istediğiniz kullanıcının Telegram ID'sini girin:"
    try:
        sent_msg = bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Admin ekleme istemi mesajı düzenlenemedi: {e}")
        sent_msg = bot.send_message(call.message.chat.id, msg_text)
    bot.register_next_step_handler(sent_msg, process_add_admin_id, call.message.message_id)

def process_add_admin_id(message, original_message_id):
    if not is_super_admin_check(message.from_user.id): return

    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ Geçersiz ID formatı. Lütfen sayısal bir ID girin.")
        try:
            bot.edit_message_text("🤖 *Admin Paneli*\nLütfen bir işlem seçin:", message.chat.id, original_message_id,
                                  reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
        except telebot.apihelper.ApiTelegramException: admin_panel_command(message)
        return

    data = load_data()
    if new_admin_id in data["admins"]:
        bot.send_message(message.chat.id, f"ℹ️ Kullanıcı `{new_admin_id}` zaten admin.", parse_mode="MarkdownV2")
    else:
        data["admins"].append(new_admin_id)
        save_data(data)
        bot.send_message(message.chat.id, f"✅ Kullanıcı `{new_admin_id}` başarıyla admin olarak eklendi.", parse_mode="MarkdownV2")
    
    try:
        bot.edit_message_text("🤖 *Admin Paneli*\nLütfen bir işlem seçin:", message.chat.id, original_message_id,
                              reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
    except telebot.apihelper.ApiTelegramException: admin_panel_command(message)


# ADMIN SİLME (Sadece Süper Admin)
@bot.callback_query_handler(func=lambda call: call.data == "admin_remove_admin_prompt")
def admin_remove_admin_prompt_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_super_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Bu işlemi sadece Süper Admin yapabilir.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    data = load_data()
    admins_to_list = [admin_id for admin_id in data.get("admins", []) if admin_id != SUPER_ADMIN_ID] 

    if not admins_to_list:
        try:
            bot.edit_message_text("➖ Silinecek başka admin bulunmuyor.", call.message.chat.id, call.message.message_id,
                                  reply_markup=get_admin_panel_markup())
        except telebot.apihelper.ApiTelegramException: pass
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for admin_id_to_remove in admins_to_list:
        markup.add(types.InlineKeyboardButton(f"🗑️ Sil: {admin_id_to_remove}", callback_data=f"admin_rem_adm_confirm:{admin_id_to_remove}"))
    markup.add(types.InlineKeyboardButton("↩️ Geri", callback_data="admin_panel_back"))
    try:
        bot.edit_message_text("➖ Silmek istediğiniz admini seçin:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except telebot.apihelper.ApiTelegramException: pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_rem_adm_confirm:"))
def admin_remove_admin_confirm_callback(call): # İsim çakışmasını önlemek için callback eklendi
    if not is_super_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Bu işlemi sadece Süper Admin yapabilir.", show_alert=True)
        return
    
    try:
        admin_id_to_remove = int(call.data.split(":", 1)[1])
    except (IndexError, ValueError):
        bot.answer_callback_query(call.id, "Geçersiz callback verisi.", show_alert=True)
        admin_remove_admin_prompt_callback(call) # Listeyi yenile
        return

    data = load_data()

    if admin_id_to_remove == SUPER_ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Süper Admin silinemez.", show_alert=True)
        admin_remove_admin_prompt_callback(call)
        return

    if admin_id_to_remove in data.get("admins", []): # get("admins", []) ile kontrol daha güvenli
        data["admins"].remove(admin_id_to_remove)
        save_data(data) # DÜZELTİLDİ: save_data(data) doğru yerde
        bot.answer_callback_query(call.id, f"✅ Admin {admin_id_to_remove} başarıyla silindi.")
    else:
        bot.answer_callback_query(call.id, f"ℹ️ Admin {admin_id_to_remove} listede bulunamadı.", show_alert=True)
    
    admin_remove_admin_prompt_callback(call) # Her durumda listeyi güncelle


# ADMIN PANELINE GERİ DÖNME
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel_back")
def admin_panel_back_callback(call):
    if not is_admin_check(call.from_user.id):
        bot.answer_callback_query(call.id, "Yetkiniz yok.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    try:
        bot.edit_message_text("🤖 *Admin Paneli*\nLütfen bir işlem seçin:",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Admin paneline geri dönerken hata: {e}")
        bot.send_message(call.message.chat.id, "🤖 *Admin Paneli*\nLütfen bir işlem seçin:",
                         reply_markup=get_admin_panel_markup(), parse_mode="MarkdownV2")


# --- Bilinmeyen Komutlar ve Mesajlar ---
@bot.message_handler(func=lambda message: True, content_types=['text', 'audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact'])
def handle_other_messages(message):
    user_id = message.from_user.id
    text = message.text

    if text and text.startswith('/'):
        logger.info(f"Kullanıcı {user_id} bilinmeyen komut gönderdi: {text}")
        escaped_text = escape_markdown_v2(text)
        if is_admin_check(user_id):
             bot.reply_to(message, f"⛔ `{escaped_text}` adında bir komut bulunamadı\\. Kullanılabilir komutlar için /help veya /admin kullanın\\.", parse_mode="MarkdownV2")
        else:
            bot.reply_to(message, f"⛔ `{escaped_text}` adında bir komut bulunamadı\\. Kullanılabilir komutlar için /help kullanın\\.", parse_mode="MarkdownV2")
        
        if user_id != SUPER_ADMIN_ID: 
            try:
                forward_text = f"⚠️ Kullanıcıdan bilinmeyen komut:\n\nKullanıcı ID: `{user_id}`\nKomut: `{escaped_text}`"
                bot.send_message(SUPER_ADMIN_ID, forward_text, parse_mode="MarkdownV2")
            except Exception as e:
                logger.error(f"Süper Admin {SUPER_ADMIN_ID} adresine bilinmeyen komut iletilemedi: {e}")


# --- Webhook ve Flask Ayarları ---
@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook_handler(): # Fonksiyon adı düzeltildi (webhook -> webhook_handler, çakışmayı önlemek için)
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        flask.abort(403)

@app.route('/')
def index():
    logger.info("Ana dizin '/' isteği alındı.") 
    return 'Bot çalışıyor!', 200

@app.route('/health')
def health_check():
    logger.info("Sağlık kontrolü '/health' isteği alındı.")
    return "OK", 200


# --- Bot Başlatma ---
if __name__ == "__main__": # DÜZELTİLDİ: name -> __name__
    logger.info("Bot başlatılıyor...")
    load_data() 

    if WEBHOOK_URL and WEBHOOK_HOST and WEBHOOK_HOST.startswith("https://"):
        logger.info(f"Webhook modu aktif. URL: {WEBHOOK_URL}")
        bot.remove_webhook()
        time.sleep(0.5) # Webhook kaldırma ve ayarlama arasında kısa bir bekleme
        
        # Basit bir secret token örneği (TOKEN'ın son 10 karakteri)
        # Gerçek uygulamalarda daha güvenli bir secret token yönetimi düşünülmelidir.
        simple_secret_token = TOKEN[-10:] if TOKEN and len(TOKEN) >= 10 else "DEFAULT_SECRET"

        bot.set_webhook(url=WEBHOOK_URL,
                        # certificate=open('path/to/cert.pem', 'r') # Eğer self-signed sertifika kullanıyorsanız
                        secret_token=simple_secret_token) 
        
        logger.info(f"Flask uygulaması {WEBHOOK_LISTEN}:{WEBHOOK_PORT} adresinde çalışacak.")
        app.run(host=WEBHOOK_LISTEN, port=WEBHOOK_PORT)
    else:
        logger.warning("WEBHOOK_HOST (RENDER_EXTERNAL_URL) ayarlanmamış veya HTTPS değil.")
        logger.info("Polling modunda başlatılıyor (Lokal geliştirme için)...")
        bot.remove_webhook() 
        bot.polling(none_stop=True, interval=0, timeout=30) # timeout artırıldı
