"""
RepairSearch Backend — Busca em grupos Telegram com tópicos e imagens
Versão otimizada para deploy no Render.com (usa StringSession)
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

# ─── CONFIG ────────────────────────────────────────────────────
API_ID       = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH     = os.getenv("TELEGRAM_API_HASH", "")
STRING_SESSION = os.getenv("TELEGRAM_STRING_SESSION", "")
GROUP        = os.getenv("TELEGRAM_GROUP", "")
PORT         = int(os.getenv("PORT", "8000"))

# ─── APP ───────────────────────────────────────────────────────
app = FastAPI(title="RepairSearch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Usa StringSession para não depender de arquivo .session
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
group_entity = None


@app.on_event("startup")
async def startup():
    global group_entity
    await client.start()
    print("✅ Telegram conectado!")

    if GROUP:
        try:
            gid = GROUP.lstrip('-')
            if gid.isdigit():
                async for dialog in client.iter_dialogs():
                    if dialog.id == int(GROUP) or str(dialog.id) == gid:
                        group_entity = dialog.entity
                        print(f"✅ Grupo encontrado: {dialog.name} (ID: {dialog.id})")
                        break
                if not group_entity:
                    try:
                        channel_id = int(gid)
                        if channel_id > 1000000000000:
                            channel_id = channel_id - 1000000000000
                        group_entity = await client.get_entity(PeerChannel(channel_id))
                        print(f"✅ Grupo via PeerChannel: {getattr(group_entity, 'title', GROUP)}")
                    except Exception as e2:
                        print(f"⚠️ PeerChannel falhou: {e2}")
            else:
                group_entity = await client.get_entity(GROUP)
                print(f"✅ Grupo: {getattr(group_entity, 'title', GROUP)}")
        except Exception as e:
            print(f"⚠️ Erro ao resolver grupo: {e}")


@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()


# ─── HELPERS ───────────────────────────────────────────────────

async def download_image_base64(message) -> str | None:
    try:
        buf = BytesIO()
        await client.download_media(message.media, file=buf)
        data = buf.getvalue()
        b64 = base64.b64encode(data).decode()
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"Erro imagem msg {message.id}: {e}")
        return None


def has_image(message) -> bool:
    if message.media is None:
        return False
    if isinstance(message.media, MessageMediaPhoto):
        return True
    if isinstance(message.media, MessageMediaDocument):
        mime = getattr(message.media.document, 'mime_type', '')
        return mime.startswith('image/')
    return False


def normalize_query(q: str) -> list[str]:
    q = q.strip().lower()
    terms = [q]
    no_space = q.replace(" ", "")
    if no_space != q:
        terms.append(no_space)
    hyphen = q.replace(" ", "-")
    if hyphen != q:
        terms.append(hyphen)
    return list(dict.fromkeys(terms))


async def search_in_entity(entity, query: str, limit: int = 30) -> list:
    messages = await client(SearchRequest(
        peer=entity,
        q=query,
        filter=InputMessagesFilterEmpty(),
        min_date=None,
        max_date=None,
        offset_id=0,
        add_offset=0,
        limit=limit,
        max_id=0,
        min_id=0,
        hash=0,
    ))
    return messages.messages


async def get_topic_name(entity, msg) -> str:
    try:
        if hasattr(msg, 'reply_to') and msg.reply_to:
            tid = getattr(msg.reply_to, 'reply_to_top_id', None) or \
                  getattr(msg.reply_to, 'reply_to_msg_id', None)
            if tid:
                return f"Tópico #{tid}"
    except:
        pass
    return "Geral"


# ─── ROUTES ────────────────────────────────────────────────────

@app.get("/search")
async def search(q: str = Query(..., min_length=1)):
    if not GROUP:
        return JSONResponse({"error": "TELEGRAM_GROUP não configurado", "results": []}, status_code=500)

    if not group_entity:
        return JSONResponse({"error": "Grupo não encontrado", "results": []}, status_code=500)

    entity = group_entity
    terms = normalize_query(q)
    seen_ids = set()
    raw_results = []

    for term in terms:
        try:
            msgs = await search_in_entity(entity, term, limit=25)
            for msg in msgs:
                if msg.id not in seen_ids:
                    seen_ids.add(msg.id)
                    raw_results.append(msg)
        except Exception as e:
            print(f"Erro buscando '{term}': {e}")

    if not raw_results:
        return JSONResponse({
            "results": [],
            "total": 0,
            "message": f"Nenhum resultado para '{q}'"
        })

    results = []
    for msg in sorted(raw_results, key=lambda m: m.date, reverse=True):
        text = msg.message or ""
        image_b64 = None

        if has_image(msg):
            image_b64 = await download_image_base64(msg)

        if not text and not image_b64:
            continue

        topic = await get_topic_name(entity, msg)

        results.append({
            "id": msg.id,
            "text": text,
            "image": image_b64,
            "date": msg.date.strftime("%d/%m/%Y %H:%M"),
            "topic": topic,
            "link": None,
        })

    return JSONResponse({
        "results": results,
        "total": len(results),
        "message": f"{len(results)} resultado(s) para '{q}'"
    })


@app.get("/health")
async def health():
    return {"status": "ok", "connected": client.is_connected(), "group": GROUP}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
