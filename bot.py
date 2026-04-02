import telebot
import pysubs2
import os
from pysubs2 import Color
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Store file IDs temporarily
user_files = {}

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    file_name = message.document.file_name

    if not file_name.endswith((".srt", ".vtt")):
        bot.reply_to(message, "Send only .srt or .vtt files")
        return

    # Save file_id
    user_files[message.chat.id] = message.document.file_id

    # Create buttons
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Cinematic", callback_data="cinema"),
        InlineKeyboardButton("Regular", callback_data="full")
    )

    bot.send_message(message.chat.id, "Choose Subtitle Type For The Donghua:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    file_id = user_files.get(call.message.chat.id)

    if not file_id:
        bot.answer_callback_query(call.id, "No file found")
        return

    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    input_file = "input.srt"
    with open(input_file, 'wb') as f:
        f.write(downloaded_file)

    subs = pysubs2.load(input_file)

    # CINEMATIC STYLE
    if call.data == "cinema":
        subs.info["PlayResX"] = 1920
        subs.info["PlayResY"] = 818

        style = pysubs2.SSAStyle()
        style.fontname = "Arial"
        style.fontsize = 60
        style.primarycolor = Color(255, 255, 255)
        style.outlinecolor = Color(0, 0, 0)
        style.backcolor = Color(0, 0, 0, 0)

        style.outline = 2
        style.shadow = 2
        style.alignment = 2
        style.marginv = 100
        style.spacing = 1
        style.scalex = 70
        style.scaley = 90

    # 🎯 FULL SIZE STYLE
    else:
        subs.info["PlayResX"] = 3840
        subs.info["PlayResY"] = 1636

        style = pysubs2.SSAStyle()
        style.fontname = "Arial"
        style.fontsize = 120
        style.primarycolor = Color(255, 255, 255)
        style.outlinecolor = Color(0, 0, 0)
        style.backcolor = Color(0, 0, 0, 0)

        style.outline = 4
        style.shadow = 4
        style.alignment = 2
        style.marginv = 200
        style.spacing = 1
        style.scalex = 70
        style.scaley = 90

    # Apply global settings
    subs.info["ScaledBorderAndShadow"] = "yes"
    subs.styles["Default"] = style

    # Save output
    output_file = "file_name.ass"
    subs.save(output_file)

    # Send back to user
    with open(output_file, "rb") as f:
        bot.send_document(call.message.chat.id, f)

    # Cleanup
    os.remove(input_file)
    os.remove(output_file)

    bot.answer_callback_query(call.id, "Done!")

print("Bot running...")
bot.infinity_polling()

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
"""👋 Hello, Welcome to Subtitle Bot!

🎬 What I can do:
• Convert SRT/VTT → ASS
• Apply clean Donghua styling
• Ready for encoding & Telegram uploads

📌 How to use:
Just send a .srt or .vtt file

⚡ Powered by The Friction Realm
""")
@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message,
"""🛠 Help Guide

1. Send subtitle file (.srt or .vtt)
2. Wait a few seconds
3. Get styled .ass file

❗ Supported:
• SRT
• VTT

❌ Not supported:
• TXT
• ASS input

If something fails, resend file.
""")

@bot.message_handler(commands=['about'])
def about(message):
    bot.reply_to(message,
"""📌 About This Bot

This bot converts subtitles into styled ASS format
optimized for Donghua / Anime releases.

✨ Features:
• Clean styling
• Proper scaling
• Ready for mux/encode

👨‍💻 Created for personal workflow automation
""")
