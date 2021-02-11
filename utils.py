import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import os
import requests
import re
import math
from datetime import datetime
import pathlib
import timeit
import time

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
    url.append('http://comp.fnguide.com/SVO2/asp/SVD_Finance.asp?pGB=1&gicode=A'+code+'&cID=&MenuYn=Y&ReportGB=D&NewMenuID=103&stkGb=701')
        
    try:
        html_snapshot = BeautifulSoup(requests.get(url[0]).content, 'html.parser').find('body')
        html_fs = BeautifulSoup(requests.get(url[1]).content, 'html.parser').find('body')
        return True, '', html_snapshot, html_fs

    except AttributeError as e :
        print('Error in get_html_fnguide : ', e)
        return False, str(e), None, None    

def parse_fnguide(html_snapshot, html_fs):
    try:
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
        if ('IFRS(연결)' in fh):
            accounting = 'IFRS(연결)'
        elif ('GAAP(연결)' in fh):
            accounting = 'GAAP(연결)'
        else:
            return False, 'Neither IFRS(연결) nor GAAP(연결)', None, None, None, None
        fh.index = fh[accounting].values
        fh.drop([accounting], inplace=True, axis=1)
        #print(fh)
        fh = fh.loc[['지배주주지분', 'ROE', 'EPS(원)', 'DPS(원)', 'BPS(원)', '배당수익률'],:]
        fh.rename(index = {'DPS(원)': 'DPS', 'BPS(원)': 'BPS', 'EPS(원)': 'EPS'}, inplace = True)
        fh.loc['DPS'] = fh.loc['DPS'].fillna(0)
        temp_df = pd.DataFrame({'배당성향(%)': fh.loc['DPS'].astype(float) / fh.loc['EPS'].astype(float) * 100}).T
        fh = pd.concat([fh, temp_df])
        #print(fh)
        
        #Parse html_fs
        table = html_fs.find_all('table')
        table = pd.read_html(str(table))
        #포괄손익계산서 ci: statement of comprehensive income
        ci = table[0]
        ci.iloc[:,0] = ci.iloc[:,0].str.replace('계산에 참여한 계정 펼치기', '')
        if ('IFRS(연결)' in ci):
            accounting = 'IFRS(연결)'
        elif ('GAAP(연결)' in ci):
            accounting = 'GAAP(연결)'            
        else:
            return False, 'Niether IFRS(연결) or GAAP(연결)', None, None, None, None
        ci.index = ci[accounting].values
        ci.drop([accounting, '전년동기', '전년동기(%)'], inplace=True, axis=1)
        #현금흐름표 cf: statement of cash flow
        cf = table[4]
        cf.iloc[:,0] = cf.iloc[:,0].str.replace('계산에 참여한 계정 펼치기', '')
        cf.index = cf[accounting].values
        cf.drop([accounting], inplace=True, axis=1)
        #포괄손익계산서 + 현금흐름표
        fs = pd.concat([ci, cf])
        fs = fs.loc[['영업이익', '영업활동으로인한현금흐름'], :]
        fs.rename(index = {'영업활동으로인한현금흐름': '영업CF'}, inplace = True)
        temp_df = pd.DataFrame({'CF이익비율': fs.loc['영업CF'] / fs.loc['영업이익']}).T
        fs = pd.concat([fs, temp_df])
        #영업이익(+), 영업현금흐름(-) 체크 : 해당하면 1
        temp1 = fs.loc['영업이익'] > 0
        temp2 = fs.loc['영업CF'] < 0
        temp_df = pd.DataFrame(temp1 & temp2, columns=['CF이익검토']).T
        fs = pd.concat([fs, temp_df])
        #print(fs)
        return True, '', current_price, revised_shares, fh, fs
    except Exception as e:
        print('Exception in parse_fnguide :', e)
        return False, str(e), None, None, None, None

def calculate_price(B0, roe, Ke, shares, discount_factor):
    values = B0 + B0*(roe-Ke)*0.01*(discount_factor)/(1+Ke*0.01-discount_factor)
    price = values / shares
    return price

def calculate_weighted_average(minus2, minus1, minus0):
    if (minus0 >= minus1) :
        if (minus1 >= minus2) :
            weighted_average = minus0 # increase pattern
        else :
            weighted_average = (1*minus2 + 2*minus1 + 3*minus0)/6 # weighted average
    else :
        if (minus1 >= minus2) :
            weighted_average = (1*minus2 + 2*minus1 + 3*minus0)/6 # weighted average
        else :
            weighted_average = minus0 # decrease pattern
    return weighted_average

