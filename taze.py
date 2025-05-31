import logging
import json
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_ID = admin id
BOT_TOKEN = "7856912713:AAHs1OQ4N5bQ-qCEdBhd_wl-mfOBEGCW66U"
USERS_FILE = "users.json"
TEST_CODES_FILE = "test_codes.txt"
PROMO_FILE = "promocodes.json"

active_orders = {}

for file in [USERS_FILE, TEST_CODES_FILE, PROMO_FILE]:
    if not os.path.exists(file):
        with open(file, "w", encoding='utf-8') as f:
            if file in [USERS_FILE, PROMO_FILE]:
                json.dump({}, f)

class Database:
    @staticmethod
    def read_db():
        try:
            with open(USERS_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    def save_db(data):
        with open(USERS_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def read_test_codes():
        try:
            with open(TEST_CODES_FILE, "r", encoding='utf-8') as f:
                return f.read().strip()
        except:
            return ""

    @staticmethod
    def write_test_codes(code):
        with open(TEST_CODES_FILE, "w", encoding='utf-8') as f:
            f.write(code)

    @staticmethod
    def read_promos():
        try:
            with open(PROMO_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    def write_promos(promos):
        with open(PROMO_FILE, "w", encoding='utf-8') as f:
            json.dump(promos, f, indent=4, ensure_ascii=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    users = Database.read_db()

    if context.args and context.args[0].isdigit():
        referrer_id = context.args[0]
        if referrer_id in users and user_id != referrer_id and user_id not in users[referrer_id].get('referrals', []):
            users[referrer_id]['ref_count'] = users[referrer_id].get('ref_count', 0) + 1
            users[referrer_id]['referrals'] = users[referrer_id].get('referrals', []) + [user_id]
            Database.save_db(users)

    if user_id not in users:
        users[user_id] = {
            "keys": [],
            "ref_count": 0,
            "referrals": [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        Database.save_db(users)

    if user.id == ADMIN_ID:
        await show_admin_menu(update)
    else:
        await show_main_menu(update, user)

async def show_admin_menu(update, context: ContextTypes.DEFAULT_TYPE = None):
    users = Database.read_db()
    active_users = len([u for u in users if users[u].get('keys')])
    text = f"""🔧 Admin panel

👥 Jemi ulanyjylar: {len(users)}
✅ Aktiw ulanyjylar: {active_users}
🎁 Jemi referallar: {sum(u.get('ref_count', 0) for u in users.values())}"""

    keyboard = [
        [InlineKeyboardButton("📤 Test kody üýtget", callback_data="admin_change_test"), InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📩 Habar iber", callback_data="admin_broadcast"), InlineKeyboardButton("📦 Users bazasy", callback_data="admin_export")],
        [InlineKeyboardButton("🎟 Promokod goş", callback_data="admin_add_promo"), InlineKeyboardButton("🎟 Promokod poz", callback_data="admin_remove_promo")],
        [InlineKeyboardButton("🔙 Baş sahypa", callback_data="main_menu")]
    ]
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = Database.read_db()
    active_users = len([u for u in users if users[u].get('keys')])
    total_refs = sum(u.get('ref_count', 0) for u in users.values())

    text = f"""📊 *Bot statistikasy* 

👥 Jemi ulanyjylar: {len(users)}
✅ Aktiw ulanyjylar: {active_users}
🎁 Jemi referallar: {total_refs}
🕒 Soňky aktivlik: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    await update.callback_query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Yza", callback_data="admin_panel")]]),
        parse_mode="Markdown"
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📨 Ýaýlym habaryny iberiň:")
    context.user_data["broadcasting"] = True

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(USERS_FILE, "rb") as f:
        await update.callback_query.message.reply_document(f)

async def admin_add_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🎟 Täze promokod we skidkany ýazyň (mysal üçin: PROMO10 10):")
    context.user_data["adding_promo"] = True

async def admin_remove_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    promos = Database.read_promos()
    if not promos:
        await update.callback_query.message.reply_text("❌ Promokodlar ýok!")
        return

    keyboard = [[InlineKeyboardButton(promo, callback_data=f"remove_{promo}")] for promo in promos]
    keyboard.append([InlineKeyboardButton("🔙 Yza", callback_data="admin_panel")])
    await update.callback_query.message.reply_text(
        "🎟 Pozmaly promokody saýlaň:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_change_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("✏️ Täze test kody iberiň:")
    context.user_data["waiting_for_test"] = True

async def show_main_menu(update, user):
    text = f"""Merhaba, {user.full_name} 👋 

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
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)
    users = Database.read_db()

    back_button = [[InlineKeyboardButton("🔙 Yza", callback_data="main_menu")]]
    if data == "my_keys":
        keys = users.get(user_id, {}).get("keys", [])
        text = "Siziň açarlaryňyz:" if keys else "Siziň açarlaryňyz ýok."
        keyboard = [[InlineKeyboardButton(f"Server {len(keys)}", callback_data="show_keys")]]
        await query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "show_keys":
        keys = users.get(user_id, {}).get("keys", [])
        await query.message.reply_text("\n".join(keys) if keys else "Açarlar ýok")
    elif data == "referral":
        ref_link = f"https://t.me/{context.bot.username}?start={user_id}"
        ref_count = users.get(user_id, {}).get("ref_count", 0)
        text = f"""Siz 5 adam çagyryp platny kod alyp bilersiňiz 🎁 

Referal sylkaňyz: {ref_link}

Referal sanyňyz: {ref_count}"""

        await query.message.reply_text(text)
    elif data == "get_test":
        test_kod = Database.read_test_codes()
        message = await query.message.reply_text("Test Kodyňyz Ýasalýar...")
        await asyncio.sleep(2)
        await message.edit_text(test_kod if test_kod else "Test kody ýok.")
    elif data == "use_promo":
        await query.message.reply_text("🎟 Promokody ýazyň:")
        context.user_data["waiting_for_promo"] = True
    elif data == "vpn_prices":
        base_prices = {
            "vpn_3": 20,
            "vpn_7": 40,
            "vpn_15": 100,
            "vpn_30": 130
        }
        discount = context.user_data.get("promo_discount", 0)
        prices_text = (
            "**Eger platny kod almakçy bolsaňyz aşakdaky knopka basyň we BOT arkaly admin'iň size ýazmagyna garaşyn📍**\n"
            "-----------------------------------------------\n"
            "🌍 **VPN adı: Shadowsocks**🛍️\n"
            "-----------------------------------------------\n"
            "🕯️ 3 Gün'lik: 20 тмт\n"
            "🔒 Hepdelik: 40 тмт\n"
            "🔑 15 Gün'lik: 100 тмт\n"
            "🔋 Aylık Trafik: 150 тмт\n"
        )
        keyboard = []
        row = []
        for key, price in base_prices.items():
            discounted_price = price * (1 - discount / 100)
            button = InlineKeyboardButton(f"📅 {key.split('_')[1]} gün - {discounted_price:.2f} 𝚃𝙼𝚃", callback_data=key)
            row.append(button)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        await query.message.reply_text(
            text=prices_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif data.startswith("vpn_"):
        days = data.split("_")[1]
        user = query.from_user
        await context.bot.send_message(
            chat_id=user.id,
            text=f"✅ {days}gün kod saýlandy!"
        )
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=user.id,
            text="⏳ Tiz wagtdan admin size ýazar."
        )
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=user.id,
            text="🚫 Eger admin'iň size ýazmagyny islemeýän bolsaňyz /stop ýazyp bilersiňiz."
        )
        admin_text = f"🆕 Täze sargyt:\n👤 Ulanyjy: {user.full_name}({user.id})\n📆 Zakaz: {days} gün"
        keyboard = [[InlineKeyboardButton("✅ Kabul etmek", callback_data=f"accept_{user.id}_{days}")]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("accept_"):
        _, target_id, days = data.split("_")
        target_id = int(target_id)
        active_orders[str(target_id)] = str(ADMIN_ID)
        active_orders[str(ADMIN_ID)] = str(target_id)

        keyboard = [[InlineKeyboardButton("🚫 Zakazy ýapmak", callback_data=f"close_{target_id}")]]
        await query.message.reply_text(
            text=f"✅ Zakaz kabul edildi!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await context.bot.send_message(
            chat_id=target_id,
            text="✅ Zakaz kabul edildi! Admin bilen habarlaşyp bilersiňiz."
        )
    elif data.startswith("close_"):
        target_id = data.split("_")[1]
        if target_id in active_orders:
            del active_orders[target_id]
            await query.message.reply_text("✅ Zakaz ýapyldy!")
            await context.bot.send_message(chat_id=int(target_id), text="🔒 Admin zakazy ýapdy!")
    elif data == "admin_change_test":
        await query.message.reply_text("✏️ Täze test kody iberiň:")
        context.user_data["waiting_for_test"] = True
    elif data == "admin_panel":
        await show_admin_menu(query, context)
    elif data == "main_menu":
        if query.from_user.id == ADMIN_ID:
            await show_admin_menu(query, context)
        else:
            await show_main_menu(query, query.from_user)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    user = update.effective_user

    if not update.message:
        return

    text = update.message.text.strip() if update.message.text else ""
    photo = update.message.photo[-1] if update.message.photo else None

    if text.startswith("close_"):
        target_id = text.split("_")[1]
        if target_id in active_orders:
            del active_orders[target_id]
            await update.message.reply_text("✅ Zakaz ýapyldy!")
            await context.bot.send_message(chat_id=int(target_id), text="🔒 Admin zakazy ýapdy!")
        return

    if str(user.id) in active_orders:
        target_id = active_orders[str(user.id)]
        if photo:
            await context.bot.send_photo(chat_id=target_id, photo=photo.file_id, caption=f"👤 {user.full_name}: Foto")
        else:
            await context.bot.send_message(chat_id=target_id, text=f"👤 {user.full_name}: {text}")
        return

    if user.id == ADMIN_ID:
        for target_id, admin_id in active_orders.items():
            if admin_id == str(user.id):
                if photo:
                    await context.bot.send_photo(chat_id=int(target_id), photo=photo.file_id, caption=f"👮 Admin: Foto")
                else:
                    await context.bot.send_message(chat_id=int(target_id), text=f"👮 Admin: {text}")

                if any(text.startswith(proto) for proto in ("ss://", "vmess://")):
                    users = Database.read_db()
                    users.setdefault(str(target_id), {"keys": [], "ref_count": 0})
                    users[str(target_id)]["keys"].append(text)
                    Database.save_db(users)
                    await update.message.reply_text(f"✅ Açar üstünlikli goşuldy: {target_id}")
        return

    if any(text.startswith(proto) for proto in ("ss://", "vmess://")):
        users = Database.read_db()
        user_id = str(user.id)
        users.setdefault(user_id, {"keys": [], "ref_count": 0})
        users[user_id]["keys"].append(text)
        Database.save_db(users)
        await update.message.reply_text("✅ Açar üstünlikli goşuldy!")
        
async def vpn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Bu buýrugy diňe admin ulanýar!")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Ulanyş usuly: /vpn <id> <açar>")
        return

    target_id = args[0]
    key = " ".join(args[1:]).strip()

    if not any(key.startswith(proto) for proto in ("ss://", "vmess://")):
        await update.message.reply_text("❌ Açar formaty nädogry!")
        return

    users = Database.read_db()
    users.setdefault(target_id, {"keys": [], "ref_count": 0})
    users[target_id]["keys"].append(key)

    Database.save_db(users)

    await update.message.reply_text(f"✅ Açar üstünlikli goşuldy: {target_id}")
    await context.bot.send_message(chat_id=int(target_id), text=f"🔑 Size täze VPN açar berildi:\n`{key}`", parse_mode="Markdown")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_orders
    user_id = str(update.effective_user.id)
    if user_id in active_orders:
        del active_orders[user_id]
        await update.message.reply_text("🔕 Adminiň size ýazmagy goýbolsun edildi!")

async def add_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text("Ullanmak: /add_promo <kod> <skidka>")
        return
    promo_code, discount = context.args
    try:
        discount = int(discount)
        if not (1 <= discount <= 100):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Skitka 1-dan 100-e çenli aralyk bolmaly.")
        return
    promos = Database.read_promos()
    promos[promo_code] = discount
    Database.write_promos(promos)
    await update.message.reply_text(f"✅ Skidka: {promo_code} {discount}% Üstünlikli goşuldy!")

async def remove_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 1:
        await update.message.reply_text("Ullanmak: /remove_promo <kod>")
        return
    promo_code = context.args[0]
    promos = Database.read_promos()
    if promo_code in promos:
        del promos[promo_code]
        Database.write_promos(promos)
        await update.message.reply_text(f"✅ Promokod {promo_code} pozuldy!")
    else:
        await update.message.reply_text("❌ Promokod tapylmady!")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    application.add_handler(CallbackQueryHandler(admin_export, pattern="^admin_export$"))
    application.add_handler(CallbackQueryHandler(admin_add_promo, pattern="^admin_add_promo$"))
    application.add_handler(CallbackQueryHandler(admin_remove_promo, pattern="^admin_remove_promo$"))
    application.add_handler(CallbackQueryHandler(admin_change_test, pattern="^admin_change_test$"))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("add_promo", add_promo))
    application.add_handler(CommandHandler("remove_promo", remove_promo))
    application.add_handler(CommandHandler("vpn", vpn_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.PHOTO, message_handler))

    application.run_polling()

if __name__ == "__main__":
    main()