import pandas as pd
import bs4
import os

import getKrx

krxList = getKrx.getAllCodeName()
print(krxList)

compCode = getKrx.getCode('삼성전자')
print(compCode)

compName = getKrx.getName('005930')
print(compName)
