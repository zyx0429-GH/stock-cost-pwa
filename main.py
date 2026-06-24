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
from fastapi.responses import FileResponse, HTMLResponse
from starlette.requests import Request
from api import router

app = FastAPI(
    title="大戶成本查詢工具 PWA",
    description="台股大戶成本分析 - 手機友善版本",
    version="1.3.3"
)

# 全域回應頭：禁止快取 HTML/CSS/JS，確保每次拿到最新版
@app.middleware("http")
async def no_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    # 對 HTML、CSS、JS 和根路徑設定禁止快取
    if not path.startswith("/api/") and not path.startswith("/health"):
        if path == "/" or any(path.endswith(ext) for ext in (".html", ".css", ".js", ".json", ".ico", ".png")):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    return response

# API 路由 (必須在 catch-all 之前)
app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return FileResponse("static/index.html")


# 掛載靜態資源目錄
app.mount("/static", StaticFiles(directory="static"), name="static")


# SPA 路由 - 所有其他路徑都回傳 index.html (必須在最後)
@app.get("/{path:path}", response_class=HTMLResponse)
async def spa_catch_all(path: str):
    """SPA 路由 - 所有路徑都回傳 index.html"""
    # 排除 API 和 static 路徑
    if path.startswith("api") or path.startswith("static"):
        return {"detail": "Not Found"}
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h1>大戶成本查詢工具</h1><p>載入中...</p>"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 大戶成本查詢工具 PWA 版")
    print(f"   端口: {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
