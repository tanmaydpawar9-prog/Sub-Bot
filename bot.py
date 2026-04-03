import telebot
import pysubs2
import os
import time
from pysubs2 import Color
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

user_files = {}

# ---------------- COMMAND ---------------- #

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
"""👋 Welcome to Subtitle Bot!

🎬 Features:
• Style ASS (Cinematic / 4K)
• Convert VTT → SRT
• Error detection

📌 Send a subtitle file to begin
""")

# ---------------- FILE HANDLER ---------------- #

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    file_name = message.document.file_name

    if not file_name.endswith((".srt", ".vtt")):
        bot.reply_to(message, "❌ Send only .srt or .vtt files")
        return

    user_files[message.chat.id] = {
        "file_id": message.document.file_id,
        "name": file_name
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Style ASS", callback_data="style"),
        InlineKeyboardButton("🔄 VTT → SRT", callback_data="convert")
    )

    bot.send_message(message.chat.id, "Choose option:", reply_markup=markup)

# ---------------- VALIDATION ---------------- #

def validate_subs(subs):
    errors = []
    prev_end = 0

    for i, line in enumerate(subs):
        if line.start >= line.end:
            errors.append(f"Line {i+1} invalid timing")

        if line.start < prev_end:
            errors.append(f"Line {i+1} overlaps")

        prev_end = line.end

    return errors

# ---------------- CALLBACK ---------------- #

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):

    file_data = user_files.get(call.message.chat.id)

    if not file_data:
        bot.answer_callback_query(call.id, "Send file again")
        return

    file_id = file_data["file_id"]
    file_name = file_data["name"]

    # ---------- STEP 1: STYLE MENU ---------- #
    if call.data == "style":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🎬 Cinematic", callback_data="cinema"),
            InlineKeyboardButton("📺 Full 4K", callback_data="full")
        )

        bot.edit_message_text(
            "Choose style:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        return

    # ---------- PROCESSING START ---------- #

    # Remove buttons AFTER final click
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except:
        pass

    bot.send_message(call.message.chat.id, "⏳ Processing...")

    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        ext = os.path.splitext(file_name)[-1]
        input_file = f"input_{int(time.time())}{ext}"

        with open(input_file, 'wb') as f:
            f.write(downloaded_file)

        # Safe load
        try:
            subs = pysubs2.load(input_file, encoding="utf-8", errors="ignore")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Invalid file:\n{e}")
            os.remove(input_file)
            return

        # Validate
        errors = validate_subs(subs)

        if errors:
            bot.send_message(call.message.chat.id,
                             "❌ Errors found:\n\n" + "\n".join(errors[:10]))
            os.remove(input_file)
            user_files.pop(call.message.chat.id, None)
            return

        name = os.path.splitext(file_name)[0]

        # ---------- CONVERT ---------- #
        if call.data == "convert":
            output_file = f"{name}.srt"
            subs.save(output_file)

        # ---------- STYLE ---------- #
        elif call.data in ["cinema", "full"]:

            subs.info["ScaledBorderAndShadow"] = "yes"

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

            style.primarycolor = Color(255, 255, 255)
            style.outlinecolor = Color(0, 0, 0)
            style.backcolor = Color(0, 0, 0, 0)
            style.alignment = 2
            style.spacing = 1
            style.scalex = 70
            style.scaley = 90

            subs.styles["Default"] = style

            output_file = f"{name}.ass"
            subs.save(output_file)

        # ---------- SEND ---------- #
        with open(output_file, "rb") as f:
            bot.send_document(call.message.chat.id, f)

        # Cleanup
        os.remove(input_file)
        os.remove(output_file)
        user_files.pop(call.message.chat.id, None)

        bot.answer_callback_query(call.id, "✅ Done")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error:\n{e}")

# ---------------- RUN ---------------- #

print("Bot running...")
bot.infinity_polling()
