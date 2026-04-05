import telebot
import pysubs2
import os
import requests
import asyncio
from pyrogram import Client
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = telebot.TeleBot(BOT_TOKEN)

# Pyrogram client (user session)
app = Client("my_session", api_id=API_ID, api_hash=API_HASH)

user_files = {}

# ===================== COMMANDS =====================

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "👋 Send subtitle file or direct download link")

# ===================== FILE HANDLER =====================

@bot.message_handler(content_types=['document'])
def handle_file(message):
    name = message.document.file_name

    if not name.endswith((".srt", ".vtt")):
        bot.reply_to(message, "❌ Only SRT/VTT supported")
        return

    user_files[message.chat.id] = {
        "file_id": message.document.file_id,
        "name": name,
        "size": message.document.file_size
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Cinematic", callback_data="cinema"),
        InlineKeyboardButton("📺 Full 4K", callback_data="full"),
        InlineKeyboardButton("🔄 Convert VTT → SRT", callback_data="vtt_srt")
    )

    bot.send_message(message.chat.id, "Choose option:", reply_markup=markup)

# ===================== ERROR CHECK =====================

def check_errors(subs):
    errors = []

    for i in range(len(subs)-1):
        if subs[i].end > subs[i+1].start:
            errors.append(f"Overlap at line {i+1}")

        if subs[i].text == subs[i+1].text:
            errors.append(f"Duplicate at line {i+1}")

    return errors

# ===================== CALLBACK =====================

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = user_files.get(call.message.chat.id)

    if not data:
        bot.answer_callback_query(call.id, "No file found")
        return

    file_info = bot.get_file(data["file_id"])
    file = bot.download_file(file_info.file_path)

    input_name = data["name"]
    output_name = os.path.splitext(input_name)[0] + ".ass"

    with open(input_name, "wb") as f:
        f.write(file)

    try:
        subs = pysubs2.load(input_name)

        # ERROR CHECK
        errors = check_errors(subs)
        if errors:
            bot.send_message(call.message.chat.id, "⚠️ Errors:\n" + "\n".join(errors))

        # VTT → SRT
        if call.data == "vtt_srt":
            out = input_name.replace(".vtt", ".srt")
            subs.save(out)
            bot.send_document(call.message.chat.id, open(out, "rb"))
            return

        # STYLING
        if call.data == "cinema":
            subs.info["PlayResX"] = 1920
            subs.info["PlayResY"] = 818
            size = 60
        else:
            subs.info["PlayResX"] = 3840
            subs.info["PlayResY"] = 1636
            size = 120

        style = pysubs2.SSAStyle()
        style.fontname = "Arial"
        style.fontsize = size
        style.outline = 2
        style.shadow = 2
        style.alignment = 2
        style.marginv = 100

        subs.styles["Default"] = style
        subs.save(output_name)

        bot.send_document(call.message.chat.id, open(output_name, "rb"))

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")

    finally:
        if os.path.exists(input_name):
            os.remove(input_name)
        if os.path.exists(output_name):
            os.remove(output_name)

    bot.answer_callback_query(call.id, "Done")

# ===================== LINK HANDLER =====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("http"))
def handle_link(message):
    url = message.text.strip()
    bot.reply_to(message, "⬇️ Downloading...")

    file_name = "downloaded_file"

    try:
        r = requests.get(url, stream=True)
        with open(file_name, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)

        bot.reply_to(message, "📤 Uploading to channel...")

        asyncio.run(upload_to_channel(file_name))

        bot.reply_to(message, "✅ Uploaded!")

    except Exception as e:
        bot.reply_to(message, f"❌ Failed: {e}")

# ===================== PYROGRAM UPLOAD =====================

async def upload_to_channel(file_name):
    async with app:
        await app.send_document(CHANNEL_ID, file_name)

# ===================== RUN =====================

print("Bot running...")
bot.infinity_polling()
