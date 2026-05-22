# chebubrya-memes-bot

Telegram-бот, который подбирает мем по текстовому запросу в групповом чате. Бот использует векторный поиск по базе мемов, опциональный reranker и собирает пользовательский feedback через inline-кнопки.

## Возможности

- Поиск мема по упоминанию бота в чате: `@bot_name запрос`.
- Поиск через команду: `/meme запрос`.
- Reply-режим: можно ответить на сообщение командой `/meme` или упоминанием бота.
- Retrieval через OpenAI embeddings или локальную SentenceTransformer-модель.
- Опциональный rerank через локальную CrossEncoder-модель или LLM.
- История запросов и feedback в PostgreSQL.
- Inline-кнопки под мемом: `👍`, `👎`, `Еще`.
- Скрипты для индексации, ручного поиска и оценки качества.

## Архитектура

- `aiogram` - Telegram bot polling.
- `ChromaDB` - векторное хранилище мемов.
- `OpenAI/OpenRouter` - embeddings и LLM rerank, если локальные модели не используются.
- `sentence-transformers` - локальная retrieval-модель.
- `CrossEncoder` - локальный reranker.
- `PostgreSQL` - история запросов, выбранных мемов, кандидатов и feedback.
- `Docker Compose` - запуск бота и PostgreSQL на сервере.

## Структура проекта

```text
src/memes_bot/
  bot.py              Telegram handlers, inline feedback
  client.py           OpenAI/OpenRouter client helpers
  config.py           env-настройки
  database.py         PostgreSQL tables and logging
  indexer.py          загрузка CSV и индексация в Chroma
  local_retrieval.py  локальные embeddings
  reranker.py         локальный reranker
  retriever.py        retrieval + выбор лучшего мема
  vector_store.py     ChromaDB helpers

src/scripts/
  index_memes.py                 индексировать датасет
  query_memes.py                 проверить поиск из консоли
  evaluate_retrieval.py          оценить retrieval
  evaluate_retrieval_rerank.py   оценить retrieval + local reranker
  compare_retrieval_configs.py   сравнить baseline/local/rerank
```

## Настройка `.env`

Скопируйте пример:

```bash
cp .env.example .env
```

Основные переменные:

```env
TELEGRAM_BOT_TOKEN=123456:replace_me

OPENAI_API_KEY=sk-or-v1-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_SITE_URL=
OPENROUTER_SITE_NAME=memes-bot

OPENAI_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENAI_RERANK_MODEL=openai/gpt-5-mini

CHROMA_DIR=storage/chroma
MEME_COLLECTION=memes
RETRIEVAL_TOP_K=5

LOCAL_RETRIEVAL_MODEL_PATH=
LOCAL_RETRIEVAL_USE_E5_PREFIXES=true
LOCAL_RERANKER_MODEL_PATH=

POSTGRES_DB=memes_bot
POSTGRES_USER=memes_bot
POSTGRES_PASSWORD=replace_me_with_strong_password
DATABASE_URL=postgresql://memes_bot:replace_me_with_strong_password@postgres:5432/memes_bot
```

Для локального запуска без Docker `DATABASE_URL` обычно должен указывать на `localhost`:

```env
DATABASE_URL=postgresql://memes_bot:password@localhost:5432/memes_bot
```

## Локальная установка

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Индексация мемов

CSV должен содержать колонку с путем к картинке и текстовые колонки для embedding. Пример:

```powershell
python src\scripts\index_memes.py `
  --dataset "путь\dataset\check_1.csv" `
  --image-column "image_path" `
  --text-columns "embedding_text" "ocr_text" "semantic_description" `
  --reset
```

Linux/bash:

```bash
python src/scripts/index_memes.py \
  --dataset "путь/dataset/check_1.csv" \
  --image-column "image_path" \
  --text-columns "embedding_text" "ocr_text" "semantic_description" \
  --reset
```

Если используется локальная retrieval-модель, `LOCAL_RETRIEVAL_MODEL_PATH` должен указывать на папку SentenceTransformer-модели, где есть `modules.json`.

## Проверка поиска из консоли

```bash
python src/scripts/query_memes.py --query "когда понедельник" --show-candidates
```

Без вывода кандидатов:

```bash
python src/scripts/query_memes.py --query "когда понедельник"
```

## Запуск бота локально

```bash
python -m memes_bot.main
```

Если запускаете не через установленный пакет, задайте `PYTHONPATH`:

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m memes_bot.main
```

Linux/bash:

```bash
PYTHONPATH=src python -m memes_bot.main
```

## сравнение baseline, local и rerank

Для честного сравнения OpenAI retrieval и local retrieval нужны разные Chroma-коллекции

Пример:

- `memes_openai` - проиндексирована OpenAI embeddings.
- `memes_local` - проиндексирована локальной SentenceTransformer-моделью.

Индексация OpenAI baseline:

```powershell
python src\scripts\index_memes.py `
  --dataset "путь\dataset\check_1.csv" `
  --image-column "image_path" `
  --text-columns "embedding_text" "ocr_text" "semantic_description" `
  --collection memes_openai `
  --embedding-backend api `
  --reset
```

Индексация local retrieval:

```powershell
python src\scripts\index_memes.py `
  --dataset "путь\dataset\check_1.csv" `
  --image-column "image_path" `
  --text-columns "embedding_text" "ocr_text" "semantic_description" `
  --collection memes_local `
  --embedding-backend local `
  --reset
```

Сравнение:

```powershell
python src\scripts\compare_retrieval_configs.py `
  --dataset "путь\dataset\val_check_1.csv" `
  --query-columns "user_messages" `
  --api-collection memes_openai `
  --local-collection memes_local `
  --top-k 1 3 5 `
  --retrieve-k 20
```

Результаты на `val_check_1.csv`, 270 запросов:

```text
mode        | queries | errors | Recall@1 | Recall@3 | Recall@5 | MRR
------------+---------+--------+----------+----------+----------+-------
local       | 270     | 0      | 0.4074   | 0.6222   | 0.7074   | 0.5464
local-local | 270     | 0      | 0.4444   | 0.6519   | 0.7296   | 0.5734
```

```text
mode      | queries | errors | Recall@1 | Recall@3 | Recall@5 | MRR
----------+---------+--------+----------+----------+----------+-------
api-api   | 270     | 0      | 0.5519   | 0.6185   | 0.6667   | 0.6089
local-api | 270     | 0      | 0.5667   | 0.6963   | 0.7630   | 0.6576
```

Лучшее качество в текущем сравнении дает `local-api`: локальная retrieval-модель поднимает более релевантный набор кандидатов, а API-reranker выбирает лучший мем из top-k. По сравнению с полностью API-based схемой `api-api`, гибридный режим выше по всем ключевым метрикам: Recall@1, Recall@3, Recall@5 и MRR.

Для production это дает два рабочих профиля:

- `local-api` - максимальное качество при умеренной стоимости API, потому что API вызывается только для rerank короткого списка кандидатов.
- `local-local` - автономный и бесплатный вариант без сетевой зависимости, с более низким качеством, но стабильной стоимостью и latency.

## Feedback и PostgreSQL

После ответа бот показывает кнопки:

- `👍` - мем подошел;
- `👎` - мем не подошел;
- `Еще` - показать следующего кандидата.

Данные сохраняются в PostgreSQL:

- `meme_requests` - запрос, выбранный мем, список кандидатов, статус, ошибка;
- `meme_feedback` - лайк, дизлайк или еще.

Эти данные можно использовать для дообучения reranker и retrieval
