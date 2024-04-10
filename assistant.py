import os, datetime, time, re, threading
from pytz import timezone
from pathlib import Path
from dotenv import load_dotenv
from playsound import playsound
from typing_extensions import override
from openai import OpenAI
from openai import AssistantEventHandler
import speech_recognition as sr

# Load the environment variables from the .env file
# Visit https://platform.openai.com/api-keys for OPENAI_API_KEY
# Visit https://platform.openai.com/assistants for ASSISTANT_ID
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ASSISTANT_ID = os.getenv('ASSISTANT_ID')

# set current path
working_path = str(Path(__file__).parent)

# get recognizer / client 
recognizer = sr.Recognizer()
client = OpenAI(api_key=OPENAI_API_KEY)

# make new thread(Note: not a multithread in python!)
thread = client.beta.threads.create()

# for managing thread termination
active_threads = []

# variables for managing speech play order
speech_order_ticket = 0 # used at EventHandler class
speech_order_to_be_played = 0

# A lock to prevent multiple audios from playing simultaneously
lock = threading.Lock()

# To ensure that audio file names do not duplicate
# For convenience, insert your country and city name
def get_now() -> str: 
    return datetime.datetime.now(timezone('Asia/Seoul')).strftime('%Y%m%d_%H%M%S%f')

'''
< execution order >
EventHandler(on_text_delta) 
-> text_to_speech (thread) 
-> make_speech_file 
-> play_audio_file_with_lock (thread)
'''

class EventHandler(AssistantEventHandler):    
    @override
    def on_text_created(self, text) -> None:
        print(f"[ASSISTANT] ", end="", flush=True)
      
    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)
        
        if delta.value in ['\n', '.', '!', '?']: # when a sentence finished.
            global active_threads, speech_order_ticket
            splited_list = re.split('[.!?\\n]', snapshot.value)
            trimed_list = [sentence for sentence in splited_list if sentence != ""]
            last_sentence = trimed_list[-1]
            sentence_number = len(splited_list) - 1 
            t = threading.Thread(target=text_to_speech, args=(last_sentence, speech_order_ticket))
            speech_order_ticket += 1
            t.daemon = True
            t.start()            
            active_threads.append(t)
      
    def on_tool_call_created(self, tool_call):
        print(f"[ASSISTANT] {tool_call.type}\n", flush=True)
  
    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                print(delta.code_interpreter.input, end="", flush=True)
            if delta.code_interpreter.outputs:
                print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)

# text to speech
def text_to_speech(input, speech_order):
    file_name = make_speech_file(input, speech_order)
    
    global active_threads
    t = threading.Thread(target=play_audio_file_with_lock, args=(file_name, speech_order))
    t.daemon = True
    t.start()    
    active_threads.append(t)

def make_speech_file(input: str, speech_order: int) -> str:
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        input=input,
    ) as response:
        file_name = f"speech_{get_now()}_{str(speech_order)}.mp3"
        response.stream_to_file(file_name)
        
    return file_name

def play_audio_file_with_lock(file_name: str, speech_order: int) -> None:
    global speech_order_to_be_played
    
    # A counter to prevent infinite loops caused by errors
    waiting_limit_seconds = 120
    sleep_seconds = 0.1
    max_sleep_count = waiting_limit_seconds / sleep_seconds
    sleep_count = 0
    
    # Loop and wait until it's your turn
    while sleep_count < max_sleep_count:
        if speech_order <= speech_order_to_be_played:
            lock.acquire()    
            file_path = os.path.join(working_path, file_name)    
            if os.path.isfile(file_path):
                playsound(file_path)    
                if 'speech' in file_name:
                    os.remove(file_path)
            speech_order_to_be_played += 1
            lock.release()
            break
        else:
            sleep_count += 1
            time.sleep(sleep_seconds)

# Used for playing audio where order is not necessary (e.g., playing sound effects)
def play_audio_file(file_name: str) -> None:
    file_path = os.path.join(working_path, file_name)
    if os.path.isfile(file_path):
        playsound(file_path)
        if 'speech' in file_name:
            os.remove(file_path)
            
def wait_for_threads() -> None:
    global active_threads
    for t in active_threads:
        t.join()
    active_threads = [] # re-initiation for next conversation

def capture_voice_input() -> str:
    text = ""
    with sr.Microphone() as source:
        print("\nListening...")
        play_audio_file("notification.wav")
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_whisper_api(audio, api_key=OPENAI_API_KEY)
        print(f"[USER] {text}")
    except sr.RequestError as e:
        print(f"Could not request results from Whisper API; {e}")        
    return text

def main():
    # main loop(conversation)
    while True:
        text_user = capture_voice_input()

        # make new message
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=text_user
        )

        with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
            instructions="you should end every sentence with one of '.', '!', '?'",
            event_handler=EventHandler(),
        ) as stream:
            stream.until_done()
            
        # After stream processing is complete, wait until all threads have terminated
        wait_for_threads()
    
if __name__ == '__main__':
    main()