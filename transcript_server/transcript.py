import multiprocessing
import queue
import time
import psycopg2
from psycopg2 import pool
import os
# sox больше не используется, теперь используем ffmpeg напрямую
import json
import requests
import logging
from typing import List, Tuple, Optional

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
DSN = os.getenv('DSN')  # Получение DSN из переменных окружения
BASE_TEMP_PATH = "./tempmedia"
MAX_RETRIES = 3  # Максимальное количество попыток повторного подключения
RETRY_DELAY = 5  # Задержка между попытками (в секундах)
NUM_WORKERS = int(os.getenv('TRANSCRIPT_NUM_WORKERS', 2)) 

import zipfile
import requests
import subprocess

MODEL_NAME = 'voxblink2_samresnet34_ft'
MODEL_URL = 'https://wenet.org.cn/downloads?models=wespeaker&version=voxblink2_samresnet34_ft.zip'
MODEL_DIR = os.path.join('models', MODEL_NAME)

def get_direct_download_url():
    """Извлекает прямую ссылку для скачивания модели."""
    # Получаем данные от API
    api_url = "https://modelscope.cn/api/v1/datasets/wenet/wespeaker_pretrained_models/oss/tree"
    response = requests.get(api_url)
    if response.status_code != 200:
        raise Exception(f"Ошибка при запросе API: {response.status_code}")
    
    # Ищем нужную модель в данных
    data = response.json()
    model_info = next((item for item in data['Data'] if item['Key'] == f"{MODEL_NAME}.zip"), None)
    
    if not model_info:
        raise Exception(f"Модель {MODEL_NAME}.zip не найдена в ответе API.")
    
    # Возвращаем прямую ссылку на модель
    return model_info['Url']

