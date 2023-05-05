# voice_perception

Система речевой аналитики на базе Vosk  
Основные фукнции
1. Распознавание звонков
2. Диаризация моно звонков
3. Определение эмоций по фразам
4. Построение отчетов по звонкам
5. Поиск звонков по тексту

**Установка**

Установить БД postgres и запустить инициализирующий скрипт *initial.sql*

**Worker node**


1. Перейти в директорию worker_node
```
cd worker_node
```
2. в файле docker-compose.yml изменить параметры подключения к БД в DSN, вместо 
```
postgresql://user:pass@host:port/db
```
прописать ваши данные  


3. в переменной VOSK_SERVER указать адрес текущей машины или вместо 127.0.0.1 прописать vosk  

4. Скачать нужные файлы моделей

в директорию 
```
cd vosk 
```
скачать и распаковать модели vosk по ссылкам из файла **loadvosk.txt**  


в директорию 
```
text_processor\ruword2tags
```
скачиваем файл ruword2tags.db по ссылке в **load.txt**  

5. Запустить через 
```
docker-compose up -d
```

**Web node**  


Устанавливаем nginx и прописываем конфигурацию как в файле default  
Указываем корректный путь до директории web_node\web в location /  


Если web node развернута на отдельном сервере, то указать в docker-compose.yml Правильный адрес машины
```
APIURL: "http://127.0.0.1/api/file/"
```

**Загрузка аудио**

в файле load.curl есть пример запроса для подгрузки новых аудио  
Так же в интерфейсе реализована форма загрузки через web

**Пример интерфейса**

Основной интерфейс просмотра звонков
![Alt text](https://github.com/bogdal1993/voice_perception/blob/main/Annotation%202023-04-30%20143825.jpg?raw=true "Основной интерфейс")


Интерфейс графических отчетов
![Alt text](https://github.com/bogdal1993/voice_perception/blob/main/Annotation%202023-04-30%20143822.jpg?raw=true "Интерфейс графических отчетов")


Интерфейс поиска по тексту
![Alt text](https://github.com/bogdal1993/voice_perception/blob/main/Annotation%202023-04-30%20143821.jpg?raw=true "Интерфейс поиска по тексту")


В проекте используются модели Vosk, DeepPavlov, I.Koziev


Присоединяйтесь к сообществу https://t.me/+mP0I5NnJrHM2YWEy
