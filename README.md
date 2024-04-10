# Environment
- microphone & speaker
- python3 (3.11 recommended for installing PyAudio. At 3.12 it is not easy to install PyAudio.)


# How to use
- install all requirements
  ```
  pip install -r requirements.txt
  ```

- make .env file and set needed items
  ```
  OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxx
  ASSISTANT_ID=asst_xxxxxxxxxxxxxxxxxxxxxxxxxx
  ```
  - https://platform.openai.com/api-keys for OPENAI_API_KEY
  - https://platform.openai.com/assistants for ASSISTANT_ID

- run **assistant.py** and start conversation with your assistant


# How is it fast?
- Adopted openai's streaming api
- Used threading fully to fetch the assistant's responses and generate audio files
