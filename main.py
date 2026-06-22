#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - FastAPI 後端入口 (修復版，支援 Render 部署)
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api import router

app = FastAPI(
    title="大戶成本查詢工具 PWA",
    description="台股大戶成本分析 - 手機友善版本",
    version="1.0.0"
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


# 掛載靜態資源目錄
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 大戶成本查詢工具 PWA 版")
    print(f"   端口: {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
