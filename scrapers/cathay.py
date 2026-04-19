"""
國泰投信爬蟲 (00400A) - 透過 MoneyDJ 第三方財經平台抓取
因為國泰投信官網使用 Akamai 企業級 CDN 防護，
無法透過 Python 直接存取 (包括 Selenium 也會被偵測封鎖)，
所以我們改從 MoneyDJ 財經資訊網抓取同等的公開持股資料。
"""
import requests
import urllib3
import re
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_data(fund_code="00400A.TW"):
    """
    從 MoneyDJ 抓取基金持股資料。
    fund_code: MoneyDJ 使用的基金代碼格式 (例如 00400A.TW)
    """
    url = f"https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid={fund_code}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=30, verify=False)
        resp.encoding = 'utf-8'
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # MoneyDJ 的持股表格格式:
        # 表頭: ['個股名稱', '投資比例(%)', '持有股數']
        # 資料: ['台積電(2330.TW)', '6.99', '436,000.00']
        
        holdings = []
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
                
            # 檢查表頭是否包含 '個股名稱' 或 '投資比例'
            header_row = rows[0]
            header_text = header_row.get_text()
            if '個股名稱' not in header_text and '投資比例' not in header_text:
                continue
            
            # 解析資料行
            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) < 3:
                    continue
                
                name_cell = cols[0].get_text(strip=True)
                weight_cell = cols[1].get_text(strip=True)
                shares_cell = cols[2].get_text(strip=True)
                
                # 從名稱中提取代碼: "台積電(2330.TW)" -> code=2330, name=台積電
                match = re.match(r'(.+?)\((\d{4})\.TW\)', name_cell)
                if not match:
                    continue
                
                name = match.group(1).strip()
                code = match.group(2)
                
                # 解析權重
                try:
                    weight = float(weight_cell)
                except ValueError:
                    continue
                
                # 解析股數
                try:
                    shares = float(shares_cell.replace(',', ''))
                except ValueError:
                    shares = 0
                
                holdings.append({
                    "code": code,
                    "name": name,
                    "shares": shares,
                    "weight": f"{weight}%"
                })
        
        # 依照權重排序
        holdings = sorted(holdings, key=lambda x: float(x['weight'].replace('%', '')), reverse=True)
        
        return holdings
        
    except Exception as e:
        print(f"❌ [國泰投信 {fund_code}] 抓取失敗: {e}")
        return []
