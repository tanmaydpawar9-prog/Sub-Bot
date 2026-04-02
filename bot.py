import telebot
import pysubs2
import os
from pysubs2 import Color
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Store user file data
user_files = {}

# ---------------- COMMANDS ---------------- #

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
"""👋 Hello, Welcome to Subtitle Bot!

🎬 What I can do:
• Convert SRT/VTT → ASS
• Apply clean Donghua styling
• Cinematic & Full 4K styles

📌 How to use:
Send a .srt or .vtt file

⚡ Powered by The Friction Realm
""")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message,
"""🛠 Help Guide

1. Send subtitle file (.srt or .vtt)
2. Choose style
3. Get styled .ass file

❗ Supported:
• SRT
• VTT

❌ Not supported:
• TXT
• ASS input
""")

@bot.message_handler(commands=['about'])
def about(message):
    bot.reply_to(message,
"""📌 About This Bot

This bot converts subtitles into styled ASS format
optimized for Donghua / Anime releases.

✨ Features:
• Cinematic scaling (1920x818)
• True 4K styling
• Clean output

👨‍💻 Built for automation workflow
""")

# ---------------- FILE HANDLER ---------------- #

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    file_name = message.document.file_name

    if not file_name.endswith((".srt", ".vtt")):
        bot.reply_to(message, "❌ Send only .srt or .vtt files")
        return

    # Store file data
    user_files[message.chat.id] = {
        "file_id": message.document.file_id,
        "name": file_name
    }

    # Buttons
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Cinematic", callback_data="cinema"),
        InlineKeyboardButton("📺 Full 4K", callback_data="full")
    )

    bot.send_message(message.chat.id,
                     "Choose subtitle style:",
                     reply_markup=markup)

# ---------------- CALLBACK HANDLER ---------------- #
def validate_subs(subs):
    errors = []
    warnings = []

    seen_lines = set()
    prev_end = 0

    for i, line in enumerate(subs):
        text = line.text.strip()

        # ❌ Empty line
        if not text:
            warnings.append(f"Line {i+1} is empty")

        # ❌ Invalid timing
        if line.start >= line.end:
            errors.append(f"Line {i+1} has invalid timing")

        # ❌ Overlap detection
        if line.start < prev_end:
            errors.append(f"Line {i+1} overlaps previous line")

        # ❌ Duplicate detection (exact)
        key = (text, line.start, line.end)
        if key in seen_lines:
            errors.append(f"Line {i+1} is duplicate")
        else:
            seen_lines.add(key)

        # ❌ Repeated text block detection (like 140–150 same lines)
        if i > 0 and text == subs[i-1].text.strip():
            warnings.append(f"Line {i+1} repeated text")

        # ❌ Too long line
        if len(text) > 120:
            warnings.append(f"Line {i+1} too long")

        prev_end = line.end

    # Detect repeated block patterns (strong duplicate case)
    text_list = [line.text.strip() for line in subs]

    for i in range(len(text_list) - 10):
        block1 = text_list[i:i+10]
        block2 = text_list[i+10:i+20]

        if block1 == block2:
            errors.append(f"Repeated block detected around line {i+1}")
            break

    return errors, warnings
    
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    file_data = user_files.get(call.message.chat.id)

    if not file_data:
        bot.answer_callback_query(call.id, "❌ No file found")
        return

    bot.send_message(call.message.chat.id, "⏳ Processing...")

    file_id = file_data["file_id"]
    file_name = file_data["name"]

    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        ext = os.path.splitext(file_name)[-1]
        input_file = "input" + ext

        with open(input_file, 'wb') as f:
            f.write(downloaded_file)

        subs = pysubs2.load(input_file)

        # -------- STYLE SELECTION -------- #

        if call.data == "cinema":
            subs.info["PlayResX"] = 1920
            subs.info["PlayResY"] = 818

            style = pysubs2.SSAStyle()
            style.fontname = "Arial"
            style.fontsize = 60
            style.outline = 2
            style.shadow = 2
            style.marginv = 100

        else:
            subs.info["PlayResX"] = 3840
            subs.info["PlayResY"] = 1636

            style = pysubs2.SSAStyle()
            style.fontname = "Arial"
            style.fontsize = 120
            style.outline = 4
            style.shadow = 4
            style.marginv = 200

        # -------- COMMON STYLE -------- #

        style.primarycolor = Color(255, 255, 255)
        style.outlinecolor = Color(0, 0, 0)
        style.backcolor = Color(0, 0, 0, 0)
        style.alignment = 2
        style.spacing = 1
        style.scalex = 70
        style.scaley = 90

        subs.info["ScaledBorderAndShadow"] = "yes"
        subs.styles["Default"] = style

        # -------- OUTPUT NAME -------- #

        name = os.path.splitext(file_name)[0]
        output_file = f"{name}_styled.ass"

        subs.save(output_file)

        with open(output_file, "rb") as f:
            bot.send_document(call.message.chat.id, f)

        # Cleanup
        os.remove(input_file)
        os.remove(output_file)

        bot.answer_callback_query(call.id, "✅ Done!")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error: {e}")

# ---------------- RUN BOT ---------------- #

print("Bot running...")
bot.infinity_polling()
