# from deeppavlov import build_model, configs
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

def get_db_connection():
    """Get a database connection with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = threaded_postgreSQL_pool.getconn()
            # Test the connection
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            return conn
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:  # Last attempt
                raise e
            time.sleep(1)  # Wait before retry
    return None

#model = build_model(configs.classifiers.rusentiment_bert, download=False)
# model = build_model(configs.classifiers.rusentiment_convers_bert, download=True)

class NeutralModel:
    def __call__(self, texts):
        """
        Мок-метод, который имитирует поведение модели DeepPavlov.
        Всегда возвращает 'neutral' для каждого входного текста.
        """
        return ['skip'] * len(texts)

model = NeutralModel()

print("ff", flush=True)
print(model(['алло'])[0], flush=True)

tokens = tokenizer.tokenize('народных')
tags = tagger.tag(tokens)
lemmas = lemmatizer.lemmatize(tags)
print(lemmas[0][2], lemmas[0][3],  flush=True)
def process_call_transcript(call_uuid,task_data):
	conn = get_db_connection()
	try:
		cur = conn.cursor()
		cur.execute("SELECT transcription FROM vp.calls_transcription where call_uuid = %s limit 1",(call_uuid,))
		result = cur.fetchone()
		cur.close()
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
		conn2 = get_db_connection()
		try:
			cur2 = conn2.cursor()
			cur2.execute("UPDATE vp.calls_transcription SET transcription = %s where call_uuid = %s",(json.dumps(transcription), call_uuid,))
			task_data['text_process'] = "OK"
			task_data['tag_process'] = "ready"
			cur2.execute("UPDATE vp.tasks SET task = %s where call_uuid = %s",(json.dumps(task_data), call_uuid,))
			conn2.commit()
			cur2.close()
		finally:
			threaded_postgreSQL_pool.putconn(conn2)
	finally:
		threaded_postgreSQL_pool.putconn(conn)
	
	

MAX_RETRIES = 3
RETRY_DELAY = 5

while 1:
	conn = None
	tasks = []
	retry_count = 0
	
	while retry_count < MAX_RETRIES:
		try:
			conn = get_db_connection()
			cur = conn.cursor()
			cur.execute("SELECT call_uuid, task FROM vp.tasks where task->>'text_process' = 'ready' limit 30")
			tasks = cur.fetchall()
			cur.close()
			break  # Success, exit retry loop
		except Exception as e:
			print(f"Database query failed: {e}, attempt {retry_count + 1}/{MAX_RETRIES}")
			if conn:
				threaded_postgreSQL_pool.putconn(conn)
				conn = None
			retry_count += 1
			if retry_count >= MAX_RETRIES:
				print("Max retries reached, sleeping before next attempt...")
				time.sleep(RETRY_DELAY)
				break
			time.sleep(RETRY_DELAY)
	
	if conn:
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
