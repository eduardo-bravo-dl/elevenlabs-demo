import os
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
response = client.text_to_speech.convert(
  voice_id="JBFqnCBsd6RMkjVDRZzb",
  model_id="eleven_v3",
  text="This is a test for the API of ElevenLabs."
)
with open("output.mp3", "wb") as f:
  f.write(b"".join(response))
print("Saved output.mp3")