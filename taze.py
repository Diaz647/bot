import logging
import json
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User as TelegramUser
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from flask import Flask, request as flask_request, jsonify as flask_jsonify # request ve jsonify flask'a özel isimlerle alındı

# --- Logging Ayarları ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Ortam Değişkenleri ve Sabitler ---
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7877979174"))
BOT_TOKEN = os.environ.get("8128882254:AAEZ_6OicThy8hlo-k4JShBlsatOyqzRhBY") # Default "YOUR_BOT_TOKEN" kaldırıldı, setup kontrol edecek
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # Örn: "https://your-app-name.render.com"

USERS_FILE = "users.json"
TEST_CODES_FILE = "test_codes.txt"
PROMO_FILE = "promocodes.json"

# Webhook için path (güvenlik için token içerir)
# BOT_TOKEN henüz None olabilir, setup_all içinde güncellenecek
WEBHOOK_PATH = f"/{BOT_TOKEN}" if BOT_TOKEN else "/telegram_webhook"


# --- Global Değişkenler ---
active_orders = {} # Uyarı: Birden fazla worker ile çalışıyorsa paylaşımlı olmayacaktır.
ptb_app: Application = None # Telegram Application objesi, setup_all içinde initialize edilecek
flask_server = Flask(__name__) # Flask uygulaması

# --- Dosya İlk Yaratma ---
for file_path in [USERS_FILE, TEST_CODES_FILE, PROMO_FILE]:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding='utf-8') as f:
            if file_path in [USERS_FILE, PROMO_FILE]:
                json.dump({}, f)
            else:
                f.write("") # test_codes.txt için boş string

# --- Veritabanı Sınıfı ---
class Database:
    @staticmethod
    def _read_json_file(filepath):
        try:
            with open(filepath, "r", encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"{filepath} okunurken hata: {e}. Boş sözlük dönülüyor.")
            return {}

    @staticmethod
    def _write_json_file(filepath, data):
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def read_db():
        return Database._read_json_file(USERS_FILE)

    @staticmethod
    def save_db(data):
        Database._write_json_file(USERS_FILE, data)

    @staticmethod
    def read_test_codes():
        try:
            with open(TEST_CODES_FILE, "r", encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"{TEST_CODES_FILE} bulunamadı.")
            return ""

    @staticmethod
    def write_test_codes(code):
        with open(TEST_CODES_FILE, "w", encoding='utf-8') as f:
            f.write(code)

    @staticmethod
    def read_promos():
        return Database._read_json_file(PROMO_FILE)

    @staticmethod
    def write_promos(promos):
        Database._write_json_file(PROMO_FILE, promos)

