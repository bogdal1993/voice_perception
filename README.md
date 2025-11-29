# voice_perception
![Alt text](https://github.com/bogdal1993/voice_perception/blob/main/docs/Annotation%202023-08-29%20210405.jpg?raw=true "Основной интерфейс")

Система речевой аналитики на базе Vosk  
Основные фукнции
1. Распознавание звонков
2. Диаризация моно звонков
3. Определение эмоций по фразам
4. Построение отчетов по звонкам
5. Поиск звонков по тексту
6. **Автотематизация**

**Установка**

1. Установить БД postgres и запустить инициализирующий скрипт *initial.sql*

2. Скопировать файл `.env_example` в `.env` и настроить параметры подключения к БД:
```
DSN=postgresql://user:pass@server:port/db_names
APIURL=http://nginx/api/file/
TRANSCRIPT_NUM_WORKERS=4
TRANSCRIPT_NUM_THREADS=4
ASR_MODEL_NAME=v2_ctc
```

Доступные модели ASR (модель по умолчанию - v2_ctc):
- v3_ctc
- v3_rnnt
- v3_e2e_ctc
- v3_e2e_rnnt
- v2_ctc
- v2_rnnt
- v1_ctc
- v1_rnnt

Скачать файл в text_processor/ruword2tags/ по ссылке в load.txt

**Сборка Docker образов**

Для автоматической сборки Docker образов используйте команду:

```
docker-compose up --build
```

**Single node. GigaAM**

Запустить через
```
docker-compose up -d
```


**Загрузка аудио**

в файле load.curl есть пример запроса для подгрузки новых аудио  
Так же в интерфейсе реализована форма загрузки через web

**Пример интерфейса**

Основной интерфейс просмотра звонков
![Alt text](https://github.com/bogdal1993/voice_perception/blob/main/docs/Annotation%202023-04-30%20143825.jpg?raw=true "Основной интерфейс")


Интерфейс графических отчетов
![Alt text](https://github.com/bogdal1993/voice_perception/blob/main/docs/Annotation%202023-04-30%20143822.jpg?raw=true "Интерфейс графических отчетов")


Интерфейс поиска по тексту
![Alt text](https://github.com/bogdal1993/voice_perception/blob/main/docs/Annotation%202023-04-30%20143821.jpg?raw=true "Интерфейс поиска по тексту")


В проекте используются модели Vosk, DeepPavlov, I.Koziev


Присоединяйтесь к сообществу https://t.me/voiceperception
