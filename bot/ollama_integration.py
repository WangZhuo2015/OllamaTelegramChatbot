import logging
from typing import List

from ollama import AsyncClient

from utils.config import INITMODEL

client = AsyncClient()


async def generate_response(messages: List[str:str]):
    logging.info(f"messages: {messages if len(messages) < 10 else len(messages)}")
    async for part in await client.chat(model=INITMODEL, messages=messages,
                                        stream=True):
        yield part['message']['content']
