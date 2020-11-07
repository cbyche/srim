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
    temp_df = pd.DataFrame({'CF이익차액': fs.loc['영업CF'] - fs.loc['영업이익']}).T
    fs = pd.concat([fs, temp_df])
    #영업이익(+), 영업현금흐름(-) 체크 : 해당하면 1
    temp1 = fs.loc['영업이익'] > 0
    temp2 = fs.loc['영업CF'] < 0
    temp_df = pd.DataFrame(temp1 & temp2, columns=['CF이익검토']).T
    fs = pd.concat([fs, temp_df])
    #print(fs)
    return current_price, revised_shares, fh, fs

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

def calculate_roe(fh, year):
    roe = fh.loc['ROE',:]
    # +2year(E)
    if not math.isnan(roe[str(year+2)+'/12(E)']):        
        selected_roe = roe[str(year+2)+'/12(E)']
        roe_reference = str(year+2)+'/12(E)'
    # +1year (E)    
    elif not math.isnan(roe[str(year+1)+'/12(E)']):
        selected_roe = roe[str(year+1)+'/12(E)']
        roe_reference = str(year+1)+'/12(E)'
    # 0year (E) - weighted average
    elif not math.isnan(roe[str(year)+'/12(E)']):
        minus2 = float(roe[str(year-2)+'/12'])
        minus1 = float(roe[str(year-1)+'/12'])
        minus0 = float(roe[str(year)+'/12(E)'])
        selected_roe = calculate_weighted_average(minus2, minus1, minus0)
        roe_reference = str(year)+'/12(E)'
    # -1year - weighted average
    else:
        minus2 = float(roe[str(year-3)+'/12'])
        minus1 = float(roe[str(year-2)+'/12'])
        minus0 = float(roe[str(year-1)+'/12'])
        selected_roe = calculate_weighted_average(minus2, minus1, minus0)
        roe_reference = str(year-1)+'/12'
    return selected_roe, roe_reference

def calculate_srim(shares, Ke, fh, current_year):
    last_year = current_year - 1;    
    #extract&determine roe
    roe, roe_reference = calculate_roe(fh, current_year)
    #extract&determine B0 : 지배주주지분
    B0 = fh.loc['지배주주지분',str(last_year)+'/12'] * 10**8
    discount_factor = 1
    sell_price = calculate_price(B0, roe, Ke, shares, discount_factor)
    discount_factor = 0.9
    moderate_price = calculate_price(B0, roe, Ke, shares, discount_factor)    
    discount_factor = 0.8
    buy_price = calculate_price(B0, roe, Ke, shares, discount_factor)
    return buy_price, moderate_price, sell_price, roe, roe_reference



# start main
current_year = datetime.now().year

required_ror_percent = get_required_rate_of_return()
#print(required_ror_percent)

krx_list = get_krx_list()
#print(krx_list)

result_df = pd.DataFrame()

count_total = 0
count_record = 0
count_skip = 0
#for iter in range(0,len(krx_list)) :
for iter in range(91,len(krx_list)) :
    count_total += 1
    
    start = timeit.default_timer()
    #time.sleep(0.5)
    print('Iter: ', iter, '\t Name: ', krx_list.iloc[iter]['name'])  

    name = krx_list.iloc[iter]['name']
    if name.find('스팩') != -1:
        count_skip += 1
        print('Skip ', name)
        continue


    code = krx_list.iloc[iter]['code']
    html_snapshot, html_fs = get_html_fnguide(code)

    current_price, shares, fh, fs = parse_fnguide(html_snapshot, html_fs)
    #print('current_price\n', current_price, '\n\n\n')
    #print('shares\n', shares, '\n\n\n')
    #print('fh\n', fh, '\n\n\n')
    #print('fs\n', fs, '\n\n\n')

    buy_price, moderate_price, sell_price, roe, roe_reference = calculate_srim(shares, required_ror_percent, fh, current_year)
    #print('')
    #print('current_price: \t', current_price)
    #print('buy_price: \t', buy_price)
    #print('moderate_price: \t', moderate_price)
    #print('sell_price: \t', sell_price)
    #print('roe: \t', roe)
    #print('roe_reference: \t', roe_reference)
    #print('')

    code = krx_list.iloc[iter]['code']
    name = krx_list.iloc[iter]['name']
    current_price = round(current_price)
    buy_price = round(buy_price)
    undervalued_rate_buy = round((buy_price - current_price)/current_price * 100, 2)
    moderate_price = round(moderate_price)
    undervalued_rate_moderate = round((moderate_price - current_price)/current_price * 100, 2)
    sell_price = round(sell_price)
    undervalued_rate_sell = round((sell_price - current_price)/current_price * 100, 2)
    roe = roe
    roe_reference = roe_reference
    CF_alerts = int(pd.DataFrame(fs.loc['CF이익검토']).sum())
    devidend_rate = fh.loc['배당수익률'].loc[str(current_year-1)+'/12']
    industry = krx_list.iloc[iter]['industry']
    product = krx_list.iloc[iter]['product']

    temp_result_df = pd.DataFrame({'code':[code], 'name':[name], '현재가':[current_price], '매수가격':[buy_price], '매수가격대비(%)':[undervalued_rate_buy], '적정가격':[moderate_price], '적정가격대비(%)':[undervalued_rate_moderate], '매도가격':[sell_price], '매도가격대비(%)':[undervalued_rate_sell], 'ROE(%)':[roe], 'ROE기준':[roe_reference], 'CF위험(회)':[CF_alerts], '배당수익률(%)':[devidend_rate], '업종':[industry], '주요제품':[product]})
    result_df = pd.concat([result_df, temp_result_df])
    #print(result_df)

    count_record += 1
    stop = timeit.default_timer()
    print('Iter: ', iter, '\t Name: ', name, '\tTime: ', stop - start)

#print(result_df)

path = str(pathlib.Path().absolute()) + '\\'
file_name = str(datetime.now().date()) + '.csv'
result_df.to_csv(path+file_name, mode='w', index=False, na_rep='NaN', encoding='utf-8-sig')

#%%
print(krx_list.iloc[11])