import os
import re
import base64
import asyncio
from io import BytesIO
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from telethon import TelegramClient
from telethon.sessions import StringSession

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
        return {"status": "online"}

@app.get("/search")
async def search(q: str = Query(..., min_length=2)):
        global client
    if not client:
                return JSONResponse(content={"error": "Client not initialized"}, status_code=500)
            if not client.is_connected():
                        await client.connect()
                    try:
                                results = []
                                async for message in client.iter_messages(GROUP_ID, search=q, limit=20):
                                                item = {
                                                                    "id": message.id,
                                                                    "text": message.text or "",
                                                                    "date": message.date.isoformat(),
                                                                    "has_media": message.media is not None
                                                }
                                                if message.photo:
                                                                    try:
                                                                                            buffer = BytesIO()
                                                                                            await client.download_media(message.photo, file=buffer, thumb=-1)
                                                                                            item["thumbnail"] = base64.b64encode(buffer.getvalue()).decode("utf-8")
                                                                                        except:
                    pass
            results.append(item)
        return results
except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
