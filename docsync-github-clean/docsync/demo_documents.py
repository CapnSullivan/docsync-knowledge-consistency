"""
demo_documents.py

Техническое назначение:
    Модуль управляет тестовыми рабочими документами игровой песочницы.

Зачем нужен модуль:
    Для проверки сканера нужны документы с разными вариантами ошибок. Если править
    их вручную, тестовые данные быстро превращаются в хаос. Этот модуль умеет
    восстановить базовые документы и затем внести контролируемые искажения.

Важный контракт для тестов:
    Генератор возвращает не только выбранные строки, но и список ожидаемых
    искажений. Поэтому тест может проверять не просто количество найденных
    проблем, а конкретные места, ключи, тексты и типы ошибок.
"""

import random
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape


TITLE_VARIANTS = [
    "Game about might and magic",
    "Game About of Might and Magik",
    "Game abaut of might and magik",
    "Game about of might and magic",
]

MANA_VARIANTS = [
    "mana",
    "mane",
    "maana",
    "мана",
    "манна",
]

SHORT_DESCRIPTION_VARIANTS = [
    "A tactical fantasy game about heroes, armies and spells.",
    "A tactic fantasy adventure about heroes, armies, spells, and ancient kingdoms.",
    "A tactical fantasy adventure about heros, armies, spells, and ancient kingdoms.",
]

GAME_TITLE_CANONICAL = "Game about of might and magik"
MANA_CANONICAL = "mana"
SHORT_DESCRIPTION_CANONICAL = "A tactical fantasy adventure about heroes, armies, spells, and ancient kingdoms."


@dataclass(frozen=True)
class ExpectedDistortion:
    """
    Одна ожидаемая проблема, которую генератор сознательно внес в документ.

    Это не результат сканера. Это обещание генератора для теста:
        "я вставил такой текст, и сканер должен найти его как такую проблему".

    Благодаря этому тест проверяет не абстрактное количество ошибок, а конкретный
    контракт: файл, ключ знания, ошибочный текст и ожидаемый тип проблемы.
    """
    file_path: str
    key: str
    created_text: str
    expected_text: str
    expected_match_type: str


@dataclass(frozen=True)
class MutateDemoResult:
    """
    Результат генерации искаженных тестовых документов.

    selected_values:
        Все значения, которые генератор вставил в документы.

    expected_distortions:
        Только те selected_values, которые должны считаться проблемами.
        Например `мана` является alias для `mana`, поэтому она остается
        в selected_values, но не попадает в expected_distortions.
    """
    selected_values: dict[str, str]
    expected_distortions: list[ExpectedDistortion]


def get_game_knowledge_dir(project_dir: Path) -> Path:
    return project_dir / "documents_sandbox" / "game_knowledge"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_docx(path: Path, paragraphs: list[str]) -> None:
    """
    Создает минимальный .docx для песочницы.

    Это не полноценный генератор Word-документов. Здесь нужен простой .docx,
    который наш docx_reader сможет прочитать как источник текста.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    def paragraph_xml(text: str) -> str:
        return f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"

    document_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {paragraphs}
    <w:sectPr/>
  </w:body>
</w:document>
'''.format(paragraphs="\n    ".join(paragraph_xml(text) for text in paragraphs))

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'''

    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'''

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)


def build_combat_document(title_variant: str, mana_variant: str, extra_mana_variant: str) -> str:
    return f"""# Заметки по боевой системе

## Назначение документа

Этот документ описывает направление боевого дизайна проекта. Он используется как рабочая спецификация для фиксации предположений о тактических сражениях, развитии героев, составе армий и применении заклинаний.

Документ является обычным рабочим markdown-файлом. Система должна анализировать такой текст через реестр знаний и находить возможные совпадения, ошибки и расхождения без вмешательства в структуру документа.

## Ссылка на проект

Боевая система относится к игре {title_variant}.

Это название может отличаться от канонического значения из реестра знаний. Такой пример показывает реалистичную проблему документации: специалист может написать название по памяти, заменить стилизованное написание на привычное или пропустить часть формулировки во время черновой работы.

## Направление боевой системы

