"""
復華投信爬蟲 (00991A) - 直接串接官方底層 API
使用自動日期倒推機制尋找最新交易日的持股資料。
"""
import requests
import urllib3
import re
from datetime import datetime, timedelta, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_data(fund_id="ETF23"):
    """
    抓取復華投信持股資料 (00991A)
    fund_id: 復華投信內部使用的代號，00991A 對應 ETF23
    """
    # 設定台灣時區
    tz_taipei = timezone(timedelta(hours=8))
    today = datetime.now(tz_taipei)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://www.fhtrust.com.tw/ETF/etf_detail/{fund_id}"
    }
    
    # 往前嘗試最多 10 天，尋找最新的交易日資料
    for i in range(10):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y/%m/%d")
        
        url = f"https://www.fhtrust.com.tw/api/assets?fundID={fund_id}&qDate={date_str}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            if resp.status_code != 200:
                continue
                
            data = resp.json()
            
            # 檢查是否有資料
            if not data.get("result") or len(data["result"]) == 0:
                continue
                
            fund_data = data["result"][0]
            details = fund_data.get("detail")
            
            # 如果 detail 存在且有內容，代表找到正確的交易日
            if details and isinstance(details, list) and len(details) > 0:
                print(f"  📅 [復華投信] 成功取得 {date_str} 之持股資料")
                holdings = []
                
                for item in details:
                    # 只抓取股票 (排除現金或其他資產)
                    if item.get("ftype") != "股票":
                        continue
                        
                    code = str(item.get("stockid", "")).strip()
                    name = item.get("stockname", "").strip()
                    weight = item.get("prate_addaccint", "0%").strip()
                    
                    # 處理股數 (移除逗號)
                    shares_str = item.get("qshare", "0").replace(",", "")
                    try:
                        shares = float(shares_str)
                    except ValueError:
                        shares = 0
                        
                    if code and code.isdigit():
                        holdings.append({
                            "code": code,
                            "name": name,
                            "shares": shares,
                            "weight": weight
                        })
                
                # 依照權重排序
                holdings = sorted(holdings, key=lambda x: float(x['weight'].replace('%', '')), reverse=True)
                return holdings
                
        except Exception as e:
            print(f"  ⚠️ 嘗試抓取 {date_str} 發生錯誤: {e}")
            continue
            
    print(f"❌ [復華投信] 無法取得最近 10 天內的持股資料")
    return []

