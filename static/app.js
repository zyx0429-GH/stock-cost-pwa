/*  ============================================================================
    大戶成本查詢工具 - 前端核心邏輯 v1.3.3
   ============================================================================ */

// ============================================================================
// 全域變數
// ============================================================================
let currentTab = 'analyze';  // 當前頁籤
let currentChart = null;      // Chart.js 實例
let analysisResult = null;    // 最新分析結果
let isAnalyzing = false;      // 防止重複點擊

// ============================================================================
// 初始化
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('📊 大戶成本查詢工具 PWA 版啟動 v1.3.3');
    
    // 強制清除所有 loading 狀態
    forceClearLoading();
    
    // 註冊 Service Worker
    registerServiceWorker();
    
    // 綁定事件
    bindEvents();
    
    // 載入監測清單（不阻塞）
    loadWatchlist();
});

// 強制清除 loading（防止快取殘留）
function forceClearLoading() {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.classList.remove('active');
        loading.style.display = 'none';
    }
    const btn = document.getElementById('analyzeBtn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = '📊 開始分析';
    }
    isAnalyzing = false;
}

// ============================================================================
// Service Worker 註冊
// ============================================================================
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('✅ SW 註冊成功:', reg.scope))
            .catch(err => console.log('❌ SW 註冊失敗:', err));
    }
}

// ============================================================================
// 事件綁定
// ============================================================================
function bindEvents() {
    // 分析按鈕
    const analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', () => analyzeStock());
    }
    
    // 輸入框 Enter 鍵
    const codeInput = document.getElementById('codeInput');
    if (codeInput) {
        codeInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') analyzeStock();
        });
    }
    
    // 底部導航
    document.querySelectorAll('.tab-item').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
}

// ============================================================================
// 頁籤切換
// ============================================================================
function switchTab(tabName) {
    currentTab = tabName;
    
    // 更新底部導航樣式
    document.querySelectorAll('.tab-item').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
    
    // 顯示對應內容
    document.querySelectorAll('.page').forEach(page => {
        page.classList.toggle('hidden', page.id !== `${tabName}Page`);
    });
    
    // 載入資料
    if (tabName === 'watchlist') {
        loadWatchlist();
    }
}

// ============================================================================
// 股票分析
// ============================================================================
async function analyzeStock() {
    if (isAnalyzing) return;  // 防重複點擊
    
    const codeInput = document.getElementById('codeInput');
    const weeksInput = document.getElementById('weeksInput');
    const code = codeInput.value.trim();
    const weeks = parseInt(weeksInput.value) || 1;
    
    // 驗證輸入
    if (!code) {
        showError('請輸入股票代號');
        return;
    }
    
    // 格式化代號（4位數補零）
    const formattedCode = code.padStart(4, '0');
    codeInput.value = formattedCode;
    
    // 顯示載入動畫
    isAnalyzing = true;
    showLoading(true);
    hideError();
    
    // 設定超時（45秒）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
        controller.abort();
    }, 45000);
    
    // 進度更新（5秒後提示冷啟動）
    const progressTimer = setTimeout(() => {
        const loadingText = document.querySelector('#loading p');
        if (loadingText) {
            loadingText.textContent = '伺服器冷啟動中，請耐心等候...';
        }
    }, 5000);
    
    // 第二段進度（15秒）
    const progressTimer2 = setTimeout(() => {
        const loadingText = document.querySelector('#loading p');
        if (loadingText) {
            loadingText.textContent = '仍在計算中，即將完成...';
        }
    }, 15000);
    
    try {
        // 呼叫 API
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: formattedCode, weeks }),
            signal: controller.signal
        });
        
        const result = await response.json();
        
        if (!response.ok || !result.success) {
            throw new Error(result.detail || '分析失敗');
        }
        
        // 儲存結果
        analysisResult = result;
        
        // 顯示結果
        displayAnalysisResult(result);
        
    } catch (error) {
        console.error('分析錯誤:', error);
        if (error.name === 'AbortError') {
            showError('分析超時（45秒），伺服器可能冷啟動中，請再試一次');
        } else {
            showError(error.message || '分析失敗，請稍後再試');
        }
    } finally {
        clearTimeout(timeoutId);
        clearTimeout(progressTimer);
        clearTimeout(progressTimer2);
        isAnalyzing = false;
        hideLoading();
        // 重置進度文字
        const loadingText = document.querySelector('#loading p');
        if (loadingText) {
            loadingText.textContent = '正在抓取資料並計算成本，請稍候...';
        }
    }
}