Боевая система строится вокруг контролируемых тактических столкновений, а не вокруг масштабных автоматических сражений. Целевой игровой опыт - последовательность понятных решений, где размещение войск, момент применения заклинаний и развитие героя влияют на исход боя.

Основные принципы боевой модели:

- Небольшие армии с понятными ролями отрядов.
- Тактическое позиционирование без чрезмерного микроменеджмента.
- Школы магии с различными стратегическими возможностями.
- Развитие героя, которое постепенно меняет доступные тактики.
- Темп сражений, совместимый с исследованием кампании и управлением ресурсами.

## Ресурсы заклинаний

В текущей черновой модели герой использует {mana_variant} для применения базовых заклинаний. В отдельных заметках встречается написание {extra_mana_variant}, которое должно рассматриваться как кандидат на проверку.
"""


def build_tooltips_document(title_variant: str, description_variant: str) -> str:
    return f"""# UI-тексты и подсказки

## Назначение документа

Этот документ содержит черновые пользовательские тексты для меню, подсказок, коротких описаний и страниц представления проекта. UI-тексты часто имеют более жесткие ограничения по длине и формату, чем дизайн-документация, поэтому именно здесь часто появляются контролируемые отличия от канона.

Документ остается чистым markdown-текстом. Технические связи не встраиваются в текст. Система должна находить кандидатов на основе центра знаний и показывать их в отчете.

## Заголовок главного меню

Заголовок главного меню сейчас указан как {title_variant}.

Это значение может отличаться от канонического названия регистром букв, пропущенным словом или другим написанием.

## Короткое описание для страницы магазина

Короткое описание страницы магазина является компактной пользовательской формулировкой. Оно может быть короче внутреннего канонического описания, но такие отличия должны отслеживаться, потому что они влияют на позиционирование, тон и обещания продукта.

Текущий черновой вариант:

