import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Данные для тестирования
USERS = {"user1": "Иван Иванов", "user2": "Петр Петров"}
LEGAL_ENTITIES = ["ООО Ромашка", "АО Голубь"]
OBJECTS = ["Склад №1", "Цех №3"]

# Состояния диалога
SELECTING_USER, SELECTING_ENTITY, SELECTING_OBJECT, ENTERING_DATE, TAKING_PHOTO = range(5)

# Хранилище данных
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=uid)] for uid, name in USERS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите пользователя:", reply_markup=reply_markup)
    return SELECTING_USER

async def select_entity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data['user'] = query.data
    keyboard = [[InlineKeyboardButton(entity, callback_data=entity)] for entity in LEGAL_ENTITIES]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Выберите юридическое лицо:", reply_markup=reply_markup)
    return SELECTING_ENTITY

async def select_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data['entity'] = query.data
    keyboard = [[InlineKeyboardButton(obj, callback_data=obj)] for obj in OBJECTS]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Выберите объект проверки:", reply_markup=reply_markup)
    return SELECTING_OBJECT

async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data['object'] = query.data
    await query.edit_message_text(text="Введите дату проверки (в формате ДД.ММ.ГГГГ):")
    return ENTERING_DATE

async def process_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        from datetime import datetime
        datetime.strptime(text, "%d.%m.%Y")
        user_data['date'] = text
        await update.message.reply_text("Теперь отправьте фото нарушений. После завершения напишите /done.")
        return TAKING_PHOTO
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Попробуйте снова (ДД.ММ.ГГГГ).")
        return ENTERING_DATE

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]  # Берём самое большое фото
    caption = update.message.caption or "Без комментария"
    if 'photos' not in user_data:
        user_data['photos'] = []
    user_data['photos'].append((photo.file_id, caption))
    await update.message.reply_text("Фото получено. Можете прислать ещё или напишите /done.")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'photos' not in user_data or len(user_data['photos']) == 0:
        await update.message.reply_text("Вы не загрузили ни одного фото.")
        return TAKING_PHOTO

    report = (
        f"📋 Отчет по проверке:\n"
        f"Пользователь: {USERS[user_data['user']]}\n"
        f"Юрлицо: {user_data['entity']}\n"
        f"Объект: {user_data['object']}\n"
        f"Дата: {user_data['date']}\n"
        f"Количество нарушений: {len(user_data['photos'])}\n\n"
        f"📸 Фото и описание нарушений:"
    )
    await update.message.reply_text(report)

    for i, (file_id, caption) in enumerate(user_data['photos']):
        await update.message.reply_photo(photo=file_id, caption=f"{i+1}. {caption}")

    user_data.clear()
    await update.message.reply_text("Проверка завершена. Чтобы начать новую — напишите /start.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Процесс отменен. Напишите /start чтобы начать заново.")
    return ConversationHandler.END

def main():
    application = ApplicationBuilder().token("8045118401:AAGrrj1LTm-UzUuwNqFIY1L-BSYCz53usUs").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_USER: [CallbackQueryHandler(select_entity)],
            SELECTING_ENTITY: [CallbackQueryHandler(select_object)],
            SELECTING_OBJECT: [CallbackQueryHandler(enter_date)],
            ENTERING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_date)],
            TAKING_PHOTO: [
                MessageHandler(filters.PHOTO, handle_photo),
                CommandHandler('done', done),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()