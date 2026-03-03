"""
RepairSearch Backend - Busca em grupos Telegram com topicos e imagens
Versao otimizada para deploy no Render.com (usa StringSession)
"""

import os
import re
import base64
import asyncio
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    InputMessagesFilterEmpty,
    PeerChannel,
)
from telethon.tl.functions.messages import SearchRequest

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
STRING_SESSION = os.getenv("TELEGRAM_STRING_SESSION", "")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP", "0"))

app = FastAPI()

app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
)

client = None

@app.on_event("startup")
async def startup_event():
        global client
        if not API_ID or not API_HASH or not STRING_SESSION:
                    print("ERRO: Variaveis de ambiente faltando!")
                    return

        client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
        await client.connect()
        print("Conectado ao Telegram!")

@app.get("/")
async def root():
        return {"status": "online", "message": "RepairBase Backend is running"}

@app.get("/search")
async def search(q: str = Query(..., min_length=2)):
        global client
        if not client:
                    return JSONResponse(content={"error": "Client not initialized"}, status_code=500)

        if not client.is_connected():
                    await client.connect()

        try:
                    results = []
                    async for message in client.iter_messages(GROUP_ID, search=q, limit=50):
                                    if not message.text and not message.media:
                                                        continue

                                    item = {
                                        "id": message.id,
                                        "text": message.text or "",
                                        "date": message.date.isoformat(),
                                        "has_media": message.media is not None,
                                        "media_type": None,
                                        "thumbnail": None
                                    }

                        if message.photo:
                                            item["media_type"] = "photo"
                                            try:
                                                                    buffer = BytesIO()
                                                                    await client.download_media(message.photo, file=buffer, thumb=-1)
                                                                    item["thumbnail"] = base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
                                print(f"Erro ao baixar thumb: {e}")

                results.append(item)

        return results

except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
        import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
