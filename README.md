## Быстрый старт

### Требования

- Свободные порты на хосте: **8501**, **8080**, **8081**, **9095**, **5430**, **2181**

### Запуск

```bash
# 1. Создать файл окружения с кредами Postgres
cp .env.example .env

# 2. Собрать и поднять весь стек
docker compose up -d --build
```

Дождаться, пока сервисы поднимутся (Airflow стартует 1-2 минуты):

```bash
docker compose ps
```

`data_loader` должен быть в статусе `Exited (0)`, остальные сервисы `Up`.

После старта доступны:

| Сервис | URL |
|--------|-----|
| Airflow | <http://localhost:8081> (логин `admin`, пароль `admin`) |
| Streamlit (приложение) | <http://localhost:8501> |
| Kafka UI | <http://localhost:8080> |
| Postgres | `localhost:5430` |
| Модели | `artifacts/models/` |
| DQ-отчёты | `artifacts/dq_reports/latest.html` |

Подключиться к базе:

```bash
docker compose exec postgres psql -U postgres_user -d postgres_db
```

### Остановка

```bash
# Остановить контейнеры, данные сохранятся
docker compose down

# Полная очистка: витрина, состояние Airflow, модели и отчёты
docker compose down -v && rm -rf artifacts
```

## Как проверить работу

### 1. DAG-и в Airflow

В <http://localhost:8081> видны три DAG-а. Они запускаются по расписанию сами.

| DAG | Расписание | Что делает |
|-----|------------|------------|
| `retrain_model` | раз в 5 минут | переобучает модель на скользящем окне и публикует, если она не хуже текущей |
| `supply_labeled_month` | раз в 15 минут | дописывает в витрину следующий месяц |
| `data_quality` | раз в 10 минут | проверяет витрину и публикует html-отчёт |

Задачи каждого DAG-а связаны в цепочку, её видно на вкладке **Graph**.

### 2. После запуска `retrain_model` в общем каталоге появляется новая модель

```bash
ls artifacts/models
cat artifacts/models/latest.txt          # версия, которая сейчас в проде
cat artifacts/models/history.jsonl       # решение по каждому прогону: published / rejected
```

### 3. Новые транзакции скорятся опубликованной версией

Сервис скоринга перед каждым сообщением читает `latest.txt` и подгружает новую модель без перезапуска контейнера:

```bash
docker compose logs fraud_detector | grep "Загружена модель"
```

Версия модели есть в каждом результате скоринга: в сообщении топика `scoring` (Kafka UI) и в таблице `scores`:

```sql
SELECT model_version, count(*), min(created_at), max(created_at)
FROM scores
GROUP BY model_version
ORDER BY max(created_at) DESC;
```

До первого прогона DAG скоринг идёт моделью `initial` из hw1, после публикации новые строки получают версию вида `201904_60135eb3`. То же самое видно в Streamlit, кнопка «Посмотреть результаты», блок «Версии модели».

### 4. DQ-отчёт

После прогона `data_quality`:

```bash
open artifacts/dq_reports/latest.html
```

Результат по каждому правилу также есть в логе задачи `evaluate_dq_rules` в Airflow.

### 5. Поставка нового месяца

После прогона `supply_labeled_month` в витрине появляется следующий месяц:

```sql
SELECT date_trunc('month', transaction_time) AS month, count(*), sum(target) AS frauds
FROM labeled_transactions
GROUP BY 1
ORDER BY 1 DESC
LIMIT 5;
```

## Переобучение модели (`retrain_model`)

```
extract_training_window -> time_train_test_split -> preprocess_dataset -> fit_catboost
  -> evaluate_candidate -> choose_deployment -> publish_model | reject_model -> advance_training_pointer
```

- **Окно скользящее, 3 месяца.** Указатель `next_batch_month` хранится в таблице `training_state`. Окно каждый раз заново выбирается из витрины: месяцы `[next_batch_month - 2, next_batch_month]`. Новый месяц добавляется, самый старый уходит. Стартовое значение указателя: апрель 2019, первое окно февраль-апрель 2019.
- **Разбиение по времени.** Два ранних месяца идут в обучение, самый свежий в test. Из обучающих месяцев последние 20% строк по времени отводятся под valid для early stopping. Test в обучении не участвует.
- **Препроцессинг** тот же, что в сервисе скоринга: `fraude_detector/preprocessing.py`.
- **Версия модели**: месяц test и хэш `run_id`, например `201906_ecafa6be`.
- Если месяца для обучения ещё нет в витрине, задачи прогона помечаются как `skipped`.

### Повторный запуск после ошибки

Указатель месяца сдвигает только последняя задача `advance_training_pointer`, и только после того, как модель сохранена. Если прогон упал раньше, указатель остаётся на месте, и повторный запуск обучает модель на том же месяце, поэтому месяц не пропускается. Сдвиг срабатывает, только пока указатель равен обработанному месяцу, так что повтор этой задачи не сдвинет окно второй раз.

Файл модели и `latest.txt` сначала записываются во временный файл и только потом переименовываются, поэтому сервис скоринга никогда не прочитает недописанную модель.

## Проверка улучшения модели

Новая модель раскатывается в прод, только если она не хуже текущей. Сравнение делает задача `evaluate_candidate`, затем `choose_deployment` выбирает ветку.