def calculate_roe(fh):
    roe = fh.loc['ROE',:]
    try:
        # +2year(E)
        if not math.isnan(roe[-1]):   
            selected_roe = roe[-1]
            roe_reference = roe.index[-1]
        # +1year (E)    
        elif not math.isnan(roe[-2]):
            selected_roe = roe[-2]
            roe_reference = roe.index[-2]
        # 0year (E) - weighted average
        elif not roe[-5:-2].isnull().values.any():
            extracted_roe = roe[-5:-2]
            extracted_roe = extracted_roe.astype(float)
            selected_roe = calculate_weighted_average(extracted_roe[0], extracted_roe[1], extracted_roe[2])
            roe_reference = roe.index[-3]
        # -1year - weighted average
        elif not roe[-6:-3].isnull().values.any():   
            extracted_roe = roe[-6:-3]
            extracted_roe = extracted_roe.astype(float)
            selected_roe = calculate_weighted_average(extracted_roe[0], extracted_roe[1], extracted_roe[2])
            roe_reference = roe.index[-4]
        else:
            return False, 'not enough ROE history', None, None
        return True, '', selected_roe, roe_reference
    except Exception as e:
        print('Exception in calculate_roe :', e)
        return False, str(e), None, None

def calculate_srim(shares, Ke, fh):
    try:
        #extract&determine roe
        status, msg, roe, roe_reference = calculate_roe(fh)
        if status == False:
            return False, msg, None, None, None, None, None
        #extract&determine B0 : 지배주주지분
        B0 = fh.loc['지배주주지분'][-4] * 10**8 # 지난 결산 년도 지배주주지분
        discount_factor = 1
        sell_price = match_tick_size(calculate_price(B0, roe, Ke, shares, discount_factor))
        discount_factor = 0.9
        proper_price = match_tick_size(calculate_price(B0, roe, Ke, shares, discount_factor))
        discount_factor = 0.8
        buy_price = match_tick_size(calculate_price(B0, roe, Ke, shares, discount_factor))
        return True, '', buy_price, proper_price, sell_price, roe, roe_reference
    except Exception as e:
        print('Exception in calculate_srim :', e)
        return False, str(e), None, None, None, None, None

def match_tick_size(price):
    if (price >= 100000):
        tick_price = round(price,-3)
    elif (price >= 10000):
        tick_price = round(price,-2)
    else:
        tick_price = round(price,-1)
    return tick_price

def check_skip_this_company(name, matches_endswith, matches_exact, matches_contain):
    if any(name.endswith(x) for x in matches_endswith):
        return 1
    elif any(x in name for x in matches_contain):
        return 1
    elif name in matches_exact:
        return 1
    else :
        return 0
      
def organize_result(code, name, current_price, buy_price, proper_price, sell_price, roe, roe_reference, fh, fs, industry, product):
    try:
        temp_result_df = pd.DataFrame({'code':[code], 
        'name':[name], 
        '현재가':[round(current_price)], 
        '매수가격':[round(buy_price)],
        '적정가격':[round(proper_price)],
        '매도가격':[round(sell_price)], 
        '매수가격예상수익률(%)':[round((buy_price - current_price)/current_price * 100, 2)],
        '적정가격예상수익률(%)':[round((proper_price - current_price)/current_price * 100, 2)], 
        '매도가격예상수익률(%)':[round((sell_price - current_price)/current_price * 100, 2)], 
        'ROE(%)':[round(roe,2)], 
        'ROE기준':[roe_reference],
        '배당수익률(%)':[fh.loc['배당수익률'][-4]], #지난 결산 년도 배당수익률
        '배당성향(%)': [round(fh.loc['배당성향(%)'][-4], 2)], #지난 결산 년도 배당 성향
        'CF위험(회)':[int(pd.DataFrame(fs.loc['CF이익검토']).sum())],
        'CF이익비율-3':[round(fs.loc['CF이익비율'][0],2)],
        'CF이익비율-2':[round(fs.loc['CF이익비율'][1],2)],
        'CF이익비율-1':[round(fs.loc['CF이익비율'][2],2)],
        'CF이익비율0':[round(fs.loc['CF이익비율'][3],2)],
        '업종':[industry], 
        '주요제품':[product]})
        return True, '', temp_result_df
    except Exception as e:
        print('Exception in calculate_srim :', e)
        return False, str(e), pd.DataFrame()
        