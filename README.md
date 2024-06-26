# srim

## Environment

- Python 3.8.3
- conda 4.9.0

## How to Run

If you want analyze all companies, (It takes about an hour)
```
$python main.py
```

If you want analyze certain list of companies
```
$python main.py company_list.txt
```

## Input

- If you want analyze certain list of companies
  - Make a txt file which lists names of companies
  - Run main.py with this txt file as an argument
  - Company names should be separated by enter

## Output

- *'date'*.csv : RIM analysis results
- *'date'*_skipped.csv : Unanalyzed lists

## Program Procedure

1. Get all lists in KRX stock market
2. Get the rate of return of BBB- grade corporate bonds
3. Get 'Financial Statement' of each company
4. Analysis each company by Residual Income Model (RIM)
5. Make outputs

## Provided Data in Output

- Analyzed buying, selling, proper prices
- Analyzed expected rate of return
- Used ROE
- The number of cash flow risk since last 3 years
  - operating profit (+) && operating cash flow (-)
- Ratio of cash flow to business profit
- Controlling interests for last 4 quaters
- Operating profits for last 4 quaters
- Devidend

## Tips

- Filtering
  - Filtering out if 'the number of cash flow risk' exists
  - Filtering out if 'ratio of cash flow to business profilt' < 0.X
  - Filtering out if 'devidend' doesn't exist
  - Filtering out if 'ROE' < 'expected rate of return'
  - Filtering out if controlling interests and operating profits are less than 0
- Finding companies with 'current price' < 'buy price'
- Taking a first-hand look at the financial statements of those companies
- Choosing companies to invest in

## History

### v0.31 (2021.04.03)

- Update price in output
  - Assumption in book : excess profit remains & reflects infinite years
  - Assumption in lecture : ROE remains & refelects 10 years
  - buy price = min(sell price in book, sell price in lecture)
  - proper price = min(proper price in book, proper price in lecture) : sell 1/3
  - sell price = min(sell price in book, sell price in lecture) : sell 1/3
  - last price = max(sell price in book, sell price in lecture) : sell 1/3

### v0.3 (2021.03.27)

- Total equity for Controlling shareholder
  - Reflection of future growth of 10 years

### v0.23 (2021.02.20)

- Apply multiprocessing 

### v0.22 (2021.02.11)

- Add reporting values
  - Controlling interests for last 4 quaters
  - Operating profits for last 4 quaters

### v0.21 (2020.11.25)

- Excluded from analysis
  - Companies related with SPAC, REITs, Bank, Finance, Holdings, and Constructions
    - S-RIM can't adequatly analysis these kinds of industries

### v0.2 (2020.11.17)

- Analyze only the specified list
  - Can receive txt file which lists the company names you want to analyze as an argument

### v0.1 (2020.11.08)

- ROE
  - If consensus exists, then I use it.
  - If not, I use weighted averaged ROE for 3 years
- Total equity - Controlling shareholder
  - the latest settlement year
- Excluded from analysis
  - Companies related with SPAC, REITs, Bank, Finance, and holdings
    - S-RIM can't adequatly analysis these kinds of industries
  - Companies with unformatted financial statement
  - Companies having problems with ROE or total equity (ex. complete encroachment, not provided)
