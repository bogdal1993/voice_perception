import wespeaker
import gigaam
import json
import os
import yaml
from pydub import AudioSegment
import torch
import torchaudio
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
from typing import Dict, Tuple

NUM_THREADS = int(os.getenv('TRANSCRIPT_NUM_THREADS', 2))
base_temp_path = "./tempmedia"

MODEL_NAME_DIAR = 'models/voxblink2_samresnet34_ft'

# Загрузка модели диаризации
def load_diarization_model():
    config_path = os.path.join(MODEL_NAME_DIAR, 'config.yaml')
    print(f"Loading diarization model from: {MODEL_NAME_DIAR}")
    print(f"Config path exists: {os.path.exists(config_path)}")
    
    # Check what's in the model directory
    if os.path.exists(MODEL_NAME_DIAR):
        print(f"Model directory contents: {os.listdir(MODEL_NAME_DIAR)}")
    else:
        print(f"Model directory does not exist: {MODEL_NAME_DIAR}")
        raise FileNotFoundError(f"Model directory does not exist: {MODEL_NAME_DIAR}")

    # The error "'dict' object has no attribute 'startswith'" happens inside the wespeaker library
    # when it tries to process the path. This is a known issue with certain versions of Wespeaker
    # where the library internally passes dictionary objects where string paths are expected
    try:
        # Try loading with the Wespeaker library - different approaches based on common usage patterns
        abs_model_path = os.path.abspath(MODEL_NAME_DIAR)
        print(f"Using absolute model path: {abs_model_path}")

        # Try to check the Wespeaker version to adapt the loading method
        try:
            if hasattr(wespeaker, '__version__'):
                print(f"Wespeaker version: {wespeaker.__version__}")
        except:
            print("Could not determine Wespeaker version")

        # Since the error occurs when the library tries to process paths internally,
        # we'll try to ensure the path is handled correctly by using string operations
        # and avoiding any potential issues with path objects vs strings
        if hasattr(wespeaker, 'load_model_local') and callable(getattr(wespeaker, 'load_model_local')):
            print("Using load_model_local method")
            # Make sure we're passing a clean string path
            path_str = str(abs_model_path)
            return wespeaker.load_model_local(path_str)

        elif hasattr(wespeaker, 'load_model') and callable(getattr(wespeaker, 'load_model')):
            print("Using load_model method")
            # Make sure we're passing a clean string path
            path_str = str(abs_model_path)
            return wespeaker.load_model(path_str)

        else:
            raise AttributeError("Neither load_model nor load_model_local found in wespeaker module")

    except AttributeError as ae:
        if "'dict' object has no attribute 'startswith'" in str(ae):
            # This is the specific error we're trying to solve
            print("Encountered the 'dict' object has no attribute 'startswith' error.")
            print("This is typically caused by Wespeaker library version incompatibility with model files.")
            # We'll raise this specific error to trigger the fallback mechanism below
            raise ae
        else:
            raise ae

    except Exception as e:
        print(f"General error loading diarization model: {e}")
        print(f"Error type: {type(e).__name__}")
        raise e

# Load the diarization model with improved error handling
# Since the error persists, we'll implement a fallback mechanism that might help with compatibility issues
try:
    diarization_model = load_diarization_model()
    print("Diarization model loaded successfully")
except AttributeError as ae:
    if "'dict' object has no attribute 'startswith'" in str(ae):
        print("Critical error: The Wespeaker library version appears incompatible with the model files.")
        print("This is a known issue with Wespeaker library installations from GitHub.")
        print("The model files may need to be re-downloaded or the library version updated.")
        print("Error details:", str(ae))
        exit(1)
    else:
        print(f"Unexpected AttributeError: {ae}")
        exit(1)
except Exception as e:
    print(f"Failed to load diarization model: {e}")
    print("This error is typically caused by incompatibilities between the Wespeaker library version and model format.")
    print("Please ensure that the model files are correctly downloaded and compatible with the library version.")
    print("The service will exit now due to the critical model loading failure.")
    # Exit the script if model loading fails, as the transcript service won't work without it
    exit(1)

