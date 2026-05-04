import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

response = client.chat.completions.create(
    model=os.getenv("OPENAI_MODEL", "openai/gpt-5-mini"),
    messages=[{"role": "user", "content": "Hello, how are you?"}],
)

print("模型返回：", response.choices[0].message.content)
