from bs4 import BeautifulSoup
import requests
from PyQt5 import QtWidgets, QtTest, QtCore
from datetime import datetime, timedelta
import sys
from MyMainWindow import MyMainWindow, BaseWorkerThread
from datetime import datetime, timedelta
import logging
import pandas as pd
import re
import json
from jugaad_data.nse import NSELive


pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_rows', None)

link_today = "https://www.moneycontrol.com/earnings-widget?indexId=N&dur=T&startDate=&endDate=&deviceType=web&classic=true"

link_tomorrow = "https://www.moneycontrol.com/earnings-widget?indexId=N&dur=TO&startDate=&endDate=&deviceType=web&classic=true"

link_in_range = "https://www.moneycontrol.com/earnings-widget?indexId=N&dur=&startDate=%s&endDate=%s&deviceType=web&classic=true"

volume_change = "https://api.moneycontrol.com/mcapi/v1/stock/price-volume?scId=%s"

fetch_symbol = "https://symbol-search.tradingview.com/symbol_search/v3/?text=%s&hl=1&exchange=&lang=en&search_type=stocks&domain=production&sort_by_country=US"

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'accept-language': 'en-US,en;q=0.9,en-IN;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'cache-control': 'max-age=0',
    'dnt': '1',
    'if-none-match': 'W/"411-qfE24Ejr+gasfuGTZ+yqhcz+cv0"',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://www.google.com/',
}


def get_stock_symbol(stock_name: str):
    results = requests.get(fetch_symbol % stock_name.upper(), headers=headers).json()['symbols']
    try:
        return results[0]['symbol']
    except Exception:
        return None


def extract_proper_code(url):
    response = requests.get(url, headers=headers)
    pattern = re.compile(fr'\bvar scid\s*=\s*(.*?);', re.DOTALL | re.IGNORECASE)
    match = pattern.search(response.text)
    if match:
        return match.group(1).strip().strip('"')
    raise Exception("No matching scid found")


def fetch_all_entries_indian_stock(link_url):
    i = 0
    row_count = 0
    result_df = pd.DataFrame(columns=['Date', 'Company', 'Result type', 'LTP', '% Change', 'Tentative Time', 'Vol Change', 'Vol Change %'])
    while True:
        i += 1
        if i != 1:
            response = requests.get(link_url + "&page=" + str(i), headers=headers)
        else:
            response = requests.get(link_url, headers=headers)
        df = pd.read_html(io=response.text, flavor='html5lib')[0]
        if df.empty:
            break
        soup = BeautifulSoup(response.text, 'html.parser')
        overview_links = [evt_alink.get('href') for evt_alink in soup.find_all('a', class_="evt_alink")]
        stock_ids = [stck.split('/')[-1] for stck in overview_links]
        volumes = []
        volume_change_perc = []
        for idx in range(len(stock_ids)):
            id = stock_ids[idx]
            try:
                vol_data = requests.get(volume_change % id, headers=headers).json()['data']['stock_price_volume_data']['volume']
                print(row_count + idx, volume_change % id, sep=": ")
            except json.JSONDecodeError:
                code = extract_proper_code(overview_links[idx])
                vol_data = requests.get(volume_change % code, headers=headers).json()['data']['stock_price_volume_data']['volume']
                print(row_count + idx, volume_change % code, sep=": ")
            vol_today = vol_data['Today']
            vol_yesterday = vol_data['Yesterday']
            vol_week = vol_data['1 Week Avg']
            vol_month = vol_data['1 Month Avg']
            volumes.append([
                str(vol_today['cvol_display_text']),
                str(vol_yesterday['cvol_display_text']),
                str(vol_week['cvol_display_text']),
                str(vol_month['cvol_display_text'])
            ])
            try:
                volume_change_perc.append([
                    str(f"{(vol_today['cvol'] - vol_month['cvol']) / vol_month['cvol'] * 100:3.2f}%"),
                    str(f"{(vol_yesterday['cvol'] - vol_month['cvol']) / vol_month['cvol'] * 100:3.2f}%"),
                    str(f"{(vol_week['cvol'] - vol_month['cvol']) / vol_month['cvol'] * 100:3.2f}%"),
                ])
            except ZeroDivisionError:
                volume_change_perc.append([])
        df = df.dropna(axis=1, how='all').iloc[:, :6]
        df.columns = ['Date', 'Company', 'Result type', 'LTP', '% Change', 'Tentative Time']
        df.insert(6, 'Vol Change', pd.Series(volumes))
        df.insert(7, 'Vol Change %', pd.Series(volume_change_perc))
        result_df = pd.concat([result_df, df], ignore_index=True)
        row_count += idx + 1
    print(result_df)


