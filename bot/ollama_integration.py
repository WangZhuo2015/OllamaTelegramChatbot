import logging
from typing import List

from ollama import AsyncClient

from utils.config import INITMODEL

client = AsyncClient()


async def generate_response(messages: List[str:str], model: str = INITMODEL):
    logging.info(f"messages: {messages if len(messages) < 10 else len(messages)}")
    async for part in await client.chat(model=model, messages=messages,
                                        stream=True):
        yield part['message']['content']


# fetch ollma model list with client.list()
async def model_list():
    return await client.list()
