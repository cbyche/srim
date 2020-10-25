def getKrxFile(fileName):
    import pandas as pd
    import bs4
    import os

    currentPwd = os.getcwd()
    fileName = 'data.xlsx'
    path = currentPwd + '\\' + fileName

    krxList = pd.read_excel(path)
    krxList = krxList[['종목코드', '기업명']]
    krxList['종목코드'] = krxList['종목코드'].map('{:06d}'.format)
    krxList = krxList.sort_values(by='종목코드')
    return krxList


def getAllCodeName():
        
    krxList = getKrxFile()
    return krxList


def getCode(name):

    krxList = getKrxFile()
    selectedItem = krxList[krxList['기업명'] == name]
    
    return selectedItem.iloc[0].종목코드


def getName(code):
    
    krxList = getKrxFile()
    selectedItem = krxList[krxList['종목코드'] == code]
    
    return selectedItem.iloc[0].기업명