// ============================================================================
// 顯示分析結果
// ============================================================================
function displayAnalysisResult(result) {
    // 顯示結果區域
    const resultDiv = document.getElementById('analysisResult');
    resultDiv.classList.remove('hidden');
    
    // 更新股票資訊
    document.getElementById('stockTitle').textContent = `${result.name}(${result.code})`;
    document.getElementById('stockPrice').textContent = `現價: ${result.price.toFixed(1)}元`;
    document.getElementById('weekLabel').textContent = `區間: 最近${result.weeks}週`;
    
    // 顯示成本
    displayCosts(result.costs, result.price);
    
    // 顯示指標
    displayIndicators(result.indicators);
    
    // 顯示圖表
    displayChart(result.chart_data);
    
    // 顯示每週明細
    displayDetailTable(result.detail_weeks, result.costs);
    
    // 顯示 LINE 摘要
    document.getElementById('lineSummary').textContent = result.summary;
    
    // 滾動到結果區域
    resultDiv.scrollIntoView({ behavior: 'smooth' });
}

// ============================================================================
// 顯示成本
// ============================================================================
function displayCosts(costs, price) {
    const container = document.getElementById('costGrid');
    container.innerHTML = '';
    
    // A法
    if (costs.a) {
        const profit = ((price - costs.a) / costs.a * 100).toFixed(1);
        container.innerHTML += `
            <div class="cost-item">
                <div class="label">📐 A法 (全市場均價)</div>
                <div class="value">${costs.a.toFixed(2)}</div>
                <div class="profit ${profit >= 0 ? 'profit-up' : 'profit-down'}">
                    ${profit >= 0 ? '+' : ''}${profit}%
                </div>
            </div>
        `;
    }
    
    // D法
    if (costs.d) {
        const profit = ((price - costs.d) / costs.d * 100).toFixed(1);
        container.innerHTML += `
            <div class="cost-item">
                <div class="label">🎯 D法 (主力精算)</div>
                <div class="value">${costs.d.toFixed(2)}</div>
                <div class="profit ${profit >= 0 ? 'profit-up' : 'profit-down'}">
                    ${profit >= 0 ? '+' : ''}${profit}%
                </div>
            </div>
        `;
        
        // D法詳細資訊
        const dDetail = costs.d_detail;
        if (dDetail) {
            const newShares = dDetail.new_shares || 0;
            const instNet = dDetail.inst_net || 0;
            const bigOnly = dDetail.big_only || 0;
            
            let detailHtml = `
                <div class="d-detail">
                    <div class="d-summary">
                        <span>大戶新增: ${Number(newShares).toLocaleString()}張</span>
                        <span>法人: ${instNet >= 0 ? '+' : ''}${(instNet/1000).toFixed(0)}張</span>
                        <span>純大戶: ${Number(bigOnly).toLocaleString()}張</span>
                    </div>
            `;
            
            if (dDetail.detail && dDetail.detail.length > 0) {
                detailHtml += '<div class="d-daily">';
                for (const day of dDetail.detail) {
                    const instStr = day.inst_net !== 0 ? ` 法人${day.inst_net >= 0 ? '+' : ''}${(day.inst_net/1000).toFixed(0)}張` : '';
                    detailHtml += `
                        <div class="d-day">
                            <span class="d-date">${day.date}</span>
                            <span>TP=${day.tp}</span>
                            <span>吃貨${day.big_shares}張</span>
                            <span class="inst-net">${instStr}</span>
                        </div>
                    `;
                }
                detailHtml += '</div>';
            }
            
            detailHtml += '</div>';
            container.innerHTML += detailHtml;
        }
    }
    
    // A/D 比較
    if (costs.a && costs.d) {
        const spread = (costs.a - costs.d).toFixed(2);
        let compareText = '';
        if (spread > 1) {
            compareText = `D法比A法低${spread}元 → 主力買在低檔`;
        } else if (spread < -1) {
            compareText = `D法比A法高${Math.abs(spread)}元 → 主力追高進場`;
        } else {
            compareText = 'A/D接近，主力成本≈市場均價';
        }
        container.innerHTML += `
            <div class="cost-compare">
                ${compareText}
            </div>
        `;
    }
}