# --- Menü Gösterim Fonksiyonları ---
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = Database.read_db()
    active_users_count = len([uid for uid, u_data in users.items() if u_data.get('keys')])
    total_refs_count = sum(u_data.get('ref_count', 0) for u_data in users.values())

    text = f"""🔧 Admin paneli

👥 Jemi ulanyjylar: {len(users)}
✅ Aktiw ulanyjylar: {active_users_count}
🎁 Jemi referallar: {total_refs_count}"""

    keyboard = [
        [InlineKeyboardButton("📤 Test kody üýtget", callback_data="admin_change_test"), InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📩 Habar iber", callback_data="admin_broadcast"), InlineKeyboardButton("📦 Users bazasy", callback_data="admin_export")],
        [InlineKeyboardButton("🎟 Promokod goş", callback_data="admin_add_promo"), InlineKeyboardButton("🎟 Promokod poz", callback_data="admin_remove_promo")],
        [InlineKeyboardButton("🔙 Baş sahypa (Bot)", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Admin menü mesajı düzenlenirken hata: {e}")
                await update.effective_chat.send_message(text, reply_markup=reply_markup, parse_mode="Markdown") # Fallback
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_main_menu(update: Update, user_obj: TelegramUser):
    text = f"""Merhaba, {user_obj.full_name} 👋 

🔑 Açarlarym - bassaňyz size mugt berilen ýa-da platny berilen kodlary ýatda saklap berer.
🎁 Referal - bassaňyz size Referal (dostlarınız) çagyryp platny kod almak üçin mümkinçilik berer.
🆓 Test Kody almak - bassaňyz siziň üçin Outline (ss://) kodyny berer.
💰 VPN Bahalary - bassaňyz platny vpn'leri alyp bilersiňiz.
🎟 Promokod - bassaňyz promokod ýazylýan ýer açylar.

'Bildirim' - 'Уведомления' Açyk goýn, sebäbi Test kody tazelenende wagtynda bot arkaly size habar beriler."""

    keyboard = [
        [InlineKeyboardButton("🔑 Açarlarym", callback_data="my_keys")],
        [InlineKeyboardButton("🎁 Referal", callback_data="referral"), InlineKeyboardButton("🆓 Test Kody Almak", callback_data="get_test")],
        [InlineKeyboardButton("💰 VPN Bahalary", callback_data="vpn_prices"), InlineKeyboardButton("🎟 Promokod", callback_data="use_promo")],
    ]
    if update.effective_user.id == ADMIN_ID: # Admin ise Admin Paneline dönüş butonu ekle
        keyboard.append([InlineKeyboardButton("🛠️ Admin Paneli", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.effective_message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Ana menü mesajı düzenlenirken hata: {e}")
                await update.effective_chat.send_message(text, reply_markup=reply_markup, parse_mode="Markdown") # Fallback
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# --- Telegram Handler Fonksiyonları ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    users = Database.read_db()

    # Referans kontrolü
    if context.args and len(context.args) > 0 and context.args[0].isdigit():
        referrer_id = context.args[0]
        if referrer_id != user_id and referrer_id in users:
            if user_id not in users[referrer_id].get('referrals', []):
                users[referrer_id]['ref_count'] = users[referrer_id].get('ref_count', 0) + 1
                users[referrer_id].setdefault('referrals', []).append(user_id)
                Database.save_db(users)
                logger.info(f"User {user_id} referred by {referrer_id}")

    if user_id not in users:
        users[user_id] = {
            "keys": [],
            "ref_count": 0,
            "referrals": [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        Database.save_db(users)
        logger.info(f"New user {user_id} ({user.full_name}) registered.")

    if user.id == ADMIN_ID:
        await show_admin_menu(update, context)
    else:
        await show_main_menu(update, user)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    query = update.callback_query
    await query.answer() # Callback'i hemen yanıtla
    data = query.data
    user = query.from_user
    user_id_str = str(user.id)
    users = Database.read_db()

    # Admin Panel Butonları
    if data == "admin_stats":
        active_users_count = len([uid for uid, u_data in users.items() if u_data.get('keys')])
        total_refs_count = sum(u_data.get('ref_count', 0) for u_data in users.values())
        text = f"""📊 *Bot Statistikasy* 👥 Jemi ulanyjylar: {len(users)}
✅ Aktiw ulanyjylar: {active_users_count}
🎁 Jemi referallar: {total_refs_count}
🕒 Soňky aktivlik: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza (Admin)", callback_data="admin_panel")]]), parse_mode="Markdown")
    elif data == "admin_broadcast":
        await query.message.reply_text("📨 Ýaýlym habaryny iberiň (/cancel bilen ýatyryp bilersiňiz):")
        context.user_data["broadcasting"] = True
    elif data == "admin_export":
        if os.path.exists(USERS_FILE):
            await query.message.reply_document(document=open(USERS_FILE, "rb"), filename=USERS_FILE)
        else:
            await query.message.reply_text("❌ Users bazasy (users.json) tapylmady.")
    elif data == "admin_add_promo":
        await query.message.reply_text("🎟 Täze promokod we skidkany ýazyň (mysal üçin: PROMO10 10) (/cancel bilen ýatyryp bilersiňiz):")
        context.user_data["adding_promo"] = True
    elif data == "admin_remove_promo":
        promos = Database.read_promos()
        if not promos:
            await query.message.reply_text("❌ Pozmak üçin promokod ýok!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza (Admin)", callback_data="admin_panel")]]))
            return
        keyboard = [[InlineKeyboardButton(f"{pcode} ({pdiscount}%) - Poz", callback_data=f"removepromo_{pcode}")] for pcode, pdiscount in promos.items()]
        keyboard.append([InlineKeyboardButton("🔙 Yza (Admin)", callback_data="admin_panel")])
        await query.edit_message_text("🎟 Pozmaly promokody saýlaň:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("removepromo_"):
        promo_to_remove = data.split("_")[1]
        promos = Database.read_promos()
        if promo_to_remove in promos:
            del promos[promo_to_remove]
            Database.write_promos(promos)
            await query.edit_message_text(f"✅ Promokod '{promo_to_remove}' pozuldy.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza (Admin)", callback_data="admin_panel")]]))
        else:
            await query.edit_message_text(f"❌ Promokod '{promo_to_remove}' tapylmady.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza (Admin)", callback_data="admin_panel")]]))
    elif data == "admin_change_test":
        await query.message.reply_text("✏️ Täze test kody iberiň (/cancel bilen ýatyryp bilersiňiz):")
        context.user_data["waiting_for_test"] = True
    
    # Kullanıcı Butonları
    elif data == "my_keys":
        keys = users.get(user_id_str, {}).get("keys", [])
        text = f"🔑 Siziň {'saklanan açarlaryňyz' if keys else 'hiç hili açaryňyz ýok'}.\n"
        if keys:
            text += "\n".join(f"<code>{key}</code>" for key in keys) # Kodları monospace yap
        text += "\n\nTäze açar almak üçin admin bilen habarlaşyp bilersiňiz."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="main_menu")]]), parse_mode="HTML")
    elif data == "referral":
        ref_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id_str}"
        ref_count = users.get(user_id_str, {}).get("ref_count", 0)
        text = f"""Siz 5 adam çagyryp platny kod alyp bilersiňiz 🎁 
Referal sylkaňyz: `{ref_link}`
Referal sanyňyz: {ref_count}"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="main_menu")]]), parse_mode="Markdown")
    elif data == "get_test":
        test_kod = Database.read_test_codes()
        message_to_edit = await query.message.reply_text("⏳ Test Kodyňyz Ýasalýar...")
        await asyncio.sleep(1) # Kısa bir bekleme
        if test_kod:
            await message_to_edit.edit_text(f"Siziň test kodyňyz:\n<code>{test_kod}</code>\n\nBu kod wagtlaýynçadyr.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="main_menu")]]), 
                                            parse_mode="HTML")
        else:
            await message_to_edit.edit_text("❌ Häzirki wagtda test kody ýok. Admin bilen habarlaşyň.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="main_menu")]]))
    elif data == "use_promo":
        await query.message.reply_text("🎟 Promokody ýazyň (/cancel bilen ýatyryp bilersiňiz):")
        context.user_data["waiting_for_promo"] = True
    elif data == "vpn_prices":
        base_prices = {"vpn_3": 20, "vpn_7": 40, "vpn_15": 100, "vpn_30": 130} # Ana fiyatlar
        discount_percentage = context.user_data.get("promo_discount", 0) # Kayıtlı indirim varsa al
        
        prices_text = ("**Eger platny kod almakçy bolsaňyz aşakdaky knopka basyň we BOT arkaly admin'iň size ýazmagyna garaşyn📍**\n"
                       "-----------------------------------------------\n"
                       "🌍 **VPN adı: Shadowsocks**🛍️\n"
                       "-----------------------------------------------\n")
        if discount_percentage > 0:
             prices_text += f"🎉 **Siziň {discount_percentage}% promokod skidkaňyz bar!** 🎉\n"
        
        prices_text_lines = []
        for duration_key, normal_price in base_prices.items():
            days_raw = duration_key.split('_')[1]
            discounted_price = normal_price * (1 - discount_percentage / 100)
            price_line = f"▪️ {days_raw} Gün'lik: "
            if discount_percentage > 0:
                price_line += f"~{normal_price} тмт~ **{discounted_price:.0f} тмт**"
            else:
                price_line += f"{normal_price} тмт"
            prices_text_lines.append(price_line)

        prices_text += "\n".join(prices_text_lines)
        
        keyboard_layout = []
        current_row = []
        for key, price in base_prices.items():
            days_display = key.split('_')[1]
            actual_price = price * (1 - discount_percentage / 100)
            button_text = f"📅 {days_display} gün - {actual_price:.0f} ТМТ"
            current_row.append(InlineKeyboardButton(button_text, callback_data=f"order_{days_display}_{actual_price:.0f}"))
            if len(current_row) == 2:
                keyboard_layout.append(current_row)
                current_row = []
        if current_row: # Kalan buton varsa ekle
            keyboard_layout.append(current_row)
        keyboard_layout.append([InlineKeyboardButton("🔙 Yza", callback_data="main_menu")])
        
        await query.edit_message_text(text=prices_text, reply_markup=InlineKeyboardMarkup(keyboard_layout), parse_mode="Markdown")

    elif data.startswith("order_"): # Örn: order_7_35 (7 gün, 35 TMT)
        parts = data.split("_")
        days = parts[1]
        price_ordered = parts[2] # Fiyatı da admin'e iletmek için aldık
        
        await context.bot.send_message(chat_id=user.id, text=f"✅ {days} günlük VPN ({price_ordered} TMT) üçin sargyt islegiňiz administrasiýa ýetirildi.")
        await asyncio.sleep(0.5)
        await context.bot.send_message(chat_id=user.id, text="⏳ Tiz wagtdan admin size ýazar. Garaşmagyňyzy haýyş edýäris.")
        await asyncio.sleep(0.5)
        # await context.bot.send_message(chat_id=user.id, text="🚫 Eger admin'iň size ýazmagyny islemeýän bolsaňyz /stop ýazyp bilersiňiz.") # Bu komut yok

        admin_text = (f"🆕 Täze sargyt:\n"
                      f"👤 Ulanyjy: {user.full_name} (@{user.username if user.username else 'N/A'}, ID: {user.id})\n"
                      f"📆 Sargyt: {days} günlük VPN\n"
                      f"💲 Bahasy (skidkaly): {price_ordered} TMT")
        admin_keyboard = [[InlineKeyboardButton("✅ Kabul etmek we Habarlaşmak", callback_data=f"accept_{user.id_str}_{days}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=InlineKeyboardMarkup(admin_keyboard))

    elif data.startswith("accept_"): # Admin sargyty kabul etti
        _, target_user_id_str, days = data.split("_")
        active_orders[target_user_id_str] = str(ADMIN_ID) # Kullanıcı -> Admin
        active_orders[str(ADMIN_ID)] = target_user_id_str # Admin -> Kullanıcı (iki yönlü chat için)

        await query.edit_message_text(text=f"✅ {days} günlük sargyt ({target_user_id_str}) kabul edildi! Indi ulanyjy bilen şu çat arkaly habarlaşyp bilersiňiz.\nSöhbeti ýapmak üçin /close_{target_user_id_str} ýazyň (ýa-da aşaky knopka basyň).",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"🚫 Sargyty ({target_user_id_str}) ýapmak", callback_data=f"close_{target_user_id_str}")]]))
        try:
            await context.bot.send_message(chat_id=int(target_user_id_str), text="✅ Sargytyňyz administrasiýa tarapyndan kabul edildi! Tiz wagtda admin sizin bilen habarlaşar. Siz hem şu çat arkaly admin bilen ýazyşyp bilersiňiz.")
        except Exception as e:
            logger.error(f"User {target_user_id_str}'a kabul mesajı gönderilemedi: {e}")

    elif data.startswith("close_"): # Admin sargyty ýapdy (butondan)
        target_user_id_str = data.split("_")[1]
        closed_by_admin = False
        if str(ADMIN_ID) in active_orders and active_orders[str(ADMIN_ID)] == target_user_id_str:
            del active_orders[str(ADMIN_ID)]
            closed_by_admin = True
        if target_user_id_str in active_orders: # Karşılıklı olarak sil
            del active_orders[target_user_id_str]
            closed_by_admin = True
        
        if closed_by_admin:
            await query.edit_message_text(f"✅ {target_user_id_str} ID-li ulanyjynyň sargyty ýapyldy.")
            try:
                await context.bot.send_message(chat_id=int(target_user_id_str), text="🔒 Admin tarapyndan sargyt söhbeti ýapyldy. Täze sargyt ýa-da sorag üçin baş menýuny ulanyň.")
            except Exception as e:
                logger.error(f"User {target_user_id_str}'a ýapylma mesajı gönderilemedi: {e}")
        else:
            await query.answer("Bu sargyt eýýäm ýapylan ýaly.", show_alert=True)


    # Menü Geçişleri
    elif data == "admin_panel":
        if user.id == ADMIN_ID:
            await show_admin_menu(update, context)
        else: # Admin olmayan biri bu butona basarsa (teorik olarak olmamalı)
            await query.answer("Bu bölüm administrasiýa üçindir.", show_alert=True)
            await show_main_menu(update, user)
    elif data == "main_menu":
        if user.id == ADMIN_ID: # Admin baş menüye dönerse admin panelini göster
            await show_admin_menu(update, context)
        else:
            await show_main_menu(update, user)
    else:
        logger.warning(f"Bilinmeyen callback_data: {data} from user {user_id_str}")
        await query.answer() # Bilinmeyen data için sadece answer et


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    user = update.effective_user
    if not user or not update.message or (not update.message.text and not update.message.photo):
        return

    user_id_str = str(user.id)
    text_received = update.message.text.strip() if update.message.text else ""
    photo_received = update.message.photo[-1] if update.message.photo else None

    # --- Durum Bazlı İşlemler (Admin için) ---
    if user.id == ADMIN_ID:
        if context.user_data.get("broadcasting"):
            if not text_received and not photo_received:
                await update.message.reply_text("Habar boş bolup bilmez. Täzeden iberiň ýa-da /cancel ýazyň.")
                return
            
            context.user_data["broadcasting"] = False # İşlem başladı, state'i temizle
            users_db = Database.read_db()
            sent_count = 0
            failed_count = 0
            broadcast_message_text = f"📢 ÄHLI ULANYJYLARA HABAR (Admin):\n\n{text_received if text_received else ''}"
            
            await update.message.reply_text(f"Yayın başlıyor ({len(users_db)} kullanıcı)...")

            for uid_str_target in users_db.keys():
                try:
                    if photo_received:
                        await context.bot.send_photo(chat_id=int(uid_str_target), photo=photo_received.file_id, caption=broadcast_message_text)
                    elif text_received: # Sadece metin varsa
                        await context.bot.send_message(chat_id=int(uid_str_target), text=broadcast_message_text)
                    sent_count += 1
                    await asyncio.sleep(0.1)  # API limitlerine takılmamak için ufak bekleme
                except Exception as e:
                    logger.error(f"Broadcast to {uid_str_target} failed: {e}")
                    failed_count += 1
            await update.message.reply_text(f"✅ Habar {sent_count} ulanyja iberildi.\n❌ {failed_count} ulanyja ýalňyşlyk boldy.")
            await show_admin_menu(update, context)
            return

        if context.user_data.get("adding_promo"):
            if not text_received:
                await update.message.reply_text("Promokod we skidka boş bolup bilmez. Mysal: PROMO25 25. Täzeden iberiň ýa-da /cancel ýazyň.")
                return
            try:
                promo_code, discount_str = text_received.split(maxsplit=1)
                discount = int(discount_str)
                if not (0 < discount <= 100):
                    raise ValueError("Skidka 1-100 aralygynda bolmaly.")
                promos = Database.read_promos()
                promos[promo_code.upper()] = discount
                Database.write_promos(promos)
                await update.message.reply_text(f"✅ Promokod '{promo_code.upper()}' ({discount}%) goşuldy.")
            except ValueError as e:
                await update.message.reply_text(f"❌ Ýalňyş format: {e}. Mysal: KOD123 20")
            except Exception as e:
                await update.message.reply_text(f"❌ Nämälim ýalňyşlyk: {e}")
            context.user_data["adding_promo"] = False
            await show_admin_menu(update, context)
            return

        if context.user_data.get("waiting_for_test"):
            if not text_received:
                await update.message.reply_text("Test kody boş bolup bilmez. Täzeden iberiň ýa-da /cancel ýazyň.")
                return
            Database.write_test_codes(text_received)
            await update.message.reply_text("✅ Täze test kody ýatda saklandy.")
            context.user_data["waiting_for_test"] = False
            await show_admin_menu(update, context)
            return

    # --- Durum Bazlı İşlemler (Kullanıcı için) ---
    if context.user_data.get("waiting_for_promo"):
        if not text_received:
            await update.message.reply_text("Promokod boş bolup bilmez. Täzeden iberiň ýa-da /cancel ýazyň.")
            return
        promo_code_input = text_received.upper()
        promos = Database.read_promos()
        if promo_code_input in promos:
            discount = promos[promo_code_input]
            context.user_data["promo_discount"] = discount
            await update.message.reply_text(f"✅ '{promo_code_input}' promokody kabul edildi! {discount}% skidka gazandyňyz.\nIndi VPN bahalaryny görüp, skidkaly alyp bilersiňiz.")
        else:
            await update.message.reply_text("❌ Nädogry ýa-da möhleti geçen promokod.")
        context.user_data["waiting_for_promo"] = False
        await show_main_menu(update, user) # Ana menüye dön
        return

    # --- Aktif Sipariş Üzerinden Chat ---
    if user_id_str in active_orders:
        recipient_id_str = active_orders[user_id_str]
        try:
            recipient_id = int(recipient_id_str)
            sender_prefix = "Admin" if user.id == ADMIN_ID else f"Ulanyjy ({user.full_name})"
            
            if photo_received:
                caption_to_forward = f"📸 Surat ({sender_prefix})"
                if update.message.caption:
                    caption_to_forward += f":\n{update.message.caption}"
                await context.bot.send_photo(chat_id=recipient_id, photo=photo_received.file_id, caption=caption_to_forward)
            elif text_received: # Sadece metin varsa
                message_to_forward = f"💬 Habar ({sender_prefix}):\n{text_received}"
                await context.bot.send_message(chat_id=recipient_id, text=message_to_forward)
            # Diğer mesaj tipleri (sticker, document vs.) eklenebilir.
        except Exception as e:
            logger.error(f"Aktif sipariş ({user_id_str} -> {recipient_id_str}) chat mesajı iletilirken hata: {e}")
        return

    # Eğer hiçbir state eşleşmediyse ve aktif chat yoksa, admin'e "Ne yapacağımı bilmiyorum" deme
    # Kullanıcıya da aynı şekilde. Şimdilik sessiz kalıyor.
    if user.id != ADMIN_ID: # Admin değilse ve komut değilse
        logger.info(f"Kullanıcıdan ({user_id_str}) işlenmeyen mesaj: {text_received[:50]}")
        # await update.message.reply_text("Näme diýýäniňize düşünmedim. Baş menýu üçin /start ýazyň.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    states_to_clear = ["broadcasting", "adding_promo", "waiting_for_test", "waiting_for_promo"]
    cleared_any = False
    for state_key in states_to_clear:
        if context.user_data.pop(state_key, None):
            cleared_any = True
    
    if cleared_any:
        await update.message.reply_text("Işlem ýatyryldy.")
    else:
        await update.message.reply_text("Häzirki wagtda ýatyrmak üçin açyk işlem ýok.")
    
    # Kullanıcıyı uygun menüye yönlendir
    if user_id == ADMIN_ID:
        await show_admin_menu(update, context)
    else:
        await show_main_menu(update, update.effective_user)

# --- Flask Rotaları ---
@flask_server.route('/health', methods=['GET'])
def health_check_route():
    # Daha detaylı kontroller eklenebilir (örn: ptb_app.bot objesi var mı?)
    bot_status_ok = ptb_app is not None and hasattr(ptb_app, 'bot') and ptb_app.bot is not None
    if bot_status_ok:
        return flask_jsonify(status="ok", message="Telegram Bot ve Flask sunucusu sağlıklı çalışıyor."), 200
    else:
        return flask_jsonify(status="error", message="Telegram Bot başlatılamadı veya sağlıklı değil."), 500

@flask_server.route(WEBHOOK_PATH, methods=['POST'])
async def telegram_webhook_handler():
    if not ptb_app:
        logger.critical("Webhook çağrıldı ancak ptb_app başlatılmamış!")
        return flask_jsonify(ok=False, error="Bot düzgün yapılandırılmamış"), 500

    if flask_request.headers.get('content-type') == 'application/json':
        json_data = flask_request.get_json(force=True)
        try:
            update = Update.de_json(json_data, ptb_app.bot)
            await ptb_app.process_update(update)
            return flask_jsonify(ok=True), 200
        except Exception as e:
            logger.error(f"Webhook'tan gelen update işlenirken hata: {e}", exc_info=True)
            return flask_jsonify(ok=False, error=str(e)), 500 # Hata detayını logla ama kullanıcıya basit mesaj
    else:
        logger.warning(f"Webhook'a JSON olmayan istek geldi: {flask_request.headers.get('content-type')}")
        return flask_jsonify(ok=False, error="Geçersiz içerik tipi, JSON bekleniyor."), 403


# --- Bot ve Sunucu Başlatma Fonksiyonları ---
_setup_lock = asyncio.Lock()
_setup_done = False

async def initialize_bot_and_webhook():
    global ptb_app, _setup_done, WEBHOOK_PATH

    async with _setup_lock:
        if _setup_done:
            return True

        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_PLACEHOLDER": # Güvenlik
            logger.critical("KRİTİK HATA: BOT_TOKEN ortam değişkeni ayarlanmamış veya geçersiz!")
            return False
        if not WEBHOOK_URL:
            logger.critical("KRİTİK HATA: WEBHOOK_URL ortam değişkeni ayarlanmamış!")
            return False
        
        WEBHOOK_PATH = f"/{BOT_TOKEN}" # Token'a göre webhook path'i güncelle

        # Persistence (opsiyonel, şimdilik kapalı)
        # persistence = PicklePersistence(filepath='bot_persistence')
        
        builder = Application.builder().token(BOT_TOKEN).updater(None) #.persistence(persistence)
        ptb_app = builder.build()

        # Handler'ları ekle
        ptb_app.add_handler(CommandHandler("start", start))
        ptb_app.add_handler(CallbackQueryHandler(button_handler))
        ptb_app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler)) # Fotoğraf filtresi eklendi
        ptb_app.add_handler(CommandHandler("cancel", cancel))
        
        # Admin özel komutları (opsiyonel)
        # ptb_app.add_handler(CommandHandler("admin", show_admin_menu, filters=filters.User(user_id=ADMIN_ID)))
        # /close_USERID komutu admin tarafından chat kapatmak için
        async def close_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user.id != ADMIN_ID: return
            try:
                target_user_id_to_close = context.args[0]
                closed = False
                if str(ADMIN_ID) in active_orders and active_orders[str(ADMIN_ID)] == target_user_id_to_close:
                    del active_orders[str(ADMIN_ID)]
                    closed = True
                if target_user_id_to_close in active_orders:
                    del active_orders[target_user_id_to_close]
                    closed = True
                
                if closed:
                    await update.message.reply_text(f"✅ {target_user_id_to_close} ID-li ulanyjy bilen söhbet ýapyldy.")
                    await context.bot.send_message(chat_id=int(target_user_id_to_close), text="🔒 Admin tarapyndan sargyt söhbeti ýapyldy.")
                else:
                    await update.message.reply_text(f"❌ {target_user_id_to_close} ID-li ulanyjy bilen açyk söhbet tapylmady.")
            except (IndexError, ValueError):
                await update.message.reply_text("❌ Ýalňyş komanda. Mysal: /close 123456789")

        ptb_app.add_handler(CommandHandler("close", close_chat_command, filters=filters.User(user_id=ADMIN_ID)))


        try:
            await ptb_app.initialize() # Bot objesini oluşturur
            await ptb_app.bot.set_webhook(
                url=f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}",
                allowed_updates=Update.ALL_TYPES,
                # drop_pending_updates=True # Yeniden başlatmada bekleyen güncellemeleri atla
            )
            logger.info(f"Webhook {WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH} adresine kuruldu.")
            _setup_done = True
            return True
        except Exception as e:
            logger.critical(f"Bot başlatılırken veya webhook kurulurken KRİTİK HATA: {e}", exc_info=True)
            return False

# Flask'ın her istekten önce botun hazır olduğundan emin olması için
@flask_server.before_request
async def ensure_bot_setup_before_request():
    if not _setup_done: # Eğer setup henüz yapılmadıysa (ilk istek veya bir sorun olduysa)
        logger.info("İlk istek geldi, bot ve webhook kurulumu kontrol ediliyor/yapılıyor...")
        await initialize_bot_and_webhook()
        if not _setup_done: # Eğer hala setup olmadıysa ciddi bir sorun var
             logger.critical("Bot kurulumu tamamlanamadı. Sunucu düzgün çalışmayabilir.")
             # Burada isteği abort etmek veya hata döndürmek de düşünülebilir
             # return flask_jsonify(message="Sunucu henüz hazır değil, bot başlatılamadı."), 503


# --- Gunicorn/Uvicorn/Hypercorn ile çalıştırmak için ---
# Bu dosya doğrudan `python taze.py` ile çalıştırılmayacak.
# Bunun yerine Render.com'da bir WSGI/ASGI sunucusu (örn: Gunicorn) flask_server objesini çalıştıracak.
# Örnek Başlatma Komutu (Render.com için Procfile veya Start Command):
# web: gunicorn --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --preload taze:flask_server
# --preload bayrağı, initialize_bot_and_webhook() fonksiyonunun worker'lar oluşmadan önce bir kere çalışmasını sağlar.
# Bu nedenle, aşağıdaki __main__ bloğu lokal test için veya alternatif bir çalıştırma yöntemi için kalabilir,
# ama Render.com'daki ana çalıştırma yöntemi Gunicorn olacaktır.

if __name__ == "__main__":
    # Bu blok genellikle Gunicorn gibi bir sunucu kullanıldığında çalışmaz,
    # ama lokal testler için veya farklı bir deployment senaryosu için faydalı olabilir.
    logger.info("Lokal test modunda çalıştırılıyor (Gunicorn/ASGI sunucusu önerilir)...")
    
    # Lokal test için basit bir şekilde botu ve webhook'u ayağa kaldır.
    # ÖNEMLİ: Lokal test için ngrok gibi bir araçla WEBHOOK_URL'nizi localhost'a yönlendirmeniz gerekir.
    # Ve BOT_TOKEN, ADMIN_ID, WEBHOOK_URL ortam değişkenlerini ayarlamanız gerekir.
    
    async def local_run():
        if await initialize_bot_and_webhook():
            logger.info(f"Bot başlatıldı. Flask sunucusu http://127.0.0.1:8080 adresinde çalışacak.")
            logger.info(f"Webhook endpoint: http://127.0.0.1:8080{WEBHOOK_PATH}")
            logger.info(f"Health check: http://127.0.0.1:8080/health")
            # Flask'ı asenkron çalıştırmak için Hypercorn gibi bir sunucuya ihtiyaç var.
            # Simplest for local dev (Flask's own server, not for production or real async webhook handling):
            # flask_server.run(host="0.0.0.0", port=8080, debug=True)
            # This is problematic as Flask's dev server is not fully async.
            # For proper local async testing:
            try:
                import uvicorn
                config = uvicorn.Config(flask_server, host="0.0.0.0", port=8080, log_level="info")
                server = uvicorn.Server(config)
                logger.info("Uvicorn ile lokal sunucu başlatılıyor...")
                await server.serve()
            except ImportError:
                logger.error("Lokalde asenkron çalıştırma için 'uvicorn' kurun: pip install uvicorn[standard]")
                logger.info("Flask'ın dahili sunucusu ile senkron modda başlatılıyor (webhook için ideal değil)...")
                # flask_server.run(host="0.0.0.0", port=8080, debug=False) # debug=True sorun çıkarabilir
        else:
            logger.critical("Bot ve webhook başlatılamadı. Sunucu çalıştırılmıyor.")

    if BOT_TOKEN and WEBHOOK_URL: # Sadece gerekli değişkenler varsa lokal testi başlat
        asyncio.run(local_run())
    else:
        logger.error("Lokal test için BOT_TOKEN ve WEBHOOK_URL ortam değişkenleri ayarlanmalı.")
        logger.error("Render.com gibi bir ortamda bu değişkenler platform üzerinden ayarlanmalıdır.")
