import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Stările conversației
DIRECTION, DATE, CITIES, SEATS, PHONE = range(5)

logging.basicConfig(level=logging.INFO)

def init_db():
    conn = sqlite3.connect('trips.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER, username TEXT, direction TEXT, date TEXT,
                  from_city TEXT, to_city TEXT, seats INTEGER, phone TEXT, created_at TEXT)''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Moldova → Germania", callback_data="md_de")],
        [InlineKeyboardButton("Germania → Moldova", callback_data="de_md")],
        [InlineKeyboardButton("Caută anunțuri", callback_data="search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Bună!\nAlege direcția sau caută anunțuri existente:", reply_markup=reply_markup)
    return DIRECTION

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "search":
        await query.edit_message_text("Scrie cuvinte-cheie (ex: Chișinău Berlin decembrie)")
        return ConversationHandler.END

    context.user_data["dir"] = "Moldova → Germania" if query.data == "md_de" else "Germania → Moldova"
    await query.edit_message_text(f"Direcție: {context.user_data['dir']}\n\nScrie data aproximativă (ex: 25 decembrie, 10-15 ianuarie, săptămâna viitoare):")
    return DATE

async def date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text
    await update.message.reply_text("Scrie ruta exactă, cu săgeată:\nEx: Chișinău → München")
    return CITIES

async def cities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace("->", "→").replace("-", "→")
    if "→" not in text:
        await update.message.reply_text("Te rog folosește săgeata → între orașe!")
        return CITIES
    context.user_data["route"] = text
    await update.message.reply_text("Câte locuri ai libere sau cauți? (ex: 2)")
    return SEATS

async def seats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        s = int(update.message.text)
        if 1 <= s <= 8:
            context.user_data["seats"] = s
            await update.message.reply_text("Număr de telefon (va fi vizibil celor interesați)\nSau apasă butonul să-l ascunzi:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Ascund telefonul", callback_data="no_phone")]]))
            return PHONE
    except:
        pass
    await update.message.reply_text("Scrie un număr valid între 1 și 8")
    return SEATS

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query and update.callback_query.data == "no_phone":
        context.user_data["phone"] = "Ascuns (contact prin Telegram)"
        msg = update.callback_query.message
    else:
        context.user_data["phone"] = update.message.text
        msg = update.message

    # Salvează în baza de date
    conn = sqlite3.connect('trips.db')
    c = conn.cursor()
    user = update.effective_user
    ruta = context.user_data["route"].split("→")
    c.execute("INSERT INTO trips VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
        user.id, user.username or user.first_name,
        context.user_data["dir"], context.user_data["date"],
        ruta[0].strip(), ruta[1].strip(),
        context.user_data["seats"], context.user_data["phone"],
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    await msg.reply_text(
        "Anunțul tău e publicat!\n\n"
        f"Direcție: {context.user_data['dir']}\n"
        f"Data: {context.user_data['date']}\n"
        f"Ruta: {context.user_data['route']}\n"
        f"Locuri: {context.user_data['seats']}\n"
        f"Telefon: {context.user_data['phone']}\n\n"
        "O să primești mesaj automat dacă apare cineva compatibil!"
    )

    # Arată ultimele anunțuri ca să vadă că funcționează
    await ultimele_anunturi(msg)
    return ConversationHandler.END

async def ultimele_anunturi(message):
    conn = sqlite3.connect('trips.db')
    c = conn.cursor()
    c.execute("SELECT * FROM trips ORDER BY id DESC LIMIT 8")
    rows = c.fetchall()
    conn.close()
    if len(rows) > 1:
        await message.reply_text("Ultimele anunțuri:")
        for r in rows[1:]:  # să nu se arate chiar al lui de două ori
            await message.reply_text(
                f"{r[3]}\n{r[5]} → {r[6]}\nData: {r[4]}\nLocuri: {r[7]}\nContact: {r[8]}\n@{r[2] if r[2] else 'anonim'}\n────────────"
            )

async def cautare_libera(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ultimele_anunturi(update.message)

def main():
    init_db()
    app = Application.builder().token(os.getenv("TOKEN")).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DIRECTION: [CallbackQueryHandler(button)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date)],
            CITIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cities)],
            SEATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, seats)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone),
                    CallbackQueryHandler(phone, pattern="no_phone")],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cautare_libera))

    print("Botul rulează...")
    app.run_polling()

if __name__ == "__main__":
    main()
