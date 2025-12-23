"""
Точка входа для Telegram бота.
Настраивает и запускает бота с обработчиками команд и сообщений.
"""

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_TOKEN, TARGET_WORDS
from handlers import (
    start_command,
    help_command,
    words_command,
    example_command,
    handle_button,
    handle_text_message,
    error_handler,
)

# Загружаем переменные окружения
load_dotenv()

def main() -> None:
    """Запускает бота"""
    print("=" * 50)
    print("🤖 Telegram Text Analyzer Bot")
    print(f"🔍 Ищем слова: {', '.join(TARGET_WORDS)}")
    print("=" * 50)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("words", words_command))
    
    # Обработчик кнопок (текст совпадает с кнопками)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(📝|ℹ️|📋)'),
        handle_button
    ))
    
    # Обработчик текстовых сообщений (для анализа)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_message
    ))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("🚀 Бот запущен! Нажмите Ctrl+C для остановки.")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()