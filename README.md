# srim

## Environment
- Python 3.8.3
- conda 4.9.0


## How to Run
```
$python main.py
```

## Input
- None

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
- Devidend

## History
### v0.2 (Scheduled)
- Toal equity - Controlling shareholder
  - Reflection of future growth of 10 years
### v0.1 (2020.11.08)
- ROE
  - If consensus exists, then I use it.
  - If not, I use weighted averaged ROE for 3 years
- Total equity - Controlling shareholder
  - the latest settlement year
- Excluded from analysis
  - Companies related with SPAC, REITs, Bank, Finance
  - Companies with unformatted financial statement
  - Companies having problems with ROE or total equity (ex. complete encroachment, not provided)

  