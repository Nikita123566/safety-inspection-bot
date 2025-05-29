import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стадии разговора
SECTION, QUIZ, COMPLETION = range(3)

# Данные инструктажа
sections = [
    {
        "title": "🛳 Общие положения",
        "content": "1.1. Работа на БМРТ связана с повышенной опасностью\n"
                   "1.2. Обязательное использование СИЗ: спасательные жилеты, нескользящая обувь, защитные очки\n"
                   "1.3. Запрещено находиться на палубе без производственной необходимости во время шторма\n\n"
                   "<b>Суда класса БМРТ:</b>\n"
                   "- 'Капитан Смирнов'\n- 'Океан'\n- 'Моряна'\n(и еще 8 судов)",
    },
    {
        "title": "⚠️ Опасные факторы",
        "content": "2.1. Скользкие палубы\n2.2. Морские волны\n2.3. Рыболовное оборудование\n"
                   "2.4. Низкие температуры\n2.5. Ограниченная видимость\n\n"
                   "<b>Требования:</b>\n- Всегда держаться за поручни\n- Работать только в спасательных жилетах\n- Не подходить к работающим механизмам"
    },
    {
        "title": "🚨 Аварийные ситуации",
        "content": "3.1. Человек за бортом: немедленно бросить спасательный круг, сообщить капитану\n"
                   "3.2. Пожар: использовать ближайший огнетушитель, следовать к местам сбора\n"
                   "3.3. Разгерметизация: надеть гидрокостюмы, следовать указаниям команды\n\n"
                   "<b>Важно:</b> Все члены экипажа должны знать расположение аварийных выходов и спассредств"
    }
]

quizzes = [
    {
        "question": "Обязательно ли использовать спасательный жилет при выходе на палубу во время шторма?",
        "options": ["Только ночью", "Да, всегда", "Только новичкам"],
        "correct": 1
    },
    {
        "question": "Что делать при обнаружении человека за бортом?",
        "options": [
            "Продолжать работу", 
            "Немедленно бросить спасательный круг и сообщить капитану", 
            "Прыгнуть за борт для спасения"
        ],
        "correct": 1
    }
]

# Обработчики команд
def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    update.message.reply_html(
        f"Привет, {user.first_name}!\n\n"
        "Добро пожаловать на вводный инструктаж по охране труда для экипажей БМРТ.\n\n"
        "<b>Пройдите 3 раздела инструктажа:</b>\n"
        "1. Общие положения\n"
        "2. Опасные факторы\n"
        "3. Действия в аварийных ситуациях\n\n"
        "Нажмите /begin чтобы начать инструктаж"
    )
    return ConversationHandler.END

def begin(update: Update, context: CallbackContext) -> int:
    context.user_data['current_section'] = 0
    return show_section(update, context)

def show_section(update: Update, context: CallbackContext) -> int:
    section_index = context.user_data['current_section']
    section = sections[section_index]
    
    keyboard = [
        [InlineKeyboardButton("Следующий раздел →", callback_data='next')],
        [InlineKeyboardButton("Начать тестирование", callback_data='quiz')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.callback_query.edit_message_text(
        text=f"<b>{section['title']}</b>\n\n{section['content']}",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return SECTION

def start_quiz(update: Update, context: CallbackContext) -> int:
    context.user_data['current_question'] = 0
    context.user_data['score'] = 0
    return show_question(update, context)

def show_question(update: Update, context: CallbackContext) -> int:
    question_index = context.user_data['current_question']
    question = quizzes[question_index]
    
    keyboard = []
    for i, option in enumerate(question['options']):
        keyboard.append([InlineKeyboardButton(option, callback_data=str(i))])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.callback_query.edit_message_text(
        text=f"❓ Вопрос {question_index+1}/{len(quizzes)}\n\n{question['question']}",
        reply_markup=reply_markup
    )
    return QUIZ

def handle_answer(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    question_index = context.user_data['current_question']
    selected_option = int(query.data)
    
    if selected_option == quizzes[question_index]['correct']:
        context.user_data['score'] += 1
        feedback = "✅ Верно!"
    else:
        feedback = "❌ Неверно!"
    
    # Следующий вопрос или завершение
    context.user_data['current_question'] += 1
    
    if context.user_data['current_question'] < len(quizzes):
        query.edit_message_text(text=f"{feedback} Переходим к следующему вопросу...")
        return show_question(update, context)
    else:
        score = context.user_data['score']
        total = len(quizzes)
        query.edit_message_text(
            text=f"📝 Тест завершен!\n\nВаш результат: {score}/{total}\n\n"
            "Инструктаж успешно пройден! Ваши данные внесены в журнал учета."
        )
        return COMPLETION

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Инструктаж прерван')
    return ConversationHandler.END

def main() -> None:
    # Токен бота (замените на ваш)
    TOKEN = "BOT_TOKEN"
    
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('begin', begin)],
        states={
            SECTION: [
                CallbackQueryHandler(show_section, pattern='^back$'),
                CallbackQueryHandler(start_quiz, pattern='^quiz$'),
                CallbackQueryHandler(show_section, pattern='^next$'),
            ],
            QUIZ: [
                CallbackQueryHandler(handle_answer)
            ],
            COMPLETION: [
                CallbackQueryHandler(start, pattern='^done$')
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
