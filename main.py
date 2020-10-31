#%%
import pandas as pd
#from pandas import DataFrame
#from pandas import ExcelWriter
from bs4 import BeautifulSoup
import os
import requests
import pprint
import re
import math
from datetime import datetime


def get_krx_list():
    krx_df = pd.read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13', header=0)[0]
    krx_df.종목코드 = krx_df.종목코드.map("{:06d}".format)
    krx_df = krx_df[['종목코드', '회사명', '업종', '주요제품']]
    krx_df = krx_df.rename(columns={'종목코드': 'code', '회사명':'name', '업종' : 'industry', '주요제품' : 'product'})
    return krx_df

def get_required_rate_of_return():
    bond_ror_df = pd.read_html('https://www.kisrating.com/ratingsStatistics/statics_spread.do')[0]
    bond_ror_df = bond_ror_df.set_index(['구분'])
    required_ror_bbb_minus = bond_ror_df.loc['BBB-']
    required_ror_bbb_minus_5year = required_ror_bbb_minus.loc['5년']
    return required_ror_bbb_minus_5year

def get_html_fnguide(code):
    url=[]

    url.append('http://comp.fnguide.com/SVO2/asp/SVD_Main.asp?pGB=1&gicode=A'+code+'&cID=&MenuYn=Y&ReportGB=D&NewMenuID=101&stkGb=701')
    url.append('http://comp.fnguide.com/SVO2/asp/SVD_Finance.asp?pGB=1&gicode=A'+code+'&cID=&MenuYn=Y&ReportGB=&NewMenuID=103&stkGb=701')
        
    try:
        html_snapshot = BeautifulSoup(requests.get(url[0]).content, 'html.parser').find('body')
        html_fs = BeautifulSoup(requests.get(url[1]).content, 'html.parser').find('body')

    except AttributeError as e :
        print(e)
        return None

    return html_snapshot, html_fs

def parse_fnguide(html_snapshot, html_fs):
    fnguide_df = pd.DataFrame()

    #parse html_snapshot
    table = html_snapshot.find_all('table')
    table = pd.read_html(str(table))
    #시세현황 cs : current status
    #current_price: 현재가(종가)
    #shares: 발행주식수(보통주+우선주)
    cs = table[0]
    current_price = float(cs.iloc[0,1].split('/')[0].replace(',',''))
    shares = cs.iloc[6,1].replace(',','').split('/')
    shares = list(map(float, shares))
    shares = shares[0] + shares[1]
    #주주구분현황 sh: stake holders
    #own_shares: 자기주식
    sh = table[4]
    own_shares = sh.iloc[4,3]
    if math.isnan(own_shares):
        own_shares = float(0.0)
    else:
        own_shares = float(own_shares)
    #주식수: 보통주+우선주-자기주식수
    revised_shares = shares - own_shares    
    #fh: Financial highlight (연결/연간)
    fh = table[11]
    fh.columns = fh.columns.droplevel()
    fh.index = fh['IFRS(연결)'].values
    fh.drop(['IFRS(연결)'], inplace=True, axis=1)
    #print(fh)
    fh = fh.loc[['지배주주지분', 'ROE', 'EPS(원)', 'DPS(원)', 'BPS(원)', '배당수익률'],:]
    fh.rename(index = {'DPS(원)': 'DPS', 'BPS(원)': 'BPS', 'EPS(원)': 'EPS'}, inplace = True)
    temp_df = pd.DataFrame({'배당성향(%)': fh.loc['DPS'] / fh.loc['EPS'] * 100}).T
    fh = pd.concat([fh, temp_df])
    #print(fh)

    
    #Parse html_fs
    table = html_fs.find_all('table')
    table = pd.read_html(str(table))
    #포괄손익계산서 ci: statement of comprehensive income
    ci = table[0]
    ci.iloc[:,0] = ci.iloc[:,0].str.replace('계산에 참여한 계정 펼치기', '')
    ci.index = ci['IFRS(연결)'].values
    ci.drop(['IFRS(연결)', '전년동기', '전년동기(%)'], inplace=True, axis=1)
    #현금흐름표 cf: statement of cash flow
    cf = table[4]
    cf.iloc[:,0] = cf.iloc[:,0].str.replace('계산에 참여한 계정 펼치기', '')
    cf.index = cf['IFRS(연결)'].values
    cf.drop(['IFRS(연결)'], inplace=True, axis=1)
    #포괄손익계산서 + 현금흐름표
    fs = pd.concat([ci, cf])
    fs = fs.loc[['영업이익', '영업활동으로인한현금흐름'], :]
    fs.rename(index = {'영업활동으로인한현금흐름': '영업CF'}, inplace = True)
    temp_df = pd.DataFrame({'현금흐름검토': fs.loc['영업CF'] - fs.loc['영업이익']}).T
    fs = pd.concat([fs, temp_df])
    #print(fs)

    return current_price, revised_shares, fh, fs

