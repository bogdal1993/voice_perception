import os, time, json
from psycopg2 import pool
from collections import defaultdict
DSN = os.getenv('DSN')
threaded_postgreSQL_pool = pool.ThreadedConnectionPool(1, 3, DSN)

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

model_checkpoint = 'cointegrated/rubert-base-cased-nli-threeway'

tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)
model = AutoModelForSequenceClassification.from_pretrained(model_checkpoint)
if torch.cuda.is_available():
    model.cuda()

def predict_zero_shot(text, label_texts, model, tokenizer, label='entailment', normalize=False,thresh = 0.7):
    if not label_texts:
        return []
    tokens = tokenizer([text] * len(label_texts), label_texts, truncation=True, return_tensors='pt', padding=True)
    with torch.inference_mode():
        result = torch.softmax(model(**tokens.to(model.device)).logits, -1)
    proba = result[:, model.config.label2id[label]].cpu().numpy()
    if normalize:
        proba /= sum(proba)
    proba_index = []
    for i, prob in enumerate(proba):
        if prob > thresh:
            proba_index.append((i,prob))
    return proba_index
    
    
def deduplicate_json(input_json):
    # Создаем словарь с уникальными значениями
    unique_entries = defaultdict(lambda: {"proba": float("-inf")})

    for entry in input_json:
        spk = entry["spk"]
        tag = entry["tag"]
        proba = entry["proba"]

        if proba > unique_entries[(spk, tag)]["proba"]:
            unique_entries[(spk, tag)] = {"proba": proba, "spk": spk, "tag": tag}

    # Преобразуем словарь обратно в список
    output_json = list(unique_entries.values())
    return output_json


def process_call_tag(call_uuid, task_data, frases_2_tag0, frases0,frases_2_tag1,frases1):
    conn = threaded_postgreSQL_pool.getconn()
    cur = conn.cursor()
    cur.execute("SELECT transcription FROM vp.calls_transcription where call_uuid = %s limit 1",(call_uuid,))
    result = cur.fetchone()
    cur.close()
    threaded_postgreSQL_pool.putconn(conn)
    transcription = result[0]
    tags_set=[]
    for frase in transcription:
        if frase["spk"]==0:
            tags = predict_zero_shot(frase['text'],frases0,model,tokenizer)
            for tag in tags:
                tags_set.append({"tag":frases_2_tag0[frases0[tag[0]]],"proba":float(tag[1]),"spk":frase["spk"]})
        if frase["spk"]==1:
            tags = predict_zero_shot(frase['text'],frases1,model,tokenizer)
            for tag in tags:
                tags_set.append({"tag":frases_2_tag1[frases1[tag[0]]],"proba":float(tag[1]),"spk":frase["spk"]})
    '''if len(tags_set)==0:
        return'''
    #tags_set = list(set(tags_set))
    tags_set = deduplicate_json(tags_set)
    conn = threaded_postgreSQL_pool.getconn()
    cur = conn.cursor()
    cur.execute("insert into vp.calls_tags values(%s,%s)",(call_uuid,json.dumps(tags_set),))
    
    task_data['tag_process'] = "OK"
    cur.execute("UPDATE vp.tasks SET task = %s where call_uuid = %s",(json.dumps(task_data), call_uuid,))
    conn.commit()
    cur.close()
    threaded_postgreSQL_pool.putconn(conn)
    

while 1:
    conn = threaded_postgreSQL_pool.getconn()
    cur = conn.cursor()
    cur.execute("SELECT call_uuid, task FROM vp.tasks where task->>'tag_process' = 'ready' limit 30")
    tasks = cur.fetchall()
    
    cur.execute("SELECT tag_name, tag_spk, tag_texts::json FROM vp.tags_core")
    tag_core = cur.fetchall()
    cur.close()
    
    frases_2_tag0 = {}
    frases0 = []
    frases_2_tag1 = {}
    frases1 = []

    #predict_zero_shot('Какая гадость эта ваша заливная рыба!', classes, model, tokenizer)

    for class_name, spk, text_list in tag_core:
        for text in text_list:
            if spk==0:
                frases0.append(text)
                frases_2_tag0[text] = class_name
            if spk==1:
                frases1.append(text)
                frases_2_tag1[text] = class_name
            if spk==-1:
                frases0.append(text)
                frases_2_tag0[text] = class_name
                frases1.append(text)
                frases_2_tag1[text] = class_name
    
    threaded_postgreSQL_pool.putconn(conn)
    i = 0
    #print(tag_core)
    for task in tasks:
        i+=1
        call_uuid,task_data = task
        process_call_tag(call_uuid,task_data,frases_2_tag0,frases0,frases_2_tag1,frases1)
        #cur.execute("update vp.transcript_queue set status = 'processing' where call_uuid = %s",(call_uuid,))
        #conn.commit()
    if i==0:
        time.sleep(5)
