"""
Обработчики команд и сообщений для Telegram бота.
Содержит функции для команд /start, /help, /words, /example,
обработку кнопок и текстовых сообщений.
"""

import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackContext
from typing import Optional
from config import TARGET_WORDS, MAX_TEXT_LENGTH, logger
from analyzer import analyzer

#TODO: Добавить "Форматирование" для выбора выделения (Bold, Italic, Underline) (см. issue #1)
#TODO: Убрать кнопку "Анализировать текст" и запускать анализ по любому тексту сразу

def create_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру для бота"""
    keyboard = [
        ["ℹ️ Помощь", "📋 Слова"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

🤖 Умею находить в тексте целевые слова и их формы.

🎯 *Что я могу:*
- Найти все формы целевых слов из банлиста (например: нейронка, нейронки, нейронкой)
- Выделить их в тексте курсивом
- Показать статистику (в разработке)

📝 *Как пользоваться:*
1. Отправьте мне текст или перешлите любое сообщение
2. Получите результат с выделенными словами
3. Замените банворды и отправьте текст для перепроверки
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=create_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"Новый пользователь: {user.username} ({user.id})")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = f"""
📚 *Справка по использованию бота*

*Основные команды:*
/start - Начать работу
/help - Показать эту справку
/words - Показать слова для поиска

*Как это работает:*
1. Вы отправляете текст (до {MAX_TEXT_LENGTH} символов)
2. Я нахожу все формы бан-слов
3. Возвращаю текст с выделенными _курсивом_ словами

*Пример:*
Пользователь: Современные нейронки используют алгоритмы
Я: Современные _нейронки_ используют _алгоритмы_

*Важно:*
- Я ищу слова с учетом падежей и чисел
- Слова с общим корнем, но другой основой (нейросети ≠ нейронка) не выделяются
- Поддерживаются русские и английские слова
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )

async def words_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список целевых слов"""
    words_text = "📋 **Слова для поиска:**\n\n"
    
    for i, word in enumerate(TARGET_WORDS, 1):
        words_text += f"{i}. **{word}**\n"
    
    words_text += f"\nВсего слов: {len(TARGET_WORDS)}"
    
    await update.message.reply_text(
        words_text,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия кнопок"""
    text = update.message.text
    
    if text == "ℹ️ Помощь":
        await help_command(update, context)
    
    elif text == "📋 Слова":
        await words_command(update, context)

def get_incoming_text(update: Update) -> Optional[str]:
    """
    Извлекает текст из входящего сообщения:

    Функция принимает аргумент update (содержит информацию о сообщении)
    и вощвращает текст из сообщения или caption, если сообщение содержит медиа
    Optional[str] означает, что функция может вернуть строку или None

    Логика:
    - Если сообщение содержит caption, возвращаем его
    - Иначе возвращаем текст сообщения
    - Если нет текста и caption, возвращаем None
    """
    msg = update.message
    if not msg:
        return None
    return msg.caption if msg.caption else msg.text

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения (анализирует текст)"""
    user = update.effective_user
    text = get_incoming_text(update)
    
    if not text:
        """Если нет текста — ничего не отвечаем"""
        return

    logger.info(f"Пользователь {user.username} ({user.id}) отправил текст: {text[:50]}...")
    
    # Проверяем длину текста
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"❌ **Текст слишком длинный!**\n\n"
            f"Максимальная длина: {MAX_TEXT_LENGTH} символов\n"
            f"Ваш текст: {len(text)} символов\n\n"
            f"Пожалуйста, разделите текст на части и отправьте по частям.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Отправляем сообщение о начале обработки
    processing_msg = await update.message.reply_text(
        "🔍 **Анализирую текст...**",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Анализируем текст
        result = analyzer.analyze_text(text)
        
        # Если ничего не найдено
        if result["total"] == 0:
            await update.message.reply_text(
                "✅ **Банвордов в тексте не обнаружено**\n\n",
                parse_mode=ParseMode.MARKDOWN
            )
            await processing_msg.delete()
            return
        
        # Отправляем обработанный текст
        await update.message.reply_text(
            result["highlighted"],
            parse_mode=ParseMode.MARKDOWN
        )
        
        """
        Блок кода для отправки статистики
        """
        # Формируем и отправляем статистику
        stats_text = "📊 **Статистика:**\n\n"
        
        # Сортируем слова по количеству найденных
        sorted_stats = sorted(
            result["stats"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for word, count in sorted_stats:
            stats_text += f"• **{word}**: {count}\n"
        
        stats_text += f"\n**Всего найдено:** {result['total']} слов\n"
        stats_text += f"**Уникальных слов:** {result['unique']}"
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN
        )

        # Удаляем сообщение об обработке
        await processing_msg.delete()
        
        logger.info(f"Пользователь {user.username} - найдено {result['total']} слов")
        
    except Exception as e:
        logger.error(f"Ошибка при анализе текста: {e}")
        
        await processing_msg.delete()
        await update.message.reply_text(
            "❌ **Произошла ошибка при анализе текста**\n\n"
            "Попробуйте еще раз или отправьте текст в другом формате.",
            parse_mode=ParseMode.MARKDOWN
        )

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке сообщения: {context.error}")
    
    try:
        if update and update.message:
            await update.message.reply_text(
                "😔 **Произошла внутренняя ошибка**\n\n",
                parse_mode=ParseMode.MARKDOWN
            )
    except:
        pass