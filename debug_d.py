"""D 法診斷 - 找出哪個 guard 觸發"""
import sys
import datetime
sys.path.insert(0, r'C:\Users\user\.qclaw\workspace\stock-app')
from core import fetch_stock_data, fetch_foreign_trade, _fetch_daily_yf
from datetime import timedelta

code = '6207'
data = fetch_stock_data(code, force=False)
print(f'total weeks: {len(data)}')
end_idx = len(data) - 1
start_idx = end_idx - 2
seg = data[start_idx:end_idx+1]
prev = data[start_idx-1]
last = seg[-1]

print(f'\n=== 區間 ===')
print(f'prev: {prev["date"]}  big_pct={prev["big_pct"]:.2f}  price={prev["price"]}')
print(f'last: {last["date"]}  big_pct={last["big_pct"]:.2f}  price={last["price"]}  total_shares={last["total_shares"]}')

big_chg = last['big_pct'] - prev['big_pct']
new_shares = big_chg / 100 * last['total_shares']
print(f'\n大戶持股%變動: {big_chg:+.4f}%')
print(f'大戶新增張數: {new_shares:,.0f}')

print(f'\n=== 法人資料 ===')
inst_data = fetch_foreign_trade(code, days=21)
print(f'法人資料筆數: {len(inst_data) if inst_data else 0}')
prev_d = prev['date'].replace('/', '-')
last_d = last['date'].replace('/', '-')
inst_net_total = 0
if inst_data:
    for fd in inst_data:
        fd_date = fd['date'].replace('/', '-')
        net = fd.get('total_net', 0)
        in_range = prev_d < fd_date <= last_d
        marker = '→' if in_range else ' '
        if in_range:
            inst_net_total += net
        print(f'  {marker} {fd_date}  net={net:>10,}')
print(f'\n區間內法人淨買超: {inst_net_total:,.0f} 張')

big_only = new_shares - inst_net_total / 1000
print(f'純大戶吃貨: {new_shares:,.0f} - {inst_net_total/1000:,.0f} = {big_only:,.0f}')

print(f'\n=== 日K 資料 ===')
ed = datetime.datetime.strptime(last_d, '%Y-%m-%d')
sd = datetime.datetime.strptime(prev_d, '%Y-%m-%d')
sd_fetch = (sd - timedelta(days=3)).strftime('%Y-%m-%d')
ed_fetch = (ed + timedelta(days=3)).strftime('%Y-%m-%d')
print(f'fetch range: {sd_fetch} ~ {ed_fetch}')
daily = _fetch_daily_yf(code, sd_fetch, ed_fetch)
print(f'daily len: {len(daily) if daily else 0}')
if daily:
    for d in daily:
        print(f'  {d["date"]}  O={d.get("open")} H={d.get("high")} L={d.get("low")} C={d.get("close")} V={d.get("volume"):,}')
