# Raw data: dimensions of macro indicators and how to move between them

An open educational and working kit about **what a macro data series actually holds and what it can be
turned into**. The same number `1.2` can be a monthly price increase, trillions of roubles since January or
the unemployment share. Before drawing a chart, computing a share of GDP or converting to dollars, you need to
know what exactly was published — and only then decide which transformations make sense.

Everything runs on plain Excel files in this folder — no database and no environment setup required.
The notebook is bilingual: the language is switched with one line, `LANG = "ru"` or `LANG = "en"`.

The third repository of the exit10 series: [seasonal adjustment](https://github.com/MikeMike13/SEASONAL) →
[trend extraction](https://github.com/MikeMike13/TREND) → raw data.

[Русский](README.md) · **English**

---

## What is in the repository

| File | What it is |
|---|---|
| `raw_data_master_pgh.ipynb` | The notebook. Indicator characteristics (`metric`, `transf`, `dim`, `currency`, `mult`, `stock_flow`, `eop_avg`, `freq`, `real_nominal`), stocks and flows, percent and percentage points, real vs nominal, currencies, the ratio to GDP. A "what derives from what" transformation map with proofs on real series. One figure with every metric of one indicator. Thirteen live examples — one per indicator type. |
| `transform.py` | The module, about 70 functions: aggregation of stocks and flows, every kind of growth rate (m/m, y/y, year-to-date, cmlt/cmlt), decumulation of cumulative series, chain indices, currency conversion, the ratio to GDP, deflating and decomposing nominal growth, the `available()` hint and the `explain()` "translator", exit10-style charts. |
| `raw_data_ru.pdf` | The presentation, 31 slides, in Russian. Numbers from the news — and what can be done with them next. |
| `raw_data_en.pdf` | The same in English. |
| `RAW_DATA/` | 14 series in Excel: Rosstat, the Treasury, the Bank of Russia (list below). |
| `requirements.txt` | Dependencies. |
| [`LICENSE`](LICENSE) | MIT for the code, CC BY 4.0 for the materials. |
| [`CITATION.cff`](CITATION.cff) | Data for GitHub's "Cite this repository" button. |

The data format is simple: one series — one file `<TICKER>.xlsx` with two columns, `Date` and `Value`, dates
at the end of the period. The characteristics of each series are described in the notebook, in the
`MANUAL_CHARACTERISTICS` table. To add your own series, put the file into `RAW_DATA/` and add its characteristics.

### Data

| Ticker | Series | Characteristics | From |
|---|---|---|---|
| `RU_GDP_Q_RS` | Nominal GDP, Rosstat | flow, RUB, billions, quarterly | 1995 |
| `RU_GDPR_Q_RS` | Real GDP, 2021 prices, Rosstat | flow, RUB, billions, quarterly, real | 1995 |
| `RU_KBK_0_FED_M_FT` | Federal budget revenue, Treasury | flow, RUB, cumulative since January | 2006 |
| `RU_EXPG_Q_CB` | Exports of goods, balance of payments, Bank of Russia | flow, USD, millions, quarterly | 1994 |
| `RU_RES_M_CB` | International reserves, Bank of Russia | stock, USD, billions, end of month | 1994 |
| `RU_M2XXFX_M_CB` | Money supply M2X ex FX revaluation, Bank of Russia | growth vs end of last year (ytd) | 2015 |
| `RU_CPIMOM_CC_0_M_RS` | CPI, Rosstat | growth vs previous month | 2008 |
| `RU_CPIWOW_CC_0_W_RS` | Weekly CPI, Rosstat | growth vs previous week | 2008 |
| `RU_INDYOY_NC_2882_M_RS` | Industrial production, Rosstat | growth vs same month last year | 2014 |
| `RU_INVCMLT_Q_RS` | Fixed investment, Rosstat | year-to-date vs same period last year | 2016 |
| `RU_CP_1820_M_RS` | Natural gas production, Rosstat | flow, m³, millions, monthly | 2008 |
| `RU_UNEMPLR_M_RS` | Unemployment rate, Rosstat | share, % | 1999 |
| `RATE_RU_KEYRATE_CBR` | Key rate, Bank of Russia | rate, % per annum, daily | 2013 |
| `FX_RUBUSD_D` | Rouble exchange rate | RUB per 1 USD, daily | 1992 |

---

## Installation

```bash
git clone https://github.com/MikeMike13/MACRO_RAW_DATA.git
cd MACRO_RAW_DATA
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter lab
```

Python 3.10 or newer is required. Open `raw_data_master_pgh.ipynb`, set the language in the first cell and
run the whole notebook.

---

## Where to start

To get the idea in ten minutes — the presentation `raw_data_en.pdf`. It starts with four numbers from the
news that have four different dimensions and shows what can be done with each of them next.

To understand it properly — the notebook. Sections 2–4 are the theory and the transformation map, section 5 is
one figure with every metric of one indicator, section 6 the live examples, section 7 a template for your own
calculation.

To compute your own series — the functions in `transform.py` take explicit arguments (frequency, series type,
currency) and work with any series, not only with the examples in the notebook.

---

## What to know before applying it

**Every transformation goes through the level.** From a year-to-date series the level is recovered exactly,
from m/m and "vs December" up to a factor, from y/y and cmlt/cmlt only given a whole known base year. This
decides what can and cannot be derived from a series.

**Flows are summed, stocks taken at the end, prices averaged.** The same principle picks the FX rate: a flow
at the average rate, a stock at the rate on the date. The gap between them reaches 19%.

**"Computable" does not mean "meaningful".** A rate y/y in percent, a sum of stocks over a year or cubic metres
over GDP in roubles — the module will compute them; `available()` will hint that the result means nothing, but
will not forbid it. Responsibility for the meaning stays with the analyst.

**The characteristics of the series in `RAW_DATA/` are described by hand.** If you take a series from another
source, check `mult` and `real_nominal`: a scale error means a thousandfold discrepancy.

---

## Licence and citation

The repository has two licences, and the split is deliberate.

**Code** — `transform.py` and the code cells of the notebook — under
**[MIT](https://opensource.org/licenses/MIT)**: use it freely, including in closed commercial products,
keeping the copyright notice.

**Materials** — the explanatory text of the notebook, the presentations, the README and the charts — under
**[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**: copy, adapt and use them, including
commercially, crediting the author and indicating whether changes were made.

MIT is a licence for software, and distributing explanations and slides under it would be a stretch. CC BY was
designed for texts and illustrations and requires attribution in any use, including a retelling in an article
or lecture.

The full texts of both licences are in [LICENSE](LICENSE), together with the terms for the data and for the
media quotes in the presentations.

If the materials were useful in a publication or research:

```
exit10.ru. Raw data: dimensions of macro indicators and how to move between them. 2026.
https://github.com/MikeMike13/MACRO_RAW_DATA
```

GitHub shows a "Cite this repository" button on the repository page — it takes the data from `CITATION.cff`
and produces a ready reference in several formats.

---

## Feedback

Found an error in a calculation or in the text — open an issue. Comments on the series characteristics and on
the "what derives from what" rules are especially valuable: in borderline cases we deliberately chose the
stricter option, but may have got something wrong.

[exit10.ru](https://exit10.ru)
