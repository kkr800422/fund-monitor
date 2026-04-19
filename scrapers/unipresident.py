import requests
import html
import re
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_data(fund_code="49YTW"):
    """
    抓取統一投信持股資料 (00981A)
    """
    # 統一投信 00981A 的主網頁
    url = f"https://www.ezmoney.com.tw/ETF/Fund/Info?FundCode={fund_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=30, verify=False)
        resp.encoding = 'utf-8'
        
        # 網站將資料以 JSON 格式隱藏在 HTML 屬性中，解碼並用 Regex 提取
        text = html.unescape(resp.text)
        
        # 尋找所有持有資產的紀錄
        # 格式: {"FundCode":"49YTW",...,"DetailCode":"2330","DetailName":"台積電",...,"Share":6556000.0,...,"NavRate":8.67}
        matches = re.finditer(r'\{"FundCode":"' + fund_code + r'".*?"DetailCode":"([^"]+)","DetailName":"([^"]+)".*?"Share":([0-9.]+),.*?"NavRate":([0-9.]+)', text)
        
        holdings = []
        for m in matches:
            code = m.group(1)
            name = m.group(2)
            shares = float(m.group(3))
            weight = m.group(4)
            
            # 確保是股票代碼 (純數字)
            if code.isdigit():
                holdings.append({
                    "code": code,
                    "name": name,
                    "shares": shares,
                    "weight": f"{weight}%"
                })
        
        # 依照權重排序
        holdings = sorted(holdings, key=lambda x: float(x['weight'].replace('%', '')), reverse=True)
        
        # 移除重複項
        seen = set()
        unique_holdings = []
        for h in holdings:
            if h['code'] not in seen:
                seen.add(h['code'])
                unique_holdings.append(h)
                
        return unique_holdings
    except Exception as e:
        print(f"❌ [統一投信 {fund_code}] 抓取失敗: {e}")
        return []
