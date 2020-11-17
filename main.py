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

import utils

exclude_list = ['스팩', '리츠', '증권', '은행', '홀딩스']

required_ror_percent = utils.get_required_rate_of_return()
#print(required_ror_percent)

krx_list = utils.get_krx_list()
#print(krx_list)

result_df = pd.DataFrame()
skip_df = pd.DataFrame()

path = str(pathlib.Path().absolute()) + '\\'
file_name = str(datetime.now().date())
extension = '.csv'

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
    if utils.check_skip_this_company(name, exclude_list):
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
        result_df.to_csv(path+file_name+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
        skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
        print('write!')
        result_df = pd.DataFrame()
        skip_df = pd.DataFrame()

#print(result_df)
result_df.to_csv(path+file_name+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')
skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=False, index=False, na_rep='NaN', encoding='utf-8-sig')

stop_total = timeit.default_timer()
print('Total Processing Time : ', format((stop_total-start_total)/60, '.1f'), ' mins')


