"""
registry.py

Техническое назначение:
    Модуль отвечает за загрузку реестра знаний продукта из JSON-файла.

Входные данные:
    Путь к файлу knowledge_registry.json.

Выходные данные:
    Список объектов RegistryEntry. Каждый объект описывает одну активную
    запись реестра: ключ знания, каноническое значение, допустимые варианты
    и подозрительные варианты написания.

Граница ответственности:
    Модуль только читает и преобразует данные реестра.
    Он не сканирует markdown-документы.
    Он не ищет совпадения в тексте.
    Он не определяет опечатки.
    Он не печатает отчет.

Почему модуль не запускается напрямую:
    Это служебный модуль. Его используют другие скрипты, например
    Scripts/find_term_candidates.py. Сам по себе registry.py не выполняет
    пользовательский сценарий и поэтому не содержит точки входа main().
"""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RegistryEntry:
    """
    Одна активная запись из центра знаний продукта.

    key - стабильный ключ знания, например term.mana.
    canonical - правильное значение.
    aliases - допустимые варианты.
    suspicious - заранее известные подозрительные варианты.
    """
    key: str
    canonical: str
    aliases: list[str]
    suspicious: list[str]


def load_registry(registry_path: Path) -> list[RegistryEntry]:
    """
    Загружает центр знаний продукта из JSON-файла.

    Функция принимает путь явно, чтобы модуль registry.py не зависел
    от конкретной папки проекта. Так этот код можно будет использовать
    и для игровой песочницы, и для другой папки документов.
    """
    raw_items = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    entries = []

    for item in raw_items:
        if item.get("status") != "active":
            continue

        entries.append(
            RegistryEntry(
                key=item["key"],
                canonical=item["canonical"],
                aliases=item.get("aliases", []),
                suspicious=item.get("suspicious", []),
            )
        )

    return entries