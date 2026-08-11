"""
Гибридная коррекция текста: алгоритмическая правка явных опечаток и оформления,
опциональная глубокая правка грамматики/пунктуации через LLM.

Модуль клиент-агностик: не зависит от Telegram и пригоден для веб-клиента.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from pymorphy3 import MorphAnalyzer
from razdel import tokenize

from config.config import (
    TARGET_WORDS,
    WORDS_LEMMA,
    DEEP_CORRECT_MAX_LENGTH,
    logger,
)
from analyzer.llm_yandex import llm_client


RUSSIAN_LETTERS = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
NAME_GRAMMEMES = {"Name", "Patr", "Surn", "Geox"}

DEEP_UNAVAILABLE_NOTE = "Глубокая правка недоступна"
DEEP_TOO_LONG_NOTE = (
    f"Глубокая правка недоступна: текст длиннее {DEEP_CORRECT_MAX_LENGTH} символов"
)


@dataclass
class CorrectionResult:
    """Структурированный результат коррекции (без статистики банвордов)."""

    original_text: str
    corrected_text: str
    algo_edits: int
    deep: bool
    deep_note: Optional[str] = None


def _build_whitelist() -> Set[str]:
    """Банворды и их словарные формы, которые алгоритм не должен 'чинить'."""
    words: Set[str] = set()
    for w in TARGET_WORDS:
        words.add(w.lower())
    for key, value in WORDS_LEMMA.items():
        words.add(key.lower())
        words.add(value.lower())
    return words


def _edits1(word: str) -> Set[str]:
    """Все строки на расстоянии одной правки (delete/transpose/replace/insert)."""
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = {a + b[1:] for a, b in splits[:-1]}
    transposes = {a + b[1] + b[0] + b[2:] for a, b in splits[:-2]}
    replaces = {a + c + b[1:] for a, b in splits[:-1] for c in RUSSIAN_LETTERS}
    inserts = {a + c + b for a, b in splits for c in RUSSIAN_LETTERS}
    return deletes | transposes | replaces | inserts


def _deletes(word: str) -> Set[str]:
    """Все строки с удалённой одной буквой (для поиска правок на расстоянии 2)."""
    return {word[:i] + word[i + 1:] for i in range(len(word))}


def _damerau_levenshtein(a: str, b: str) -> int:
    """Расстояние Дамерау-Левенштейна (optimal string alignment)."""
    if a == b:
        return 0
    len_a, len_b = len(a), len(b)
    if len_a == 0:
        return len_b
    if len_b == 0:
        return len_a
    if abs(len_a - len_b) > 2:
        return 3
    d = [[0] * (len_b + 1) for _ in range(len_a + 1)]
    for i in range(len_a + 1):
        d[i][0] = i
    for j in range(len_b + 1):
        d[0][j] = j
    for i in range(1, len_a + 1):
        for j in range(1, len_b + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len_a][len_b]


class AlgorithmicCorrector:
    """Бесплатный этап: явные опечатки и пунктуационно-оформительские правки."""

    def __init__(self) -> None:
        self.morph = MorphAnalyzer()
        self.whitelist = _build_whitelist()
        self._cache: Dict[str, Optional[str]] = {}

    def _word_known(self, word: str) -> bool:
        return word in self.whitelist or self.morph.word_is_known(word)

    def _fix_word(self, word: str) -> Optional[str]:
        """Возвращает замену для опечатки или None, если правка неоднозначна."""
        if word in self._cache:
            return self._cache[word]
        result = self._compute_fix(word)
        self._cache[word] = result
        return result

    def _is_proper_name(self, word: str) -> bool:
        """Имя собственное (имя/фамилия/отчество/топоним) — не кандидат в правку."""
        if not word:
            return False
        parse = self.morph.parse(word)[0]
        return bool(parse.tag.grammemes & NAME_GRAMMEMES)

    def _compute_fix(self, word: str) -> Optional[str]:
        if self.morph.word_is_known(word):
            return None

        # Правки на расстоянии 1: предпочитаем нарицательные, игнорируем имена
        distance1 = [c for c in _edits1(word) if c != word and self._word_known(c)]
        non_names = [c for c in distance1 if not self._is_proper_name(c)]
        if len(non_names) == 1:
            return non_names[0]
        if non_names:
            return None

        # Правки на расстоянии 2: паттерн "удалить букву + одна правка"
        candidates: Dict[str, int] = {}
        for w in _deletes(word):
            for c in _edits1(w):
                if c == word or not self._word_known(c):
                    continue
                dist = _damerau_levenshtein(word, c)
                if dist <= 2 and not self._is_proper_name(c):
                    candidates[c] = dist
        if not candidates:
            return None

        best_dist = min(candidates.values())
        best = [c for c, d in candidates.items() if d == best_dist]
        if len(best) == 1:
            return best[0]
        return None

    def correct(self, text: str) -> Tuple[str, int]:
        """Возвращает (исправленный текст, количество правок)."""
        if not text.strip():
            return text, 0

        edits: List[Tuple[int, int, str]] = []
        for token in tokenize(text):
            word = token.text
            if not word.isalpha():
                continue
            if word != word.lower():
                continue
            if len(word) < 3:
                continue
            if word.lower() in self.whitelist:
                continue
            replacement = self._fix_word(word.lower())
            if replacement and replacement != word.lower():
                edits.append((token.start, token.stop, replacement))

        text_out = text
        for start, stop, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
            text_out = text_out[:start] + replacement + text_out[stop:]

        # Пробел после , ; : ! ? перед буквой (без точки, чтобы не ломать т.д./URL)
        text_out, n1 = re.subn(r"(?<=[,;:!?])(?=[A-Za-zА-Яа-яЁё])", " ", text_out)
        # Схлопывание подряд идущих пробелов
        text_out, n2 = re.subn(r" {2,}", " ", text_out)
        # Заглавная буква после . ! ?
        text_out, n3 = re.subn(
            r"([.!?])(\s+)([а-яё])",
            lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
            text_out,
        )

        return text_out, len(edits) + n1 + n2 + n3


class Corrector:
    """Оркестрация: алгоритм → (опционально) LLM. С кэшем результата."""

    def __init__(self, algorithmic: AlgorithmicCorrector, llm_client) -> None:
        self.algorithmic = algorithmic
        self.llm = llm_client
        self.cache: Dict[str, CorrectionResult] = {}

    def _cache_key(self, text: str, deep: bool) -> str:
        import hashlib

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{digest}|{deep}"

    async def correct_text(self, text: str, deep: bool = False) -> CorrectionResult:
        """Корректирует текст и возвращает структурированный результат."""
        key = self._cache_key(text, deep)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        algo_text, algo_edits = self.algorithmic.correct(text)
        corrected = algo_text
        deep_applied = False
        note: Optional[str] = None

        if deep:
            if len(algo_text) > DEEP_CORRECT_MAX_LENGTH:
                note = DEEP_TOO_LONG_NOTE
            elif not self.llm.available():
                note = DEEP_UNAVAILABLE_NOTE
            else:
                try:
                    corrected = await self.llm.correct_text(algo_text)
                    deep_applied = True
                except Exception as e:
                    logger.warning(f"Ошибка LLM при глубокой правке: {e}")
                    note = DEEP_UNAVAILABLE_NOTE

        result = CorrectionResult(
            original_text=text,
            corrected_text=corrected,
            algo_edits=algo_edits,
            deep=deep_applied,
            deep_note=note,
        )
        self.cache[key] = result
        return result


corrector = Corrector(AlgorithmicCorrector(), llm_client)
