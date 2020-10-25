#%%
import pandas as pd
import bs4
import requests

code = '005930'

giCode = 'A' + code
cID = ''
menuYn = 'Y'
reportGB = 'D' #D: 연결, B: 별도

fnSSUrl = 'http://comp.fnguide.com/SVO2/asp/SVD_Main.asp?pGB=1&gicode=' + giCode + '&cID=&MenuYn=' + menuYn + '&ReportGB=' + reportGB + '&NewMenuID=101&stkGb=701'
#fnSSUrl = 'http://comp.fnguide.com/SVO2/asp/SVD_Main.asp?pGB=1&gicode=A005930&cID=&MenuYn=Y&ReportGB=D&NewMenuID=101&stkGb=701'
fnSSPage = requests.get(fnSSUrl)
fnSSTables=pd.read_html(fnSSPage.text)

siseHyunHwang = fnSSTables[0].set_index([0]) #종가, 발행주식수(보통주/우선주)
jujuGubunHyunaHwang = fnSSTables[4].set_index(['주주구분']) #자기주식 (자사수+자사주신탁)
financialHighlightAnnual = fnSSTables[11].set_index(['IFRS(연결)']) #ROE, 지배주주지분, 배당수익률, DPS(주당배당금), ROA, EPS, BPS

print(siseHyunHwang)
print(jujuGubunHyunaHwang)
print(financialHighlightAnnual)
#10 연결 전체
#11 연결 연간
#12 연결 분기
#13 별도 전체
#14 별도 연간
#15 별도 분기

#%%
code = '005930'

giCode = 'A' + code
cID = ''
menuYn = 'Y'
reportGB = 'D' #D:연결, B:별도

fnFSurl = 'http://comp.fnguide.com/SVO2/asp/SVD_Finance.asp?pGB=1&gicode=' + giCode + '&cID=&MenuYn=' + menuYn + '&ReportGB=' + reportGB + '&NewMenuID=103&stkGb=701'
fnFSUrl = 'http://comp.fnguide.com/SVO2/asp/SVD_Finance.asp?pGB=1&gicode=A005930&cID=&MenuYn=Y&ReportGB=&NewMenuID=103&stkGb=701'
fnFSPage = requests.get(fnFSUrl)
fnFSTables=pd.read_html(fnFSPage.text)

# 연결
#0 : 손익계산서 연간
#1 : 손익계산서 분기
#2 : 재무상태표 연간
#3 : 재무상태표 분기
#4 : 현금흐름표 연간
#5 : 현금흐름표 분기

IncomeStatementAnnual = fnFSTables[0].set_index(['IFRS(연결)']) # 영업이익, 당기순이익, 지배주주순이익, 계속영업이익, 중단영업이익
IncomeStatementQuarter = fnFSTables[1].set_index(['IFRS(연결)'])
CashFlowStatementAnnual = fnFSTables[4].set_index(['IFRS(연결)']) # 영업현금흐름
CashFlowStatementQuarter = fnFSTables[5].set_index(['IFRS(연결)'])
print(IncomeStatementAnnual)
print(IncomeStatementQuarter)
print(CashFlowStatementAnnual)
print(CashFlowStatementQuarter)
