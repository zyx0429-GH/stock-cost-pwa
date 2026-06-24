#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 路由 - 大戶成本查詢工具 PWA 版
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import traceback

from core import (
    fetch_stock_data,
    fetch_tdcc_weekly,
    calc_costs,
    calc_momentum,
    calc_concentration,
    line_summary,
    get_stock_name,
    load_watchlist,
    save_watchlist,
    get_quick_price,
    STOCK_NAMES
)

# 建立路由
router = APIRouter()

# ============================================================================
# 請求/回應模型
# ============================================================================
class AnalyzeRequest(BaseModel):
    code: str
    weeks: int = 13

class WatchlistAddRequest(BaseModel):
    category: str  # "持倉" or "觀察"
    code: str
    name: Optional[str] = None
    cost: Optional[float] = None
    shares: Optional[int] = None

class WatchlistRemoveRequest(BaseModel):
    category: str
    code: str

# ============================================================================
# API 端點
# ============================================================================

@router.post("/analyze")
async def analyze_stock(req: AnalyzeRequest):
    """
    分析個股大戶成本
    POST /api/analyze
    Body: {"code": "6770", "weeks": 13}
    """
    try:
        code = req.code.strip().zfill(4)
        weeks = min(max(req.weeks, 4), 52)  # 限制 4-52 週
        
        print(f"\n{'='*60}")
        print(f"📊 分析請求: {code} ({weeks}週)")
        print(f"{'='*60}")
        
        # 取得股票名稱
        name = get_stock_name(code)
        
        # 抓取大戶持股資料
        data = fetch_stock_data(code, force=False)
        if not data:
            raise HTTPException(status_code=404, detail=f"無法取得 {code} 的資料")
        
        # 取最近 n 週
        if len(data) < weeks:
            weeks = len(data)
        seg = data[-weeks:]
        
        # 計算成本
        start_idx = len(data) - weeks
        end_idx = len(data) - 1
        costs = calc_costs(data, start_idx, end_idx, code=code)
        
        # 計算指標
        momentum = calc_momentum(seg)
        concentration = calc_concentration(seg)
        
        # 取得 TDCC 每週資料（大戶持股%變動）
        tdcc_data = fetch_tdcc_weekly(code, display_weeks=weeks)
        
        # 準備圖表資料
        dates = [d['date'] for d in seg]
        big_pcts = [d['big_pct'] for d in seg]
        ultra_pcts = [d['ultra_pct'] for d in seg]
        prices = [d['price'] for d in seg]
        mom_values = [m['big'] for m in momentum]
        conc_values = [c['conc'] for c in concentration]
        
        # 產生 LINE 摘要
        price = seg[-1]['price']
        summary = line_summary(code, name, seg, costs, price)
        
        # 產生關鍵指標列表
        indicators = []
        d = seg[-1]
        p = seg[-2] if len(seg) >= 2 else d
        bc = d['big_pct'] - p['big_pct']
        uc = d['ultra_pct'] - p['ultra_pct']
        
        # 大戶動向
        if bc > 0.5:
            indicators.append(f"🟢 大戶本週加碼 +{bc:.2f}%")
        elif bc > 0:
            indicators.append(f"🟡 大戶微加 +{bc:.2f}%")
        elif bc > -0.5:
            indicators.append(f"🟡 大戶微減 {bc:.2f}%")
        else:
            indicators.append(f"🔴 大戶明顯減碼 {bc:.2f}%")
        
        # 超大戶動向
        if uc > 0.3:
            indicators.append(f"🟢 超大戶加碼 +{uc:.2f}%")
        elif uc < -0.3:
            indicators.append(f"🔴 超大戶減碼 {uc:.2f}%")
        
        # 集中度
        conc = d['cnt_over_1000'] / d['big_count'] * 100 if d['big_count'] > 0 else 0
        indicators.append(f"📊 集中度(>1000張): {conc:.1f}%")
        
        # A法成本分析
        if costs.get('a'):
            da = (price - costs['a']) / costs['a'] * 100
            if da > 0:
                indicators.append(f"📐 股價高於A法成本 +{da:.1f}%")
            else:
                indicators.append(f"📐 股價低於A法成本 {da:.1f}%")
        
        # D法成本分析
        if costs.get('d'):
            dd = (price - costs['d']) / costs['d'] * 100
            if dd > 0:
                indicators.append(f"🎯 股價高於D法主力成本 +{dd:.1f}%")
            else:
                indicators.append(f"🎯 股價低於D法主力成本 {dd:.1f}%")
            
            d_detail = costs.get('d_detail', {})
            if d_detail:
                new_sh = d_detail.get('new_shares', 0)
                inst_net = d_detail.get('inst_net', 0)
                big_only = d_detail.get('big_only', 0)
                indicators.append(f"📋 大戶新增{new_sh:,.0f}張 法人{inst_net/1000:+,.0f}張 純大戶{big_only:,.0f}張")
        
        # 每週明細（供表格顯示）
        detail_weeks = []
        for i, d in enumerate(seg):
            prev = seg[i - 1] if i > 0 else None
            bc = d['big_pct'] - prev['big_pct'] if prev else None
            uc = d['ultra_pct'] - prev['ultra_pct'] if prev else None
            detail_weeks.append({
                'date': d['date'],
                'total_shares': d['total_shares'],
                'holder_count': d['holder_count'],
                'avg_shares': round(d['avg_shares'], 1),
                'big_shares': d['big_shares'],
                'big_pct': round(d['big_pct'], 2),
                'big_pct_chg': round(bc, 2) if bc is not None else None,
                'ultra_pct': round(d['ultra_pct'], 2),
                'ultra_pct_chg': round(uc, 2) if uc is not None else None,
                'conc': round(d['cnt_over_1000'] / d['big_count'] * 100, 1) if d['big_count'] > 0 else 0,
                'price': d['price']
            })
        
        # 成功回應
        return {
            'success': True,
            'code': code,
            'name': name,
            'weeks': weeks,
            'price': price,
            'costs': costs,
            'indicators': indicators,
            'detail_weeks': detail_weeks,
            'chart_data': {
                'dates': dates,
                'big_pct': big_pcts,
                'ultra_pct': ultra_pcts,
                'prices': prices,
                'momentum': mom_values,
                'concentration': conc_values
            },
            'summary': summary,
            'data_count': len(data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[錯誤] 分析失敗: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"分析失敗: {str(e)}")


@router.get("/watchlist")
async def get_watchlist():
    """
    取得監測清單
    GET /api/watchlist
    """
    try:
        watchlist = load_watchlist()
        return {
            'success': True,
            'watchlist': watchlist
        }
    except Exception as e:
        print(f"[錯誤] 讀取監測清單失敗: {e}")
        raise HTTPException(status_code=500, detail=f"讀取失敗: {str(e)}")


@router.post("/watchlist/add")
async def add_to_watchlist(req: WatchlistAddRequest):
    """
    新增到監測清單
    POST /api/watchlist/add
    Body: {"category": "持倉", "code": "6770", "name": "力積電", "cost": 65.0, "shares": 10}
    """
    try:
        watchlist = load_watchlist()
        
        if req.category not in watchlist:
            watchlist[req.category] = []
        
        # 檢查是否已存在
        for item in watchlist[req.category]:
            if item['code'] == req.code:
                raise HTTPException(status_code=400, detail=f"{req.code} 已在清單中")
        
        # 取得股票名稱
        name = req.name or get_stock_name(req.code)
        
        new_item = {'code': req.code.zfill(4), 'name': name}
        if req.cost is not None:
            new_item['cost'] = req.cost
        if req.shares is not None:
            new_item['shares'] = req.shares
        
        watchlist[req.category].append(new_item)
        save_watchlist(watchlist)
        
        return {
            'success': True,
            'message': f"已新增 {name}({req.code}) 到 {req.category}",
            'watchlist': watchlist
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[錯誤] 新增失敗: {e}")
        raise HTTPException(status_code=500, detail=f"新增失敗: {str(e)}")


@router.post("/watchlist/remove")
async def remove_from_watchlist(req: WatchlistRemoveRequest):
    """
    從監測清單移除
    POST /api/watchlist/remove
    Body: {"category": "持倉", "code": "6770"}
    """
    try:
        watchlist = load_watchlist()
        
        if req.category not in watchlist:
            raise HTTPException(status_code=400, detail=f"類別 {req.category} 不存在")
        
        before = len(watchlist[req.category])
        watchlist[req.category] = [item for item in watchlist[req.category] if item['code'] != req.code]
        after = len(watchlist[req.category])
        
        if before == after:
            raise HTTPException(status_code=404, detail=f"{req.code} 不在清單中")
        
        save_watchlist(watchlist)
        
        return {
            'success': True,
            'message': f"已移除 {req.code} 從 {req.category}",
            'watchlist': watchlist
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[錯誤] 移除失敗: {e}")
        raise HTTPException(status_code=500, detail=f"移除失敗: {str(e)}")


@router.get("/price/{code}")
async def get_price(code: str):
    """
    取得即時股價
    GET /api/price/6770
    """
    try:
        result = get_quick_price(code)
        if not result['success']:
            raise HTTPException(status_code=404, detail=f"無法取得 {code} 的股價")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"[錯誤] 查詢股價失敗: {e}")
        raise HTTPException(status_code=500, detail=f"查詢失敗: {str(e)}")


@router.get("/stock-name/{code}")
async def get_name(code: str):
    """
    查詢股票名稱
    GET /api/stock-name/6770
    """
    try:
        name = get_stock_name(code.strip().zfill(4))
        return {
            'success': True,
            'code': code.strip().zfill(4),
            'name': name
        }
    except Exception as e:
        print(f"[錯誤] 查詢名稱失敗: {e}")
        raise HTTPException(status_code=500, detail=f"查詢失敗: {str(e)}")


@router.get("/health")
async def health_check():
    """健康檢查"""
    return {'status': 'ok', 'version': '1.0.0'}
