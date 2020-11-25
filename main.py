#%%
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
import sys

import utils


exclude_list_endswith = ['스팩', '리츠', '증권', '은행', '홀딩스', '지주', '건설']
exclude_list_exact = ['한국테크놀로지그룹', '인터파크', '아세아', 'CJ', 'LG', '경동인베스트', '엘브이엠씨', '대웅', '아모레퍼시픽그룹', '지투알', 'BGF', '코오롱', 'GS', 'SK']; #holdings
exclude_list_contain = ['스팩']

path = str(pathlib.Path().absolute()) + '\\'
file_name = str(datetime.now().date())
extension = '.csv'

required_ror_percent = utils.get_required_rate_of_return()

krx_list = utils.get_krx_list()
#print(krx_list)
if len(sys.argv) > 1 :
    new_krx_list = pd.DataFrame()
    with open(sys.argv[1], 'rt', encoding='UTF8') as f:
        input_list = f.read().splitlines()
    for item in input_list:
        temp = krx_list[krx_list['name']==item]
        if (temp.empty) :
            print('[Failed] Please check the company name :', item)
        new_krx_list = pd.concat([new_krx_list, temp])
    krx_list = new_krx_list
    file_name = file_name+'_from_list'


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

    # check_skip_this_company
    if utils.check_skip_this_company(name, exclude_list_endswith, exclude_list_exact, exclude_list_contain):
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', '분석 제외 대상')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['분석 제외 대상']})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    # get_html_fnguide
    status, msg, html_snapshot, html_fs = utils.get_html_fnguide(code)
    if status == False:
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', 'Error on get_html_fnguide ('+msg+')')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on get_html_fnguide : '+msg]})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    # parse_fnguide
    status, msg, current_price, shares, fh, fs = utils.parse_fnguide(html_snapshot, html_fs)
    if status == False:
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', 'Error on parse_fnguide ('+msg+')')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on parse_fnguide : '+msg]})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    # calculate_srim
    status, msg, buy_price, proper_price, sell_price, roe, roe_reference = utils.calculate_srim(shares, required_ror_percent, fh)
    if status == False:
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', 'Error on calculate_srim ('+msg+')')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on calculate_srim : '+msg]})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue

    # organize_result
    status, msg, temp_result_df = utils.organize_result(code, name, current_price, buy_price, proper_price, sell_price, roe, roe_reference, fh, fs, krx_list.iloc[iter]['industry'], krx_list.iloc[iter]['product'])
    if status == False:
        count_skip += 1
        print('[Failed] Iter: ', iter, '\t Code: ', code, '\t Name: ', name, '\t Reason:', 'Error on organize_result ('+msg+')')
        temp_skip_df = pd.DataFrame({'code':[code], 'name':[name], 'reason':['Error on organize_result : '+msg]})
        skip_df = pd.concat([skip_df, temp_skip_df])
        continue
    result_df = pd.concat([result_df, temp_result_df])
    #print(result_df)

    count_record += 1
    stop = timeit.default_timer()
    print('[Successful] Iter: ', iter, '/', len(krx_list), '\t Code: ', code, '\t Name: ', name, '\tTime: ', format(stop - start,'.2f'))

    # write to csv file
    if not (iter % 10):
        result_header = False
        skip_header = False
        if not os.path.isfile(path+file_name+extension): result_header = True
        if not os.path.isfile(path+file_name+'_skipped'+extension): skip_header = True
        result_df.to_csv(path+file_name+extension, mode='a', header=result_header, index=False, na_rep='NaN', encoding='utf-8-sig')
        skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=skip_header, index=False, na_rep='NaN', encoding='utf-8-sig')
        result_df = pd.DataFrame()
        skip_df = pd.DataFrame()

#print(result_df)
result_df.to_csv(path+file_name+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')

stop_total = timeit.default_timer()
print('Total Processing Time : ', format((stop_total-start_total)/60, '.1f'), ' mins')

print('Required Return of Rate : ', required_ror_percent, ' %')
