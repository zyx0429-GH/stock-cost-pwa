"""測試 v1.4 D 法"""
import sys
sys.path.insert(0, r'C:\Users\user\.qclaw\workspace\stock-app')
from core import fetch_stock_data, calc_d_cost, calc_costs

code = '6207'
data = fetch_stock_data(code, force=False)
end_idx = len(data) - 1
start_idx = end_idx - 2

print('=== v1.4 D 法測試 ===')
d = calc_d_cost(data, start_idx, end_idx, code=code)
print(f'D 法結果: {d}')

print('\n=== calc_costs 完整結果 ===')
c = calc_costs(data, start_idx, end_idx, code=code)
print(f'costs: {c}')
