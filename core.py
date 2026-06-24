#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心計算邏輯 - v1.3 同步桌面版
A法(加權均價VWAP) + D法(主力精算成本)，移除B/C法
"""

import sys, io, os, json, sqlite3, datetime, re
from typing import Optional, Dict, List, Tuple

import requests

# 編碼安全處理
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 常數
WORKSPACE = os.environ.get('STOCK_APP_WORKSPACE', os.path.expanduser("~/.qclaw/workspace"))
DB_PATH = os.path.join(WORKSPACE, "stock_cost.db")
WATCHLIST_PATH = os.path.join(WORKSPACE, "stock_watchlist.json")
REPORT_DIR = os.path.join(WORKSPACE, "stock_reports")
TDCC_WEEKLY_CACHE = os.path.join(REPORT_DIR, "cache", "tdcc", "weekly")
TDCC_ARCHIVE = "https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots"

# 確保目錄存在（雲端環境相容）
def _ensure_dirs():
    for d in [WORKSPACE, REPORT_DIR, TDCC_WEEKLY_CACHE]:
        try:
            os.makedirs(d, exist_ok=True)
        except:
            pass

_ensure_dirs()

# 持股分級
TDCC_LV_400P = {12, 13, 14, 15}    # >400張累計
TDCC_LV_1000P = {15}                # >1000張
TDCC_LV_CONC = {13, 14, 15}        # 集中度(>600張累計)

STOCK_NAMES = {
    "2303": "聯電", "2313": "華通", "2314": "台揚", "2317": "鴻海",
    "2327": "國巨", "2329": "華泰", "2330": "台積電", "2337": "旺宏",
    "2347": "聯強", "2356": "英業達", "2379": "瑞昱", "2382": "廣達",
    "2399": "映泰", "2449": "京元電子", "2451": "創見", "2481": "強茂",
    "2486": "一詮", "2890": "永豐金", "2884": "玉山金", "2882": "國泰金",
    "2881": "富邦金", "2887": "台新新光金", "2883": "凱基金",
    "3006": "晶豪科", "3017": "奇鋐", "3020": "禾伸堂", "3036": "文曄",
    "3131": "弘塑", "3138": "耀登", "3149": "正達", "3178": "公準",
    "3231": "緯創", "3324": "雙鴻", "3491": "昇達科", "3481": "群創",
    "3706": "神達", "3702": "大聯大", "4916": "事欣科", "4967": "十銓",
    "5880": "合庫金", "6005": "群益證", "6182": "合晶", "6176": "瑞儀",
    "6187": "萬潤", "6213": "聯茂", "6265": "方土昶", "6282": "康舒",
    "6285": "啟碁", "6291": "沛亨", "6546": "正基", "6770": "力積電",
    "6890": "來億-KY", "8021": "尖點", "8070": "長華", "8112": "至上",
    "8131": "福懋科", "8150": "南茂", "8210": "勤誠", "8261": "富鼎",
    "2618": "長榮航", "3234": "光環", "1514": "亞力", "6207": "雷科",
    "2243": "宏旭-KY", "4513": "福裕", "8093": "保馳", "5351": "鉅創",
    "4931": "新盛力", "4534": "康騰", "3147": "大絲", "3689": "湧德",
    "6265": "方土銀", "3615": "安可", "4939": "亞電",
}

# ============================================================================
# 股票名稱查詢
# ============================================================================
def fetch_stock_name(code: str) -> str:
    """從 TWSE MIS API 或 yfinance 查詢股票名稱"""
    if code in STOCK_NAMES:
        return STOCK_NAMES[code]
    for ex in ('tse', 'otc'):
        try:
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex}_{code}.tw&json=1&delay=0"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get('msgArray') and len(data['msgArray']) > 0:
                n = data['msgArray'][0].get('n', '')
                if n:
                    STOCK_NAMES[code] = n
                    return n
        except:
            pass
    try:
        import yfinance as yf
        t = yf.Ticker(f"{code}.TW")
        info = t.info
        n = info.get('shortName') or info.get('longName') or ''
        if n:
            STOCK_NAMES[code] = n
            return n
    except:
        pass
    return code

def get_stock_name(code: str) -> str:
    """取得股票名稱"""
    return STOCK_NAMES.get(code) or fetch_stock_name(code)

# ============================================================================
# TDCC 集保每週資料
# ============================================================================
def _tdcc_last_fridays(n: int = 22) -> List[str]:
    today = datetime.date.today()
    last_fri = today - datetime.timedelta(days=(today.weekday() - 4) % 7)
    return sorted([(last_fri - datetime.timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(n)])

def _tdcc_download(date_str: str) -> Optional[Dict]:
    d = os.path.join(TDCC_WEEKLY_CACHE, "csv")
    os.makedirs(d, exist_ok=True)
    cp = os.path.join(d, f"{date_str}.csv")
    
    if os.path.exists(cp):
        with open(cp, 'r', encoding='utf-8-sig') as f:
            txt = f.read()
    else:
        y = date_str[:4]
        url = f"{TDCC_ARCHIVE}/{y}/{date_str}.csv"
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            if resp.status_code != 200:
                return None
            txt = resp.text
            with open(cp, 'w', encoding='utf-8') as f:
                f.write(txt)
        except:
            return None
    
    out = {}
    for ln in txt.strip().split('\n')[1:]:
        fs = [f.strip().strip('"') for f in ln.split(',')]
        if len(fs) < 6:
            continue
        code_s = fs[1]
        if not code_s.isdigit():
            continue
        code_s = code_s.zfill(4)
        try:
            lv = int(fs[2])
            pct = float(fs[5]) if fs[5] else 0
        except:
            continue
        if code_s not in out:
            out[code_s] = {'p400': 0.0, 'p1000': 0.0, 'conc': 0.0}
        if lv in TDCC_LV_400P:
            out[code_s]['p400'] += pct
        if lv in TDCC_LV_1000P:
            out[code_s]['p1000'] += pct
        if lv in TDCC_LV_CONC:
            out[code_s]['conc'] += pct
    return out

def _tdcc_fill_closes(code: str, records: List[dict]):
    if not records:
        return
    try:
        import yfinance as yf
        sd = records[0]['date']
        ed_dt = datetime.datetime.strptime(records[-1]['date'], "%Y-%m-%d") + datetime.timedelta(days=3)
        ed = ed_dt.strftime("%Y-%m-%d")
        for sfx in ['.TW', '.TWO']:
            try:
                df = yf.Ticker(f"{code}{sfx}").history(start=sd, end=ed)
                if df.empty:
                    continue
                pm = {}
                for idx, row in df.iterrows():
                    dk = idx.strftime("%Y-%m-%d")
                    pm[dk] = round(float(row['Close']), 1)
                if not pm:
                    continue
                sds = sorted(pm.keys())
                for rec in records:
                    tgt = rec['date']
                    if tgt in pm:
                        rec['close'] = pm[tgt]
                    else:
                        best = None
                        for dk in sds:
                            if dk <= tgt:
                                best = dk
                            else:
                                break
                        if best:
                            rec['close'] = pm[best]
                break
            except:
                continue
    except Exception as e:
        print(f"[TDCC] 收盤價擷取失敗: {e}")

def fetch_tdcc_weekly(code: str, display_weeks: int = 22) -> List[dict]:
    code = code.strip().zfill(4)
    fridays = _tdcc_last_fridays(display_weeks + 2)
    recs = []
    for fr in fridays:
        m = _tdcc_download(fr)
        if m and code in m:
            recs.append({**m[code], 'date': fr, 'close': 0})
        if len(recs) >= display_weeks + 1:
            break
    if not recs:
        return []
    recs.sort(key=lambda x: x['date'])
    for r in recs:
        r['p400'] = round(r['p400'], 2)
        r['p1000'] = round(r['p1000'], 2)
        r['conc'] = round(r['conc'], 2)
    for i in range(1, len(recs)):
        recs[i]['p400_chg'] = round(recs[i]['p400'] - recs[i-1]['p400'], 2)
        recs[i]['p1000_chg'] = round(recs[i]['p1000'] - recs[i-1]['p1000'], 2)
    recs[0]['p400_chg'] = None
    recs[0]['p1000_chg'] = None
    _tdcc_fill_closes(code, recs)
    return recs

# ============================================================================
# 資料庫操作
# ============================================================================
def init_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS weekly_data (
            code TEXT, date TEXT, total_shares INTEGER, holder_count INTEGER,
            avg_shares REAL, big_shares INTEGER, big_pct REAL, big_count INTEGER,
            cnt_400_600 INTEGER, cnt_600_800 INTEGER, cnt_800_1000 INTEGER,
            cnt_over_1000 INTEGER, ultra_pct REAL, price REAL, fetched_at TEXT,
            PRIMARY KEY (code, date))""")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[警告] 無法初始化資料庫: {e}")

