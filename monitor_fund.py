import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import html

# 強制設定標準輸出編碼為 utf-8，解決 Windows 終端機 Emoji 顯示問題
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python 3.6 以下備用方案
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# =================配置區=================
FUND_URL = "https://www.ezmoney.com.tw/ETF/Fund/Info?FundCode=49YTW"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
STATE_FILE = "last_holdings.json"
MAX_ITEMS = 999 # 抓取全部持股
# ========================================

def get_holdings():
    """抓取網頁持股資料"""
    # 忽略 SSL 憑證警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        print(f"📡 正在從基金主頁抓取底層行情資料...")
        resp = requests.get(FUND_URL, headers=headers, timeout=30, verify=False)
        resp.encoding = 'utf-8'
        
        # 網站將資料以 JSON 格式隱藏在 HTML 屬性中，我們直接解碼並用 Regex 提取
        text = html.unescape(resp.text)
        
        # 尋找所有持有資產的紀錄 (增加抓取 Share 股數)
        import re
        matches = re.finditer(r'\{"FundCode":"49YTW".*?"DetailCode":"([^"]+)","DetailName":"([^"]+)".*?"Share":([0-9.]+),.*?"NavRate":([0-9.]+)', text)
        
        holdings = []
        for m in matches:
            code = m.group(1)
            name = m.group(2)
            shares = float(m.group(3))
            weight = m.group(4)
            if code.isdigit():
                holdings.append({
                    "code": code,
                    "name": name,
                    "shares": shares,
                    "weight": f"{weight}%"
                })
        
        # 依照權重排序 (由大到小)
        holdings = sorted(holdings, key=lambda x: float(x['weight'].replace('%', '')), reverse=True)
        
        # 移除重複項
        seen = set()
        unique_holdings = []
        for h in holdings:
            if h['code'] not in seen:
                seen.add(h['code'])
                unique_holdings.append(h)
                
        # 取全部筆數
        final_holdings = unique_holdings
        
        if final_holdings:
            print(f"✅ 成功抓取到 {len(final_holdings)} 筆有效持股 (全部)")
        else:
            print("⚠️ 警告: 未能從網頁底層解析出持股資料。")
            
        return final_holdings
        
    except Exception as e:
        print(f"❌ 抓取過程發生錯誤: {e}")
        return []

def send_telegram(message):
    """發送 Telegram 訊息"""
    if not TOKEN or not CHAT_ID:
        print("⚠️ 未設定 Telegram Token 或 Chat ID，跳過發送訊息。")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram 發送失敗: {e}")

def compare_and_notify(current):
    """比對新舊持股並產生報告"""
    last = []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                last = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ 警告: last_holdings.json 格式錯誤或為空，將視為首次執行。")
            last = []

    # 建立字典方便比對
    last_dict = {item['code']: item for item in last}
    curr_dict = {item['code']: item for item in current}

    added = [c for c in curr_dict if c not in last_dict]
    removed = [p for p in last_dict if p not in curr_dict]
    
    # 比對股數變化 (Shares) 而非權重
    trades = []
    for c in curr_dict:
        if c in last_dict:
            curr_shares = curr_dict[c].get('shares', 0)
            last_shares = last_dict[c].get('shares', 0)
            
            if curr_shares != last_shares and last_shares > 0:
                diff = curr_shares - last_shares
                change_rate = (diff / last_shares) * 100
                
                label = ""
                if change_rate >= 10: label = "🔥 大幅加碼"
                elif change_rate > 0: label = "➕ 加碼"
                elif change_rate <= -10: label = "📉 大幅減碼"
                elif change_rate < 0: label = "➖ 減碼"
                
                if label:
                    trades.append({
                        "name": curr_dict[c]['name'],
                        "label": label,
                        "diff": diff,
                        "rate": change_rate,
                        "weight": curr_dict[c]['weight']
                    })

    # 偵測是否有任何變動 (新增、移除、或股數有變)
    if added or removed or trades:
        print("💡 偵測到交易變動！正在產生報告...")
        
        msg = "<b>🔔 00981A 基金最新交易變動報告</b>\n\n"
        
        if added:
            msg += "<b>🆕 新增持股：</b>\n"
            for c in added:
                msg += f"• {curr_dict[c]['name']} ({c}): {curr_dict[c]['weight']}\n"
            msg += "\n"
            
        if removed:
            msg += "<b>❌ 移除持股：</b>\n"
            for p in removed:
                msg += f"• {last_dict[p]['name']} ({p})\n"
            msg += "\n"
            
        if trades:
            msg += "<b>💹 經理人買賣動態：</b>\n"
            for t in trades:
                diff_str = f"{t['diff']:,.0f}"
                if t['diff'] > 0: diff_str = f"+{diff_str}"
                msg += f"• {t['name']}: {t['label']} ({diff_str} 股, {t['rate']:.1f}%)\n"
            msg += "\n"
        
        msg += f"<a href='{FUND_URL}'>🔗 查看官方即時持股</a>"
        
        # 發送通知
        send_telegram(msg)
        
        # 本地端顯示結果 (純文字版)
        print("-" * 30)
        print(msg.replace("<b>", "").replace("</b>", "").replace("<a href='", "").replace("'>", " ").replace("</a>", ""))
        print("-" * 30)
        
        # 更新存檔
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    else:
        print("✅ 持股內容與權重完全無變動，略過通知。")

def main():
    holdings = get_holdings()
    if holdings:
        compare_and_notify(holdings)

if __name__ == "__main__":
    main()