**Как считаются метрики:**

1. Кандидат и текущая модель из прода (на неё указывает `latest.txt`) скорят **один и тот же test-месяц**. Ни одна из моделей его не видела при обучении.
2. Основная метрика: **PR-AUC**.
3. Правило публикации:

   ```
   PR-AUC кандидата >= PR-AUC прода - 0.005  =>  publish_model
   иначе                                     =>  reject_model
   ```

   Допуск 0.005 нужен, чтобы шум на одном месяце не решал судьбу почти одинаковых моделей.
4. Исключение: если в проде модель `initial` из hw1, кандидат публикуется без сравнения. Она обучена на всём `train.csv`, включая test-месяцы, и честно сравнить с ней нельзя.

**Что происходит дальше:**

- `publish_model`: модель кладётся в `artifacts/models/model_<версия>.cbm`, метрики в `model_<версия>.json`, `latest.txt` переключается на новую версию.
- `reject_model`: `latest.txt` не меняется, прод работает на прежней модели. Метрики и причина отказа сохраняются в `artifacts/models/rejected/model_<версия>.json`.
- В обоих случаях решение пишется в `history.jsonl`, а указатель месяца сдвигается: отклонённый месяц тоже считается обработанным.

**Где смотреть метрики:** в Airflow, лог задачи `evaluate_candidate` (таблица метрик кандидата и прода и решение), а также в `model_<версия>.json` и `history.jsonl`.

## Поставка данных (`supply_labeled_month`)

```
sample_next_month -> append_labeled_batch -> prune_old_months
```

| Параметр | Значение |
|----------|----------|
| Размер батча | 50 000 строк |
| Глубина истории | 24 месяца |
| Расписание | раз в 15 минут |

1. Из витрины берутся 50 000 случайных строк, их `transaction_time` переносится в месяц, следующий за последним (день, час и минута сохраняются).
2. Батч записывается в витрину. Удаление строк этого месяца и вставка идут одной транзакцией.
3. Удаляются строки старше 24 месяцев от самого нового месяца. Граница не заходит в текущее окно обучения, чтобы не удалить месяцы, до которых переобучение ещё не дошло.

Поставка запускается реже переобучения (15 и 5 минут), чтобы переобучение догоняло её: сначала оно проходит 12 исторических месяцев из `train.csv`, затем переходит на поставленные.

## Data Quality (`data_quality`)

```
collect_dataset_profile -> evaluate_dq_rules -> render_dq_report -> publish_dq_report
```

Проверки считаются SQL-запросами по витрине `labeled_transactions`:

| ID | Правило | Порог |
|----|---------|-------|
| DQ1 | Полнота: нет NULL ни в одной колонке | 0 NULL |
| DQ2 | Разметка: `target` только 0 или 1 | 0 нарушений |
| DQ3 | Сумма транзакции положительная и правдоподобная | 0 < `amount` < 100 000 |
| DQ4 | Уникальность: нет полных дублей строк | 0 дублей |
| DQ5 | Месяцы: в каждом не меньше 10 000 строк, пропущенных месяцев нет | >= 10 000 строк, 0 пропусков |

Отчёт публикуется в `artifacts/dq_reports/` рядом с каталогом моделей:

```
artifacts/
├── models/
└── dq_reports/
    ├── dq_<время>.html    # отчёт конкретного прогона
    ├── dq_<время>.json
    ├── latest.html        # последний отчёт
    └── latest.json
```

Нарушение правила не роняет DAG: статус FAIL виден в отчёте и в логе задачи `evaluate_dq_rules`.

## Структура проекта

```
.
├── fraude_detector/                  # ML-сервис
│   ├── models/
│   │   └── catboost_fraud.cbm        # исходная модель из hw1 (версия initial)
│   ├── preprocessing.py              # генерация признаков, общая для скоринга и обучения
│   ├── inference.py                  # загрузка модели по latest.txt и предсказание
│   ├── kafka_broker.py               # consume transactions → score → produce scoring
│   ├── logger_config.py
│   ├── main.py
│   └── Dockerfile
├── interface/                        # Streamlit UI
├── db_writer/                        # scoring → Postgres (таблица scores)
├── transaction_simulator/            # test.csv → Kafka, бесконечный поток
├── data_loader/                      # train.csv → витрина labeled_transactions
├── airflow/
│   ├── Dockerfile                    # Airflow + CatBoost
│   └── entrypoint.sh
├── dags/                             # только сборка графов
│   ├── retrain_model.py
│   ├── supply_labeled_month.py
│   └── data_quality.py
├── pipeline/                         # функции задач
│   ├── settings.py                   # пути и параметры
│   ├── db.py                         # витрина и указатель месяца
│   ├── registry.py                   # каталог моделей: файлы, latest.txt, история
│   ├── retrain/                      # задачи retrain_model
│   ├── supply/                       # задачи supply_labeled_month
│   └── dq/                           # задачи data_quality
├── data/
│   ├── train.csv                     # размеченные транзакции (Git LFS)
│   └── test.csv                      # поток для симулятора (Git LFS)
├── artifacts/                        # создаётся при запуске, общий каталог Airflow и fraud_detector
│   ├── models/
│   └── dq_reports/
├── docker-compose.yaml
├── .env.example                      # шаблон переменных окружения
└── README.md
```
