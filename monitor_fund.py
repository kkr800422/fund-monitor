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
        
        # 尋找所有持有資產的紀錄
        import re
        matches = re.finditer(r'\{"FundCode":"49YTW".*?"DetailCode":"([^"]+)","DetailName":"([^"]+)".*?"NavRate":([0-9.]+)', text)
        
        holdings = []
        for m in matches:
            code = m.group(1)
            name = m.group(2)
            weight = m.group(3)
            # 確保是股票代碼 (排除一些可能混入的現金或期貨代碼)
            if code.isdigit():
                holdings.append({
                    "code": code,
                    "name": name,
                    "weight": f"{weight}%" # 加上百分比符號以符合先前的格式
                })
        
        # 依照權重排序 (由大到小)
        holdings = sorted(holdings, key=lambda x: float(x['weight'].replace('%', '')), reverse=True)
        
        # 移除重複項 (有時網頁底層會重複印出兩次)
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
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            last = json.load(f)

    # 建立字典方便比對
    last_dict = {item['code']: item for item in last}
    curr_dict = {item['code']: item for item in current}

    added = [c for c in curr_dict if c not in last_dict]
    removed = [p for p in last_dict if p not in curr_dict]
    changed = [c for c in curr_dict if c in last_dict and curr_dict[c]['weight'] != last_dict[c]['weight']]

    # 偵測是否有任何變動
    if added or removed or changed:
        print("💡 偵測到持股變動！正在產生報告...")
        
        msg = "<b>🔔 00981A 基金投資組合變動報告 (全部持股)</b>\n\n"
        
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
            
        if changed:
            msg += "<b>⚖️ 比例權重變動：</b>\n"
            for c in changed:
                msg += f"• {curr_dict[c]['name']}: {last_dict[c]['weight']} ➔ <b>{curr_dict[c]['weight']}</b>\n"
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
