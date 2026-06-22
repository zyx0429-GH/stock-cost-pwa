#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 後端主入口 - 大戶成本查詢工具 PWA 版
"""

import sys
import os

# 加入當前目錄到 Python 路徑，以便匯入 core 和 api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api import router

# 建立 FastAPI 應用程式
app = FastAPI(
    title="大戶成本查詢工具 PWA",
    description="台股大戶成本分析 - 手機友善 PWA 版",
    version="1.0.0"
)

# 掛載 API 路由
app.include_router(router, prefix="/api")

# 掛載靜態檔案
app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.on_event("startup")
async def startup_event():
    """應用程式啟動時初始化"""
    from core import init_db
    init_db()
    print("✅ 資料庫初始化完成")
    print("🚀 服務啟動於 http://localhost:8000")


@app.get("/")
async def root():
    """根路徑 - 返回 index.html"""
    return FileResponse("static/index.html")


if __name__ == "__main__":
    print("=" * 60)
    print("📊 大戶成本查詢工具 PWA 版")
    print("=" * 60)
    print("啟動中...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