def fetch_all_entries_us_stock(link_url, refresh=False):
    def get_page_limit():
        link = link_url + "&limit=1"
        resp = requests.get(link, headers=headers).json()
        for idx in range(len(resp)):
            if resp[idx]["title"] == "All Foreign Stocks":
                return resp[idx]["data"]["count"], idx
        raise Exception(f"No key named 'All Foreign Stocks' in url: {link}")

    us_stocks_list = []
    accepted_list_type = list
    if not refresh:
        try:
            with open("us_stocks_list.json", "r") as f:
                us_stocks_list = eval(f.read())
                if not isinstance(us_stocks_list, accepted_list_type):
                    us_stocks_list = accepted_list_type()
        except FileNotFoundError:
            # It will automatically start fetching
            pass
    if not us_stocks_list:
        limit, idx = get_page_limit()
        print("link_url: ", link_url + "&limit=" + str(limit), sep='')
        lists_of_stocks = requests.get(link_url + "&limit=" + str(limit), headers=headers).json()[idx]["data"]["data"]
        # Assuming the storing_type to be made as list
        print("Formatting obtained US Stocks...")
        us_stocks_list = [stck["nse_symbol"] for stck in lists_of_stocks]
        print("Writing entries to the us_stocks_list.json file...")
        with open("us_stocks_list.json", "w+") as fw:
            fw.write(str(us_stocks_list))
        print("Successfully added the entries...")
    base_url = "https://finviz.com/"
    post_url = "screener.ashx?v=111&s=ta_unusualvolume&f=exch_nasd&o=-volume"
    cnt = 1
    result_df = pd.DataFrame(columns=['Ticker', 'Company', 'Market Cap', 'P/E', 'Price', 'Change', 'Volume', 'Sector', 'Industry'])
    print("Finviz URL:", base_url + post_url + "&r=" + str(cnt))
    resp = requests.get(base_url + post_url + "&r=" + str(cnt), headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    pages_links = set(anchor.get('href') for anchor in soup.find('td', class_='body-table screener_pagination').find_all(
        'a', class_=lambda value: value not in ['tab-link is-next', 'tab-link is-prev']))
    for page_url in pages_links:
        # import pdb; pdb.set_trace()
        resp = requests.get(base_url + page_url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        main_table = soup.find('table', class_='styled-table-new is-rounded is-tabular-nums w-full screener_table')
        df = pd.read_html(io=str(main_table), flavor='html5lib')[0]
        condition = (df['Ticker'].isin(us_stocks_list))
        result_df = pd.concat([result_df, df[condition].loc[:, df[condition].columns.intersection(result_df.columns)]], ignore_index=True)
    result_df = result_df.sort_values(by='Volume', ascending=False).reset_index(drop=True)
    print(result_df)
    for idx in range(len(result_df.iloc[:, 0])):
        print(f"{idx} https://finviz.com/quote.ashx?t={result_df.iloc[:, 0][idx]}&p=d&b=1")


def fetch_broker_analyst_target(link_url):
    resp = requests.get(link_url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    main_table = soup.find('table', class_='table fs09rem tl-dataTable')
    df = pd.read_html(io=str(main_table), flavor='html5lib')[0]
    df = df.dropna(axis=1, how='all')
    condition = (df['Date'] != 'more') & (df['Upside(%)'] != 'Target met')
    df = df[condition].loc[:, df.columns.intersection(['Date', 'Stock', 'Author', 'LTP', 'Target',
                                                        'Price at reco(Change since reco%)', 'Upside(%)', 'Type'])]
    print(df)
    # result_df = result_df.sort_values(by='Volume', ascending=False).reset_index(drop=True)


def nse_sectors_positive_stocks(link_url):
    n = NSELive()
    resp = n.s.get(link_url, headers=headers)
    sectorial_indices = resp.json()["Sectoral Indices"]
    equity_indices_url = "https://www.nseindia.com/api/equity-stockIndices?index="

    for idx in sectorial_indices:
        try:
            stocks_list = n.s.get(equity_indices_url + idx).json()["data"]
        except Exception:
            print(f"Error in URL: {equity_indices_url + idx}, obtained error: {n.s.get(equity_indices_url + idx).json()}")
        main_index = stocks_list[0]
        if main_index["change"] > 20:
            result_df = pd.DataFrame(columns=['symbol', 'open', 'lastPrice', 'change'])
            for stck in stocks_list:
                data = {
                    'symbol': stck['symbol'],
                    'open': stck['open'],
                    'lastPrice': stck['lastPrice'],
                    'change': stck['change']
                }
                result_df = result_df.append(data, ignore_index=True)
            print(result_df, end="\n\n")


if __name__ == "__main__":
    fetch_all_entries_indian_stock(f"https://www.moneycontrol.com/earnings-widget?indexId=N&dur=&startDate={(datetime.now() + timedelta(days=-2)).strftime('%Y-%m-%d')}&endDate={(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')}&deviceType=web&classic=true")

    # fetch_all_entries_us_stock("https://apixt-fz.indmoney.com/us-stocks-ext/api/v3/user/foreign-stocks/bulkcategory?category_filters=all&page=1&include_data=1&sort_order=desc&sort_key=mcap")

    # fetch_broker_analyst_target("https://trendlyne.com/research-reports/buy/?page=1&querystring_key=page")

    # nse_sectors_positive_stocks("https://www.nseindia.com/api/equity-master")
