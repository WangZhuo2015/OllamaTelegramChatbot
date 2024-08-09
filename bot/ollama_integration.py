from ollama import AsyncClient

from utils.config import INITMODEL

client = AsyncClient()


async def generate_response(prompt: str):
    async for part in await client.chat(model=INITMODEL, messages=[{'role': 'user', 'content': prompt}], stream=True):
        yield part['message']['content']