// ============================================================================
// 顯示指標
// ============================================================================
function displayIndicators(indicators) {
    const list = document.getElementById('indicatorList');
    list.innerHTML = '';
    indicators.forEach(ind => {
        const li = document.createElement('li');
        li.textContent = ind;
        list.appendChild(li);
    });
}

// ============================================================================
// 顯示圖表 (Chart.js)
// ============================================================================
function displayChart(chartData) {
    const ctx = document.getElementById('priceChart');
    if (!ctx) return;
    
    // 銷毀舊圖表
    if (currentChart) {
        currentChart.destroy();
    }
    
    // 建立新圖表
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.dates,
            datasets: [
                {
                    label: '收盤價',
                    data: chartData.prices,
                    borderColor: '#00d2ff',
                    backgroundColor: 'rgba(0, 210, 255, 0.1)',
                    borderWidth: 2,
                    yAxisID: 'y',
                    tension: 0.3
                },
                {
                    label: '>400張%',
                    data: chartData.big_pct,
                    borderColor: '#ff6384',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    borderWidth: 2,
                    yAxisID: 'y1',
                    tension: 0.3
                },
                {
                    label: '>1000張%',
                    data: chartData.ultra_pct,
                    borderColor: '#ffa500',
                    backgroundColor: 'rgba(255, 165, 0, 0.1)',
                    borderWidth: 2,
                    yAxisID: 'y1',
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#e0e0e0'
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#b0b0b0' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: { color: '#00d2ff' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: { color: '#ff6384' },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });
}

// ============================================================================
// 顯示每週明細表格
// ============================================================================
function displayDetailTable(detailWeeks, costs) {
    const tbody = document.getElementById('detailTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    // 只顯示最近20週
    const recentWeeks = detailWeeks.slice(-20);
    
    recentWeeks.forEach(week => {
        const row = document.createElement('tr');
        
        // 大戶%變動樣式
        const bigChgClass = week.big_pct_chg > 0 ? 'up' : week.big_pct_chg < 0 ? 'down' : '';
        const bigChgText = week.big_pct_chg !== null 
            ? `<span class="${bigChgClass}">${week.big_pct_chg >= 0 ? '+' : ''}${week.big_pct_chg.toFixed(2)}%</span>`
            : '-';
        
        // 超大戶%變動樣式
        const ultraChgClass = week.ultra_pct_chg > 0 ? 'up' : week.ultra_pct_chg < 0 ? 'down' : '';
        const ultraChgText = week.ultra_pct_chg !== null
            ? `<span class="${ultraChgClass}">${week.ultra_pct_chg >= 0 ? '+' : ''}${week.ultra_pct_chg.toFixed(2)}%</span>`
            : '-';
        
        row.innerHTML = `
            <td>${week.date}</td>
            <td>${week.big_pct.toFixed(2)}% ${bigChgText}</td>
            <td>${week.ultra_pct.toFixed(2)}% ${ultraChgText}</td>
            <td>${week.conc.toFixed(1)}%</td>
            <td>${week.price.toFixed(1)}</td>
        `;
        
        tbody.appendChild(row);
    });
}

// ============================================================================
// 複製 LINE 摘要
// ============================================================================
function copyLineSummary() {
    const summary = document.getElementById('lineSummary').textContent;
    
    if (!summary) {
        alert('請先分析股票');
        return;
    }
    
    // 使用 Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(summary)
            .then(() => {
                showCopySuccess();
            })
            .catch(err => {
                console.error('複製失敗:', err);
                fallbackCopy(summary);
            });
    } else {
        // 降級方案
        fallbackCopy(summary);
    }
}

function fallbackCopy(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    
    try {
        const success = document.execCommand('copy');
        if (success) {
            showCopySuccess();
        } else {
            alert('複製失敗，請手動複製');
        }
    } catch (err) {
        console.error('複製失敗:', err);
        alert('複製失敗，請手動複製');
    }
    
    document.body.removeChild(textarea);
}

function showCopySuccess() {
    const btn = document.getElementById('copyBtn');
    if (btn) {
        const originalText = btn.textContent;
        btn.textContent = '✅ 已複製！';
        btn.style.background = '#00e676';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '';
        }, 2000);
    }
}

