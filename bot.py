import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import inch

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Создаем папку photos, если её нет
if not os.path.exists("photos"):
    os.makedirs("photos")

# ---- ДАННЫЕ ----
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

# ---- СОСТОЯНИЯ ----
(SELECTING_USER,
 SELECTING_ENTITY,
 SELECTING_SHIP,
 ENTERING_DATE,
 ADDING_VIOLATION) = range(5)

user_data = {}

# ---- ОСНОВНЫЕ ФУНКЦИИ ----
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
        user_data['violations'].append({"description": text, "photo": None, "caption": ""})
        await update.message.reply_text("Нарушение добавлено. Отправьте фото или напишите /done.")
        return ADDING_VIOLATION

    photo = update.message.photo[-1]  # самое большое фото
    caption = update.message.caption or ""

    if not user_data['violations']:
        user_data['violations'].append({
            "description": "Нарушение без текста",
            "photo": photo.file_id,
            "caption": caption
        })
    else:
        user_data['violations'][-1]["photo"] = photo.file_id
        user_data['violations'][-1]["caption"] = caption

    # Скачиваем фото локально
    file_id = photo.file_id
    photo_path = os.path.join("photos", f"{file_id}.jpg")
    photo_file = await context.bot.get_file(file_id)
    await photo_file.download_to_drive(photo_path)

    await update.message.reply_text("Фото добавлено. Продолжайте или напишите /done.")
    return ADDING_VIOLATION


async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    violations = user_data.get('violations', [])
    if not violations:
        await update.message.reply_text("Вы не добавили ни одного нарушения.")
        return ADDING_VIOLATION

    # Сообщение об отчете
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

    for i, v in enumerate(violations):
        desc = f"{i + 1}. {v['description']}"
        await update.message.reply_text(desc)
        if v.get('photo'):
            await update.message.reply_photo(photo=v['photo'], caption=v['caption'])

    # Генерация PDF
    pdf_path = create_pdf_report(user_data)
    await update.message.reply_document(document=open(pdf_path, 'rb'))

    # Очистка данных
    user_data.clear()
    await update.message.reply_text("Проверка завершена. Чтобы начать новую — напишите /start.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.clear()
    await update.message.reply_text("Процесс отменён. Чтобы начать заново — напишите /start.")
    return ConversationHandler.END


# ---- ГЕНЕРАЦИЯ PDF ----
def create_pdf_report(data):
    font_path = os.path.join("fonts", "DejaVuSans.ttf")

    if not os.path.exists(font_path):
        print(f"[ERROR] Шрифт не найден: {font_path}")
        return None

    try:
        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
    except Exception as e:
        print(f"[ERROR] Не удалось зарегистрировать шрифт: {e}")
        return None

    style_normal = ParagraphStyle(
        'normal',
        fontName='DejaVu',
        fontSize=12,
        leading=14,
        alignment=TA_LEFT
    )

    style_title = ParagraphStyle(
        'title',
        fontName='DejaVu',
        fontSize=16,
        leading=20,
        alignment=TA_LEFT
    )

    filename = f"report_{data['date'].replace('.', '_')}.pdf"
    doc = SimpleDocTemplate(filename)
    story = []

    # Заголовок
    story.append(Paragraph("📋 Отчет по проверке охраны труда", style_title))
    story.append(Spacer(1, 24))

    # Информация
    text = f"""
    <b>Пользователь:</b> {USERS[data['user']]}</br>
    <b>Юридическое лицо:</b> {data['entity']}</br>
    <b>Судно:</b> {data['ship']}</br>
    <b>Дата:</b> {data['date']}</br>
    <b>Количество нарушений:</b> {len(data['violations'])}</br>
    """
    story.append(Paragraph(text.replace("</br>", "<br/>"), style_normal))
    story.append(Spacer(1, 12))

    # Нарушения
    for i, v in enumerate(data['violations']):
        desc = f"<b>{i + 1}.</b> {v['description']}"
        story.append(Paragraph(desc, style_normal))
        story.append(Spacer(1, 8))

        if v.get('photo'):
            photo_path = os.path.join("photos", f"{v['photo']}.jpg")
            if os.path.exists(photo_path):
                story.append(RLImage(photo_path, width=4 * inch, height=3 * inch))
                if v.get('caption'):
                    story.append(Paragraph(f"<i>Подпись: {v['caption']}</i>", style_normal))
                story.append(Spacer(1, 12))

    # Сохраняем PDF
    try:
        doc.build(story)
        return filename
    except Exception as e:
        print(f"[ERROR] Ошибка при создании PDF: {e}")
        return None


# ---- ЗАПУСК БОТА ----
def main():
    application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

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
