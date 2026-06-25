#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - FastAPI 后端入口 v1.4
全内联版：CSS/JS 内嵌于 HTML，不依赖外部文件，根除 SW 缓存问题
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
    title="大户成本查询工具 PWA",
    description="台股大户成本分析 - 手机友善版本",
    version="1.4"
)

# 全域回应头：禁止缓存 HTML/CSS/JS/JSON/PNG
@app.middleware("http")
async def no_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if not path.startswith("/api/") and not path.startswith("/health"):
        if path == "/" or any(path.endswith(ext) for ext in (".html", ".css", ".js", ".json", ".ico", ".png")):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    return response

# 独立静态资源（sw.js 可选，仅用于 PWA 安装）
@app.get("/sw.js")
async def serve_sw():
    return FileResponse("static/sw.js", media_type="application/javascript")

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse("static/manifest.json", media_type="application/json")

@app.get("/icon-192.png")
async def serve_icon():
    return FileResponse("static/icon-192.png", media_type="image/png")

# API 路由（必须在 catch-all 之前）
app.include_router(router, prefix="/api")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return FileResponse("static/index.html")

# 静态资源目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# SPA catch-all：非已知路径回传 index.html
STATIC_EXTENSIONS = {".js", ".css", ".png", ".ico", ".jpg", ".jpeg", ".svg", ".json", ".woff", ".woff2", ".ttf", ".map"}

@app.get("/{path:path}", response_class=HTMLResponse)
async def spa_catch_all(path: str):
    if path.startswith("api") or path.startswith("static"):
        return {"detail": "Not Found"}
    for ext in STATIC_EXTENSIONS:
        if path.endswith(ext):
            return {"detail": "Not Found"}
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h1>大户成本查询工具</h1><p>载入中...</p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 大户成本查询工具 PWA v1.4")
    print(f"   端口: {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
