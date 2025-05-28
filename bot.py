import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
print("Проверяем наличие шрифта:", os.path.exists("fonts/DejaVuSans.ttf"))
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet
import os

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Данные
USERS = {
    "moiseenko": "Моисеенко А.С.",
    "zorin": "Зорин Я.Д.",
    "chernov": "Чернов Н.В.",
    "zuev": "Зуев Р.И."
}

LEGAL_ENTITIES = {
    "turnif": {
        "name": "АО Турниф",
        "ships": ["БМРТ Капитан Олейничук", "БМРТ Владивосток"]
    },
    "vostokryb": {
        "name": "ООО Востокрыбпром",
        "ships": ["БМРТ Владимир Лиманов", "БМРТ Иван Калинин"]
    },
    "intraros": {
        "name": "АО Интрарос",
        "ships": ["БМРТ Березина"]
    },
    "dmp": {
        "name": "АО ДМП РМ",
        "ships": ["БМРТ Павел Батов"]
    },
    "rmd": {
        "name": "ООО РМД ЮВА",
        "ships": ["БМРТ Мыс Басаргина"]
    },
    "mintay": {
        "name": "ООО Минтай Первый",
        "ships": ["БМРТ Капитан Вдовиченко"]
    },
    "novostroy": {
        "name": "ООО Новострой",
        "ships": ["БМРТ Механик Маслак"]
    },
    "rrpk": {
        "name": "ООО РРПК-Восток",
        "ships": ["БМРТ Механик Сизов"]
    },
    "seyval": {
        "name": "ООО Новый Сейвал",
        "ships": ["БМРТ Капитан Мартынов"]
    }
}

# Состояния
(SELECTING_USER,
 SELECTING_ENTITY,
 SELECTING_SHIP,
 ENTERING_DATE,
 ADDING_VIOLATION) = range(5)

user_data = {}  # Хранилище данных для текущего пользователя


# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=uid)] for uid, name in USERS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите пользователя:", reply_markup=reply_markup)
    return SELECTING_USER


async def select_entity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data['user'] = query.data
    keyboard = [[InlineKeyboardButton(entity["name"], callback_data=key)] for key, entity in LEGAL_ENTITIES.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Выберите юридическое лицо:", reply_markup=reply_markup)
    return SELECTING_ENTITY


async def select_ship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    entity_key = query.data
    entity = LEGAL_ENTITIES[entity_key]
    user_data['entity'] = entity["name"]
    keyboard = [[InlineKeyboardButton(ship, callback_data=ship)] for ship in entity["ships"]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Выберите судно:", reply_markup=reply_markup)
    return SELECTING_SHIP


async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data['ship'] = query.data
    await query.edit_message_text("Введите дату проверки (в формате ДД.ММ.ГГГГ):")
    return ENTERING_DATE


async def process_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        from datetime import datetime
        datetime.strptime(text, "%d.%m.%Y")
        user_data['date'] = text
        if 'violations' not in user_data:
            user_data['violations'] = []
        await update.message.reply_text("Опишите нарушение. Если фото есть — отправьте его.")
        return ADDING_VIOLATION
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Попробуйте снова (ДД.ММ.ГГГГ).")
        return ENTERING_DATE


async def handle_violation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text and text.lower() == "/done":
        return await generate_report(update, context)

    if text:
        user_data['violations'].append({"description": text, "photo": None})
        await update.message.reply_text("Нарушение добавлено. Отправьте фото или напишите /done.")
        return ADDING_VIOLATION

    photo = update.message.photo[-1]  # самое большое фото
    caption = update.message.caption or ""
    user_data['violations'][-1]["photo"] = photo.file_id
    user_data['violations'][-1]["caption"] = caption
    await update.message.reply_text("Фото добавлено. Продолжайте описывать нарушения или напишите /done.")
    return ADDING_VIOLATION


async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    violations = user_data.get('violations', [])
    if not violations:
        await update.message.reply_text("Вы не добавили ни одного нарушения.")
        return ADDING_VIOLATION

    # Текст отчета
    report_text = (
        f"📋 Отчет по проверке:\n"
        f"Пользователь: {USERS[user_data['user']]}\n"
        f"Юрлицо: {user_data['entity']}\n"
        f"Судно: {user_data['ship']}\n"
        f"Дата: {user_data['date']}\n"
        f"Количество нарушений: {len(violations)}\n\n"
        f"🔍 Описания нарушений:"
    )
    await update.message.reply_text(report_text)

    for i, violation in enumerate(violations):
        desc = f"{i + 1}. {violation['description']}"
        await update.message.reply_text(desc)
        if violation['photo']:
            await update.message.reply_photo(photo=violation['photo'], caption=violation['caption'])

    # Генерация PDF
    pdf_path = create_pdf_report(user_data)
    await update.message.reply_document(document=open(pdf_path, 'rb'))

    # Очистка данных
    user_data.clear()
    await update.message.reply_text("Проверка завершена. Чтобы начать новую — напишите /start.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.clear()
    await update.message.reply_text("Процесс отменен. Чтобы начать заново — напишите /start.")
    return ConversationHandler.END


def create_pdf_report(data):
    filename = f"report_{data['date'].replace('.', '_')}.pdf"
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph("📋 Отчет по проверке охраны труда", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 24))

    text = f"""
    <b>Пользователь:</b> {USERS[data['user']]}<br/>
    <b>Юридическое лицо:</b> {data['entity']}<br/>
    <b>Судно:</b> {data['ship']}<br/>
    <b>Дата проверки:</b> {data['date']}<br/>
    <b>Количество нарушений:</b> {len(data['violations'])}<br/>
    """
    story.append(Paragraph(text, styles['Normal']))
    story.append(Spacer(1, 12))

    for i, v in enumerate(data['violations']):
        story.append(Paragraph(f"<b>{i+1}.</b> {v['description']}", styles['Normal']))
        if v['photo']:
            story.append(Spacer(1, 12))
            # Для сохранения картинок нужно их загрузить (это пример)
            # Здесь можно использовать file.download_as_bytearray(), если нужно полное сохранение
            # Для упрощения просто указываем, что они приложены к PDF

    doc.build(story)
    return filename


# --- Конец функций ---

def main():
    application = ApplicationBuilder().token("8045118401:AAGrrj1LTm-UzUuwNqFIY1L-BSYCz53usUs").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_USER: [CallbackQueryHandler(select_entity)],
            SELECTING_ENTITY: [CallbackQueryHandler(select_ship)],
            SELECTING_SHIP: [CallbackQueryHandler(enter_date)],
            ENTERING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_date)],
            ADDING_VIOLATION: [
                MessageHandler(filters.PHOTO, handle_violation),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_violation),
                CommandHandler('done', generate_report),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    print("Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()
