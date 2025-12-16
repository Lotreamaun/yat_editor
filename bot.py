"""
Telegram Text Analyzer Bot
Ищет целевые слова и их формы в тексте с учетом морфологии
"""

import os
import re
import logging
from typing import Dict, List, Tuple
from dotenv import load_dotenv
from pymorphy3 import MorphAnalyzer
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext,
)
from telegram.constants import ParseMode

# Загружаем переменные окружения
load_dotenv()

# ==================== КОНФИГУРАЦИЯ ====================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    print("❌ ОШИБКА: TELEGRAM_TOKEN не найден в .env файле!")
    print("Создайте файл .env и добавьте: TELEGRAM_TOKEN=ваш_токен")
    exit(1)

# Слова для поиска (можно менять)
TARGET_WORDS = ["нейронка", "алгоритм", "программа", "бот", "тест"]

# Максимальная длина текста (чтобы бот не падал на больших текстах)
MAX_TEXT_LENGTH = 4000

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== АНАЛИЗАТОР ТЕКСТА ====================

class TextAnalyzer:
    """Анализатор текста для поиска целевых слов"""
    
    def __init__(self, target_words: List[str]):
        self.morph = MorphAnalyzer()
        self.target_words = set(word.lower() for word in target_words)
        self.cache = {}  # Кэш для ускорения
        
    def normalize_word(self, word: str) -> str:
        """Приводит слово к нормальной форме (лемме)"""
        word_lower = word.lower()
        
        if word_lower in self.cache:
            return self.cache[word_lower]
        
        try:
            parsed = self.morph.parse(word_lower)[0]
            normal_form = parsed.normal_form
            self.cache[word_lower] = normal_form
            return normal_form
        except:
            return word_lower
    
    def is_target_word(self, word: str) -> bool:
        """Проверяет, является ли слово формой целевого слова"""
        normal_form = self.normalize_word(word)
        return normal_form in self.target_words
    
    def analyze_text(self, text: str) -> Dict:
        """
        Анализирует текст и возвращает результат
        
        Возвращает:
        {
            "highlighted": str,  # Текст с выделенными словами
            "matches": List[Dict],  # Найденные слова
            "stats": Dict[str, int],  # Статистика по словам
            "total": int,  # Всего найдено слов
            "unique": int,  # Уникальных слов
        }
        """
        if not text.strip():
            return {
                "highlighted": "",
                "matches": [],
                "stats": {},
                "total": 0,
                "unique": 0
            }
        
        # Находим все слова в тексте с позициями
        matches = []
        for match in re.finditer(r'[а-яА-ЯёЁa-zA-Z]+', text):
            word = match.group()
            start, end = match.span()
            
            if self.is_target_word(word):
                matches.append({
                    "word": word,
                    "normal": self.normalize_word(word),
                    "start": start,
                    "end": end,
                })
        
        # Сортируем совпадения с конца для корректного выделения
        matches_sorted = sorted(matches, key=lambda x: x["start"], reverse=True)
        
        # Выделяем слова в тексте
        highlighted_text = text
        for match in matches_sorted:
            word = match["word"]
            start, end = match["start"], match["end"]
            # Жирный текст для Telegram (используем MarkdownV2)
            highlighted_word = f"**{word}**"
            highlighted_text = highlighted_text[:start] + highlighted_word + highlighted_text[end:]
        
        # Считаем статистику
        stats = {}
        for match in matches:
            base_word = match["normal"]
            stats[base_word] = stats.get(base_word, 0) + 1
        
        return {
            "highlighted": highlighted_text,
            "matches": matches,
            "stats": stats,
            "total": len(matches),
            "unique": len(stats),
        }

# Инициализируем анализатор
analyzer = TextAnalyzer(TARGET_WORDS)

# ==================== TELEGRAM БОТ ====================