def download_and_extract_model():
    logger.info(f"Проверка наличия модели {MODEL_NAME}...")
    if not os.path.exists(MODEL_DIR):
        logger.info(f"Папка {MODEL_NAME} не существует, начинается процесс загрузки модели...")
        os.makedirs(MODEL_DIR)
        logger.info(f"Папка {MODEL_NAME} создана.")
        
        # Получаем прямую ссылку для скачивания
        logger.info("Получение прямой ссылки для скачивания...")
        direct_url = get_direct_download_url()
        logger.info(f"Прямая ссылка: {direct_url}")
        
        # Скачивание модели с помощью wget
        logger.info("Скачивание модели с помощью wget...")
        zip_path = os.path.join(MODEL_DIR, f"{MODEL_NAME}.zip")
        subprocess.run(
            ["wget", direct_url, "-O", zip_path, "--max-redirect=10"],
            check=True
        )
        
        # Распаковка модели
        logger.info("Распаковка модели...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall('models')
        
        # Удаление zip-файла после распаковки
        os.remove(zip_path)
        logger.info("Модель успешно загружена и распакована.")
    else:
        logger.info(f"Папка {MODEL_NAME} уже существует.")

# Проверка и загрузка модели
download_and_extract_model()

# Загрузка модели диаризации
#diarization_model = wespeaker.load_model_local(MODEL_NAME)

# Инициализация пула соединений с базой данных
def init_db_pool() -> Optional[psycopg2.pool.ThreadedConnectionPool]:
    logger.info("Инициализация пула соединений с базой данных...")
    try:
        pool = psycopg2.pool.ThreadedConnectionPool(1, 16, DSN)
        logger.info("Пул соединений с базой данных успешно инициализирован.")
        return pool
    except psycopg2.Error as e:
        logger.error(f"Ошибка при создании пула соединений: {e}")
        return None

def get_db_connection(db_pool) -> Optional[psycopg2.extensions.connection]:
    """Get a database connection with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = db_pool.getconn()
            # Test the connection
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            return conn
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"Max retries reached, re-raising exception: {e}")
                raise e
            time.sleep(1)  # Wait before retry
    return None

# Загрузка файла с сервера
def download_file(file_path: str, call_uuid: str, file_server: str) -> bool:
    logger.debug(f"Начало загрузки аудиофайла {call_uuid} с сервера {file_server} по пути {file_path}...")
    try:
        response = requests.get(f"{file_server}/file/{call_uuid}", stream=True)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            logger.debug(f"Аудиофайл {call_uuid} успешно загружен.")
            return True
        else:
            logger.error(f"Ошибка загрузки файла: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {e}")
        return False

# Преобразование аудио в формат PCM16 WAV
def convert_audio(file_path: str, call_uuid: str) -> Optional[str]:
    logger.debug(f"Начало преобразования аудио {call_uuid} в формат PCM16 WAV с использованием ffmpeg...")
    try:
        import subprocess
        import os
        
        temp_file_path = os.path.join(BASE_TEMP_PATH, f"temp_{call_uuid}.wav")
        
        # Проверяем наличие ffmpeg в системе
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            ffmpeg_cmd = 'ffmpeg'
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Если ffmpeg не найден в PATH, пробуем стандартные пути
            possible_paths = ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/opt/bin/ffmpeg', '/usr/bin/avconv', '/usr/local/bin/avconv']
            ffmpeg_cmd = None
            for path in possible_paths:
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    ffmpeg_cmd = path
                    break
        
        if not ffmpeg_cmd:
            logger.error("ffmpeg не найден в системе. Убедитесь, что ffmpeg установлен.")
            return None
        
        # Используем ffmpeg для конвертации любого аудиоформата в WAV PCM16
        cmd = [
            ffmpeg_cmd,
            '-i', file_path,
            '-ar', '16000',  # частота дискретизации 16kHz
            '-sample_fmt', 's16',  # 16-bit PCM
            '-y',  # перезаписать файл если существует
            temp_file_path
        ]
        
        logger.debug(f"Выполнение команды ffmpeg: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        
        # Удаляем исходный файл после успешной конвертации
        os.remove(file_path)
        
        logger.debug(f"Аудио {call_uuid} успешно преобразовано в PCM16 WAV и сохранено как {temp_file_path}")
        return temp_file_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при выполнении ffmpeg: {e}")
        logger.error(f"stderr: {e.stderr.decode()}")
        logger.error(f"stdout: {e.stdout.decode()}")
        return None
    except FileNotFoundError:
        logger.error("ffmpeg не найден в системе. Убедитесь, что ffmpeg установлен.")
        return None
    except Exception as e:
        logger.error(f"Ошибка при преобразовании аудио: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        return None

# Обработка задачи воркером
def worker(task_queue: multiprocessing.JoinableQueue, db_pool: psycopg2.pool.ThreadedConnectionPool) -> None:
    logger.info("Запуск воркера для обработки задач транскрипции...")
    logger.info(f"Воркер PID: {os.getpid()}")
    try:
        from tr_lib import process_audio  # Импорт внутри функции worker
        logger.info("Успешный импорт process_audio из tr_lib")
    except ImportError as e:
        logger.error(f"Ошибка импорта process_audio из tr_lib: {e}")
        logger.error("Воркер не может обработать задачи без process_audio")
        logger.error("Проверьте, что все зависимости установлены и доступны в контейнере")
        return
    except Exception as e:
        logger.error(f"Неизвестная ошибка при импорте process_audio: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        logger.error(f"Трассировка стека: {str(e)}")
        return
    
    # Для дочерних процессов нужно создать новый пул соединений, так как psycopg2 пулы не сериализуются
    worker_db_pool = init_db_pool()
    if not worker_db_pool:
        logger.error("Не удалось инициализировать пул соединений для воркера. Завершение работы воркера.")
        return
    logger.debug("Воркер готов к обработке задач, ожидание в цикл...")
    logger.debug(f"Воркер {os.getpid()} ожидает задач в очереди...")
    while True:
        try:
            logger.debug(f"Воркер {os.getpid()} ожидает получение задачи из очереди...")
            file_path, call_uuid, file_server = task_queue.get()
            logger.info(f"Воркер {os.getpid()} получил задачу: UUID={call_uuid}, файл={file_path}, сервер={file_server}")

            # Загрузка файла
            logger.debug(f"Начало загрузки файла для задачи {call_uuid}...")
            if not download_file(file_path, call_uuid, file_server):
                logger.error(f"Не удалось загрузить файл для задачи {call_uuid}, задача пропущена.")
                continue
            logger.debug(f"Файл для задачи {call_uuid} успешно загружен.")

            # Преобразование аудио
            logger.debug(f"Начало преобразования аудио для задачи {call_uuid}...")
            converted_file_path = convert_audio(file_path, call_uuid)
            if not converted_file_path:
                logger.error(f"Не удалось преобразовать аудио для задачи {call_uuid}, задача пропущена.")
                continue
            logger.debug(f"Аудио для задачи {call_uuid} успешно преобразовано.")

            # Обработка аудио
            logger.debug(f"Начало обработки аудио для задачи {call_uuid}...")
            try:
                logger.debug(f"Вызов process_audio для файла {converted_file_path}")
                transcriptions = process_audio(converted_file_path)
                logger.debug(f"process_audio успешно выполнен, результат получен")
                os.remove(converted_file_path)
                logger.info(f"Аудио для задачи {call_uuid} успешно обработано, транскрипции получены.")
                transcriptions.sort(key=lambda x: x['result'][0]['start'])
                logger.debug(f"Транскрипции для задачи {call_uuid} отсортированы по времени начала.")
            except Exception as e:
                logger.error(f"Ошибка при обработке аудио для задачи {call_uuid}: {e}")
                logger.error(f"Тип ошибки: {type(e)}")
                logger.error(f"Детали ошибки: {str(e)}")
                transcriptions = []

            # Сохранение результатов в базу данных
            logger.debug(f"Начало сохранения результатов для задачи {call_uuid} в базу данных...")
            conn = get_db_connection(worker_db_pool)
            try:
                cur = conn.cursor()
                logger.debug(f"Сохранение транскрипции в таблицу calls_transcription для задачи {call_uuid}...")
                cur.execute(
                    "INSERT INTO vp.calls_transcription(call_uuid, transcription) VALUES (%s, %s) "
                    "ON CONFLICT ON CONSTRAINT calls_transcription_pkey DO NOTHING;",
                    (call_uuid, json.dumps(transcriptions))
                )
                conn.commit()
                logger.info(f"Транскрипция для задачи {call_uuid} сохранена в базу данных.")
                
                logger.debug(f"Обновление статуса задачи в таблице tasks для задачи {call_uuid}...")
                cur.execute(
                    "INSERT INTO vp.tasks(call_uuid, task) VALUES (%s, %s) "
                    "ON CONFLICT ON CONSTRAINT tasks_pkey DO NOTHING;",
                    (call_uuid, '{"transcript": "OK","text_process": "ready","tag_process":"wait"}')
                )
                conn.commit()
                logger.debug(f"Статус задачи для {call_uuid} обновлен в таблице tasks.")
                
                logger.debug(f"Удаление задачи из очереди transcript_queue для {call_uuid}...")
                cur.execute("DELETE FROM vp.transcript_queue WHERE call_uuid = %s", (call_uuid,))
                conn.commit()
                logger.debug(f"Задача {call_uuid} удалена из очереди transcript_queue.")
                
                cur.close()
                logger.debug(f"Результаты для задачи {call_uuid} успешно сохранены в базу данных.")
            except Exception as d:
                logger.error(f"Ошибка при работе с базой данных для задачи {call_uuid}: {d}")
            finally:
                worker_db_pool.putconn(conn)
                logger.debug(f"Соединение с базой данных возвращено в пул для задачи {call_uuid}.")

        except Exception as d:
            logger.error(f"Ошибка в воркере при обработке задачи: {d}")
        finally:
            task_queue.task_done()
            logger.debug(f"Задача {call_uuid} завершена, task_done() вызван.")

# Основной цикл обработки задач
def main_loop(db_pool: psycopg2.pool.ThreadedConnectionPool, task_queue: multiprocessing.JoinableQueue) -> None:
    logger.info("Запуск основного цикла обработки задач транскрипции...")
    while True:
        conn = None
        retry_count = 0
        max_retries = MAX_RETRIES
        
        while retry_count < max_retries:
            try:
                logger.debug("Получение соединения с базой данных для выборки задач...")
                conn = get_db_connection(db_pool)
                cur = conn.cursor()
                logger.debug("Выборка задач из очереди transcript_queue с готовыми к обработке записями...")
                cur.execute("SELECT file_path, file_server, call_uuid FROM vp.transcript_queue WHERE status = 'ready' LIMIT 30")
                tasks = cur.fetchall()
                logger.info(f"Найдено {len(tasks)} задач для обработки.")
                for task in tasks:
                    file_path, file_server, call_uuid = task
                    logger.debug(f"Обновление статуса задачи {call_uuid} на 'processing'...")
                    cur.execute("UPDATE vp.transcript_queue SET status = 'processing' WHERE call_uuid = %s", (call_uuid,))
                    conn.commit()
                    logger.debug(f"Добавление задачи {call_uuid} в очередь для обработки воркеров...")
                    logger.debug(f"Размер очереди перед добавлением: {task_queue.qsize()}")
                    task_queue.put((file_path, call_uuid, file_server))
                    logger.debug(f"Задача добавлена в очередь, новый размер: {task_queue.qsize()}")
                cur.close()
                logger.debug(f"Обработано {len(tasks)} задач, соединение закрыто.")
                break # Success, exit retry loop
            except psycopg2.OperationalError as e:
                logger.error(f"Ошибка подключения к базе данных в основном цикле: {e}, attempt {retry_count + 1}/{max_retries}")
                if conn:
                    db_pool.putconn(conn)
                    conn = None
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error("Max retries reached, continuing to next iteration...")
                    break
                time.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"Неизвестная ошибка в основном цикле: {e}, attempt {retry_count + 1}/{max_retries}")
                if conn:
                    db_pool.putconn(conn)
                    conn = None
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error("Max retries reached, continuing to next iteration...")
                    break
                time.sleep(RETRY_DELAY)
        if conn:
            db_pool.putconn(conn)
            logger.debug("Соединение с базой данных возвращено в пул.")
        logger.debug("Ожидание 5 секунд перед следующей итерацией основного цикла...")
        time.sleep(5)

if __name__ == '__main__':
    logger.info("Запуск сервера транскрипции...")
    # Инициализация пула соединений
    logger.info("Инициализация пула соединений с базой данных...")
    db_pool = init_db_pool()
    if not db_pool:
        logger.error("Не удалось инициализировать пул соединений. Завершение работы.")
        exit(1)

    # Создание очереди задач
    logger.info("Создание очереди задач...")
    task_queue = multiprocessing.JoinableQueue(maxsize=30)
    logger.info(f"Очередь задач создана с максимальным размером {30}.")

    # Создание и запуск процессов-воркеров
    logger.info(f"Создание {NUM_WORKERS} воркеров для обработки задач...")
    processes = []
    for i in range(NUM_WORKERS):
        logger.info(f"Создание воркера {i+1}...")
        p = multiprocessing.Process(target=worker, args=(task_queue, db_pool))
        p.start()
        processes.append(p)
        logger.info(f"Воркер {i+1} запущен с PID {p.pid}.")

    # Задержка перед началом основного цикла
    #logger.info("Ожидание 5 секунд перед запуском основного цикла обработки задач...")
    time.sleep(5)

    # Запуск основного цикла обработки задач
    logger.info("Запуск основного цикла обработки задач...")
    try:
        main_loop(db_pool, task_queue)
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C), завершение работы...")
    finally:
        logger.debug("Ожидание завершения всех задач в очереди...")
        # Ожидание завершения всех задач
        task_queue.join()
        logger.debug("Все задачи в очереди завершены.")
        
        logger.info("Завершение процессов-воркеров...")
        # Завершение процессов
        for i, p in enumerate(processes):
            logger.debug(f"Завершение воркера {i+1} с PID {p.pid}...")
            p.terminate()
            p.join()
            logger.debug(f"Воркер {i+1} завершен.")

        logger.info("Закрытие пула соединений с базой данных...")
        # Закрытие пула соединений
        db_pool.closeall()
        logger.info("Пул соединений с базой данных закрыт.")
        logger.info("Сервер транскрипции завершил работу.")