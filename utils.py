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
import numpy_financial as npf

def run(sema, path, file_name, extension, exclude_list_endswith, exclude_list_exact, exclude_list_contain, required_ror_percent, idx, row):
    
    proc = os.getpid()
    # print(proc)

    name = row['name']
    code = row['code']
    industry = row['industry']
    product = row['product']

    # check_skip_this_company
    if check_skip_this_company(name, code, exclude_list_endswith, exclude_list_exact, exclude_list_contain):
        print('    [Failed] Idx: ', '{:4d}'.format(idx), '\t Code: ', '{:6}'.format(code), '\t Name: ', '{:10}'.format(name), '\t Reason:', '분석 제외 대상')
        skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['분석 제외 대상']})
        skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
        sema.release()
        return

    # get_parse_fnguide
    status, msg, current_price, shares, fh, fh_quater, fs = get_parse_fnguide(code)
    if status == False:
        print('    [Failed] Idx: ', '{:4d}'.format(idx), '\t Code: ', '{:6}'.format(code), '\t Name: ', '{:10}'.format(name), '\t Reason:', 'Error on get_parse_fnguide ('+msg+')')
        skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on parse_fnguide : '+msg]})
        skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
        sema.release()
        return
    
    # calculate_srim
    status, msg, buy_price, proper_price, sell_price, last_price, roe, roe_reference = calculate_srim(shares, required_ror_percent, fh)
    if status == False:
        print('    [Failed] Idx: ', '{:4d}'.format(idx), '\t Code: ', '{:6}'.format(code), '\t Name: ', '{:10}'.format(name), '\t Reason:', 'Error on calculate_srim ('+msg+')')
        skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on calculate_srim : '+msg]})
        skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
        sema.release()
        return

    # organize_result
    result_df = pd.DataFrame()
    status, msg, result_df = organize_result(code, name, current_price, buy_price, proper_price, sell_price, last_price, roe, roe_reference, fh, fh_quater, fs, industry, product)
    if status == False:
        print('    [Failed] Idx: ', '{:4d}'.format(idx), '\t Code: ', '{:6}'.format(code), '\t Name: ', '{:10}'.format(name), '\t Reason:', 'Error on organize_result ('+msg+')')
        skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on organize_result : '+msg]})
        skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
        sema.release()
        return
    #print(result_df)
    print('[Successful] Idx: ', '{:4d}'.format(idx), '\t Code: ', '{:6}'.format(code), '\t Name: ', '{:10}'.format(name))
    result_df.to_csv(path+file_name+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')    
    sema.release()
    return

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

def get_parse_fnguide(code):
    
    url=[]
    url.append('http://comp.fnguide.com/SVO2/asp/SVD_Main.asp?pGB=1&gicode=A'+code+'&cID=&MenuYn=Y&ReportGB=D&NewMenuID=101&stkGb=701')
    url.append('http://comp.fnguide.com/SVO2/asp/SVD_Finance.asp?pGB=1&gicode=A'+code+'&cID=&MenuYn=Y&ReportGB=D&NewMenuID=103&stkGb=701')
    
    try:
        fnguide_df = pd.DataFrame()

        #parse html_snapshot
        html_snapshot = BeautifulSoup(requests.get(url[0]).content, 'html.parser').find('body')
        table = html_snapshot.find_all('table')
        table = pd.read_html(str(table))
        #시세현황 cs : current status
        #current_price: 현재가(종가)
        #shares: 발행주식수(보통주+우선주)
        cs = table[0]
        current_price = int(cs.iloc[0,1].split('/')[0].replace(',',''))
        shares = cs.iloc[6,1].replace(',','').split('/')
        shares = list(map(int, shares))
        shares = shares[0] + shares[1]
        #주주구분현황 sh: stake holders
        #own_shares: 자기주식
        sh = table[4]
        own_shares = sh.iloc[4,2]
        if math.isnan(own_shares):
            own_shares = 0
        else:
            own_shares = own_shares.astype(int)
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
            return False, 'Neither IFRS(연결) nor GAAP(연결)', None, None, None, None, None
        fh.index = fh[accounting].values
        fh.drop([accounting], inplace=True, axis=1)
        #print(fh)
        fh = fh.loc[['지배주주지분', 'ROE', 'EPS(원)', 'DPS(원)', 'BPS(원)', '배당수익률'],:]
        fh.rename(index = {'DPS(원)': 'DPS', 'BPS(원)': 'BPS', 'EPS(원)': 'EPS'}, inplace = True)
        fh.loc['DPS'] = fh.loc['DPS'].fillna(0)
        temp_df = pd.DataFrame({'배당성향(%)': fh.loc['DPS'].astype(float) / fh.loc['EPS'].astype(float) * 100}).T
        fh = pd.concat([fh, temp_df])
        #print(fh)
        
        #fh_quater: Financial highlight (연결/분기)
        fh_quater = table[12]
        fh_quater.columns = fh_quater.columns.droplevel()
        if ('IFRS(연결)' in fh_quater):
            accounting = 'IFRS(연결)'
        elif ('GAAP(연결)' in fh_quater):
            accounting = 'GAAP(연결)'
        else:
            return False, 'Neither IFRS(연결) nor GAAP(연결)', None, None, None, None, None
        fh_quater.index = fh_quater[accounting].values
        fh_quater.drop([accounting], inplace=True, axis=1)
        #print(fh_quater)
        fh_quater = fh_quater.loc[['지배주주순이익','영업이익'],:].fillna(0)
        fh_quater = fh_quater.loc[:,[False, True, True, True, True, False, False, False]]
        #print(fh_quater)
        
        #Parse html_fs
        html_fs = BeautifulSoup(requests.get(url[1]).content, 'html.parser').find('body')
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
            return False, 'Niether IFRS(연결) or GAAP(연결)', None, None, None, None, None
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
        return True, '', current_price, revised_shares, fh, fh_quater, fs
    except Exception as e:
        #print('Exception in get_parse_fnguide :', e)
        return False, str(e), None, None, None, None, None

# Assumption : Excess earning remains, it means ROE decreased (consider infinite years)
def calculate_price_book(B0, roe, Ke, shares, discount_factor):
    roe *= 0.01
    Ke *= 0.01
    values = B0 + B0*(roe-Ke)*(discount_factor)/(1+Ke-discount_factor)
    price = values / shares
    return price

# Assumption : ROE remains with increased controlling shareholder
def calculate_price_lecture(B0, roe, Ke, shares, discount_factor, pos):
    if pos == -1 :
        years = 7
        referenceDate = datetime(datetime.now().year+2,12,31)
    elif pos == -2 :
        years = 8
        referenceDate = datetime(datetime.now().year+1,12,31)
    elif pos == -3 :
        years = 9
        referenceDate = datetime(datetime.now().year,12,31)
    else :
        years = 10
        referenceDate = datetime(datetime.now().year-1,12,31)
    Ke *= 0.01
    roe *= 0.01
    Bt = B0
    excesses = [0,]
    excessRate = roe-Ke
    for i in range(years) :
        excessRate *= discount_factor
        roe = Ke + excessRate
        excess = Bt * roe - Bt * Ke
        excesses.append(excess)
        Bt += Bt * roe
    excessNetPresentValue = npf.npv(Ke,excesses)
    B = B0 + excessNetPresentValue
    priceAtThatTime = B/shares
    dayDifference = (referenceDate - datetime.now()).days
    price = priceAtThatTime / (1+Ke)**(dayDifference/365)
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

def calculate_roe_B0(fh):
    roe = fh.loc['ROE',:]
    B0 = fh.loc['지배주주지분',:]
    pos = 0
    try:
        # +2year(E)
        if not math.isnan(roe[-1]) and not math.isnan(B0[-1]):
            selected_roe = roe[-1].astype(float)
            roe_reference = roe.index[-1]
            selected_B0 = float(B0[-1]) * 10**8
            pos = -1
        # +1year (E)    
        elif not math.isnan(roe[-2]) and not math.isnan(B0[-2]):
            selected_roe = roe[-2].astype(float)
            roe_reference = roe.index[-2]
            selected_B0 = float(B0[-2]) * 10**8
            pos = -2
        # 0year (E) - weighted average
        elif not roe[-5:-2].isnull().values.any() and not math.isnan(B0[-3]):
            extracted_roe = roe[-5:-2]
            extracted_roe = extracted_roe.astype(float)
            selected_roe = calculate_weighted_average(extracted_roe[0], extracted_roe[1], extracted_roe[2])
            roe_reference = roe.index[-3]
            selected_B0 = float(B0[-3]) * 10**8
            pos = -3
        # -1year - weighted average
        elif not roe[-6:-3].isnull().values.any() and not math.isnan(float(B0[-4])):
            extracted_roe = roe[-6:-3]
            extracted_roe = extracted_roe.astype(float)
            selected_roe = calculate_weighted_average(extracted_roe[0], extracted_roe[1], extracted_roe[2])
            roe_reference = roe.index[-4]
            selected_B0 = float(B0[-4]) * 10**8
            pos = -4
        else:
            return False, 'not enough ROE history', None, None, None, None
        return True, '', selected_roe, roe_reference, selected_B0, pos
    except Exception as e:
        #print('Exception in calculate_roe_B0 :', e)
        return False, str(e), None, None, None, None

def calculate_srim(shares, Ke, fh):
    try:
        #extract&determine roe
        status, msg, roe, roe_reference, B0, pos = calculate_roe_B0(fh)
        if status == False:
            return False, msg, None, None, None, None, None, None
        discount_factor = 1
        sell_price_book = match_tick_size(calculate_price_book(B0, roe, Ke, shares, discount_factor))
        sell_price_lecture = match_tick_size(calculate_price_lecture(B0, roe, Ke, shares, discount_factor, pos))
        discount_factor = 0.9
        proper_price_book = match_tick_size(calculate_price_book(B0, roe, Ke, shares, discount_factor))
        proper_price_lecture = match_tick_size(calculate_price_lecture(B0, roe, Ke, shares, discount_factor, pos))
        discount_factor = 0.8
        buy_price_book = match_tick_size(calculate_price_book(B0, roe, Ke, shares, discount_factor))
        buy_price_lecture = match_tick_size(calculate_price_lecture(B0, roe, Ke, shares, discount_factor, pos))

        buy_price = min(buy_price_book, buy_price_lecture)
        proper_price = min(proper_price_book, proper_price_lecture)
        sell_price = min(sell_price_book, sell_price_lecture)
        last_price = max(sell_price_book, sell_price_lecture)

        return True, '', buy_price, proper_price, sell_price, last_price, roe, roe_reference
    except Exception as e:
        #print('Exception in calculate_srim :', e)
        return False, str(e), None, None, None, None, None, None

def match_tick_size(price):
    if (price >= 100000):
        tick_price = round(price,-3)
    elif (price >= 10000):
        tick_price = round(price,-2)
    else:
        tick_price = round(price,-1)
    return tick_price

def check_skip_this_company(name, code, matches_endswith, matches_exact, matches_contain):
    if any(name.endswith(x) for x in matches_endswith):
        return 1
    elif any(x in name for x in matches_contain):
        return 1
    elif name in matches_exact:
        return 1
    elif code[0] == '9':
        return 1
    else :
        return 0
      
def organize_result(code, name, current_price, buy_price, proper_price, sell_price, last_price, roe, roe_reference, fh, fh_quater, fs, industry, product):
    try:
        temp_result_df = pd.DataFrame({'code':[code], 
        'name':[name], 
        '현재가':[round(current_price)],
        '매수가격':[round(buy_price)],
        '적정가격':[round(proper_price)],
        '매도가격':[round(sell_price)],
        '최종가격':[round(last_price)],
        '매수가격수익률(%)':[round((buy_price - current_price)/current_price * 100, 2)],
        '적정가격수익률(%)':[round((proper_price - current_price)/current_price * 100, 2)],
        '매도가격수익률(%)':[round((sell_price - current_price)/current_price * 100, 2)],
        '최종가격수익률(%)':[round((last_price - current_price)/current_price * 100, 2)],
        'ROE(%)':[round(roe,2)],
        'ROE기준년도':[roe_reference],
        '배당수익률(%)':[fh.loc['배당수익률'][-4]], #지난 결산 년도 배당수익률
        '배당성향(%)': [round(fh.loc['배당성향(%)'][-4], 2)], #지난 결산 년도 배당 성향
        '현금흐름위험(회)':[int(pd.DataFrame(fs.loc['CF이익검토']).sum())], #현금흐름(-), 영업이익(+)
        '영업이익/현금흐름(4개년도평균)':[fs.loc['CF이익비율'].mean()], #현금흐름/영업이익 4개년도 평균
        '순이익(4분기누적)':[fh_quater.loc['지배주주순이익'].astype(float).sum()], #지배주주순이익 최근 4분기 누적
        '순이익적자(4분기횟수)':[pd.DataFrame(fh_quater.loc['지배주주순이익'].astype(float) < 0).sum()['지배주주순이익']], #지배주주순이익 최근 4분기 횟수
        '영업이익(4분기누적)':[fh_quater.loc['영업이익'].astype(float).sum()], #최근 4분기 누적
        '영업이익적자(4분기횟수)':[pd.DataFrame(fh_quater.loc['영업이익'].astype(float) < 0).sum()['영업이익']], #최근 4분기 횟수
        '업종':[industry],
        '주요제품':[product]})
        return True, '', temp_result_df
    except Exception as e:
        #print('Exception in calculate_srim :', e)
        return False, str(e), pd.DataFrame()
