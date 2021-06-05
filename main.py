# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import os
import requests
import math
from datetime import datetime
import pathlib
import timeit
import time
import sys
import multiprocessing

import utils

if __name__ == '__main__':

    procs = []
    num_process = min(multiprocessing.cpu_count() - 1, 4);
    sema = multiprocessing.Semaphore(num_process)

    exclude_list_endswith = ['스팩', '리츠', '증권', '은행', '홀딩스', '지주', '건설', '화재', '종금', '캐피탈', '투자']
    exclude_list_exact = ['한국테크놀로지그룹', '인터파크', '아세아', 'CJ', 'LG', '경동인베스트', '엘브이엠씨', '대웅', '아모레퍼시픽그룹', '지투알', 'BGF', '코오롱', 'GS', 'SK', '한화', '현대모비스', 'DL', 'HDC', '효성', '동원개발', '금호산업', '휴온스글로벌']; #holdings
    exclude_list_contain = ['스팩']

    required_ror_percent = utils.get_required_rate_of_return()

    path = str(pathlib.Path().absolute()) + '\\'
    file_name = str(datetime.now().date()) + '_ROE' + str(required_ror_percent)
    extension = '.csv'

    krx_list = utils.get_krx_list()
    #print(krx_list)
    if len(sys.argv) > 1 :
        new_krx_list = pd.DataFrame()
        with open(sys.argv[1], 'rt', encoding='utf-8-sig') as f:
            input_list = f.read().splitlines()
        for item in input_list:
            temp = krx_list[krx_list['name']==item]
            if (temp.empty) :
                print('[Failed] Please check the company name :', item)
            new_krx_list = pd.concat([new_krx_list, temp])
        krx_list = new_krx_list
        file_name = file_name + '_from_list'

    result_column_names = ['code', 'name', '현재가', '매수가격', '적정가격', '매도가격', '최종가격', '매수가격수익률(%)', '적정가격수익률(%)', '매도가격수익률(%)', '최종가격수익률(%)', 'ROE(%)', 'ROE기준년도', '배당수익률(%)', '배당성향(%)', '현금흐름위험(회)', '현금흐름/영업이익(4개년도평균)', '순이익(4분기누적)', '순이익적자(4분기횟수)', '영업이익(4분기누적)', '영업이익적자(4분기횟수)', '업종', '주요제품']
    skip_column_names = ['code', 'name', 'reason']
    result_df = pd.DataFrame(columns=result_column_names)
    skip_df = pd.DataFrame(columns=skip_column_names)
    result_df.to_csv(path+file_name+extension, mode='a', header=True, index=False, na_rep='NaN', encoding='utf-8-sig')
    skip_df.to_csv(path+file_name+'_skipped'+extension, mode='a', header=True, index=False, na_rep='NaN', encoding='utf-8-sig')

    start_time = timeit.default_timer()

    for idx, row in krx_list.iterrows():
        sema.acquire()
        proc=multiprocessing.Process(target=utils.run, args=(sema, path, file_name, extension, exclude_list_endswith, exclude_list_exact, exclude_list_contain, required_ror_percent, idx, row,))
        procs.append(proc)
        proc.start()

    for proc in procs:
        proc.join()

    stop_time = timeit.default_timer()
    print('Total Processing Time : ', format((stop_time-start_time)/60, '.1f'), ' mins')
    print('Required Return of Rate : ', required_ror_percent, ' %')
