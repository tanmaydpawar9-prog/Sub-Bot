import telebot
import pysubs2
import os
import requests
import asyncio
import time
from pyrogram import Client
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = telebot.TeleBot(BOT_TOKEN)
app = Client("my_session", api_id=API_ID, api_hash=API_HASH)

user_files = {}

# ================= START ================= #

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "👋 Send subtitle file or direct link")

# ================= FILE ================= #

@bot.message_handler(content_types=['document'])
def handle_file(message):
    name = message.document.file_name

    if not name.endswith((".srt", ".vtt")):
        bot.reply_to(message, "❌ Only SRT/VTT supported")
        return

    user_files[message.chat.id] = {
        "file_id": message.document.file_id,
        "name": name
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Style", callback_data="style"),
        InlineKeyboardButton("🔄 Convert", callback_data="convert")
    )

    bot.send_message(message.chat.id, "Choose option:", reply_markup=markup)

# ================= ERROR CHECK ================= #

def check_errors(subs):
    errors = []
    for i in range(len(subs)-1):
        if subs[i].end > subs[i+1].start:
            errors.append(f"Overlap at line {i+1}")
        if subs[i].text == subs[i+1].text:
            errors.append(f"Duplicate at line {i+1}")
    return errors

# ================= CALLBACK ================= #

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = user_files.get(call.message.chat.id)

    if not data:
        bot.answer_callback_query(call.id, "Send file again")
        return

    if call.data == "style":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🎬 Cinematic", callback_data="cinema"),
            InlineKeyboardButton("📺 Full 4K", callback_data="full")
        )
        bot.edit_message_text("Choose style:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return

    if call.data == "convert":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("VTT → SRT", callback_data="vtt_srt")
        )
        bot.edit_message_text("Choose conversion:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return

    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except:
        pass

    bot.send_message(call.message.chat.id, "⏳ Processing...")

    file_info = bot.get_file(data["file_id"])
    file = bot.download_file(file_info.file_path)

    name = data["name"]
    base = os.path.splitext(name)[0]
    input_file = f"{int(time.time())}_{name}"

    with open(input_file, "wb") as f:
        f.write(file)

    try:
        subs = pysubs2.load(input_file)

        errors = check_errors(subs)
        if errors:
            bot.send_message(call.message.chat.id, "⚠️ Errors:\n" + "\n".join(errors[:10]))

        if call.data == "vtt_srt":
            out = f"{base}.srt"
            subs.save(out)
            bot.send_document(call.message.chat.id, open(out, "rb"))
            os.remove(out)
            return

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

        output_file = f"{base}.ass"
        subs.save(output_file)

        bot.send_document(call.message.chat.id, open(output_file, "rb"))
        os.remove(output_file)

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")

    finally:
        os.remove(input_file)
        user_files.pop(call.message.chat.id, None)

# ================= LINK ================= #

@bot.message_handler(func=lambda m: m.text and m.text.startswith("http"))
def handle_link(message):
    url = message.text.strip()
    msg = bot.reply_to(message, "🔍 Checking link...")

    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
        r = requests.get(url, stream=True, timeout=10, headers=headers)

        if r.status_code != 200:
            bot.edit_message_text("❌ Invalid link", message.chat.id, msg.message_id)
            return

        if "text/html" in r.headers.get("Content-Type", ""):
            bot.edit_message_text("❌ Not a direct file link", message.chat.id, msg.message_id)
            return

        total = int(r.headers.get('content-length', 0))
        size_mb = total / 1024 / 1024

        bot.edit_message_text(
            f"📦 File Size: {size_mb:.2f} MB\n⬇️ Starting download...",
            message.chat.id,
            msg.message_id
        )

        file_name = url.split("/")[-1]
        if not file_name or "." not in file_name:
            file_name = f"file_{int(time.time())}.bin"

        downloaded = 0
        start = time.time()
        last = 0
        stall_time = 0
        last_downloaded = 0

        with open(file_name, "wb") as f:
            for chunk in r.iter_content(5 * 1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if downloaded == last_downloaded:
                        stall_time += 1
                    else:
                        stall_time = 0

                    last_downloaded = downloaded

                    if stall_time > 20:
                        bot.edit_message_text("❌ Download stalled", message.chat.id, msg.message_id)
                        return

                    now = time.time()
                    speed = downloaded / (now - start)
                    percent = downloaded / total * 100 if total else 0
                    eta = (total - downloaded) / speed if speed > 0 else 0

                    downloaded_mb = downloaded / 1024 / 1024
                    total_mb = total / 1024 / 1024 if total else 0

                    if now - last > 2 or percent < 1:
                        text = (
                            f"⬇️ Downloading...\n\n"
                            f"{downloaded_mb:.2f} / {total_mb:.2f} MB\n"
                            f"📊 {percent:.2f}%\n"
                            f"⚡ {speed/1024/1024:.2f} MB/s\n"
                            f"⏱ {eta:.1f}s"
                        )
                        bot.edit_message_text(text, message.chat.id, msg.message_id)
                        last = now

        bot.edit_message_text("📤 Uploading...", message.chat.id, msg.message_id)
        asyncio.run(upload(file_name, message, msg))

    except Exception as e:
        bot.edit_message_text(f"❌ {e}", message.chat.id, msg.message_id)

    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

# ================= UPLOAD ================= #

async def upload(file_name, message, msg):
    start = time.time()
    last = 0

    async def progress(current, total):
        nonlocal last
        now = time.time()

        speed = current / (now - start)
        percent = current / total * 100
        eta = (total - current) / speed if speed > 0 else 0

        if now - last > 2 or percent < 1:
            text = (
                f"📤 Uploading...\n\n"
                f"📊 {percent:.2f}%\n"
                f"⚡ {speed/1024/1024:.2f} MB/s\n"
                f"⏱ {eta:.1f}s"
            )
            bot.edit_message_text(text, message.chat.id, msg.message_id)
            last = now

    async with app:
        await app.send_document(CHANNEL_ID, file_name, progress=progress)

    bot.edit_message_text("✅ Uploaded!", message.chat.id, msg.message_id)

# ================= RUN ================= #

print("Bot running...")
bot.infinity_polling()
