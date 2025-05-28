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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

def create_pdf_report(data, photos=None):
    """
    Генерирует PDF-отчет по данным проверки.
    
    :param data: dict с данными пользователя, юрлица, даты и нарушений
    :param photos: dict с путями к фото или file_id
    :return: путь к созданному PDF
    """

    # Путь к шрифту
    font_path = os.path.join("fonts", "DejaVuSans.ttf")
    
    # Регистрация шрифта
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
    except Exception as e:
        print(f"[ERROR] Шрифт не найден: {e}")
        return None

    # Стили
    style_title = ParagraphStyle(
        'title',
        fontName='DejaVu',
        fontSize=16,
        leading=20,
        alignment=TA_LEFT
    )

    style_normal = ParagraphStyle(
        'normal',
        fontName='DejaVu',
        fontSize=12,
        leading=14,
        alignment=TA_LEFT
    )

    style_bold = ParagraphStyle(
        'bold',
        fontName='DejaVu',
        fontSize=12,
        leading=14,
        alignment=TA_LEFT,
        fontName='DejaVu'
    )

    # Создаем документ
    filename = f"report_{data['date'].replace('.', '_')}.pdf"
    doc = SimpleDocTemplate(filename)
    story = []

    # Заголовок
    story.append(Paragraph("📋 Отчет по проверке охраны труда", style_title))
    story.append(Spacer(1, 24))

    # Информация
    user_name = USERS[data['user']]
    story.append(Paragraph(f"<b>Пользователь:</b> {user_name}", style_normal))
    story.append(Paragraph(f"<b>Юридическое лицо:</b> {data['entity']}", style_normal))
    story.append(Paragraph(f"<b>Судно:</b> {data['ship']}", style_normal))
    story.append(Paragraph(f"<b>Дата проверки:</b> {data['date']}", style_normal))
    story.append(Paragraph(f"<b>Количество нарушений:</b> {len(data['violations'])}", style_normal))
    story.append(HRFlowable(width="100%", thickness=1, color="black"))
    story.append(Spacer(1, 12))

    # Нарушения
    for i, violation in enumerate(data['violations']):
        desc = f"<b>{i + 1}.</b> {violation['description']}"
        story.append(Paragraph(desc, style_normal))

        # Если есть фото
        if violation.get('photo'):
            photo_file_id = violation['photo']
            caption = violation.get('caption', '')

            # Путь для сохранённого фото (если ты его скачиваешь)
            photo_path = os.path.join("photos", f"{photo_file_id}.jpg")

            if os.path.exists(photo_path):
                story.append(Spacer(1, 12))
                story.append(RLImage(photo_path, width=300, height=200))
                if caption:
                    story.append(Paragraph(f"<i>Подпись: {caption}</i>", style_normal))
                story.append(Spacer(1, 12))

    # Генерируем PDF
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
