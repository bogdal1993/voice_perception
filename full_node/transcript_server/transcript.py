import multiprocessing
import queue
import time
import psycopg2
from psycopg2 import pool
import os
import sox
import json
import requests
import logging
from typing import List, Tuple, Optional

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
DSN = os.getenv('DSN')  # Получение DSN из переменных окружения
BASE_TEMP_PATH = "/opt/tempmedia"
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
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        print(f"Папка {MODEL_NAME} создана.")
        
        # Получаем прямую ссылку для скачивания
        print("Получение прямой ссылки для скачивания...")
        direct_url = get_direct_download_url()
        print(f"Прямая ссылка: {direct_url}")
        
        # Скачивание модели с помощью wget
        print("Скачивание модели с помощью wget...")
        zip_path = os.path.join(MODEL_DIR, f"{MODEL_NAME}.zip")
        subprocess.run(
            ["wget", direct_url, "-O", zip_path, "--max-redirect=10"],
            check=True
        )
        
        # Распаковка модели
        print("Распаковка модели...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall('models')
        
        # Удаление zip-файла после распаковки
        os.remove(zip_path)
        print("Модель успешно загружена и распакована.")
    else:
        print(f"Папка {MODEL_NAME} уже существует.")

# Проверка и загрузка модели
download_and_extract_model()

# Загрузка модели диаризации
#diarization_model = wespeaker.load_model_local(MODEL_NAME)

# Инициализация пула соединений с базой данных
def init_db_pool() -> Optional[psycopg2.pool.ThreadedConnectionPool]:
    try:
        return psycopg2.pool.ThreadedConnectionPool(1, 16, DSN)
    except psycopg2.Error as e:
        logger.error(f"Ошибка при создании пула соединений: {e}")
        return None

# Загрузка файла с сервера
def download_file(file_path: str, call_uuid: str, file_server: str) -> bool:
    try:
        response = requests.get(f"{file_server}/file/{call_uuid}", stream=True)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            logger.error(f"Ошибка загрузки файла: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {e}")
        return False

# Преобразование аудио в формат PCM16 WAV
def convert_audio(file_path: str, call_uuid: str) -> Optional[str]:
    try:
        res = sox.file_info.info(file_path)
        if res['encoding'] != 'PCM16' or res['file_type'] != 'wav':
            temp_file_path = os.path.join(BASE_TEMP_PATH, f"temp_{call_uuid}.wav")
            tfm = sox.Transformer()
            tfm.set_output_format(file_type='wav', bits=16, rate=res['sample_rate'], channels=res['channels'])
            tfm.build(file_path, temp_file_path)
            os.remove(file_path)
            return temp_file_path
        return file_path
    except Exception as e:
        logger.error(f"Ошибка при преобразовании аудио: {e}")
        return None

# Обработка задачи воркером
def worker(task_queue: multiprocessing.JoinableQueue, db_pool: psycopg2.pool.ThreadedConnectionPool) -> None:
    from tr_lib import process_audio  # Импорт внутри функции worker
    db_pool = init_db_pool()
    while True:
        try:
            file_path, call_uuid, file_server = task_queue.get()

            # Загрузка файла
            if not download_file(file_path, call_uuid, file_server):
                task_queue.task_done()
                continue

            # Преобразование аудио
            converted_file_path = convert_audio(file_path, call_uuid)
            if not converted_file_path:
                task_queue.task_done()
                continue

            # Обработка аудио
            try:
                transcriptions = process_audio(converted_file_path)
                os.remove(converted_file_path)
                transcriptions.sort(key=lambda x: x['result'][0]['start'])
            except Exception as e:
                logger.error(f"Ошибка при обработке аудио: {e}")
                transcriptions = []

            # Сохранение результатов в базу данных
            conn = db_pool.getconn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO vp.calls_transcription(call_uuid, transcription) VALUES (%s, %s) "
                    "ON CONFLICT ON CONSTRAINT calls_transcription_pkey DO NOTHING;",
                    (call_uuid, json.dumps(transcriptions))
                )
                conn.commit()
                cur.execute(
                    "INSERT INTO vp.tasks(call_uuid, task) VALUES (%s, %s) "
                    "ON CONFLICT ON CONSTRAINT tasks_pkey DO NOTHING;",
                    (call_uuid, '{"transcript": "OK","text_process": "ready","tag_process":"wait"}')
                )
                conn.commit()
                cur.execute("DELETE FROM vp.transcript_queue WHERE call_uuid = %s", (call_uuid,))
                conn.commit()
                cur.close()
            except Exception as d:
                logger.error(f"Ошибка при работе с базой данных: {d}")
            finally:
                db_pool.putconn(conn)

        except Exception as d:
            logger.error(f"Ошибка в воркере: {d}")
        finally:
            task_queue.task_done()

# Основной цикл обработки задач
def main_loop(db_pool: psycopg2.pool.ThreadedConnectionPool, task_queue: multiprocessing.JoinableQueue) -> None:
    while True:
        conn = None
        try:
            conn = db_pool.getconn()
            cur = conn.cursor()
            cur.execute("SELECT file_path, file_server, call_uuid FROM vp.transcript_queue WHERE status = 'ready' LIMIT 30")
            tasks = cur.fetchall()
            for task in tasks:
                file_path, file_server, call_uuid = task
                cur.execute("UPDATE vp.transcript_queue SET status = 'processing' WHERE call_uuid = %s", (call_uuid,))
                conn.commit()
                task_queue.put((file_path, call_uuid, file_server))
            cur.close()
        except psycopg2.OperationalError as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            time.sleep(RETRY_DELAY)
        finally:
            if conn:
                db_pool.putconn(conn)
        time.sleep(5)

if __name__ == '__main__':
    # Инициализация пула соединений
    db_pool = init_db_pool()
    if not db_pool:
        logger.error("Не удалось инициализировать пул соединений. Завершение работы.")
        exit(1)

    # Создание очереди задач
    task_queue = multiprocessing.JoinableQueue(maxsize=30)

    # Создание и запуск процессов-воркеров
    processes = []
    for _ in range(NUM_WORKERS):
        p = multiprocessing.Process(target=worker, args=(task_queue, db_pool))
        p.start()
        processes.append(p)

    # Задержка перед началом основного цикла
    time.sleep(5)

    # Запуск основного цикла обработки задач
    try:
        main_loop(db_pool, task_queue)
    except KeyboardInterrupt:
        logger.info("Завершение работы...")
    finally:
        # Ожидание завершения всех задач
        task_queue.join()

        # Завершение процессов
        for p in processes:
            p.terminate()
            p.join()

        # Закрытие пула соединений
        db_pool.closeall()