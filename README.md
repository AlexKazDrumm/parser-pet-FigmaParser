# parser-pet-FigmaParser

Сервис для экспорта выбранных узлов Figma в HTML, CSS и JSON. Макет можно
загрузить по ссылке или `file key`, выбрать нужные узлы в дереве и открыть
результат во встроенном предпросмотре.

## Режимы экспорта

- **Структурный** — формирует HTML, CSS и JSON по свойствам узлов Figma:
  геометрии, заливкам, обводкам, теням, типографике и auto-layout.
- **Pixel** — получает SVG или PNG выбранных узлов через Figma API и собирает
  их в разметку с абсолютным позиционированием.
- **AI** — передаёт описание узлов и изображения модели OpenAI и получает
  HTML и CSS. Подключается отдельной зависимостью.
- **По изображению** — строит HTML и CSS по загруженному скриншоту; при
  установленном Playwright сравнивает отрисовку с исходным изображением.

Поддерживаются ссылки вида
`https://www.figma.com/design/<key>/<name>?node-id=<id>`.

## Стек

- Python 3.11+
- FastAPI, Starlette, Uvicorn
- Pydantic и pydantic-settings
- httpx
- pytest и ruff
- OpenAI, Pillow и Playwright для дополнительных режимов

## Запуск

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m figma_exporter
```

Веб-интерфейс: <http://127.0.0.1:8000/>

OpenAPI: <http://127.0.0.1:8000/docs>

Проверка состояния: <http://127.0.0.1:8000/healthz>

Для работы с файлами Figma укажите `FIGMA_TOKEN` в `.env` или передайте токен
в запросе.

### Дополнительные режимы

```powershell
pip install -r requirements-ai.txt
pip install -r requirements-image.txt
python -m playwright install chromium
```

Для AI-режимов также нужен `OPENAI_API_KEY`.

## Основные маршруты

| Метод и путь | Назначение |
| --- | --- |
| `POST /api/figma/tree` | загрузка дерева узлов файла |
| `POST /api/figma/export/structured` | структурный экспорт |
| `POST /api/figma/export/pixel` | экспорт через изображения Figma |
| `POST /api/figma/export/ai` | экспорт с обработкой моделью |
| `POST /api/image/export` | экспорт по загруженному изображению |

## Конфигурация

Основные переменные окружения:

| Переменная | Назначение |
| --- | --- |
| `FIGMA_TOKEN` | токен Figma REST API |
| `OPENAI_API_KEY` | ключ для AI-режимов |
| `HOST`, `PORT` | адрес и порт сервера |
| `HTTP_TIMEOUT_SECONDS` | таймаут обращений к Figma |
| `HTTP_MAX_RETRIES` | число повторных запросов |
| `HTTP_MAX_RESPONSE_BYTES` | максимальный размер ответа Figma |
| `MAX_SELECTED_IDS` | максимальное число выбранных узлов |
| `MAX_UPLOAD_BYTES` | максимальный размер изображения |
| `OPENAI_DEFAULT_MODEL` | модель для AI-режимов |

Остальные настройки и значения по умолчанию перечислены в `.env.example`.

## Пример экспорта

В каталоге `examples` находятся данные карточки входа и результаты экспорта:

- `demo_figma_file.json`;
- `demo_output.html`;
- `demo_output.css`;
- `demo_output.json`;
- `demo_preview.html`.

Пересобрать пример:

```powershell
python examples/render_demo.py
```

## Проверки

```powershell
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

## Docker

```powershell
docker build -t figma-exporter .
docker run --rm -p 8000:8000 --env-file .env figma-exporter
```