```text
{description_variant}
```
"""


def write_clean_docx(game_knowledge_dir: Path) -> None:
    """
    Восстанавливает чистый Word-документ песочницы.
    """
    write_docx(
        game_knowledge_dir / "word" / "overview.docx",
        [
            GAME_TITLE_CANONICAL,
            SHORT_DESCRIPTION_CANONICAL,
            "The hero uses mana for basic spells.",
        ],
    )


def reset_demo_documents(project_dir: Path) -> None:
    """
    Восстанавливает чистую базовую версию рабочих тестовых документов.

    После reset_demo_documents() обычный scan должен показывать 0 проблем.
    Ошибки должны появляться только после mutate_demo_documents().
    """
    game_knowledge_dir = get_game_knowledge_dir(project_dir)

    write_text(
        game_knowledge_dir / "design" / "combat.md",
        build_combat_document(
            title_variant=GAME_TITLE_CANONICAL,
            mana_variant=MANA_CANONICAL,
            extra_mana_variant="мана",
        ),
    )
    write_text(
        game_knowledge_dir / "ui" / "tooltips.md",
        build_tooltips_document(
            title_variant=GAME_TITLE_CANONICAL,
            description_variant=SHORT_DESCRIPTION_CANONICAL,
        ),
    )
    write_clean_docx(game_knowledge_dir)


def build_title_distortion(file_path: str, created_text: str) -> ExpectedDistortion | None:
    """
    Классифицирует сгенерированный вариант названия игры.

    Возвращает ExpectedDistortion, если вариант должен быть проблемой.
    Возвращает None, если вариант совпадает с каноном.
    """
    if created_text == GAME_TITLE_CANONICAL:
        return None

    match_type_by_text = {
        "Game about might and magic": "suspicious",
        "Game About of Might and Magik": "case_mismatch",
        "Game abaut of might and magik": "possible_phrase_typo",
        "Game about of might and magic": "possible_phrase_typo",
    }

    return ExpectedDistortion(
        file_path=file_path,
        key="game.title",
        created_text=created_text,
        expected_text=GAME_TITLE_CANONICAL,
        expected_match_type=match_type_by_text[created_text],
    )


def build_mana_distortion(file_path: str, created_text: str) -> ExpectedDistortion | None:
    """
    Классифицирует сгенерированный вариант термина mana.

    Здесь видно важное правило: не каждый вариант является ошибкой.
    `мана` является допустимым alias, поэтому тест не должен ждать проблему.
    """
    if created_text in {MANA_CANONICAL, "Mana", "мана"}:
        return None

    match_type_by_text = {
        "mane": "suspicious",
        "манна": "suspicious",
        "maana": "possible_typo",
    }

    return ExpectedDistortion(
        file_path=file_path,
        key="term.mana",
        created_text=created_text,
        expected_text=MANA_CANONICAL,
        expected_match_type=match_type_by_text[created_text],
    )


def build_description_distortion(file_path: str, created_text: str) -> ExpectedDistortion | None:
    """
    Классифицирует сгенерированный вариант короткого описания игры.

    Сейчас часть вариантов уже занесена как suspicious, а часть должна ловиться
    фразовым поиском как possible_phrase_typo.
    """
    if created_text == SHORT_DESCRIPTION_CANONICAL:
        return None

    match_type_by_text = {
        "A tactical fantasy game about heroes, armies and spells.": "suspicious",
        "A tactic fantasy adventure about heroes, armies, spells, and ancient kingdoms.": "possible_phrase_typo",
        "A tactical fantasy adventure about heros, armies, spells, and ancient kingdoms.": "possible_phrase_typo",
    }

    return ExpectedDistortion(
        file_path=file_path,
        key="game.short_description",
        created_text=created_text,
        expected_text=SHORT_DESCRIPTION_CANONICAL,
        expected_match_type=match_type_by_text[created_text],
    )


def collect_expected_distortions(selected_values: dict[str, str]) -> list[ExpectedDistortion]:
    """
    Собирает список ожидаемых проблем по выбранным генератором значениям.

    Не каждое выбранное значение является проблемой. Например `мана` является
    alias для `mana`, поэтому оно не должно попадать в expected_distortions.
    """
    possible_distortions = [
        build_title_distortion("design/combat.md", selected_values["combat_title"]),
        build_mana_distortion("design/combat.md", selected_values["combat_mana"]),
        build_mana_distortion("design/combat.md", selected_values["combat_extra_mana"]),
        build_title_distortion("ui/tooltips.md", selected_values["ui_title"]),
        build_description_distortion("ui/tooltips.md", selected_values["ui_description"]),
    ]

    return [distortion for distortion in possible_distortions if distortion is not None]


def mutate_demo_documents(project_dir: Path, seed: int | None = None) -> MutateDemoResult:
    """
    Восстанавливает базовые документы и вносит случайные искажения.

    Возвращает структурированный результат, чтобы CLI мог показать выбранные
    значения, а тесты могли сверить ожидаемые типы проблем с результатом сканера.
    """
    random_generator = random.Random(seed)
    game_knowledge_dir = get_game_knowledge_dir(project_dir)

    # selected_values - это все конкретные строки, которые попадут в документы.
    # Они нужны CLI для вывода и collect_expected_distortions() для классификации.
    selected_values = {
        "combat_title": random_generator.choice(TITLE_VARIANTS),
        "combat_mana": random_generator.choice(MANA_VARIANTS),
        "combat_extra_mana": random_generator.choice(MANA_VARIANTS),
        "ui_title": random_generator.choice(TITLE_VARIANTS),
        "ui_description": random_generator.choice(SHORT_DESCRIPTION_VARIANTS),
    }

    write_text(
        game_knowledge_dir / "design" / "combat.md",
        build_combat_document(
            title_variant=selected_values["combat_title"],
            mana_variant=selected_values["combat_mana"],
            extra_mana_variant=selected_values["combat_extra_mana"],
        ),
    )
    write_text(
        game_knowledge_dir / "ui" / "tooltips.md",
        build_tooltips_document(
            title_variant=selected_values["ui_title"],
            description_variant=selected_values["ui_description"],
        ),
    )
    write_clean_docx(game_knowledge_dir)

    # expected_distortions строится после записи документов из тех же selected_values.
    # Так генератор и тест говорят об одном и том же наборе вставленных строк.
    return MutateDemoResult(
        selected_values=selected_values,
        expected_distortions=collect_expected_distortions(selected_values),
    )