def save_to_db(code: str, data_list: List[dict]):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
        for d in data_list:
            c.execute("""INSERT OR REPLACE INTO weekly_data
                (code,date,total_shares,holder_count,avg_shares,big_shares,big_pct,
                 big_count,cnt_400_600,cnt_600_800,cnt_800_1000,cnt_over_1000,
                 ultra_pct,price,fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (code, d['date'], d['total_shares'], d['holder_count'], d['avg_shares'],
                 d['big_shares'], d['big_pct'], d['big_count'], d['cnt_400_600'],
                 d['cnt_600_800'], d['cnt_800_1000'], d['cnt_over_1000'],
                 d['ultra_pct'], d['price'], now))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[警告] 無法儲存資料庫: {e}")

def load_from_db(code: str) -> List[dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT date,total_shares,holder_count,avg_shares,big_shares,
        big_pct,big_count,cnt_400_600,cnt_600_800,cnt_800_1000,cnt_over_1000,
        ultra_pct,price FROM weekly_data WHERE code=? ORDER BY date ASC""", (code,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return []
        keys = ['date', 'total_shares', 'holder_count', 'avg_shares', 'big_shares',
                'big_pct', 'big_count', 'cnt_400_600', 'cnt_600_800', 'cnt_800_1000',
                'cnt_over_1000', 'ultra_pct', 'price']
        return [dict(zip(keys, r)) for r in rows]
    except Exception as e:
        print(f"[警告] 無法讀取資料庫: {e}")
        return []

def get_latest_db_date(code: str) -> Optional[str]:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT MAX(date) FROM weekly_data WHERE code=?", (code,))
        row = c.fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except:
        return None

# ============================================================================
# 網頁抓取 (神秘金字塔)
# ============================================================================
URL_TEMPLATE = "https://norway.twsthr.info/StockHolders.aspx?stock={code}"

def parse_norway_html(text: str) -> List[dict]:
    td_pat = re.compile(r'<td[^>]*>([^<]*?)</td>', re.IGNORECASE)
    tr_matches = list(re.finditer(r'<tr[^>]*>(.*?)</tr>', text, re.IGNORECASE | re.DOTALL))
    all_cells = []
    for tr in tr_matches:
        cells = td_pat.findall(tr.group(1))
        all_cells.extend([c.replace('&nbsp;', '').replace(',', '').strip() for c in cells])
    data = []
    i = 0
    while i < len(all_cells) - 12:
        if re.match(r'^\d{8}$', all_cells[i]):
            try:
                rd = all_cells[i]
                data.append({
                    'date': f"{rd[:4]}/{rd[4:6]}/{rd[6:8]}",
                    'raw_date': rd,
                    'total_shares': int(all_cells[i + 1]),
                    'holder_count': int(all_cells[i + 2]),
                    'avg_shares': float(all_cells[i + 3]),
                    'big_shares': int(all_cells[i + 4]),
                    'big_pct': float(all_cells[i + 5]),
                    'big_count': int(all_cells[i + 6]),
                    'cnt_400_600': int(all_cells[i + 7]),
                    'cnt_600_800': int(all_cells[i + 8]),
                    'cnt_800_1000': int(all_cells[i + 9]),
                    'cnt_over_1000': int(all_cells[i + 10]),
                    'ultra_pct': float(all_cells[i + 11]),
                    'price': float(all_cells[i + 12]),
                })
                i += 14
            except (ValueError, IndexError):
                i += 1
        else:
            i += 1
    data.reverse()
    return data

def fetch_stock_data(code: str, force: bool = False) -> List[dict]:
    code = code.strip().zfill(4)
    data = None
    
    if not force:
        latest = get_latest_db_date(code)
        if latest:
            try:
                age = (datetime.datetime.now() - datetime.datetime.strptime(latest, "%Y/%m/%d")).days
                if age <= 7:
                    print(f"[快取] {code} 大戶資料{age}天前取得")
                    data = load_from_db(code)
            except:
                pass
    
    if not data:
        print(f"[抓取] 從神秘金字塔抓取 {code} ...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(URL_TEMPLATE.format(code=code), headers=headers, timeout=20)
            text = resp.content.decode('utf-8')
        except Exception as e:
            print(f"[錯誤] 抓取失敗：{e}")
            db = load_from_db(code)
            if db:
                print(f"[備用] 使用本地快取{len(db)}筆")
            return db
        data = parse_norway_html(text)
        if not data:
            print(f"[警告] 未能解析到資料")
            db = load_from_db(code)
            return db if db else []
    
    original_price = data[-1]['price']
    yahoo_price, price_source, price_warning = fetch_yahoo_price(code)
    
    if yahoo_price:
        diff_pct = abs(yahoo_price - original_price) / original_price * 100 if original_price > 0 else 0
        data[-1]['price'] = yahoo_price
        data[-1]['_original_price'] = original_price
        data[-1]['_price_diff_pct'] = round(diff_pct, 2)
        data[-1]['_price_source'] = price_source or 'yahoo'
        data[-1]['_price_warning'] = price_warning or f'已更新 (差異 {diff_pct:.2f}%)'
        print(f'[即時價格] {code}: {original_price:.1f} → {yahoo_price:.1f} ({diff_pct:+.2f}%)')
    else:
        data[-1]['_price_source'] = 'norway'
        data[-1]['_price_warning'] = '⚠️ 無法取得 Yahoo 即時價格！使用每週收盤價'
    
    save_to_db(code, data)
    print(f"[完成] {code} 共 {len(data)} 週資料，現價={data[-1]['price']:.1f}")
    return data

def fetch_yahoo_price(code: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    yahoo_price = None
    source = None
    warning = None
    
    for suffix in ['.TW', '.TWO']:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}{suffix}?interval=1d&range=1d"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, headers=headers, timeout=10, verify=True)
            if resp.status_code == 200:
                data = resp.json()
                result = data.get('chart', {}).get('result', [None])[0]
                if result and 'meta' in result:
                    price = result['meta'].get('regularMarketPrice') or result['meta'].get('previousClose')
                    if price and price > 0:
                        yahoo_price = round(float(price), 1)
                        source = 'yahoo-v8'
                        print(f'[價格] {code}{suffix} v8 API = {yahoo_price}')
                        break
        except Exception as e:
            print(f'[價格] {code}{suffix} v8 API 失敗: {e}')
            continue
    
    if not yahoo_price:
        try:
            import yfinance as yf
            for suffix in ['.TW', '.TWO']:
                try:
                    t = yf.Ticker(f'{code}{suffix}')
                    h = t.history(period='1d')
                    if len(h) > 0:
                        yahoo_price = round(float(h['Close'].iloc[-1]), 1)
                        source = 'yahoo-yf'
                        print(f'[價格] {code}{suffix} yfinance = {yahoo_price}')
                        break
                except:
                    continue
        except:
            pass
    
    if not yahoo_price:
        try:
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{code}.tw&json=1&delay=0"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('msgArray') and len(data['msgArray']) > 0:
                    price_str = data['msgArray'][0].get('z') or data['msgArray'][0].get('y')
                    if price_str and price_str != '-':
                        yahoo_price = round(float(price_str), 1)
                        source = 'twse'
                        print(f'[價格] {code} TWSE = {yahoo_price}')
        except Exception as e:
            print(f'[價格] {code} TWSE 失敗: {e}')
    
    if not yahoo_price:
        warning = '⚠️ 所有價格來源均失敗！'
        print(f'[嚴重] {code}: Yahoo v8 / yfinance / TWSE 全部失敗！')
    
    return yahoo_price, source, warning

# ============================================================================
# 日K VWAP 計算
# ============================================================================
def _fetch_daily_yf(code: str, start_str: str, end_str: str) -> List[dict]:
    try:
        import yfinance as yf
        df = None
        for suffix in ['.TW', '.TWO']:
            try:
                ticker = yf.Ticker(f"{code}{suffix}")
                df = ticker.history(start=start_str, end=end_str, auto_adjust=True)
                if not df.empty:
                    break
            except:
                continue
        if df is None or df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            dt = idx.tz_localize(None).replace(tzinfo=None).strftime('%Y-%m-%d')
            rows.append({
                'date': dt,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume']),
            })
        return rows
    except:
        return []

def _weekly_vwap(daily_rows: List[dict]) -> float:
    if not daily_rows:
        return 0.0
    total_pv = 0.0
    total_vol = 0
    for d in daily_rows:
        tp = (d['high'] + d['low'] + d['close']) / 3.0
        total_pv += tp * d['volume']
        total_vol += d['volume']
    return total_pv / total_vol if total_vol > 0 else (daily_rows[-1]['close'] if daily_rows else 0.0)

def calc_daily_vwap_map(code: str, seg: List[dict]) -> Tuple[Dict, Dict, Dict]:
    if not seg:
        return {}, {}, {}
    from datetime import timedelta as _td
    dates = [datetime.datetime.strptime(d['date'].replace('/', '-'), '%Y-%m-%d') for d in seg]
    sd = min(dates) - _td(days=3)
    ed = max(dates) + _td(days=3)
    daily = _fetch_daily_yf(code, sd.strftime('%Y-%m-%d'), ed.strftime('%Y-%m-%d'))
    if not daily:
        return {}, {}, {}
    
    daily_map = {r['date']: r for r in daily}
    vwap_map = {}
    high_map = {}
    low_map = {}
    
    for d in seg:
        wd = datetime.datetime.strptime(d['date'].replace('/', '-'), '%Y-%m-%d')
        monday = wd - _td(days=wd.weekday())
        friday = monday + _td(days=4)
        week_days = []
        cur = monday
        while cur <= friday:
            date_str = cur.strftime('%Y-%m-%d')
            if date_str in daily_map:
                week_days.append(daily_map[date_str])
            cur += _td(days=1)
        
        if week_days:
            vwap_map[d['date']] = _weekly_vwap(week_days)
            high_map[d['date']] = max(day['high'] for day in week_days)
            low_map[d['date']] = min(day['low'] for day in week_days)
        else:
            p = d.get('price', 0)
            vwap_map[d['date']] = p
            high_map[d['date']] = p
            low_map[d['date']] = p
    
    return vwap_map, high_map, low_map

# ============================================================================
# 法人買賣超（D法用）
# ============================================================================
def fetch_foreign_trade(code, days=30):
    """抓取三大法人逐日買賣超（TWSE + TPEx 雙源）"""
    result = []
    
    is_otc = code.startswith('0') or code.startswith('2') or code.startswith('5') or code.startswith('6') or code.startswith('7') or code.startswith('8')
    
    if is_otc:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept': 'application/json',
                'Referer': 'https://www.tpex.org.tw/',
            }
            url = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
            
            end_date = datetime.date.today()
            check_days = min(days + 10, 30)
            result = []
            
            for i in range(check_days):
                d = end_date - datetime.timedelta(days=i)
                roc_year = d.year - 1911
                roc_date = f"{roc_year}/{d.month:02d}/{d.day:02d}"
                
                params = {'l': 'zh-tw', 'o': 'json', 'd': roc_date, 'stkno': code}
                try:
                    resp = requests.get(url, params=params, headers=headers, timeout=10)
                    text = resp.content.decode('utf-8', errors='replace')
                    j = json.loads(text)
                    
                    tables = j.get('tables', [])
                    if tables and tables[0].get('data'):
                        for row in tables[0]['data']:
                            if row[0] == code:
                                try:
                                    fii_net = int(row[4].replace(',', ''))
                                    sitc_net = int(row[7].replace(',', ''))
                                    dealer_net = int(row[10].replace(',', ''))
                                    total_net = int(row[-1].replace(',', ''))
                                    
                                    result.append({
                                        'date': d.strftime('%Y/%m/%d'),
                                        'fii_net': fii_net,
                                        'sitc_net': sitc_net,
                                        'dealer_net': dealer_net,
                                        'total_net': total_net,
                                    })
                                except (ValueError, IndexError):
                                    pass
                                break
                except:
                    continue
                
                if len(result) >= days:
                    break
            
            if result:
                result.sort(key=lambda x: x['date'])
                return result
        except Exception:
            pass
    
    # TWSE 上市 API
    try:
        url = f"https://www.twse.com.tw/exchangeReport/TWT74U"
        params = {
            'response': 'json',
            'stockNo': code,
            'type': 'day'
        }
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        j = resp.json()
        if j.get('stat') == 'OK' and j.get('data'):
            rows = j['data']
            for r in rows:
                try:
                    parts = r[0].split('/')
                    if len(parts) == 3 and int(parts[0]) < 200:
                        date_str = f"{int(parts[0])+1911}/{parts[1]}/{parts[2]}"
                    else:
                        date_str = r[0]
                    fii_net = int(r[3].replace(',', ''))
                    sitc_net = int(r[6].replace(',', ''))
                    dealer_net = int(r[9].replace(',', ''))
                    total_net = fii_net + sitc_net + dealer_net
                    result.append({
                        'date': date_str,
                        'fii_net': fii_net,
                        'sitc_net': sitc_net,
                        'dealer_net': dealer_net,
                        'total_net': total_net,
                    })
                except (ValueError, IndexError):
                    continue
            if result:
                return result
    except Exception:
        pass
    
    return []

# ============================================================================
# 成本計算 - v1.3: A法 + D法
# ============================================================================
def calc_d_cost(data, start_idx, end_idx, code=None):
    """D法：主力精算成本
    回傳 dict: {'cost': float, 'new_shares': float, 'inst_net': int, 'big_only': float, 'detail': list}
    """
    seg = data[start_idx:end_idx+1]
    if len(seg) < 1 or not code:
        return None
    
    if start_idx <= 0:
        return None
    
    prev = data[start_idx - 1]
    last = seg[-1]
    
    big_chg = last['big_pct'] - prev['big_pct']
    
    if big_chg <= 0:
        return None
    
    new_shares = big_chg / 100 * last['total_shares']
    
    from datetime import timedelta as _td
    try:
        ed = datetime.datetime.strptime(last['date'].replace('/', '-'), '%Y-%m-%d')
        sd = datetime.datetime.strptime(prev['date'].replace('/', '-'), '%Y-%m-%d')
        sd_fetch = (sd - _td(days=3)).strftime('%Y-%m-%d')
        ed_fetch = (ed + _td(days=3)).strftime('%Y-%m-%d')
    except:
        return None
    
    daily = _fetch_daily_yf(code, sd_fetch, ed_fetch)
    if not daily or len(daily) < 2:
        return None
    
    prev_date_str = prev['date'].replace('/', '-')
    trading_days = [d for d in daily if d['date'] > prev_date_str]
    
    if not trading_days:
        return None
    
    total_vol = sum(d['volume'] for d in trading_days)
    if total_vol <= 0:
        return None
    
    inst_net_total = 0
    inst_net_map = {}
    try:
        inst_data = fetch_foreign_trade(code, days=(end_idx - start_idx + 1) * 7)
        if inst_data:
            for fd in inst_data:
                fd_date = fd['date'].replace('/', '-')
                net = fd.get('total_net', 0)
                inst_net_map[fd_date] = net
                if fd_date > prev_date_str and fd_date <= last['date'].replace('/', '-'):
                    inst_net_total += net
    except:
        pass
    
    big_only_shares = new_shares - inst_net_total / 1000
    
    if big_only_shares <= 0:
        return None
    
    # 按每日「非法人成交量」比例分配大戶吃貨量
    non_inst_vols = []
    for d in trading_days:
        inst_net = inst_net_map.get(d['date'], 0)
        ni_vol = max(d['volume'] - abs(inst_net), 0)
        non_inst_vols.append(ni_vol)
    
    non_inst_total = sum(non_inst_vols)
    
    if non_inst_total <= 0:
        non_inst_vols = [d['volume'] for d in trading_days]
        non_inst_total = total_vol
    
    d_wsum = 0
    detail = []
    for i, d in enumerate(trading_days):
        vol_ratio = non_inst_vols[i] / non_inst_total
        day_shares = big_only_shares * vol_ratio
        tp = (d['high'] + d['low'] + d['close']) / 3
        d_wsum += tp * day_shares
        inst_net = inst_net_map.get(d['date'], 0)
        detail.append({
            'date': d['date'],
            'vol': d['volume'],
            'non_inst_vol': non_inst_vols[i],
            'tp': round(tp, 1),
            'inst_net': inst_net,
            'big_shares': round(day_shares, 0),
        })
    
    d_cost = d_wsum / big_only_shares
    
    return {
        'cost': round(d_cost, 2),
        'new_shares': round(new_shares, 0),
        'inst_net': inst_net_total,
        'big_only': round(big_only_shares, 0),
        'detail': detail,
    }

def calc_costs(data: List[dict], start_idx: int, end_idx: int, code: Optional[str] = None) -> Dict:
    """v1.3: A法 + D法"""
    seg = data[start_idx:end_idx + 1]
    
    vwap_map = {}
    if code:
        vwap_map, _, _ = calc_daily_vwap_map(code, seg)
    
    # A法：加權均價（使用 VWAP）
    ws = 0
    ww = 0
    for i in range(len(seg)):
        price = vwap_map.get(seg[i]['date'], seg[i]['price'])
        if i == 0:
            ws += price * abs(seg[i]['big_pct'])
            ww += abs(seg[i]['big_pct'])
        else:
            chg = seg[i]['big_pct'] - seg[i - 1]['big_pct']
            if chg > 0:
                ws += price * chg
                ww += chg
    cost_a = ws / ww if ww > 0 else (sum(d['price'] for d in seg) / len(seg) if seg else None)
    
    # D法：主力精算成本
    d_result = calc_d_cost(data, start_idx, end_idx, code=code)
    cost_d = d_result['cost'] if isinstance(d_result, dict) else d_result
    
    result = {
        'a': round(cost_a, 2) if cost_a else None,
        'd': cost_d,
    }
    
    if isinstance(d_result, dict) and 'detail' in d_result:
        result['d_detail'] = d_result
    
    return result

# ============================================================================
# 指標計算
# ============================================================================
def calc_momentum(data: List[dict]) -> List[dict]:
    result = []
    for i in range(len(data)):
        if i == 0:
            result.append({'date': data[i]['date'], 'big': 0, 'ultra': 0})
        else:
            result.append({
                'date': data[i]['date'],
                'big': round(data[i]['big_pct'] - data[i - 1]['big_pct'], 2),
                'ultra': round(data[i]['ultra_pct'] - data[i - 1]['ultra_pct'], 2),
            })
    return result

def calc_concentration(data: List[dict]) -> List[dict]:
    return [{
        'date': d['date'],
        'conc': round(d['cnt_over_1000'] / d['big_count'] * 100, 2) if d['big_count'] > 0 else 0
    } for d in data]

# ============================================================================
# LINE 摘要生成 - v1.3: A+D法
# ============================================================================
def line_summary(code: str, name: str, data: List[dict], costs: Dict, price: float) -> str:
    if not data:
        return ""
    d = data[-1]
    p = data[-2] if len(data) >= 2 else d
    bc = d['big_pct'] - p['big_pct']
    uc = d['ultra_pct'] - p['ultra_pct']
    be = "+" if bc > 0 else "-" if bc < 0 else "="
    ue = "+" if uc > 0 else "-" if uc < 0 else "="
    conc = d['cnt_over_1000'] / d['big_count'] * 100 if d['big_count'] > 0 else 0
    
    if bc > 0.5:
        big_comment = "大戶明顯加碼"
    elif bc > 0:
        big_comment = "大戶微加"
    elif bc > -0.5:
        big_comment = "大戶微減"
    else:
        big_comment = "大戶明顯減碼"
    
    lines = [
        f"{name}({code}) 大戶成本分析",
        "",
        f"最新: {d['date']}",
        f"收盤: {price:.1f}元",
        f"大戶(>400張): {d['big_pct']:.2f}% {be}{abs(bc):.2f}% {big_comment}",
        f"超大戶(>1K張): {d['ultra_pct']:.2f}% {ue}{abs(uc):.2f}%",
        f"集中度: {conc:.1f}%",
    ]
    
    if costs:
        lines += ["", "大戶成本:"]
        if costs.get('a'):
            da = (price - costs['a']) / costs['a'] * 100
            lines.append(f"  A法(均價): {costs['a']:.2f}元 (浮盈{da:+.1f}%)")
        if costs.get('d'):
            dd = (price - costs['d']) / costs['d'] * 100
            lines.append(f"  D法(主力精算): {costs['d']:.2f}元 (浮盈{dd:+.1f}%)")
        
        # D法詳細
        d_detail = costs.get('d_detail', {})
        if d_detail:
            new_sh = d_detail.get('new_shares', 0)
            inst_net = d_detail.get('inst_net', 0)
            big_only = d_detail.get('big_only', 0)
            lines.append(f"  大戶新增: {new_sh:,.0f}張 | 法人淨買: {inst_net/1000:+,.0f}張 | 純大戶: {big_only:,.0f}張")
            
            for dd_item in d_detail.get('detail', []):
                inst_n = dd_item.get('inst_net', 0)
                inst_str = f" 法人{inst_n/1000:+,.0f}張" if inst_n != 0 else ""
                lines.append(f"    {dd_item['date']}: TP={dd_item['tp']:.1f} 吃貨{dd_item['big_shares']:.0f}張{inst_str}")
        
        if costs.get('a') and costs.get('d'):
            spread = costs['a'] - costs['d']
            if spread > 1:
                lines.append(f"  比A法低{spread:.2f}元 → 主力買在低檔")
            elif spread < -1:
                lines.append(f"  比A法高{abs(spread):.2f}元 → 主力追高進場")
            else:
                lines.append(f"  與A法接近，主力成本=市場均價")
    
    # 操作建議
    if costs and costs.get('a'):
        da = (price - costs['a']) / costs['a'] * 100
        lines += ["", "操作建議:"]
        if da < 0 and bc > 0:
            lines.append("  股價低於成本+大戶加碼=可考慮進場")
        elif da < 10 and bc > 0:
            lines.append("  成本附近+大戶加碼=可小量進場")
        elif bc < 0:
            lines.append("  大戶減碼中，觀望為宜")
        elif da > 30:
            lines.append(f"  已漲{da:.0f}%，不追高")
        else:
            lines.append("  觀望，等大戶方向明確")
    
    return "\n".join(lines)

# ============================================================================
# 快速價格查詢
# ============================================================================
def get_quick_price(code: str) -> Dict:
    code = code.strip().zfill(4)
    price, source, warning = fetch_yahoo_price(code)
    name = get_stock_name(code)
    return {
        'code': code,
        'name': name,
        'price': price,
        'source': source,
        'warning': warning,
        'success': price is not None
    }

# ============================================================================
# 監測清單
# ============================================================================
DEFAULT_WATCHLIST = {
    "持倉": [
        {"code": "2327", "name": "國巨", "cost": 332.5, "shares": 5},
        {"code": "6182", "name": "合晶", "cost": 90.9, "shares": 10},
        {"code": "6213", "name": "聯茂", "cost": 276.25, "shares": 10},
    ],
    "觀察": [
        {"code": "2303", "name": "聯電"},
        {"code": "2890", "name": "永豐金"},
        {"code": "2337", "name": "旺宏"},
        {"code": "6770", "name": "力積電"},
        {"code": "2356", "name": "英業達"},
        {"code": "6282", "name": "康舒"},
    ]
}

def load_watchlist() -> Dict:
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_WATCHLIST

def save_watchlist(watchlist: Dict):
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    with open(WATCHLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)