def calculate_price(B0, ROE, Ke, shares, discount_factor):
    values = B0 + B0*(ROE-Ke)*0.01*(discount_factor)/(1+Ke*0.01-discount_factor)
    price = values / shares
    return price

def calculate_weighted_average(minus2, minus1, minus0):
    weighted_average = (1*minus2 + 2*minus1 + 3*minus0)/6
    return weighted_average

def calculate_roe(fh, year):
    roe = fh.loc['ROE',:]
    if ~math.isnan(roe[str(year+2)+'/12(E)']):
        selected_roe = roe[str(year+2)+'/12(E)']
        roe_reference = str(year+2)+'/12(E)'
    elif ~math.isnan(roe[str(year+1)+'/12(E)']):
        selected_roe = roe[str(year+1)+'/12(E)']
        roe_reference = str(year+1)+'/12(E)'
    elif ~math.isnan(roe[str(year)+'/12(E)']):
        minus2 = roe[str(year)+'/12(E)']
        minus1 = roe[str(year-1)+'/12(E)']
        minus0 = roe[str(year-2)+'/12(E)']
        selected_roe = calculate_weighted_average(minus2, minus1, minus0)
        roe_reference = str(year)+'/12(E)'
    else:
        minus2 = roe[str(year-1)+'/12(E)']
        minus1 = roe[str(year-2)+'/12(E)']
        minus0 = roe[str(year-3)+'/12(E)']
        selected_roe = calculate_weighted_average(minus2, minus1, minus0)
        roe_reference = str(year-1)+'/12(E)'

    #selected_roe = 33
    #roe_reference = 'ttest'    
    return selected_roe, roe_reference

def calculate_srim(shares, Ke, fh, current_year):

    last_year = current_year - 1;    
    
    #extract&determine ROE
    ROE, ROE_reference = calculate_roe(fh, current_year)
    print('\nROE: \t', ROE, '\n')
    print('\nROE_reference: \t', ROE_reference, '\n')

    #extract&determine B0 : 지배주주지분
    B0 = fh.loc['지배주주지분',str(last_year)+'/12'] * 10**8

    discount_factor = 1
    sell_price = calculate_price(B0, ROE, Ke, shares, discount_factor)

    discount_factor = 0.9
    moderate_price = calculate_price(B0, ROE, Ke, shares, discount_factor)
    
    discount_factor = 0.8
    buy_price = calculate_price(B0, ROE, Ke, shares, discount_factor)

    return buy_price, moderate_price, sell_price


current_year = datetime.now().year

krx_list = get_krx_list()
#print(krx_list)

required_ror_percent = get_required_rate_of_return()
#print(required_ror_percent)

code = '005930'
html_snapshot, html_fs = get_html_fnguide('005930')

current_price, shares, fh, fs = parse_fnguide(html_snapshot, html_fs)
#print('current_price\n', current_price, '\n\n\n')
#print('shares\n', shares, '\n\n\n')
#print('fh\n', fh, '\n\n\n')
#print('fs\n', fs, '\n\n\n')

buy_price, moderate_price, sell_price = calculate_srim(shares, required_ror_percent, fh, current_year)
print('')
print('buy_price: \t', buy_price)
print('moderate_price: \t', moderate_price)
print('sell_price: \t', sell_price)

