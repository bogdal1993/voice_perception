import psycopg2, time
from psycopg2 import pool
import threading
import queue, sox, os, sys
from websocket import create_connection, ABNF
import wave, json
import subprocess
from sklearn.cluster import KMeans
import numpy as np
import time
import requests

VOSK_SERVER = os.environ.get('VOSK_SERVER')
DSN = os.getenv('DSN')
q = queue.Queue()
threaded_postgreSQL_pool = psycopg2.pool.ThreadedConnectionPool(1, 32, DSN)

base_temp_path = "/opt/tempmedia"

def wsSend(uri,file_path):
	answer = []
	wf = wave.open(file_path, "rb")
	ws=create_connection(uri)
	ws.send('{ "config" : { "sample_rate" : %d } }' % (wf.getframerate()))
	buffer_size = int(wf.getframerate() * 0.2)
	while True:
		data = wf.readframes(buffer_size)

		if len(data) == 0:
			break

		ws.send(data, ABNF.OPCODE_BINARY)
		#ws.send_binary(data)
		res = json.loads(ws.recv())
		
		if 'result' in res:
			if len(res['result']):
				answer.append(res)

	ws.send('{"eof" : 1}')
	res = json.loads(ws.recv())
	if 'result' in res:
		if len(res['result']):
			answer.append(res)
	ws.close()
	return answer
	
def diarization(answer):
	transcriptions = []
	n_clusters = 2
	kmeans = None
	def last_spk_toogle(last):
		if last == 0:
			return 1
		else:
			return 0
	X = [x['spk'] for x in answer if 'spk' in x]
	if len(X)>=n_clusters:
		kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(X)
	last_spk = 0
	for frase in answer:
		if 'spk' in frase and kmeans:
			last_spk = int(kmeans.predict([frase['spk']])[0])
		else:
			last_spk = last_spk_toogle(last_spk)
		try:
			transcriptions.append({'text':frase['text'],'result':frase['result'],'spk':last_spk})
		except:
			pass
	return transcriptions
	
	
def download_file(file_path,call_uuid,file_server):
	response = requests.get(file_server+'file/'+call_uuid, stream=True)
	if response.status_code == 200:
		with open(file_path, 'wb') as f:
			f.write(response.content)      

def worker():
	while True:
		file_path,call_uuid,file_server = q.get()
		download_file(file_path,call_uuid,file_server)
		res = sox.file_info.info(file_path)#{'channels': 2, 'sample_rate': 8000.0, 'bitdepth': 16, 'bitrate': 256000.0, 'duration': 21.68, 'num_samples': 173440, 'encoding': 'Signed Integer PCM', 'silent': False}
		sounds_to_transcript = []
		transcriptions = []
		sample_rate = int(res['sample_rate'])
		if sample_rate > 16000:
			sample_rate = 16000
		if sample_rate < 8000:
			sample_rate = 8000
		if res['encoding']=='Signed Integer PCM':
			if res['channels']>1:
				for ch in range(res['channels']):
					ch = ch+1
					sound_name = os.path.basename(file_path)
					sound_name = os.path.splitext(sound_name)[0]
					sound_name = os.path.join(base_temp_path,sound_name+'_'+str(ch)+'.wav')
					subprocess.call('sox "{}" -r {} -c 1 -b 16 "{}" remix {}'.format(file_path,sample_rate,sound_name,ch), shell=True)
					sounds_to_transcript.append(sound_name)
				#sox disturbence.wav -r 16000 -c 1 -b 16 disturbence_16000_mono_16bit.wav
			else:
				sounds_to_transcript.append(file_path)
		else:
			if res['channels']>1:
				for ch in range(res['channels']):
					ch = ch+1
					sound_name = os.path.basename(file_path)
					sound_name = os.path.splitext(sound_name)[0]
					sound_name = os.path.join(base_temp_path,sound_name+'_'+str(ch)+'.wav')
					subprocess.call('sox "{}" -r {} -c 1 -b 16 "{}" remix {}'.format(file_path,sample_rate,sound_name,ch), shell=True)
					sounds_to_transcript.append(sound_name)
			else:
				ch = 1
				sound_name = os.path.basename(file_path)
				sound_name = os.path.splitext(sound_name)[0]
				sound_name = os.path.join(base_temp_path,sound_name+'_'+str(ch)+'.wav')
				subprocess.call('sox "{}" -r {} -c 1 -b 16 "{}" remix {}'.format(file_path,sample_rate,sound_name,ch), shell=True)
				sounds_to_transcript.append(sound_name)
		if len(sounds_to_transcript) >1:
			for spk,sound in enumerate(sounds_to_transcript):
				res = wsSend(VOSK_SERVER,sound)
				for frase in res:
					frase['spk'] = spk
					transcriptions.append(frase)
					print(frase, flush=True)
				os.remove(sound)
		else:
			result = wsSend(VOSK_SERVER,sounds_to_transcript[0])
			transcriptions = diarization(result)
			os.remove(sounds_to_transcript[0])
		transcriptions.sort(key=lambda x:x['result'][0]['start'])
		conn = threaded_postgreSQL_pool.getconn()
		try:
			cur = conn.cursor()
			cur.execute("INSERT INTO vp.calls_transcription(call_uuid, transcription) VALUES (%s, %s) ON CONFLICT ON CONSTRAINT calls_transcription_pkey DO NOTHING;",(call_uuid,json.dumps(transcriptions),))
			conn.commit()
			cur.execute("INSERT INTO vp.tasks(call_uuid, task) VALUES (%s, %s) ON CONFLICT ON CONSTRAINT tasks_pkey DO NOTHING;",(call_uuid,'{"transcript": "OK","text_process": "ready","tag_process":"wait"}',))
			conn.commit()
			cur.execute("delete from vp.transcript_queue where call_uuid = %s",(call_uuid,))
			conn.commit()
			cur.close()
		except Exception as d:
			print(d, flush=True)
		finally:
			threaded_postgreSQL_pool.putconn(conn)
		#os.remove(file_path)
		q.task_done()

for i in range(16):
	threading.Thread(target=worker, daemon=True).start()
time.sleep(30)
while 1:
	conn = threaded_postgreSQL_pool.getconn()
	cur = conn.cursor()
	cur.execute("SELECT file_path, file_server, call_uuid FROM vp.transcript_queue where status = 'ready' limit 30")
	tasks = cur.fetchall()
	for task in tasks:
		file_path,file_server,call_uuid = task
		cur.execute("update vp.transcript_queue set status = 'processing' where call_uuid = %s",(call_uuid,))
		conn.commit()
		q.put((file_path,call_uuid,file_server))
	cur.close()
	threaded_postgreSQL_pool.putconn(conn)
	time.sleep(5)