def create_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру для бота"""
    keyboard = [
        ["📝 Анализировать текст"],
        ["ℹ️ Помощь", "📋 Слова"],
        ["🚀 Пример", "🧹 Очистить"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

🤖 Я бот для анализа текста. Я умею находить в тексте целевые слова и их формы.

🎯 **Что я могу:**
✓ Найти все формы целевых слов (например: нейронка, нейронки, нейронкой)
✓ Выделить их в тексте жирным
✓ Показать статистику

📝 **Как пользоваться:**
1. Нажмите "📝 Анализировать текст"
2. Отправьте мне текст
3. Получите результат с выделенными словами

🔍 **Сейчас я ищу слова:**
{', '.join(f'`{word}`' for word in TARGET_WORDS)}

Просто отправьте мне текст или нажмите "📝 Анализировать текст"!
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
📚 **Справка по использованию бота**

**Основные команды:**
/start - Начать работу
/help - Показать эту справку
/words - Показать слова для поиска
/example - Пример работы

**Как это работает:**
1. Вы отправляете текст (до {MAX_TEXT_LENGTH} символов)
2. Я нахожу все формы целевых слов
3. Возвращаю текст с выделенными **жирным** словами
4. Показываю статистику

**Пример:**
Вы: `Современные нейронки используют алгоритмы`
Я: `Современные **нейронки** используют **алгоритмы**`

**Важно:**
• Я ищу слова с учетом падежей и чисел
• Слова с общим корнем, но другой основой (нейросети ≠ нейронка) не выделяются
• Поддерживаются русские и английские слова

📝 Просто отправьте мне текст и попробуйте!
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

async def example_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает пример работы"""
    example_text = """
🚀 **Пример работы бота:**

Отправьте мне такой текст:
Современные нейронки используют сложные алгоритмы для обработки данных.
Каждая нейронка имеет свои особенности, а нейронками сегодня пользуются многие программисты. 
Однако нейросети - это не то же самое, что нейронки.

**И статистику:**
📊 **Статистика:**
• нейронка: 4
• алгоритм: 1

**Всего найдено:** 5 слов
**Уникальных слов:** 2

Попробуйте отправить этот текст или свой!
    """
    
    await update.message.reply_text(
        example_text,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия кнопок"""
    text = update.message.text
    
    if text == "📝 Анализировать текст":
        await update.message.reply_text(
            "📝 **Отправьте текст для анализа**\n\n"
            "Просто напишите или вставьте текст сообщением. "
            f"Максимальная длина: {MAX_TEXT_LENGTH} символов.\n\n"
            "Я найду все целевые слова и выделю их **жирным**.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif text == "ℹ️ Помощь":
        await help_command(update, context)
    
    elif text == "📋 Слова":
        await words_command(update, context)
    
    elif text == "🚀 Пример":
        await example_command(update, context)
    
    elif text == "🧹 Очистить":
        # Очищаем контекст пользователя
        context.user_data.clear()
        await update.message.reply_text(
            "✅ История очищена. Можно отправлять новый текст!",
            reply_markup=create_keyboard()
        )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения (анализирует текст)"""
    user = update.effective_user
    text = update.message.text
    
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
    
    # Сохраняем текст в контексте (для возможного использования в будущем)
    context.user_data['last_text'] = text
    
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
                "❌ **Целевые слова не найдены**\n\n"
                "В вашем тексте не обнаружено слов из списка для поиска.\n"
                "Попробуйте другой текст или проверьте список слов командой /words",
                parse_mode=ParseMode.MARKDOWN
            )
            await processing_msg.delete()
            return
        
        # Отправляем обработанный текст
        await update.message.reply_text(
            result["highlighted"],
            parse_mode=ParseMode.MARKDOWN
        )
        
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
                "😔 **Произошла внутренняя ошибка**\n\n"
                "Пожалуйста, попробуйте еще раз или обратитесь к разработчику.",
                parse_mode=ParseMode.MARKDOWN
            )
    except:
        pass

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
    application.add_handler(CommandHandler("example", example_command))
    
    # Обработчик кнопок (текст совпадает с кнопками)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(📝|ℹ️|📋|🚀|🧹)'),
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