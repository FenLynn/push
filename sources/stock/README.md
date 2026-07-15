# Stock market snapshot

The `stock` workflow runs on A-share trading days at 11:30 and 15:05 Beijing time.
Its full-market dataframe is used for the Push report and for the two statistics that
cannot be obtained from the compact realtime API:

- average percentage change
- median percentage change

When at least 1,000 market rows and both statistics are valid, the workflow overwrites
the fixed KV key `dashboard:snapshot:stock:latest`. The payload records the trade date,
the `midday` or `close` session, both values, and the sample size. Failed or incomplete
runs do not overwrite the previous valid snapshot, and no date-suffixed KV keys are
created.

`sci-worker` reads this snapshot only for average and median change. Realtime breadth,
turnover, sectors, rankings, ETF rankings, limit counts, and dragon-tiger data use
compact Eastmoney aggregate/list endpoints, so interactive clients never wait for the
full-market scan.
