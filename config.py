import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Токен Телеграм бота
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