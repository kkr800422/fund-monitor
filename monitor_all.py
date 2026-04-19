import os
import json
import sys
import requests
from scrapers import unipresident, cathay, fuhhwa

# 強制設定標準輸出編碼為 utf-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# =================配置區=================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 監控基金清單
FUNDS_TO_MONITOR = [
    {
        "id": "00981A",
        "name": "統一台股增長",
        "scraper": unipresident,
        "fund_code": "49YTW",
        "url": "https://www.ezmoney.com.tw/ETF/Fund/Info?FundCode=49YTW"
    },
    {
        "id": "00400A",
        "name": "國泰台股動能高息",
        "scraper": cathay,
        "fund_code": "00400A.TW", # MoneyDJ 使用的代碼格式
        "url": "https://www.cathaysite.com.tw/ETF/detail/EEA?tab=etf3"
    },
    {
        "id": "00991A",
        "name": "復華台灣未來50",
        "scraper": fuhhwa,
        "fund_code": "ETF23", # 復華 API 使用的代碼
        "url": "https://www.fhtrust.com.tw/ETF/etf_detail/ETF23#stockhold"
    }
]
# ========================================

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
        # 修改這裡：接收 response 並印出結果
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            print("✅ Telegram 訊息發送成功！")
        else:
            print(f"❌ TG API 報錯: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Telegram 通訊異常: {e}")

def compare_and_notify(fund, current):
    """比對單一基金的新舊持股並產生報告"""
    fund_id = fund['id']
    fund_name = fund['name']
    state_file = f"last_holdings_{fund_id}.json"
    
    last = []
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                last = json.load(f)
        except json.JSONDecodeError:
            last = []

    # 建立字典方便比對
    last_dict = {item['code']: item for item in last}
    curr_dict = {item['code']: item for item in current}

    added = [c for c in curr_dict if c not in last_dict]
    removed = [p for p in last_dict if p not in curr_dict]
    
    # 比對股數變化 (Shares)
    heavy_adds, adds, reduces, heavy_reduces = [], [], [], []
    for c in curr_dict:
        if c in last_dict:
            curr_shares = curr_dict[c].get('shares', 0)
            last_shares = last_dict[c].get('shares', 0)
            
            if curr_shares != last_shares and last_shares > 0:
                diff = curr_shares - last_shares
                rate = (diff / last_shares) * 100
                # 計算張數 (無條件捨去小數點，1張=1000股)
                diff_lots = int(diff / 1000) 
                trade_info = {"code": c, "name": curr_dict[c]['name'], "diff_lots": diff_lots, "rate": rate}
                
                if rate >= 10: heavy_adds.append(trade_info)
                elif rate > 0: adds.append(trade_info)
                elif rate <= -10: heavy_reduces.append(trade_info)
                elif rate < 0: reduces.append(trade_info)

    # 偵測是否有任何變動
    if added or removed or heavy_adds or adds or reduces or heavy_reduces:
        print(f"💡 偵測到 [{fund_id} {fund_name}] 交易變動！正在產生報告...")
        
        # 取得台灣台北當天日期
        from datetime import datetime, timezone, timedelta
        tz_taipei = timezone(timedelta(hours=8))
        today_date = datetime.now(tz_taipei).strftime("%Y-%m-%d")
        
        msg = f"<b>📅 日期：{today_date}</b>\n"
        msg += f"<b>🔔 {fund_id} {fund_name} 最新交易變動報告</b>\n"
        msg += "--------------------------------\n\n"
        
        if added:
            msg += "<b>🆕 [新增持股]</b>\n"
            for c in added:
                msg += f"• {curr_dict[c]['name']} ({c}): {curr_dict[c]['weight']}\n"
            msg += "\n"
            
        if heavy_adds:
            msg += "<b>🔥 [大幅加碼] (增逾10%)</b>\n"
            for t in heavy_adds:
                msg += f"• {t['name']} ({t['code']}): +{t['diff_lots']:,} 張 ({t['rate']:.1f}%)\n"
            msg += "\n"

        if adds:
            msg += "<b>➕ [一般加碼]</b>\n"
            for t in adds:
                msg += f"• {t['name']} ({t['code']}): +{t['diff_lots']:,} 張 ({t['rate']:.1f}%)\n"
            msg += "\n"

        if reduces:
            msg += "<b>➖ [一般減碼]</b>\n"
            for t in reduces:
                msg += f"• {t['name']} ({t['code']}): {t['diff_lots']:,} 張 ({t['rate']:.1f}%)\n"
            msg += "\n"

        if heavy_reduces:
            msg += "<b>📉 [大幅減碼] (減逾10%)</b>\n"
            for t in heavy_reduces:
                msg += f"• {t['name']} ({t['code']}): {t['diff_lots']:,} 張 ({t['rate']:.1f}%)\n"
            msg += "\n"

        if removed:
            msg += "<b>❌ [全數移除]</b>\n"
            for p in removed:
                msg += f"• {last_dict[p]['name']} ({p})\n"
            msg += "\n"
        
        msg += "--------------------------------\n"
        msg += f"<a href='{fund['url']}'>🔗 查看官方即時持股</a>"
        
        # 發送通知
        send_telegram(msg)
        
        # 本地端顯示結果 (純文字)
        print(msg.replace("<b>", "").replace("</b>", "").replace("<a href='", "").replace("'>", " ").replace("</a>", ""))
        
        # 更新該基金的紀錄檔
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    else:
        print(f"✅ [{fund_id} {fund_name}] 持股數量與權重完全無變動。")

def main():
    print(f"🚀 開始執行多基金監控任務 (共 {len(FUNDS_TO_MONITOR)} 個標的)")
    for fund in FUNDS_TO_MONITOR:
        print(f"--- 正在處理: {fund['id']} {fund['name']} ---")
        holdings = fund['scraper'].fetch_data(fund['fund_code'])
        if holdings:
            compare_and_notify(fund, holdings)
        else:
            print(f"⚠️ 無法取得 {fund['id']} 的持股資料，跳過。")
    print("✨ 所有任務執行完畢。")

if __name__ == "__main__":
    main()