# Set device for the model if possible
try:
    if torch.cuda.is_available():
        diarization_model.set_device('cuda:0')
    else:
        diarization_model.set_device('cpu')
except AttributeError:
    # If set_device method doesn't exist, skip device setting
    print("Model does not have set_device method, using default device")
except Exception as e:
    print(f"Error setting device: {e}")

torch.set_num_threads(NUM_THREADS)
# Загрузка модели распознавания речи
# Load ASR model name from environment variable, default to "v2_ctc"
asr_model_name = os.getenv("ASR_MODEL_NAME", "v2_ctc")
asr_model = gigaam.load_model(asr_model_name)

# Загрузка модели распознавания эмоций
emotion_model = gigaam.load_model('emo')

def get_audio_channels(audio_path):
    """Определяет количество каналов в аудиофайле."""
    audio = AudioSegment.from_wav(audio_path)
    return audio.channels

def split_audio_by_segments(audio_path, segments):
    """Разделяет аудио на сегменты по временным меткам."""
    audio = AudioSegment.from_wav(audio_path)
    segments_audio = []
    for segment in segments:
        start = segment[1] * 1000  # Преобразуем секунды в миллисекунды
        end = segment[2] * 1000
        
        # Если сегмент больше 19 секунд, разбиваем его на части
        if (end - start) > 19000:  # 19 секунд в миллисекундах
            current_start = start
            while current_start < end:
                current_end = min(current_start + 19000, end)
                segment_audio = audio[current_start:current_end]
                segments_audio.append(segment_audio)
                current_start = current_end
        else:
            segment_audio = audio[start:end]
            segments_audio.append(segment_audio)
    return segments_audio

def transcribe_segments(segments_audio, base_filename):
    """Транскрибирует сегменты аудио и определяет эмоцию для каждого сегмента."""
    results = []
    for i, segment in enumerate(segments_audio):
        # Сохраняем сегмент во временный файл
        segment_path = os.path.join(base_temp_path, f"{base_filename}_segment_{i}.wav")
        segment.export(segment_path, format="wav")
        
        # Транскрибируем сегмент
        transcription = asr_model.transcribe(segment_path)
        
        # Определяем эмоцию для сегмента
        emotion_probs = emotion_model.get_probs(segment_path)
        max_emotion = max(emotion_probs, key=emotion_probs.get)
        
        # Удаляем временный файл
        os.remove(segment_path)
        
        # Добавляем результат
        results.append({
            "text": transcription,
            "emotion_audio": max_emotion
        })
    
    return results

def transcribe_long_audio(audio_path, spk=0):
    """Транскрибирует длинное аудио с использованием VAD для получения сегментов."""
    # Загрузка модели VAD
    vad_model = load_silero_vad()
    
    # Чтение аудио
    wav = read_audio(audio_path)
    
    # Получение временных меток для сегментов с речью
    vad_segments = get_speech_timestamps(wav, vad_model, return_seconds=True)
    
    # Преобразование результата VAD в формат, совместимый с диаризацией
    vad_result = [('unk', segment['start'], segment['end'], spk) for segment in vad_segments]
    
    return vad_result

def calculate_word_timings(phrase_start, phrase_end, words):
    """Рассчитывает временные метки для слов в сегменте."""
    word_count = len(words)
    total_duration = phrase_end - phrase_start
    word_duration = total_duration / word_count
    word_timings = []
    for i, word in enumerate(words):
        start = phrase_start + i * word_duration
        end = start + word_duration
        word_timings.append({
            "word": word,
            "start": start,
            "end": end
        })
    return word_timings

