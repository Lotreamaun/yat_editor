"""
Логика анализа текста с учетом морфологии.
Ищет целевые слова и их формы в тексте.
"""

import re
from typing import List, Dict
from pymorphy3 import MorphAnalyzer
from config import TARGET_WORDS, WORDS_LEMMA
from razdel import tokenize

class TextAnalyzer:
    
    def __init__(self, target_words: List[str]):
        self.morph = MorphAnalyzer()
        self.target_words = set(word.lower() for word in target_words)
        self.words_lemma: Dict[str, str] = WORDS_LEMMA
        self.cache = {}  # Кэш для ускорения
        
    def normalize_word(self, word: str) -> str:
        """Приводит слово к начальной форме (напр. ед.ч., именит. падеж для сущ.)"""
        word_lower = word.lower()
        
        if word_lower in self.cache:
            return self.cache[word_lower]
        
        if word_lower in self.words_lemma:
                print("Слово найдено в нашем словаре:", word_lower, "->", self.words_lemma[word_lower])
                normal_form = self.words_lemma[word_lower].lower()
        else:
            parsed = self.morph.parse(word_lower)
            print("Ищем слово в pymorphy3:", word_lower, "->", parsed[0].normal_form)
            normal_form = parsed[0].normal_form.lower() if parsed else word_lower

        self.cache[word_lower] = normal_form
        return normal_form
    
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

        # Находим все слова в тексте с позициями (razdel возвращает start/end и текст токена)
        matches = []
        for token in tokenize(text):
            word = token.text
            start = token.start
            end = token.stop

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
            highlighted_word = f"_{word}_"
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