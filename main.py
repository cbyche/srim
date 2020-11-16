#%%
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import os
import requests
import pprint
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
        sell_price = calculate_price(B0, roe, Ke, shares, discount_factor)
        discount_factor = 0.9
        proper_price = calculate_price(B0, roe, Ke, shares, discount_factor)    
        discount_factor = 0.8
        buy_price = calculate_price(B0, roe, Ke, shares, discount_factor)
        return True, '', buy_price, proper_price, sell_price, roe, roe_reference
    except Exception as e:
        print('Exception in calculate_srim :', e)
        return False, str(e), None, None, None, None, None

def check_skip_this_company(name):
    matches = ['스팩', '리츠', '증권', '은행']
    if any(x in name for x in matches):
        return 1
    else :
        return 0
      

# start main
current_year = datetime.now().year

required_ror_percent = get_required_rate_of_return()
#print(required_ror_percent)

krx_list = get_krx_list()
#print(krx_list)

result_df = pd.DataFrame()
skip_df = pd.DataFrame()

count_total = 0
count_record = 0
count_skip = 0

start_total = timeit.default_timer()
for iter in range(0,len(krx_list)) :
    start = timeit.default_timer()
    
    count_total += 1
    temp_result_df = pd.DataFrame()     

    name = krx_list.iloc[iter]['name']
    code = krx_list.iloc[iter]['code']
    #print('Iter: ', iter, '\t Code: ', code, '\t Name: ', name)

    if check_skip_this_company(name):
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', '분석 제외 대상')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['분석 제외 대상']})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    
    status, msg, html_snapshot, html_fs = get_html_fnguide(code)
    if status == False:
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', 'Error on get_html_fnguide ('+msg+')')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on get_html_fnguide : '+msg]})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    status, msg, current_price, shares, fh, fs = parse_fnguide(html_snapshot, html_fs)
    if status == False:
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', 'Error on parse_fnguide ('+msg+')')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on parse_fnguide : '+msg]})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    status, msg, buy_price, proper_price, sell_price, roe, roe_reference = calculate_srim(shares, required_ror_percent, fh)
    if status == False:
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', 'Error on calculate_srim ('+msg+')')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on calculate_srim : '+msg]})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    # Organize results
    code = krx_list.iloc[iter]['code']
    name = krx_list.iloc[iter]['name']
    current_price = round(current_price)
    buy_price = round(buy_price)    
    proper_price = round(proper_price)    
    sell_price = round(sell_price)
    undervalued_rate_buy = round((buy_price - current_price)/current_price * 100, 2)
    undervalued_rate_proper = round((proper_price - current_price)/current_price * 100, 2)
    undervalued_rate_sell = round((sell_price - current_price)/current_price * 100, 2)
    roe = round(roe, 2)
    roe_reference = roe_reference    
    devidend_rate = fh.loc['배당수익률'][-4] #지난 결산 년도 배당수익률
    devidend_propensity = round(fh.loc['배당성향(%)'][-4], 2) # 지난 결산 년도 배당성향
    CF_alerts = int(pd.DataFrame(fs.loc['CF이익검토']).sum())
    CF_profit_ratio = round(fs.loc['CF이익비율'],2)
    industry = krx_list.iloc[iter]['industry']
    product = krx_list.iloc[iter]['product']

    temp_result_df = pd.DataFrame({'code':[code], 
    'name':[name], 
    '현재가':[current_price], 
    '매수가격':[buy_price],      
    '적정가격':[proper_price],     
    '매도가격':[sell_price], 
    '매수가격예상수익률(%)':[undervalued_rate_buy],
    '적정가격예상수익률(%)':[undervalued_rate_proper], 
    '매도가격예상수익률(%)':[undervalued_rate_sell], 
    'ROE(%)':[roe], 
    'ROE기준':[roe_reference],
    '배당수익률(%)':[devidend_rate],
    '배당성향(%)': [devidend_propensity],
    'CF위험(회)':[CF_alerts],
    'CF이익비율'+'('+str(CF_profit_ratio.index[0])+')':[CF_profit_ratio[0]],
    'CF이익비율'+'('+str(CF_profit_ratio.index[1])+')':[CF_profit_ratio[1]],
    'CF이익비율'+'('+str(CF_profit_ratio.index[2])+')':[CF_profit_ratio[2]],
    'CF이익비율'+'('+str(CF_profit_ratio.index[3])+')':[CF_profit_ratio[3]],
    '업종':[industry], 
    '주요제품':[product]})
    result_df = pd.concat([result_df, temp_result_df])
    #print(result_df)

    count_record += 1
    stop = timeit.default_timer()
    print('[Successful] Iter: ', iter, '/', len(krx_list), '\t Code: ', code, '\t Name: ', name, '\tTime: ', format(stop - start,'.2f'))

#print(result_df)
stop_total = timeit.default_timer()
print('Total Processing Time : ', format((stop_total-start_total)/60, '.1f'), ' mins')

path = str(pathlib.Path().absolute()) + '\\'
file_name = str(datetime.now().date())
extension = '.csv'
result_df.to_csv(path+file_name+extension, mode='w', index=False, na_rep='NaN', encoding='utf-8-sig')
skip_df.to_csv(path+file_name+'_skipped_'+extension, mode='w', index=False, na_rep='NaN', encoding='utf-8-sig')