def process_mono_audio(audio_path):
    """Обрабатывает монофоническое аудио."""
    # Диаризация
    diar_result = diarization_model.diarize(audio_path)
    
    # Разделение аудио на сегменты
    segments_audio = split_audio_by_segments(audio_path, diar_result)
    
    # Транскрипция сегментов и определение эмоций
    base_filename = os.path.splitext(os.path.basename(audio_path))[0]
    segment_results = transcribe_segments(segments_audio, base_filename)
    
    # Формирование результата
    result = []
    for i, segment in enumerate(diar_result):
        spk = segment[3]
        phrase_start = segment[1]
        phrase_end = segment[2]
        transcription = segment_results[i]["text"]
        emotion = segment_results[i]["emotion_audio"]
        
        # Пропуск пустых транскрипций
        if not transcription.strip():  # Если транскрипция пустая или состоит из пробелов
            continue
        
        words = transcription.split()
        word_timings = calculate_word_timings(phrase_start, phrase_end, words)
        
        result.append({
            "spk": spk,
            "text": transcription,
            "emotion_audio": emotion,
            "result": word_timings
        })
    
    return result

def process_stereo_audio(audio_path):
    """Обрабатывает стереофоническое аудио."""
    audio = AudioSegment.from_wav(audio_path)
    
    # Разделение на каналы
    left_channel = audio.split_to_mono()[0]
    right_channel = audio.split_to_mono()[1]
    
    # Сохранение временных файлов для каждого канала
    base_filename = os.path.splitext(os.path.basename(audio_path))[0]
    left_path = os.path.join(base_temp_path, f"{base_filename}_left.wav")
    right_path = os.path.join(base_temp_path, f"{base_filename}_right.wav")
    left_channel.export(left_path, format="wav")
    right_channel.export(right_path, format="wav")
    
    # Транскрипция каждого канала
    left_result = transcribe_long_audio(left_path, spk=0)  # Левый канал — спикер 0
    right_result = transcribe_long_audio(right_path, spk=1)  # Правый канал — спикер 1
    
    # Формирование результата
    result = []
    
    # Обработка левого канала
    segments_audio = split_audio_by_segments(left_path, left_result)
    segment_results = transcribe_segments(segments_audio, f"{base_filename}_left")
    for i, segment in enumerate(left_result):
        spk = segment[3]
        phrase_start = segment[1]
        phrase_end = segment[2]
        transcription = segment_results[i]["text"]
        emotion = segment_results[i]["emotion_audio"]
        
        # Пропуск пустых транскрипций
        if not transcription.strip():  # Если транскрипция пустая или состоит из пробелов
            continue
        
        words = transcription.split()
        word_timings = calculate_word_timings(phrase_start, phrase_end, words)
        
        result.append({
            "spk": spk,
            "text": transcription,
            "emotion_audio": emotion,
            "result": word_timings
        })
    
    # Обработка правого канала
    segments_audio = split_audio_by_segments(right_path, right_result)
    segment_results = transcribe_segments(segments_audio, f"{base_filename}_right")
    for i, segment in enumerate(right_result):
        spk = segment[3]
        phrase_start = segment[1]
        phrase_end = segment[2]
        transcription = segment_results[i]["text"]
        emotion = segment_results[i]["emotion_audio"]
        
        # Пропуск пустых транскрипций
        if not transcription.strip():  # Если транскрипция пустая или состоит из пробелов
            continue
        
        words = transcription.split()
        word_timings = calculate_word_timings(phrase_start, phrase_end, words)
        
        result.append({
            "spk": spk,
            "text": transcription,
            "emotion_audio": emotion,
            "result": word_timings
        })
    
    # Удаление временных файлов
    os.remove(left_path)
    os.remove(right_path)
    
    return result

def process_audio(audio_path):
    """Основная функция обработки аудио."""
    channels = get_audio_channels(audio_path)
    
    if channels == 1:
        print("Обработка монофонического аудио...")
        result = process_mono_audio(audio_path)
    elif channels == 2:
        print("Обработка стереофонического аудио...")
        result = process_stereo_audio(audio_path)
    else:
        raise ValueError("Аудио должно быть моно или стерео.")
    
    result.sort(key=lambda x: x['result'][0]['start'])
    return result