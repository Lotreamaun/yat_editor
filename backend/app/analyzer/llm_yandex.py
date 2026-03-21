import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("YANDEX_CLOUD_API_KEY"),
    base_url="https://rest-assistant.api.cloud.yandex.net/v1",
    project=os.getenv("YANDEX_CLOUD_FOLDER")
)

response = client.responses.create(
    model=f"gpt://{os.getenv("YANDEX_CLOUD_FOLDER")}/{os.getenv("YANDEX_CLOUD_MODEL")}",
    temperature=0.3,
    instructions="Исправь грамматические, орфографические и пунктуационные ошибки в тексте. Сохраняй исходный порядок слов.",
    input="Привет! Исправь: Я хачю чтобы все было харашо",
    max_output_tokens=500
)

print(response.output_text)