// ============================================================================
// 監測清單
// ============================================================================
async function loadWatchlist() {
    try {
        const response = await fetch('/api/watchlist');
        const result = await response.json();
        
        if (!response.ok || !result.success) {
            throw new Error('載入失敗');
        }
        
        displayWatchlist(result.watchlist);
        
    } catch (error) {
        console.error('載入監測清單失敗:', error);
        showError('載入監測清單失敗');
    }
}

function displayWatchlist(watchlist) {
    const container = document.getElementById('watchlistContent');
    if (!container) return;
    
    container.innerHTML = '';
    
    // 建立頁籤
    const tabsDiv = document.createElement('div');
    tabsDiv.className = 'watchlist-tabs';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'watchlist-items';
    
    let isFirst = true;
    
    for (const [category, items] of Object.entries(watchlist)) {
        // 頁籤按鈕
        const tabBtn = document.createElement('button');
        tabBtn.className = `watchlist-tab ${isFirst ? 'active' : ''}`;
        tabBtn.textContent = `${category} (${items.length})`;
        tabBtn.dataset.category = category;
        tabBtn.addEventListener('click', () => {
            document.querySelectorAll('.watchlist-tab').forEach(t => t.classList.remove('active'));
            tabBtn.classList.add('active');
            displayWatchlistCategory(items);
        });
        tabsDiv.appendChild(tabBtn);
        
        // 第一次載入顯示第一個類別
        if (isFirst) {
            displayWatchlistCategory(items);
            isFirst = false;
        }
    }
    
    container.appendChild(tabsDiv);
    container.appendChild(contentDiv);
}

function displayWatchlistCategory(items) {
    const container = document.querySelector('.watchlist-items');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (items.length === 0) {
        container.innerHTML = '<div class="text-center text-secondary">此類別尚無項目</div>';
        return;
    }
    
    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'watchlist-item';
        div.innerHTML = `
            <div class="info">
                <div class="code">${item.code} ${item.name || ''}</div>
                ${item.cost ? `<div class="text-sm text-secondary">成本: ${item.cost}元 / ${item.shares || 0}張</div>` : ''}
            </div>
            <button class="remove-btn" onclick="removeFromWatchlist('${item.code}')">移除</button>
        `;
        
        // 點擊查詢
        div.addEventListener('click', (e) => {
            if (!e.target.classList.contains('remove-btn')) {
                document.getElementById('codeInput').value = item.code;
                switchTab('analyze');
                analyzeStock();
            }
        });
        
        container.appendChild(div);
    });
}

async function removeFromWatchlist(code) {
    if (!confirm(`確定要移除 ${code} 嗎？`)) return;
    
    try {
        const response = await fetch('/api/watchlist/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: '觀察', code })
        });
        
        const result = await response.json();
        
        if (!response.ok || !result.success) {
            throw new Error(result.detail || '移除失敗');
        }
        
        // 重新載入
        loadWatchlist();
        
    } catch (error) {
        console.error('移除失敗:', error);
        alert('移除失敗');
    }
}

// ============================================================================
// 工具函式
// ============================================================================
// ============================================================================
// 工具函式
// ============================================================================
function showLoading(show) {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.classList.toggle('active', show);
    }
    
    const btn = document.getElementById('analyzeBtn');
    if (btn) {
        btn.disabled = show;
        btn.textContent = show ? '分析中...' : '分析';
    }
}

// 強制清除所有 loading 狀態（防快取殘留 + Service Worker 亂序）
function forceClearLoading() {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.classList.remove('active');
        loading.style.display = 'none';
    }
    const btn = document.getElementById('analyzeBtn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = '📊 開始分析';
    }
    isAnalyzing = false;
    console.log('✅ Loading 狀態已強制清除');
}

// 關閉載入動畫
function hideLoading() {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.classList.remove('active');
    }
    const btn = document.getElementById('analyzeBtn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = '📊 開始分析';
    }
    isAnalyzing = false;
}

// （超時已改用 AbortController，此段保留為空）

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }
}

function hideError() {
    const errorDiv = document.getElementById('errorMessage');
    if (errorDiv) {
        errorDiv.classList.add('hidden');
    }
}

// ============================================================================
// 頁面可見性：切回頁面時清除殘留 loading
// ============================================================================
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && !isAnalyzing) {
        forceClearLoading();
    }
});

// ============================================================================
// 匯出函式供 HTML 使用
// ============================================================================
window.analyzeStock = analyzeStock;
window.copyLineSummary = copyLineSummary;
window.switchTab = switchTab;
