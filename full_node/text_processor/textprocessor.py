from deeppavlov import build_model, configs
import os, time, json
from psycopg2 import pool
import rutokenizer
import rupostagger
import rulemma
import torch
torch.set_num_threads(4)
lemmatizer = rulemma.Lemmatizer()
lemmatizer.load()

tokenizer = rutokenizer.Tokenizer()
tokenizer.load()

tagger = rupostagger.RuPosTagger()
tagger.load()

DSN = os.getenv('DSN')
threaded_postgreSQL_pool = pool.ThreadedConnectionPool(1, 3, DSN)

#model = build_model(configs.classifiers.rusentiment_bert, download=False)
model = build_model(configs.classifiers.rusentiment_convers_bert, download=True)

print("ff", flush=True)
print(model(['алло'])[0], flush=True)

tokens = tokenizer.tokenize('народных')
tags = tagger.tag(tokens)
lemmas = lemmatizer.lemmatize(tags)
print(lemmas[0][2], lemmas[0][3],  flush=True)

def process_call_transcript(call_uuid,task_data):
	conn = threaded_postgreSQL_pool.getconn()
	cur = conn.cursor()
	cur.execute("SELECT transcription FROM vp.calls_transcription where call_uuid = %s limit 1",(call_uuid,))
	result = cur.fetchone()
	cur.close()
	threaded_postgreSQL_pool.putconn(conn)
	transcription = result[0]
	for frase in transcription:
		frase['emotion'] = model([frase['text']])[0]
		try:
			for word in frase['result']:
				tokens = tokenizer.tokenize(word['word'])
				tags = tagger.tag(tokens)
				lemmas = lemmatizer.lemmatize(tags)
				word['lemma'] = lemmas[0][2]
				word['part'] = lemmas[0][3]
		except:
			pass
	conn = threaded_postgreSQL_pool.getconn()
	cur = conn.cursor()
	cur.execute("UPDATE vp.calls_transcription SET transcription = %s where call_uuid = %s",(json.dumps(transcription), call_uuid,))
	task_data['text_process'] = "OK"
	task_data['tag_process'] = "ready"
	cur.execute("UPDATE vp.tasks SET task = %s where call_uuid = %s",(json.dumps(task_data), call_uuid,))
	conn.commit()
	cur.close()
	threaded_postgreSQL_pool.putconn(conn)
	

while 1:
	conn = threaded_postgreSQL_pool.getconn()
	cur = conn.cursor()
	cur.execute("SELECT call_uuid, task FROM vp.tasks where task->>'text_process' = 'ready' limit 30")
	tasks = cur.fetchall()
	cur.close()
	threaded_postgreSQL_pool.putconn(conn)
	i = 0
	for task in tasks:
		i+=1
		call_uuid,task_data = task
		process_call_transcript(call_uuid,task_data)
		#cur.execute("update vp.transcript_queue set status = 'processing' where call_uuid = %s",(call_uuid,))
		#conn.commit()
	if i==0:
		time.sleep(5)
