import wespeaker
import gigaam
import json
import os
from pydub import AudioSegment
import torch
import torchaudio
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
from typing import Dict, Tuple

NUM_THREADS = int(os.getenv('TRANSCRIPT_NUM_THREADS', 2)) 
base_temp_path = "/opt/tempmedia"

MODEL_NAME_DIAR = 'models/voxblink2_samresnet34_ft'
# Загрузка модели диаризации
#diarization_model = wespeaker.load_model_local(MODEL_NAME_DIAR)
# Загрузка модели диаризации
diarization_model = wespeaker.load_model_local(MODEL_NAME_DIAR)
#diarization_model.set_device('cuda:0')
torch.set_num_threads(NUM_THREADS)

# Загрузка модели распознавания речи
asr_model_name = "v2_ctc"
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