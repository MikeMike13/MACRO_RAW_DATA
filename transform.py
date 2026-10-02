# -*- coding: utf-8 -*-
# ============================================================================
#  transform -- dimensions of macro indicators and conversions between them
#
#  Автор:       exit10.ru
#  Лицензия:    MIT (код). Пояснительные материалы -- CC BY 4.0.
#
#  Author:      exit10.ru
#  Licence:     MIT (code). The explanatory materials -- CC BY 4.0.
# ============================================================================
"""transform -- what an indicator series actually holds and what it can be turned into.
Version 0.1.

An indicator in the sovdb database is a table (Date, Value) plus a row of CHARACTERISTICS
in the catalog `macro_indicators`: metric, transf, dim, currency, mult, stock_flow, eop_avg,
freq, sa, real_nominal. The characteristics say what the number is; this module turns them
into arithmetic: levels and units, aggregation of stocks and flows, growth rates of every
kind, cumulative series, currency conversion, ratios to GDP, real vs nominal.

Usage:

    import transform as tf
    pal = tf.econ_style("light")
    chars = tf.read_characteristics_db(conn)          # or tf.characteristics_from_records([...])
    s = tf.load_series("RU_GDP_Q_RS", chars, source="files", folder="RAW_DATA")

Design rule: the low-level functions (pop, yoy, decumulate, aggregate, convert, pct_gdp ...)
take explicit arguments and never check whether the operation "makes sense". That check
is `available()`, and it is advisory only: the analyst is responsible for what is computed.

Contents:
  * language & plotting style -- set_lang, tr, econ_style, chart_frame, set_section,
                                 plot_series, season_chart, plot_all_metrics
  * characteristics           -- normalize_characteristics, characteristics_from_records,
                                 read_characteristics_db, kind_of
  * data access               -- db_read_raw, file_read_raw, to_series, load_series
  * units & formatting        -- to_units, unit_label, fmt_amount, fmt_period
  * aggregation               -- aggregate, rolling
  * growth & cumulation       -- growth_x, pop, yoy, diff_pp, chain, ytd, decumulate, cumulate,
                                 mom_from_ytd, cmlt_cmlt, roll12_from_cmlt, level_from_yoy,
                                 level_from_cmlt_cmlt
  * real vs nominal           -- deflator, deflate, decompose_growth
  * currencies                -- fx_at, convert, convert_by_chars
  * ratio to GDP              -- pct_gdp
  * rules & interpretation    -- available, avail_table, avail_line, explain
  * year profiles & errors    -- year_profile, plot_year_profile, plot_year_range,
                                 compare_estimates
  * indicator types           -- INDICATOR_TYPES, find_example

Language: every comment and docstring is written in English and followed by its Russian
translation. User-facing strings switch with tf.set_lang("ru" | "en").

[RU] transform -- что лежит в ряду индикатора и во что его можно превратить. Версия 0.1.

Индикатор в базе sovdb -- это таблица (Date, Value) и строка ХАРАКТЕРИСТИК в каталоге
`macro_indicators`: metric, transf, dim, currency, mult, stock_flow, eop_avg, freq, sa,
real_nominal. Характеристики говорят, что это за число; модуль превращает их в арифметику:
уровни и единицы, агрегацию запасов и потоков, приросты всех видов, накопленные ряды,
пересчёт валют, отношение к ВВП, реальное и номинальное.

Правило устройства: низкоуровневые функции (pop, yoy, decumulate, aggregate, convert,
pct_gdp ...) принимают явные аргументы и никогда не проверяют, «имеет ли смысл» операция.
Такая проверка -- `available()`, и она только подсказывает: за то, что считается,
отвечает аналитик.

Язык: каждый комментарий и докстринг написан по-английски, за ним -- русский перевод.
Строки, которые видит пользователь, переключаются через tf.set_lang("ru" | "en").
"""

__version__ = "0.1"

import os

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ======================================================================
#  LANGUAGE
#  ЯЗЫК
# ======================================================================
LANG = "ru"


def set_lang(lang):
    """Set the language of every user-facing string: "ru" or "en".

    [RU] Устанавливает язык всех пользовательских строк: "ru" или "en".
    """
    global LANG
    if lang not in ("ru", "en"):
        raise ValueError('LANG must be "ru" or "en" / LANG должен быть "ru" или "en"')
    LANG = lang
    return LANG


def tr(ru, en):
    """Return the variant for the current language.

    [RU] Возвращает вариант для текущего языка.
    """
    return en if LANG == "en" else ru


def tx(entry):
    """Pick the current-language item from a {"ru": ..., "en": ...} entry; other objects pass through.

    [RU] Выбирает элемент текущего языка из записи {"ru": ..., "en": ...}; прочее возвращается как есть.
    """
    if isinstance(entry, dict) and "ru" in entry and "en" in entry:
        return entry["en"] if LANG == "en" else entry["ru"]
    return entry


def show_md(entry):
    """Render a {"ru": ..., "en": ...} Markdown block in the current language -- the notebook's
    replacement for static Markdown cells, which cannot switch language.

    [RU] Отображает Markdown-блок {"ru": ..., "en": ...} на текущем языке -- замена статическим
    Markdown-ячейкам блокнота, которые не умеют переключать язык.
    """
    from IPython.display import Markdown, display
    display(Markdown(tx(entry)))


# ======================================================================
#  PLOTTING STYLE (exit10, the same as in seasonal_toolbox)
#  СТИЛЬ ОТРИСОВКИ (exit10, тот же, что в seasonal_toolbox)
# ======================================================================
PALETTE_LIGHT = {
    "bg": "#FAF5E9", "text": "#16283B",
    "lazur": "#1D4E7E", "zoloto": "#D9A13B", "volna": "#3E7E7A",
    "korall": "#C05A3E", "sliva": "#7C6A9C",
    "grid": "#16283B", "muted": "#16283B",
}
PALETTE_DARK = {
    "bg": "#171613", "text": "#F0EDE4",
    "lazur": "#79B6D0", "zoloto": "#E8BA5E", "volna": "#6FBBA8",
    "korall": "#E0836A", "sliva": "#B3A0CE",
    "grid": "#F0EDE4", "muted": "#F0EDE4",
}
CYCLE_ORDER = ["lazur", "zoloto", "volna", "korall", "sliva"]
pal = PALETTE_LIGHT

_installed = {f.name for f in fm.fontManager.ttflist}
FONT_TITLE = "Lora" if "Lora" in _installed else "serif"
FONT_LABEL = "DejaVu Sans" if "DejaVu Sans" in _installed else "sans-serif"

# Chart kicker = number and name of the current section; updated by set_section().
# Рубрика графика = номер и название текущего раздела; обновляется set_section().
CURRENT_SECTION = ("", "")


def econ_style(mode="light"):
    """Apply the exit10 plotting style: warm light or graphite dark background, azure as
    the main colour, gold as the accent. Updates the module-level `pal`.

    [RU] Применяет стиль exit10: тёплый светлый или графитовый тёмный фон, лазурь --
    основной цвет, золото -- акцент. Обновляет модульную `pal`.
    """
    global pal
    pal = PALETTE_DARK if mode == "dark" else PALETTE_LIGHT
    mpl.rcParams.update({
        "figure.facecolor": pal["bg"], "axes.facecolor": pal["bg"], "savefig.facecolor": pal["bg"],
        "text.color": pal["text"], "axes.labelcolor": pal["text"],
        "xtick.color": pal["text"], "ytick.color": pal["text"], "axes.edgecolor": pal["text"],
        "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": pal["grid"], "grid.alpha": 0.28,
        "grid.linewidth": 0.75, "grid.linestyle": (0, (1, 2)),
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": True, "axes.linewidth": 0.7,
        "font.family": FONT_LABEL, "font.size": 9,
        "axes.titlesize": 14, "axes.titleweight": "regular", "axes.labelsize": 8.5,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "legend.frameon": False, "figure.figsize": [11, 5.2], "lines.linewidth": 2.0,
        "axes.prop_cycle": mpl.cycler(color=[pal[k] for k in CYCLE_ORDER]),
        "xtick.bottom": True, "ytick.left": False,
    })
    return pal


def cycle_colors(n, pal_=None):
    """Colours for n series, cycling through the palette.

    [RU] Цвета для n рядов -- по кругу палитры.
    """
    p = pal_ or pal
    return [p[CYCLE_ORDER[i % len(CYCLE_ORDER)]] for i in range(n)]


def set_section(number, name):
    """Declare the section the following charts belong to; shown as the kicker.

    [RU] Объявляет раздел, к которому относятся следующие графики; он выводится рубрикой.
    """
    global CURRENT_SECTION
    CURRENT_SECTION = (number, name)


def annotate_source(ax, text=None, y=-0.14):
    """Write the source credit under the axes.

    [RU] Подпись источника под осями.
    """
    text = text if text is not None else tr("Источник: exit10.ru", "Source: exit10.ru")
    ax.text(0.0, y, text, transform=ax.transAxes, fontsize=7.5,
            color=pal["text"], alpha=0.6, family=FONT_LABEL, ha="left")


def chart_frame(ax, title, subtitle=None, source=None, title_size=14, kicker=True):
    """Kicker (section) + title (a conclusion, not a label) + subtitle (units / method)
    + source -- identical for every chart. On a multi-panel figure the kicker is drawn once.

    [RU] Рубрика (раздел) + заголовок (вывод, а не ярлык) + подзаголовок (единицы / метод)
    + источник -- одинаково для каждого графика. На фигуре из нескольких панелей рубрика
    рисуется один раз.
    """
    fig = ax.figure
    num, name = CURRENT_SECTION
    name = tx(name)
    if kicker and name and not getattr(fig, "_kicker_drawn", False):
        ax.text(0, 1.14 if subtitle else 1.08, f"{num}. {name}".upper() if num else str(name).upper(),
                transform=ax.transAxes, fontsize=7.5, fontweight="bold",
                color=pal["zoloto"], family=FONT_LABEL, ha="left")
        fig._kicker_drawn = True
    ax.set_title(title, loc="left", fontfamily=FONT_TITLE, fontsize=title_size,
                 color=pal["text"], pad=18 if subtitle else 10)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=8.5,
                color=pal["text"], alpha=0.65, family=FONT_LABEL, ha="left")
    if source is not False:
        annotate_source(ax, source)


# ======================================================================
#  CONSTANTS AND DICTIONARIES
#  КОНСТАНТЫ И СЛОВАРИ
# ======================================================================
PPY = {"D": None, "W": 52, "M": 12, "Q": 4, "Y": 1}            # periods per year | периодов в году
FREQ_NAME = {"D": "день", "W": "неделя", "M": "месяц", "Q": "квартал", "Y": "год"}

TRANSF_ALIASES = {
    "none": "none", "": "none", "nan": "none",
    "cmlt": "cmlt",                                   # cumulative since January | накопленным итогом с начала года
    "cmlt/cmlt": "cmlt_cmlt", "cmlt_cmlt": "cmlt_cmlt", "cmltcmlt": "cmlt_cmlt",
    "ytd": "ytd",                                     # growth vs end of previous year | прирост к концу прошлого года
    "mom": "mom", "qoq": "qoq", "wow": "wow", "pop": "pop",
    "yoy": "yoy",
}
METRIC_ALIASES = {"index": "index", "%": "%", "pct": "%", "rate": "rate",
                  "%gdp": "%gdp", "% gdp": "%gdp", "%ввп": "%gdp"}
KNOWN_TRANSF = set(TRANSF_ALIASES.values())
POP_TRANSF = {"mom", "qoq", "wow", "pop"}            # growth vs previous period | прирост к предыдущему периоду

AGG_HOW = {"flow": "sum", "stock": "last", "avg": "mean"}    # how to go to a lower frequency | как сворачивать в более низкую частоту
FX_HOW = {"flow": "mean", "stock": "last", "avg": "mean"}    # which FX rate: average or end of period | какой курс: средний или на конец

MULT_TXT = {1: "единицы", 1e3: "тысячи", 1e6: "миллионы", 1e9: "миллиарды", 1e12: "триллионы"}
CCY_TXT = {"RUB": "руб.", "USD": "долл.", "EUR": "евро", "KZT": "тенге", "CNY": "юаней"}
CCY_TXT_EN = {"RUB": "RUB", "USD": "USD", "EUR": "EUR", "KZT": "KZT", "CNY": "CNY"}
DIM_TXT = {"items": "шт.", "km": "км", "m": "м", "m2": "м²", "m3": "м³", "t": "т",
           "persons": "чел.", "kwh": "кВт·ч"}
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
          "сентябрь", "октябрь", "ноябрь", "декабрь"]

# ======================================================================
#  CHARACTERISTICS
#  The catalog row describing an indicator. In the seasonal toolbox the word "passport"
#  means the adjustment settings; here we deliberately say "characteristics".
#  ХАРАКТЕРИСТИКИ
#  Строка каталога, описывающая индикатор. В сезонном модуле «паспорт» -- это настройки
#  корректировки; здесь сознательно говорим «характеристики».
# ======================================================================
CHAR_DEFAULTS = dict(metric="index", transf="none", dim="none", currency="none", stock_flow="none",
                     eop_avg="none", freq="M", mult=1, sa=False, ca=False, real_nominal="none",
                     short_name_rus="", source_org="", region_level_name="country")


def _clean(col, lower=True):
    s = col.astype(object).where(col.notna(), "none").astype(str).str.strip()
    s = s.str.lower() if lower else s.str.upper()
    return s.replace({"nan": "none", "": "none", "NAN": "none", "NONE": "none"})


def normalize_characteristics(df):
    """Bring a characteristics table to one canonical form: lower-case codes, aliases
    (cmlt/cmlt -> cmlt_cmlt, %GDP -> %gdp), numeric mult, boolean sa/ca. Missing columns
    are filled with defaults. Returns a DataFrame indexed by ticker.

    [RU] Приводит таблицу характеристик к единому виду: коды в нижнем регистре, синонимы
    (cmlt/cmlt -> cmlt_cmlt, %GDP -> %gdp), числовой mult, логические sa/ca. Недостающие
    колонки заполняются значениями по умолчанию. Возвращает DataFrame с индексом ticker.
    """
    df = df.copy()
    for c, v in CHAR_DEFAULTS.items():
        if c not in df.columns:
            df[c] = v
    for c in ["metric", "transf", "dim", "stock_flow", "eop_avg", "real_nominal"]:
        df[c] = _clean(df[c])
    df["currency"] = _clean(df["currency"], lower=False)
    df["freq"] = df["freq"].astype(str).str.strip().str.upper()
    df["metric"] = df["metric"].map(lambda x: METRIC_ALIASES.get(x, x))
    df["transf"] = df["transf"].map(lambda x: TRANSF_ALIASES.get(x, x))
    df["mult"] = pd.to_numeric(df["mult"], errors="coerce").fillna(1.0)
    for c in ["sa", "ca"]:
        df[c] = df[c].astype(str).str.strip().str.lower().isin(["true", "t", "1", "yes", "y", "1.0"])
    return df.drop_duplicates("ticker", keep="last").set_index("ticker", drop=False)


def characteristics_from_records(records):
    """Characteristics entered by hand: a list of dicts (one per ticker) -> normalized table.

    [RU] Характеристики, введённые вручную: список словарей (по одному на тикер) ->
    нормализованная таблица.
    """
    return normalize_characteristics(pd.DataFrame(records))


def read_characteristics_db(conn, schema="sovdb_schema", table="macro_indicators"):
    """Read the whole catalog from the database and normalize it.

    [RU] Читает весь каталог из базы и нормализует его.
    """
    return normalize_characteristics(_query(conn, f"SELECT * FROM {schema}.{table}"))


def get_chars(chars, ticker):
    """Characteristics of one ticker as a dict (None if absent).

    [RU] Характеристики одного тикера в виде словаря (None, если нет).
    """
    if ticker not in chars.index:
        return None
    c = chars.loc[ticker].to_dict()
    c["ticker"] = ticker
    return c


def kind_of(c):
    """Series type for aggregation and FX: 'flow' (sum over the period), 'stock' (snapshot
    at a date) or 'avg' (average over the period -- prices, rates, FX).

    [RU] Тип ряда для агрегации и пересчёта по курсу: 'flow' (поток за период), 'stock'
    (запас на дату) или 'avg' (среднее за период -- цены, ставки, курсы).
    """
    if c["stock_flow"] == "flow":
        return "flow"
    if c.get("eop_avg") == "avg":
        return "avg"
    if c["stock_flow"] == "stock":
        return "stock"
    return "avg"


# ======================================================================
#  DATA ACCESS: database or Excel files (one ticker -- one file)
#  ДОСТУП К ДАННЫМ: база или Excel-файлы (один тикер -- один файл)
# ======================================================================
def _query(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def db_read_raw(conn, ticker, schema="sovdb_schema"):
    """Read one indicator table (Date, Value) from the database; None if it does not exist.

    [RU] Читает таблицу одного индикатора (Date, Value) из базы; None, если таблицы нет.
    """
    try:
        return _query(conn, f'SELECT "Date", "Value" FROM {schema}."{ticker}" ORDER BY "Date"')
    except Exception:
        conn.rollback()        # otherwise the transaction stays aborted | иначе транзакция останется в ошибке
        return None


def file_read_raw(ticker, folder="."):
    """Read <folder>/<ticker>.xlsx (or .csv) with columns Date, Value; None if absent.

    [RU] Читает <folder>/<ticker>.xlsx (или .csv) с колонками Date, Value; None, если файла нет.
    """
    for ext in (".xlsx", ".csv"):
        path = os.path.join(folder, ticker + ext)
        if os.path.exists(path):
            df = pd.read_csv(path) if ext == ".csv" else pd.read_excel(path)
            return df[["Date", "Value"]]
    return None


def to_series(df, freq):
    """DataFrame(Date, Value) -> Series. M/Q/Y: a regular PeriodIndex (gaps become NaN),
    so it does not matter whether a month is dated by its first or its last day.
    D/W: ordinary dates.

    [RU] DataFrame(Date, Value) -> Series. M/Q/Y: регулярный PeriodIndex (пропуски -- NaN),
    поэтому не важно, датирован месяц первым или последним днём. D/W: обычные даты.
    """
    s = pd.Series(pd.to_numeric(df["Value"], errors="coerce").astype(float).values,
                  index=pd.to_datetime(df["Date"])).sort_index()
    if freq in ("M", "Q", "Y"):
        s.index = s.index.to_period(freq)
        s = s[~s.index.duplicated(keep="last")]
        s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq=freq))
    else:
        s = s[~s.index.duplicated(keep="last")]
    return s


def load_series(ticker, freq, source="files", conn=None, folder="."):
    """Load one indicator as a Series of the given frequency from the database or a file.

    [RU] Загружает один индикатор как Series заданной частоты из базы или из файла.
    """
    df = db_read_raw(conn, ticker) if source == "db" else file_read_raw(ticker, folder)
    if df is None or df.empty:
        return None
    return to_series(df, freq)


# ======================================================================
#  UNITS AND FORMATTING
#  ЕДИНИЦЫ И ФОРМАТИРОВАНИЕ
# ======================================================================
def to_units(s, mult):
    """Stored value -> absolute units (roubles, dollars, m3, items): Value x mult.
    `mult` may be a number or a characteristics dict.

    [RU] Значение из базы -> абсолютные единицы (рубли, доллары, м³, штуки): Value × mult.
    `mult` -- число или словарь характеристик.
    """
    m = mult["mult"] if isinstance(mult, dict) else mult
    return s * m


def unit_label(c):
    """Unit caption from characteristics: currency symbol or physical unit.

    [RU] Подпись единиц по характеристикам: валюта или натуральная единица.
    """
    if c["dim"] == "currency":
        return tr(CCY_TXT.get(c["currency"], c["currency"]), CCY_TXT_EN.get(c["currency"], c["currency"]))
    if c["dim"] == "none":
        return ""
    return tr(DIM_TXT.get(c["dim"], c["dim"]), {"m2": "m²", "m3": "m³", "items": "items", "persons": "persons"}
              .get(c["dim"], c["dim"]))


def name_of(c):
    """Indicator name in the current language: short_name_rus / short_name_en (or short_name), else ticker.

    [RU] Название индикатора на текущем языке: short_name_rus / short_name_en (или short_name), иначе тикер.
    """
    def ok(v):
        return isinstance(v, str) and v.strip() not in ("", "none", "nan")
    ru = c.get("short_name_rus")
    en = c.get("short_name_en") if ok(c.get("short_name_en")) else c.get("short_name")
    if LANG == "en":
        return en if ok(en) else (ru if ok(ru) else c["ticker"])
    return ru if ok(ru) else (en if ok(en) else c["ticker"])


def months_short():
    """Three-letter month labels in the current language.

    [RU] Трёхбуквенные подписи месяцев на текущем языке.
    """
    return [m[:3] for m in (MONTHS_EN if LANG == "en" else MONTHS)]


def quarter_labels():
    """Quarter axis labels in the current language.

    [RU] Подписи кварталов на текущем языке.
    """
    return ["Q1", "Q2", "Q3", "Q4"] if LANG == "en" else ["1 кв", "2 кв", "3 кв", "4 кв"]


def ru_num(x, nd=1):
    """Number in the current language's format: RU -- space thousands and decimal comma (1 234,5);
    EN -- comma thousands and decimal point (1,234.5).

    [RU] Число в формате текущего языка: RU -- пробел между тысячами и десятичная запятая
    (1 234,5); EN -- запятая между тысячами и десятичная точка (1,234.5).
    """
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if LANG == "en":
        return f"{x:,.{nd}f}"
    return f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")


def fmt_amount(v, unit=""):
    """12_300_000_000_000 -> '12,3 трлн руб.' (RU) or '12.3 tn RUB' (EN).

    [RU] 12_300_000_000_000 -> '12,3 трлн руб.' (RU) или '12.3 tn RUB' (EN).
    """
    names = [(1e12, "трлн", "tn"), (1e9, "млрд", "bn"), (1e6, "млн", "mn"), (1e3, "тыс.", "k")]
    for k, nm_ru, nm_en in names:
        if abs(v) >= k:
            return f"{ru_num(v / k)} {tr(nm_ru, nm_en)} {unit}".strip()
    return f"{ru_num(v)} {unit}".strip()


def fmt_period(per, freq):
    """Human-readable period: 'март 2026' / 'March 2026', '2 кв. 2026' / 'Q2 2026', '2026', a date.

    [RU] Период по-человечески: 'март 2026' / 'March 2026', '2 кв. 2026' / 'Q2 2026', '2026', дата.
    """
    if isinstance(per, pd.Period):
        if freq == "M":
            return f"{(MONTHS_EN if LANG == 'en' else MONTHS)[per.month - 1]} {per.year}"
        if freq == "Q":
            return tr(f"{per.quarter} кв. {per.year}", f"Q{per.quarter} {per.year}")
        if freq == "Y":
            return f"{per.year}"
    return pd.Timestamp(per).strftime(tr("%d.%m.%Y", "%d %b %Y"))


def pct(v, nd=2):
    """Signed percentage in the current language's format: +0,45% (RU) / +0.45% (EN).

    [RU] Процент со знаком в формате текущего языка: +0,45% (RU) / +0.45% (EN).
    """
    out = f"{v:+.{nd}f}%"
    return out if LANG == "en" else out.replace(".", ",")


def same(a, b):
    """True if two series coincide on their common non-empty dates.

    [RU] True, если два ряда совпадают на общих непустых датах.
    """
    j = pd.concat([a, b], axis=1).dropna()
    return len(j) > 0 and bool(np.allclose(j.iloc[:, 0], j.iloc[:, 1]))


# ======================================================================
#  AGGREGATION
#  АГРЕГАЦИЯ
# ======================================================================
def periods_per(src, tgt):
    """How many periods of frequency src fit into one period of tgt (M->Q = 3).

    [RU] Сколько периодов частоты src в одном периоде tgt (M->Q = 3).
    """
    return PPY[src] // PPY[tgt]


def aggregate(s, target, how, src_freq=None, full_only=True):
    """Convert a series to a lower frequency ('M', 'Q', 'Y').
    how: 'sum' (flows), 'last' (stocks), 'mean' (prices, rates).
    With full_only, incomplete periods are dropped: two months of a quarter are not a quarterly
    flow, and the last month of an incomplete quarter is not the end of the quarter.

    [RU] Перевод ряда в более низкую частоту ('M', 'Q', 'Y').
    how: 'sum' (потоки), 'last' (запасы), 'mean' (цены, ставки).
    При full_only неполные периоды отбрасываются: два месяца квартала -- не квартальный поток,
    а последний месяц неполного квартала -- не конец квартала.
    """
    s = s.dropna()
    if isinstance(s.index, pd.PeriodIndex):
        key = s.index.asfreq(target)
        if full_only and src_freq in ("M", "Q") and src_freq != target:
            if how == "last":     # the last sub-period itself is required | нужен именно последний подпериод
                is_end = s.index.asfreq(target).asfreq(src_freq, how="end") == s.index
                return s[is_end].groupby(key[is_end]).last()
            g = s.groupby(key)
            out = g.agg(how)
            return out[g.count() == periods_per(src_freq, target)]
        return s.groupby(key).agg(how)
    # daily and weekly series: group by calendar periods | дневные и недельные: группируем по календарю
    key = s.index.to_period(target)
    out = s.groupby(key).agg(how)
    if full_only and len(out):
        last_end = out.index[-1].end_time.normalize()
        if s.index[-1] < last_end - pd.Timedelta(days=7 if src_freq == "W" else 4):
            out = out.iloc[:-1]
    return out.reindex(pd.period_range(out.index.min(), out.index.max(), freq=target))


def rolling(s, freq, window="Y", how="sum"):
    """Rolling sum/mean over a window ('Y', 'Q', 'M') for a series of frequency freq.
    For daily series the window is calendar-based (365/91/30 days).

    [RU] Скользящая сумма/среднее за окно ('Y', 'Q', 'M') для ряда частоты freq.
    Для дневных рядов окно календарное (365/91/30 дней).
    """
    if freq == "D":
        days = {"Y": "365D", "Q": "91D", "M": "30D"}[window]
        r = s.dropna().rolling(days).agg(how)
        return r[r.index >= r.index[0] + pd.Timedelta(days)]
    n = periods_per(freq, window)
    return s.rolling(n, min_periods=n).agg(how)


# ======================================================================
#  GROWTH RATES AND CUMULATION
#  ПРИРОСТЫ И НАКОПЛЕНИЕ
# ======================================================================
def growth_x(s):
    """Growth in percent. If stored as 100+x (100.4), subtract 100; otherwise return as is.

    [RU] Прирост в процентах. Если хранится как 100+x (100,4) -- вычитаем 100.
    """
    if s.dropna().abs().median() > 50:
        return s - 100
    return s.copy()


def pop(level):
    """Growth vs the previous period, %: 100 (L(t)/L(t-1) - 1).

    [RU] Прирост к предыдущему периоду, %: 100 (L(t)/L(t-1) - 1).
    """
    return 100 * (level / level.shift(1) - 1)


def yoy(level, freq):
    """Growth vs the same period a year earlier, %. Weekly: a 52-week shift (approximate).

    [RU] Прирост к тому же периоду прошлого года, %. Недельные: сдвиг на 52 недели (приближённо).
    """
    return 100 * (level / level.shift(PPY[freq]) - 1)


def diff_pp(x, lag=1):
    """Change in percentage points: x(t) - x(t-lag). This is how changes of shares, rates and
    growth rates are measured (unemployment 4.5% -> 3.0% is -1.5 p.p., not -33%).

    [RU] Изменение в процентных пунктах: x(t) - x(t-lag). Так измеряют изменения долей, ставок
    и темпов роста (безработица 4,5% -> 3,0% -- это -1,5 п.п., а не -33%).
    """
    return x - x.shift(lag)


def chain(x, base=100.0):
    """Chain index from growth vs previous period: base x prod(1 + x/100).
    A level known only up to a factor: base 100 is arbitrary.

    [RU] Цепной индекс из приростов к предыдущему периоду: base × Π(1 + x/100).
    Уровень с точностью до множителя: база 100 выбрана произвольно.
    """
    return base * (1 + x / 100).cumprod()


def rebase(level, period):
    """Rescale so that the average over `period` (e.g. '2021') equals 100.

    [RU] Перебазирование: среднее за `period` (например, '2021') становится равным 100.
    """
    return 100 * level / level[period].mean()


def year_end_base(level, freq):
    """For every period -- the value in the last period of the previous year
    (December, Q4, the last week).

    [RU] Для каждого периода -- значение в последнем периоде предыдущего года
    (декабрь, 4 кв., последняя неделя).
    """
    yrs = level.index.year
    if freq in ("M", "Q"):
        sub = level.index.month if freq == "M" else level.index.quarter
        ends = level[sub == (12 if freq == "M" else 4)]
        ends = pd.Series(ends.values, index=ends.index.year)
    else:
        ln = level.dropna()
        ends = ln.groupby(ln.index.year).last()
    return pd.Series(np.asarray(yrs) - 1, index=level.index).map(ends)


def ytd(level, freq):
    """Growth vs the end of the previous year, %.

    [RU] Прирост к концу предыдущего года, %.
    """
    return 100 * (level / year_end_base(level, freq) - 1)


def first_in_year(s):
    """Mask: the first non-empty observation of every calendar year.

    [RU] Маска: первое непустое наблюдение каждого календарного года.
    """
    nn = s.notna()
    return nn & (nn.groupby(s.index.year).cumsum() == 1)


def first_sub(idx, freq):
    """Mask: the period is the first of its year (January, Q1).

    [RU] Маска: период -- первый в году (январь, 1 кв.).
    """
    if freq == "M":
        return idx.month == 1
    if freq == "Q":
        return idx.quarter == 1
    return np.zeros(len(idx), dtype=bool)


def decumulate(c):
    """Cumulative-since-January (cmlt) -> values for the period: the difference between
    neighbouring cumulative values within a year; the first value of a year is kept as is.

    [RU] Накопленный с начала года (cmlt) -> значения за период: разность соседних
    накопленных внутри года; первое значение года остаётся как есть.
    """
    d = c - c.groupby(c.index.year).shift(1)
    f = first_in_year(c)
    d[f] = c[f]
    return d


def lumped_periods(c, freq):
    """Periods that, after decumulation, hold the sum of several periods (the first value of a
    year is not January: the series starts mid-year or January is not published).

    [RU] Периоды, которые после разкопления содержат сумму нескольких периодов (первое
    значение года -- не январь: ряд начался в середине года или январь не публикуется).
    """
    f = first_in_year(c)
    return list(c.index[f & ~first_sub(c.index, freq)])


def cumulate(x):
    """Values for the period -> cumulative since January.

    [RU] Значения за период -> накопленным итогом с начала года.
    """
    return x.groupby(x.index.year).cumsum().where(x.notna())


def mom_from_ytd(y):
    """ytd (growth vs December, %) -> growth vs the previous period, %.
    1 + m(t) = (1 + ytd(t)) / (1 + ytd(t-1)) within a year; in January m = ytd.

    [RU] ytd (прирост к декабрю, %) -> прирост к предыдущему периоду, %.
    1 + m(t) = (1 + ytd(t)) / (1 + ytd(t-1)) внутри года; в январе m = ytd.
    """
    g = 1 + y / 100
    out = 100 * (g / g.groupby(g.index.year).shift(1) - 1)
    f = first_in_year(g)
    out[f] = y[f]
    return out


def cmlt_cmlt(level, freq):
    """Flow for the period -> 'January..t this year vs January..t last year', %.

    [RU] Поток за период -> «январь–t к январю–t прошлого года», %.
    """
    c = cumulate(level)
    return 100 * (c / c.shift(PPY[freq]) - 1)


def roll12_from_cmlt(c, freq):
    """Sum over the last 12 months (4 quarters) directly from cumulative values:
    S(t) = C(t) + C(December last year) - C(t - 1 year). Needs no decumulation and does not
    break when January is missing.

    [RU] Сумма за последние 12 месяцев (4 квартала) прямо из накопленных:
    S(t) = C(t) + C(декабрь прошлого года) - C(t - год). Не требует разкопления и не боится
    пропущенного января.
    """
    return c + year_end_base(c, freq) - c.shift(PPY[freq])


def level_from_yoy(g, base, freq):
    """Rebuild the level from yoy growth -- possible only when a whole year of levels (base)
    is known: L(t) = L(t-year) (1 + g(t)).

    [RU] Восстановление уровня из г/г -- возможно, только если известен целый год уровней
    (base): L(t) = L(t-год) (1 + g(t)).
    """
    k = PPY[freq]
    idx = pd.period_range(base.index.min(), g.index.max(), freq=freq)
    lv = base.reindex(idx).copy()
    gg = g.reindex(idx)
    for i in range(k, len(idx)):
        if np.isnan(lv.iloc[i]) and not np.isnan(gg.iloc[i]):
            lv.iloc[i] = lv.iloc[i - k] * (1 + gg.iloc[i] / 100)
    return lv


def level_from_cmlt_cmlt(cc, base, freq):
    """Rebuild the flow from cmlt/cmlt given one base year of flows.

    [RU] Восстановление потока из cmlt/cmlt при известном базовом годе потоков.
    """
    return decumulate(level_from_yoy(cc, cumulate(base), freq))


# ======================================================================
#  REAL VS NOMINAL
#  Nominal = volume x prices. Real = volume in constant prices of a base year (or physical
#  units). Their ratio is the price index (deflator).
#  РЕАЛЬНОЕ И НОМИНАЛЬНОЕ
#  Номинал = объём × цены. Реальный показатель -- объём в постоянных ценах базового года
#  (или в натуральных единицах). Их отношение -- индекс цен (дефлятор).
# ======================================================================
def deflator(nominal, real):
    """Implicit deflator: 100 x nominal / real (both in the same units and frequency).
    Equals 100 on average in the base year of the real series.

    [RU] Неявный дефлятор: 100 × номинал / реальный (одинаковые единицы и частота).
    В среднем за базовый год реального ряда равен 100.
    """
    return 100 * nominal / real


def deflate(nominal, price_index, base=None):
    """Nominal -> real: divide by a price index. With `base` (e.g. '2025-12') the result is in
    prices of that period; otherwise in prices of the index base (index = 100).

    [RU] Номинал -> реальный: делим на индекс цен. С `base` (например, '2025-12') результат --
    в ценах этого периода; иначе -- в ценах базы индекса (индекс = 100).
    """
    p = price_index.reindex(nominal.index)
    if base is not None:
        p = 100 * p / price_index[base].mean()
    return nominal / p * 100


def decompose_growth(nominal, real, freq, annual=False):
    """Split nominal yoy growth into real growth, price growth and the cross term:
    (1 + n) = (1 + r)(1 + p)  =>  n = r + p + r p / 100 (all in %).
    annual=True works on 4-quarter (12-month) rolling sums -- the growth of the 'year'.
    Returns a DataFrame: nominal, real, prices, cross.

    [RU] Раскладывает номинальный рост г/г на реальный рост, рост цен и перекрёстный член:
    (1 + n) = (1 + r)(1 + p)  =>  n = r + p + r p / 100 (всё в %).
    annual=True -- на скользящих суммах за 4 квартала (12 месяцев), т.е. рост «за год».
    Возвращает DataFrame: nominal, real, prices, cross.
    """
    if annual:
        nominal, real = rolling(nominal, freq, "Y", "sum"), rolling(real, freq, "Y", "sum")
    n, r = yoy(nominal, freq), yoy(real, freq)
    p = yoy(deflator(nominal, real), freq)
    return pd.DataFrame({"nominal": n, "real": r, "prices": p, "cross": r * p / 100})


# ======================================================================
#  CURRENCIES
#  FX series are stored as 'units of currency per 1 USD' (FX_RUBUSD_D ~ 80 roubles per dollar).
#  The dollar is the common denominator: x_B = x_A / (A per USD) x (B per USD).
#  ВАЛЮТЫ
#  Курсы хранятся как «единиц валюты за 1 USD» (FX_RUBUSD_D ≈ 80 рублей за доллар).
#  Доллар -- общий знаменатель: x_B = x_A / (A за USD) × (B за USD).
# ======================================================================
FX = {}          # registry: currency -> daily series 'currency per USD' | реестр: валюта -> дневной ряд «валюты за USD»


def set_fx(ccy, series):
    """Register the daily FX series for a currency (units of ccy per 1 USD).

    [RU] Регистрирует дневной ряд курса валюты (единиц ccy за 1 USD).
    """
    FX[ccy] = series.dropna()


def fx_at(ccy, index, freq, how, fx_table=None):
    """FX rate 'ccy per USD' aligned to a series index. M/Q/Y: average ('mean') or end of
    period ('last'); D/W: the rate on the observation date (weekly average for weekly flows).

    [RU] Курс «ccy за USD», приведённый к индексу ряда. M/Q/Y: средний ('mean') или на конец
    периода ('last'); D/W: курс на дату наблюдения (для недельных потоков -- среднее за неделю).
    """
    if ccy == "USD":
        return pd.Series(1.0, index=index)
    fx = (fx_table or FX)[ccy]
    if freq in ("M", "Q", "Y"):
        return aggregate(fx, freq, how, "D", full_only=False).reindex(index)
    r = fx.rolling("7D").mean() if (freq == "W" and how == "mean") else fx
    return r.reindex(r.index.union(index)).ffill().reindex(index)


def convert(s, from_ccy, to_ccy, freq, how, fx_table=None):
    """Convert a series of levels from one currency to another through the dollar.
    how='mean' for flows (average rate of the period), 'last' for stocks (end-of-period rate).

    [RU] Пересчёт ряда уровней из одной валюты в другую через доллар.
    how='mean' для потоков (средний курс периода), 'last' для запасов (курс на конец периода).
    """
    if from_ccy == to_ccy:
        return s.copy()
    return s / fx_at(from_ccy, s.index, freq, how, fx_table) * fx_at(to_ccy, s.index, freq, how, fx_table)


def convert_by_chars(s, c, to_ccy, fx_table=None):
    """Convert using the characteristics: rate by series type; a cmlt series is decumulated,
    converted month by month and cumulated back. Scale (mult) is preserved.

    [RU] Пересчёт по характеристикам: курс по типу ряда; накопленный ряд разкапливается,
    пересчитывается помесячно и снова накапливается. Масштаб (mult) сохраняется.
    """
    how = FX_HOW[kind_of(c)]
    if c["transf"] == "cmlt":
        return cumulate(convert(decumulate(s), c["currency"], to_ccy, c["freq"], how, fx_table))
    return convert(s, c["currency"], to_ccy, c["freq"], how, fx_table)


# ======================================================================
#  RATIO TO GDP
#  ОТНОШЕНИЕ К ВВП
# ======================================================================
def pct_gdp(x_units, gdp_q_units, freq, kind, mode="4q"):
    """Indicator as % of GDP. Both series in absolute units and in the GDP currency;
    gdp_q_units is quarterly GDP. Flow: 'q' -- quarter to quarterly GDP, '4q' -- sum of 4
    quarters to GDP over 4 quarters, 'y' -- calendar year. Stock: value at the end of the
    quarter ('4q') or year ('y') to GDP over the year. 'q' for a stock is computed too, but it
    is 4 times too high and seasonal -- the user decides.

    [RU] Индикатор в % ВВП. Оба ряда в абсолютных единицах и в валюте ВВП; gdp_q_units --
    квартальный ВВП. Поток: 'q' -- квартал к ВВП квартала, '4q' -- сумма 4 кварталов к ВВП
    за 4 квартала, 'y' -- календарный год. Запас: значение на конец квартала ('4q') или года
    ('y') к ВВП за год. 'q' для запаса тоже посчитается, но это завышение в 4 раза и
    сезонность -- решает пользователь.
    """
    g = gdp_q_units
    g4 = rolling(g, "Q", "Y", "sum")
    if kind == "flow":
        xq = x_units if freq == "Q" else aggregate(x_units, "Q", "sum", freq)
        xq = xq.reindex(pd.period_range(xq.index.min(), xq.index.max(), freq="Q"))
        if mode == "q":
            return 100 * xq / g.reindex(xq.index)
        if mode == "4q":
            return 100 * rolling(xq, "Q", "Y", "sum") / g4.reindex(xq.index)
        return 100 * aggregate(xq, "Y", "sum", "Q") / aggregate(g, "Y", "sum", "Q")
    xq = x_units if freq == "Q" else aggregate(x_units, "Q", AGG_HOW[kind], freq)
    if mode == "q":
        return 100 * xq / g.reindex(xq.index)
    if mode == "4q":
        return 100 * xq / g4.reindex(xq.index)
    return 100 * aggregate(xq, "Y", "last", "Q") / aggregate(g, "Y", "sum", "Q")


# ======================================================================
#  RULES: WHAT CAN BE DERIVED FROM WHAT (advisory, never enforced)
#  ПРАВИЛА: ЧТО ИЗ ЧЕГО ПОЛУЧАЕТСЯ (подсказка, а не запрет)
# ======================================================================
TARGETS = [("level", "уровень в единицах", "level in units"), ("chain", "цепной индекс", "chain index"),
           ("pop", "к пред. периоду", "vs previous period"), ("yoy", "г/г", "y/y"),
           ("ytd", "к декабрю (ytd)", "vs December (ytd)"), ("cmlt", "накопл. с начала года (cmlt)", "year-to-date sum (cmlt)"),
           ("cmlt_cmlt", "cmlt/cmlt", "cmlt/cmlt"), ("agg", "в квартал/год", "to quarter/year"),
           ("roll", "скользящее окно", "rolling window"), ("fx", "в другую валюту", "to another currency"),
           ("gdp", "%ВВП", "% of GDP"), ("real", "реальное ↔ номинальное", "real ↔ nominal"),
           ("smooth", "сглаживание", "smoothing")]


def targets():
    """[(key, label)] of the transformations in the current language.

    [RU] [(ключ, подпись)] преобразований на текущем языке.
    """
    return [(k, tr(ru, en)) for k, ru, en in TARGETS]


def available(c):
    """Which transformations are meaningful for an indicator with characteristics c.
    Returns {target: (status, note)}, status: '✓' yes, '✓*' only with extra data (an anchor level,
    a base year, a price index), '◇' computable but meaningless, '✗' not applicable.
    Advisory only: every function of the module computes regardless.

    [RU] Какие преобразования осмысленны для индикатора с характеристиками c.
    Возвращает {цель: (статус, пояснение)}, статус: '✓' можно, '✓*' только с дополнительными данными
    (якорь, базовый год, индекс цен), '◇' посчитать можно, но смысла нет, '✗' не применимо.
    Только подсказка: любая функция модуля посчитает независимо от неё.
    """
    m, t, k, f = c["metric"], c["transf"], kind_of(c), c["freq"]
    cur, rn, R = c["dim"] == "currency", c.get("real_nominal", "none"), {}

    def s(key, st, ru, en=None):
        R[key] = (st, tr(ru, en if en is not None else ru))

    yearly = (f == "Y")
    if rn == "real":
        real = ("✓", "уже реальный; номинал = реальный × дефлятор / 100", "already real; nominal = real × deflator / 100")
    elif rn == "nominal":
        real = ("✓*", "нужен индекс цен: уровень -- делением на него, прирост -- (1+n)/(1+p) − 1",
                "needs a price index: level -- divide by it, growth -- (1+n)/(1+p) − 1")
    else:
        real = ("✓*", "для номинального ряда нужен индекс цен; к ценам и натуральным единицам не применяется",
                "a nominal series needs a price index; not applicable to prices and physical units")
    not_cur = ("◇", "прирост к ВВП -- бессмыслица", "growth as % of GDP is meaningless")

    if m in ("%", "rate", "%gdp"):
        s("level", "✓", "ряд уже уровень в процентах", "the series is already a level in percent")
        s("chain", "◇", "перемножить можно, но цепной индекс доли или ставки ничего не значит",
          "can be chained, but a chain index of a share or rate means nothing")
        s("pop", "◇", "относительный прирост ставки или доли смысла не имеет; изменение -- в п.п.: x(t) − x(t−1)",
          "a relative change of a rate or share is meaningless; use p.p.: x(t) − x(t−1)")
        s("yoy", "◇", "«ставка г/г +30%» ничего не значит; изменение за год -- в п.п.: x(t) − x(t−год)",
          "'rate +30% y/y' means nothing; the annual change is in p.p.: x(t) − x(t−year)")
        s("ytd", "◇", "относительный прирост к декабрю смысла не имеет; в п.п.: x(t) − x(декабрь)",
          "a relative change vs December is meaningless; in p.p.: x(t) − x(December)")
        s("cmlt", "◇", "сложить ставки или доли можно, но сумма ничего не значит", "rates or shares can be summed, but the sum means nothing")
        s("cmlt_cmlt", "◇", "сложить ставки или доли можно, но сумма ничего не значит", "rates or shares can be summed, but the sum means nothing")
        s("agg", "✗" if yearly else "✓", "уже годовые" if yearly else "среднее за период (или значение на конец)",
          "already annual" if yearly else "average over the period (or end-of-period value)")
        s("roll", "✓", "скользящее среднее", "rolling mean")
        s("fx", "◇", "процент на курс поделить можно, но это бессмыслица", "dividing a percentage by an FX rate is meaningless")
        s("gdp", "✓" if m == "%gdp" else "◇", "уже отнесено к ВВП" if m == "%gdp" else "процент к рублям ВВП -- бессмыслица",
          "already a ratio to GDP" if m == "%gdp" else "a percentage over GDP in money is meaningless")
        if m == "rate":
            s("real", "✓*", "реальная ставка = ставка − инфляционные ожидания (ex ante); минус фактическая инфляция -- лишь грубая оценка ex post",
              "real rate = rate − inflation expectations (ex ante); minus actual inflation is only a rough ex post proxy")
        else:
            s("real", "◇", "отношение: цены в числителе и знаменателе сокращаются", "a ratio: prices cancel out")
        s("smooth", "✓", "скользящее среднее", "rolling mean")
        return R

    if t in ("none", "cmlt"):
        s("level", "✓", "уже уровень" if t == "none" else "разность соседних накопленных внутри года",
          "already a level" if t == "none" else "difference of neighbouring cumulative values within a year")
        s("chain", "✓", "уровень / уровень базового периода", "level / level in the base period")
        s("pop", "✓", "L(t) / L(t−1)")
        s("yoy", "✓", "L(t) / L(t−год)" + (" (52 недели -- приближённо)" if f == "W" else ""),
          "L(t) / L(t−year)" + (" (52 weeks -- approximate)" if f == "W" else ""))
        if k == "flow":
            s("ytd", "◇", "посчитать можно, но поток к декабрю -- это сезонность, а не динамика; используйте cmlt/cmlt",
              "computable, but a flow vs December shows seasonality, not dynamics; use cmlt/cmlt")
            s("cmlt", "✓", "уже" if t == "cmlt" else "накопленная сумма внутри года",
              "already" if t == "cmlt" else "cumulative sum within the year")
            s("cmlt_cmlt", "✓", "накопленное к накопленному год назад", "cumulative vs cumulative a year earlier")
        else:
            s("ytd", "✓", "к значению в конце прошлого года", "vs the value at the end of last year")
            s("cmlt", "◇", "сложить снимки на даты (или средние) можно, но сумма ничего не значит",
              "snapshots (or averages) can be summed, but the sum means nothing")
            s("cmlt_cmlt", "◇", "сложить снимки на даты (или средние) можно, но сумма ничего не значит",
              "snapshots (or averages) can be summed, but the sum means nothing")
        agg_ru = {"flow": "сумма полных периодов", "stock": "значение на конец периода", "avg": "среднее"}[k]
        agg_en = {"flow": "sum of complete periods", "stock": "end-of-period value", "avg": "average"}[k]
        s("agg", "✗" if yearly else "✓", "уже годовые" if yearly else
          agg_ru + ("; для cmlt -- значение на конец квартала и приведение к квартальным" if t == "cmlt" else ""),
          "already annual" if yearly else agg_en + ("; for cmlt -- end-of-quarter value, then decumulate" if t == "cmlt" else ""))
        s("roll", "✗" if yearly else "✓", "уже годовые" if yearly else
          ("сумма за год (годовой объём) или среднее" if k == "flow" else "скользящее среднее (средний уровень)"),
          "already annual" if yearly else
          ("sum over a year (annual volume) or mean" if k == "flow" else "rolling mean (average level)"))
        if cur:
            how_ru = "по среднему курсу периода" if FX_HOW[k] == "mean" else "по курсу на конец периода"
            how_en = "at the period-average rate" if FX_HOW[k] == "mean" else "at the end-of-period rate"
            s("fx", "✓", how_ru + ("; cmlt -- привести к месячным, пересчитать, накопить" if t == "cmlt" else ""),
              how_en + ("; cmlt -- decumulate, convert, cumulate back" if t == "cmlt" else ""))
            s("gdp", "✓",
              ("квартал к кварталу ВВП и 4 кв. к 4 кв." if k == "flow" else "на конец квартала к ВВП за 4 кв.")
              + ("; сначала свернуть в квартал" if f in ("D", "W", "M") else "")
              + ("; номинальный ВВП -- только к номинальному ряду" if rn == "real" else ""),
              ("quarter to quarterly GDP and 4Q to 4Q" if k == "flow" else "end of quarter to 4-quarter GDP")
              + ("; aggregate to quarters first" if f in ("D", "W", "M") else "")
              + ("; nominal GDP only for a nominal series" if rn == "real" else ""))
        else:
            s("fx", "◇", f"не валюта (dim = {c['dim']}): делить на курс можно, смысла нет",
              f"not money (dim = {c['dim']}): dividing by an FX rate is meaningless")
            s("gdp", "◇", f"не валюта (dim = {c['dim']}): {c['dim']} к рублям ВВП -- бессмыслица",
              f"not money (dim = {c['dim']}): {c['dim']} over GDP in money is meaningless")
        if not cur and c["dim"] != "none":
            s("real", "✓", "натуральные единицы -- это уже физический объём", "physical units are already a real volume")
        else:
            s("real", real[0], real[1], real[2])
        s("smooth", "✓", "скользящее среднее", "rolling mean")
        return R

    if t in POP_TRANSF or t == "ytd":
        s("level", "✓*", "с точностью до множителя; в единицах -- если известен хотя бы один уровень (якорь)",
          "up to a factor; in units -- only if at least one level is known (an anchor)")
        s("chain", "✓", "Π(1+x)" if t != "ytd" else "ytd → м/м (отношением внутри года) → Π(1+x)",
          "Π(1+x)" if t != "ytd" else "ytd → m/m (ratio within the year) → Π(1+x)")
        s("pop", "✓", "уже" if t != "ytd" else "отношение соседних (1+ytd) внутри года",
          "already" if t != "ytd" else "ratio of neighbouring (1+ytd) within the year")
        s("yoy", "✓*" if f == "W" else "✓", "по цепному индексу" + (" (52 недели -- приближённо)" if f == "W" else ""),
          "from the chain index" + (" (52 weeks -- approximate)" if f == "W" else ""))
        s("ytd", "✓", "уже" if t == "ytd" else "цепной индекс к концу прошлого года",
          "already" if t == "ytd" else "chain index vs the end of last year")
        s("cmlt", "✓*", "в единицах -- только с якорем", "in units -- only with an anchor")
        s("cmlt_cmlt", "✓" if k == "flow" else "◇",
          "масштаб сокращается: отношение сумм не зависит от базы" if k == "flow" else "не поток: сумма ничего не значит",
          "the scale cancels: a ratio of sums does not depend on the base" if k == "flow" else "not a flow: the sum means nothing")
        s("agg", "✓", "цепной индекс: среднее (цены) или сумма (поток) за период → к/к, г/г",
          "chain index: average (prices) or sum (flow) over the period → q/q, y/y")
        s("roll", "✓", "на цепном индексе, в относительных единицах", "on the chain index, in relative units")
        s("fx", "◇", "прирост безразмерен -- делить его на курс бессмысленно", "growth has no units -- dividing it by an FX rate is meaningless")
        if cur:
            s("gdp", "✓*", "нужен уровень в рублях -- якорь для цепного индекса", "needs a level in money -- an anchor for the chain index")
        else:
            s("gdp", *not_cur)
        s("real", real[0], real[1], real[2])
        s("smooth", "✓", "скользящее среднее", "rolling mean")
        return R

    if t == "yoy":
        base_ru = "только если известен целый год уровней: L(t) = L(t−год)·(1+g)"
        base_en = "only with a whole year of levels: L(t) = L(t−year)·(1+g)"
        for key in ["level", "chain", "pop", "ytd", "cmlt", "cmlt_cmlt"]:
            s(key, "✓*", base_ru, base_en)
        s("yoy", "✓", "уже", "already")
        s("agg", "✓*", "среднее г/г за квартал ≈ г/г квартала; точно -- только с уровнями (весами месяцев)",
          "average y/y over a quarter ≈ quarterly y/y; exact only with levels (monthly weights)")
        s("roll", "✓", "скользящее среднее г/г", "rolling mean of y/y")
        s("fx", "◇", "прирост безразмерен -- делить его на курс бессмысленно", "growth has no units -- dividing it by an FX rate is meaningless")
        if cur:
            s("gdp", "✓*", "нужен уровень в рублях -- базовый год", "needs a level in money -- a base year")
        else:
            s("gdp", *not_cur)
        s("real", real[0], real[1], real[2])
        s("smooth", "✓", "в конце ряда -- только нецентрированное окно", "at the end of the series -- trailing window only")
        return R

    if t == "cmlt_cmlt":
        base_ru = "только если известен базовый год потоков: C(t) = C(t−год)·(1+g), затем приведение к периодам"
        base_en = "only with a base year of flows: C(t) = C(t−year)·(1+g), then decumulate"
        for key in ["level", "chain", "pop", "yoy", "ytd", "cmlt"]:
            s(key, "✓*", base_ru, base_en)
        s("cmlt_cmlt", "✓", "уже", "already")
        s("agg", "✓", "значение за декабрь (4 кв.) = рост за год; концы кварталов -- за 1 кв., полугодие, 9 мес.",
          "the December (Q4) value = growth over the year; quarter ends -- Q1, H1, 9 months")
        s("roll", "◇", "усреднить можно, но внутри года значения не независимы -- каждое включает предыдущие",
          "can be averaged, but values within a year are not independent -- each includes the previous ones")
        s("fx", "◇", "прирост безразмерен -- делить его на курс бессмысленно", "growth has no units -- dividing it by an FX rate is meaningless")
        if cur:
            s("gdp", "✓*", "нужен уровень в рублях -- базовый год", "needs a level in money -- a base year")
        else:
            s("gdp", *not_cur)
        s("real", real[0], real[1], real[2])
        s("smooth", "◇", "сгладить можно, но внутри года значения не независимы", "can be smoothed, but values within a year are not independent")
        return R

    for key, _, _ in TARGETS:
        s(key, "?", f"неизвестное сочетание metric={m}, transf={t}", f"unknown combination metric={m}, transf={t}")
    return R


def avail_table(c):
    """available() as a table: transformation | status | how / why.

    [RU] available() в виде таблицы: преобразование | статус | как / почему.
    """
    R = available(c)
    return pd.DataFrame([(lab, *R[k]) for k, lab in targets()],
                        columns=[tr("преобразование", "transformation"), "", tr("как / почему", "how / why")])


def avail_line(c):
    """available() in Markdown lines: possible / needs extra data / computable but meaningless / not applicable.

    [RU] available() строками Markdown: можно / нужны доп. данные / можно, но без смысла / не применимо.
    """
    R, lab, out = available(c), dict(targets()), []
    for st, ru, en in [("✓", "можно", "possible"), ("✓*", "нужны доп. данные", "needs extra data"),
                       ("◇", "можно, но без смысла", "computable but meaningless"), ("✗", "не применимо", "not applicable")]:
        keys = [lab[k] for k, _ in targets() if R[k][0] == st]
        if keys:
            out.append(f"**{tr(ru, en)}:** " + ", ".join(keys))
    return "  \n".join(out)


def explain(c, s, at=-1, show=True):
    """Characteristics + the latest value -> a plain sentence: what exactly the published
    number means and what can be done with it. Returns Markdown (and displays it if show).

    [RU] Характеристики + последнее значение -> обычная фраза: что именно значит опубликованная
    цифра и что с ней можно делать. Возвращает Markdown (и показывает его, если show).
    """
    s = s.dropna()
    f, t, m, k = c["freq"], c["transf"], c["metric"], kind_of(c)
    per, v = s.index[at], s.iloc[at]
    unit = unit_label(c)
    rn = c.get("real_nominal", "none")
    P = fmt_period(per, f)
    nd0 = 2 if abs(v) < 1e6 else 0
    L = [f"**{name_of(c)}** (`{c['ticker']}`), {tr('источник', 'source')}: {c.get('source_org') or '—'}",
         f"{tr('Характеристики', 'Characteristics')}: metric=`{m}`, transf=`{t}`, dim=`{c['dim']}`, "
         f"currency=`{c['currency']}`, mult=`{c['mult']:g}`, stock_flow=`{c['stock_flow']}`, "
         f"eop_avg=`{c.get('eop_avg')}`, freq=`{f}`, real_nominal=`{rn}`, sa=`{c.get('sa')}`",
         tr(f"Последнее значение: **{ru_num(v, nd0)}** -- {P}.", f"Latest value: **{ru_num(v, nd0)}** -- {P}.")]
    if m == "%":
        L.append(tr(f"Смысл: доля **{ru_num(v, 2)}%**. Изменения считаются в п.п.; складывать по времени и переводить в валюту нельзя.",
                    f"Meaning: a share of **{ru_num(v, 2)}%**. Changes are measured in p.p.; it cannot be summed over time or converted to a currency."))
    elif m == "rate":
        L.append(tr(f"Смысл: ставка **{ru_num(v, 2)}% годовых** на {P}. За месяц при такой ставке набегает ≈{ru_num(v / 12, 2)}%. "
                    f"Реальная ставка -- за вычетом инфляционных ожиданий.",
                    f"Meaning: a rate of **{ru_num(v, 2)}% per annum** as of {P}. Over a month this accrues ≈{ru_num(v / 12, 2)}%. "
                    f"The real rate is net of inflation expectations."))
    elif m == "%gdp":
        L.append(tr(f"Смысл: **{ru_num(v, 2)}% ВВП**. Повторно к ВВП не относят; изменения -- в п.п.",
                    f"Meaning: **{ru_num(v, 2)}% of GDP**. Not divided by GDP again; changes are in p.p."))
    elif t == "none":
        amt = fmt_amount(v * c["mult"], unit) if unit else tr(f"{ru_num(v, 2)} пунктов индекса", f"{ru_num(v, 2)} index points")
        if k == "flow":
            L.append(tr(f"Смысл: **поток** -- **{amt}** за {P}. Потоки за соседние периоды складываются: квартал = сумма месяцев, год = сумма кварталов.",
                        f"Meaning: a **flow** -- **{amt}** in {P}. Flows of neighbouring periods add up: a quarter = sum of months, a year = sum of quarters."))
        elif k == "stock":
            L.append(tr(f"Смысл: **запас** -- **{amt}** по состоянию на {P}. Это снимок на дату: складывать снимки нельзя, в квартал/год берётся значение на конец.",
                        f"Meaning: a **stock** -- **{amt}** as of {P}. A snapshot at a date: snapshots are not summed; for a quarter/year take the end value."))
        else:
            L.append(tr(f"Смысл: **среднее за период** -- **{amt}** в среднем за {P}. В квартал/год -- среднее.",
                        f"Meaning: a **period average** -- **{amt}** on average in {P}. For a quarter/year -- the average."))
    elif t == "cmlt":
        prev = s[(s.index.year == per.year) & (s.index < per)]
        L.append(tr(f"Смысл: **накопленный итог** -- с начала {per.year} года по {P} включительно **{fmt_amount(v * c['mult'], unit)}**",
                    f"Meaning: a **year-to-date total** -- from the start of {per.year} through {P} **{fmt_amount(v * c['mult'], unit)}**"))
        if len(prev):
            d = fmt_amount((v - prev.iloc[-1]) * c["mult"], unit)
            L.append(tr(f"Только за {P}: {ru_num(v, nd0)} − {ru_num(prev.iloc[-1], nd0)} = **{d}** (разность соседних накопленных).",
                        f"For {P} alone: {ru_num(v, nd0)} − {ru_num(prev.iloc[-1], nd0)} = **{d}** (difference of neighbouring cumulative values)."))
    elif t in POP_TRANSF:
        x = growth_x(s).iloc[at]
        prd = {"mom": ("предыдущему месяцу", "the previous month"), "qoq": ("предыдущему кварталу", "the previous quarter"),
               "wow": ("предыдущей неделе", "the previous week"), "pop": ("предыдущему периоду", "the previous period")}[t]
        fmt100 = s.abs().median() > 50
        L.append(tr(f"Смысл: **{pct(x)} к {prd[0]}**" + (" (хранится как 100+x)" if fmt100 else "") + ".",
                    f"Meaning: **{pct(x)} vs {prd[1]}**" + (" (stored as 100+x)" if fmt100 else "") + "."))
        n = PPY.get(f) or 12
        ann = 100 * ((1 + x / 100) ** n - 1)
        if c.get("sa"):
            L.append(tr(f"Ряд сезонно сглажен -- можно аннуализировать: (1+x)^{n} − 1 = **{pct(ann, 1)}** в годовом выражении.",
                        f"The series is seasonally adjusted -- it can be annualised: (1+x)^{n} − 1 = **{pct(ann, 1)}** per annum."))
        else:
            L.append(tr(f"Ряд **не** очищен от сезонности: аннуализировать ({pct(ann, 1)}) нельзя -- сравнивайте с тем же периодом прошлых лет или с SA-оценкой.",
                        f"The series is **not** seasonally adjusted: annualising ({pct(ann, 1)}) is wrong -- compare with the same period of past years or with an SA estimate."))
    elif t == "yoy":
        x = growth_x(s).iloc[at]
        prev = f" ({fmt_period(per - PPY[f], f)})" if f in ("M", "Q") else ""
        L.append(tr(f"Смысл: **{pct(x)} к тому же периоду прошлого года**{prev}. Сезонность почти сокращается, но г/г запаздывает: отражает изменения за последние 12 месяцев целиком.",
                    f"Meaning: **{pct(x)} vs the same period a year earlier**{prev}. Seasonality mostly cancels, but y/y lags: it reflects the whole last 12 months."))
    elif t == "ytd":
        x = growth_x(s).iloc[at]
        fmt100 = s.abs().median() > 50
        L.append(tr(f"Смысл: **{pct(x)} к концу {per.year - 1} года**, т.е. с начала года" + (" (хранится как 100+x)" if fmt100 else "") + ".",
                    f"Meaning: **{pct(x)} vs the end of {per.year - 1}**, i.e. year to date" + (" (stored as 100+x)" if fmt100 else "") + "."))
    elif t == "cmlt_cmlt":
        x = growth_x(s).iloc[at]
        if f == "M":
            span = tr(f"январь–{MONTHS[per.month - 1]}", f"January–{MONTHS_EN[per.month - 1]}")
        else:
            span = tr(f"1–{per.quarter} кв.", f"Q1–Q{per.quarter}")
        more = tr("больше", "higher") if x >= 0 else tr("меньше", "lower")
        L.append(tr(f"Смысл: за **{span} {per.year}** на **{pct(x)}** {more}, чем за {span} {per.year - 1}. Значение за декабрь (4 кв.) -- рост за весь год.",
                    f"Meaning: **{span} {per.year}** is **{pct(x)}** {more} than {span} {per.year - 1}. The December (Q4) value is the growth over the whole year."))
    if rn == "nominal" and m == "index":
        L.append(tr("Ряд **номинальный** (в текущих ценах): его рост = рост объёма × рост цен.",
                    "The series is **nominal** (current prices): its growth = volume growth × price growth."))
    elif rn == "real" and m == "index":
        L.append(tr("Ряд **реальный** (в постоянных ценах или натуральных единицах): рост цен из него исключён.",
                    "The series is **real** (constant prices or physical units): price growth is excluded."))
    L.append(avail_line(c))
    md = "\n\n".join(L)
    if show:
        from IPython.display import Markdown, display
        display(Markdown(md))
    return md


# ======================================================================
#  INDICATOR TYPES (generic combinations of characteristics)
#  ТИПЫ ПОКАЗАТЕЛЕЙ (общие сочетания характеристик)
# ======================================================================
INDICATOR_TYPES = {
    "cur_flow_nominal": dict(title="Показатель в валюте, поток, номинальный", title_en="Money indicator, flow, nominal",
                             metric="index", transf="none", stock_flow="flow", dim="currency", ccy="base", real_nominal="nominal"),
    "cur_flow_real":    dict(title="Показатель в валюте, поток, реальный (в постоянных ценах)",
                             title_en="Money indicator, flow, real (constant prices)",
                             metric="index", transf="none", stock_flow="flow", dim="currency", ccy="base", real_nominal="real"),
    "cur_flow_cmlt":    dict(title="Показатель в валюте, поток, накопленным итогом с начала года",
                             title_en="Money indicator, flow, cumulative since January",
                             metric="index", transf="cmlt", stock_flow="flow", dim="currency"),
    "fcur_flow":        dict(title="Показатель в иностранной валюте, поток", title_en="Foreign-currency indicator, flow",
                             metric="index", transf="none", stock_flow="flow", dim="currency", ccy="foreign"),
    "fcur_stock":       dict(title="Показатель в иностранной валюте, запас", title_en="Foreign-currency indicator, stock",
                             metric="index", transf="none", stock_flow="stock", dim="currency", ccy="foreign"),
    "nat_flow":         dict(title="Показатель в натуральных единицах, поток", title_en="Physical-unit indicator, flow",
                             metric="index", transf="none", stock_flow="flow", dim_not=["currency", "none"]),
    "pop_growth":       dict(title="Прирост к предыдущему месяцу (кварталу)", title_en="Growth vs previous month (quarter)",
                             metric="index", transf=["mom", "qoq", "pop"]),
    "wow_growth":       dict(title="Прирост к предыдущей неделе", title_en="Growth vs previous week", metric="index", transf=["wow"]),
    "ytd_growth":       dict(title="Прирост к концу прошлого года (ytd)", title_en="Growth vs end of last year (ytd)",
                             metric="index", transf=["ytd"]),
    "yoy_growth":       dict(title="Прирост к тому же периоду прошлого года", title_en="Growth vs same period last year",
                             metric="index", transf=["yoy"]),
    "cmlt_cmlt":        dict(title="С начала года к тому же периоду прошлого года", title_en="Year-to-date vs same period last year",
                             metric="index", transf=["cmlt_cmlt"]),
    "share":            dict(title="Доля, %", title_en="Share, %", metric="%"),
    "rate":             dict(title="Ставка, % годовых", title_en="Rate, % per annum", metric="rate"),
}


def type_title(key):
    """Indicator type title in the current language.

    [RU] Название типа показателя на текущем языке.
    """
    t = INDICATOR_TYPES[key]
    return tr(t["title"], t.get("title_en", t["title"]))


def find_example(chars, key, base_ccy="RUB", exclude=()):
    """Pick an indicator of the given type from the characteristics table: filter by the type's
    fields, prefer Russian country-level, recent and long series. None if nothing fits.

    [RU] Подбирает индикатор заданного типа из таблицы характеристик: фильтр по полям типа,
    приоритет -- российские, уровня страны, свежие и длинные ряды. None, если ничего нет.
    """
    spec, c = INDICATOR_TYPES[key], chars[~chars["ticker"].isin(exclude)]
    for fld in ["metric", "transf", "stock_flow", "dim", "real_nominal"]:
        if fld in spec:
            vals = spec[fld] if isinstance(spec[fld], list) else [spec[fld]]
            c = c[c[fld].isin(vals)]
    if "dim_not" in spec:
        c = c[~c["dim"].isin(spec["dim_not"])]
    if spec.get("ccy") == "base":
        c = c[c["currency"] == base_ccy]
    elif spec.get("ccy") == "foreign":
        c = c[(c["currency"] != base_ccy) & (c["currency"] != "none")]
    c = c[~c["ticker"].str.startswith("FX_")]
    if c.empty:
        return None
    c = c.copy()
    c["score"] = c["ticker"].str.startswith("RU_").astype(int)
    c["score"] += (c["region_level_name"].astype(str).str.lower() == "country").astype(int)
    if "end_date" in c:
        end = pd.to_datetime(c["end_date"], errors="coerce")
        c["score"] += (end >= end.max() - pd.Timedelta(days=400)).astype(int)
    return c.sort_values("score", ascending=False)["ticker"].iloc[0]


# ======================================================================
#  CHARTS
#  ГРАФИКИ
# ======================================================================
def _x(idx):
    if isinstance(idx, pd.PeriodIndex):
        return idx.to_timestamp(how="start") + (idx.to_timestamp(how="end") - idx.to_timestamp(how="start")) / 2
    return idx


def _cut(s, start):
    s = s.dropna()
    if start is None:
        return s
    ts = s.index.to_timestamp() if isinstance(s.index, pd.PeriodIndex) else s.index
    return s[ts >= pd.Timestamp(start)]


def _draw(ax, s, color, kind="line", label=None, nd=1, ls="-", lw=1.8, value=True):
    if s.empty:
        return None
    x = _x(s.index)
    if kind == "bar":
        w = (np.median(np.diff(x.values)) / np.timedelta64(1, "D")) * 0.8 if len(x) > 1 else 20
        h = ax.bar(x, s.values, width=w, color=color, alpha=0.55, label=label)
    else:
        h, = ax.plot(x, s.values, color=color, lw=lw, ls=ls, label=label)
    if value:
        ax.text(x[-1], s.values[-1], " " + ru_num(s.values[-1], nd), color=color, fontsize=8, va="center")
    return h


def plot_series(series, title, subtitle=None, bars=(), right=(), dashed=(), start=None, hline=None,
                nd=1, figsize=None):
    """One exit10 chart: series = {label: Series}; bars -- drawn as columns, right -- on the
    right axis, dashed -- dashed lines; hline -- a horizontal reference line.

    [RU] Один график в стиле exit10: series = {подпись: Series}; bars -- столбиками, right -- на
    правой оси, dashed -- пунктиром; hline -- горизонтальная опорная линия.
    """
    fig, ax = plt.subplots(figsize=figsize)
    ax2 = ax.twinx() if right else None
    handles, cols = [], cycle_colors(len(series))
    for (lab, s), col in zip(series.items(), cols):
        a = ax2 if lab in right else ax
        h = _draw(a, _cut(s, start), col, "bar" if lab in bars else "line",
                  lab + (tr(", п.ш.", ", rhs") if lab in right else ""), nd, "--" if lab in dashed else "-")
        if h is not None:
            handles.append(h)
    if hline is not None:
        ax.axhline(hline, color=pal["muted"], lw=0.7)
    if ax2 is not None:
        ax2.grid(False)
        ax2.spines["bottom"].set_visible(False)
    chart_frame(ax, title, subtitle)
    ax.legend(handles=handles, loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.show()


def season_chart(level, freq, title, subtitle=None, years=6, nd=1):
    """Values by month (quarter) of the year, one line per year: the seasonal pattern.

    [RU] Значения по месяцам (кварталам) года, по линии на год: сезонный рисунок.
    """
    s = level.dropna()
    fig, ax = plt.subplots(figsize=(11, 4.6))
    yrs = sorted(set(s.index.year))[-years:]
    for i, y in enumerate(yrs):
        z = s[s.index.year == y]
        pos = z.index.month if freq == "M" else z.index.quarter
        col = pal["korall"] if y == yrs[-1] else pal["lazur"]
        ax.plot(pos, z.values, color=col, alpha=0.3 + 0.7 * (i + 1) / len(yrs), lw=1.6, marker="o", ms=3)
        ax.text(pos[-1], z.values[-1], f" {y}", fontsize=8, va="center", color=col)
    ax.set_xticks(range(1, 13) if freq == "M" else range(1, 5))
    ax.set_xticklabels(months_short() if freq == "M" else quarter_labels())
    chart_frame(ax, title, subtitle)
    plt.tight_layout()
    plt.show()


def all_metrics(level, freq, kind, ccy=None, base_ccy="RUB", fx_target="USD",
                gdp_q_units=None, fx_table=None, base_period=None):
    """Every standard metric that can be derived from a LEVEL series (in absolute units).
    kind: 'flow' | 'stock' | 'avg'. ccy -- currency of the level (None if not money);
    gdp_q_units -- quarterly GDP in base_ccy for the %GDP panel.
    Returns an ordered dict {key: (title, formula, series, style)}.

    [RU] Все стандартные метрики, которые получаются из ряда УРОВНЕЙ (в абсолютных единицах).
    kind: 'flow' | 'stock' | 'avg'. ccy -- валюта уровня (None, если не деньги);
    gdp_q_units -- квартальный ВВП в base_ccy для панели %ВВП.
    Возвращает упорядоченный словарь {ключ: (заголовок, формула, ряд, стиль)}.
    """
    k = PPY[freq]
    lag = {"M": "t−12", "Q": "t−4", "W": "t−52"}.get(freq, tr("t−год", "t−year"))
    win = {"M": tr("12 мес.", "12 months"), "Q": tr("4 кв.", "4 quarters"), "W": tr("52 нед.", "52 weeks")}.get(freq, tr("год", "year"))
    base_period = base_period or str(level.dropna().index[-1].year - 5)
    out = {}
    out["level"] = ({"flow": tr("Уровень: за период", "Level: over the period"),
                     "stock": tr("Уровень: на конец периода", "Level: end of period"),
                     "avg": tr("Уровень: в среднем за период", "Level: period average")}[kind],
                    "L(t)", level, "bar" if kind == "flow" else "line")
    out["pop"] = (tr("К предыдущему периоду, %", "Vs previous period, %"), "L(t) / L(t−1) − 1", pop(level), "bar")
    out["yoy"] = (tr("К тому же периоду прошлого года, %", "Vs same period last year, %"), f"L(t) / L({lag}) − 1",
                  yoy(level, freq), "line")
    if kind == "flow":
        out["cmlt"] = (tr("Накопленным итогом с начала года", "Cumulative since January"),
                       tr("C(t) = Σ L(январь … t)", "C(t) = Σ L(January … t)"), cumulate(level), "line")
        out["cmlt_cmlt"] = (tr("С начала года к тому же периоду прошлого года, %", "Year-to-date vs same period last year, %"),
                            f"C(t) / C({lag}) − 1", cmlt_cmlt(level, freq), "line")
        out["roll"] = (tr(f"Сумма за {win} (годовой объём)", f"Sum over {win} (annual volume)"), f"Σ L(t−{k - 1} … t)",
                       rolling(level, freq, "Y", "sum"), "line")
    else:
        out["ytd"] = (tr("К концу прошлого года, %", "Vs end of last year, %"), tr("L(t) / L(декабрь) − 1", "L(t) / L(December) − 1"),
                      ytd(level, freq), "line")
        out["roll"] = (tr(f"Среднее за {win}", f"Average over {win}"), f"Σ L(t−{k - 1} … t) / {k}",
                       rolling(level, freq, "Y", "mean"), "line")
    if freq == "M":
        q = aggregate(level, "Q", AGG_HOW[kind], "M")
        out["agg"] = ({"flow": tr("Квартальная сумма", "Quarterly sum"), "stock": tr("На конец квартала", "End of quarter"),
                       "avg": tr("Среднее за квартал", "Quarterly average")}[kind],
                      {"flow": tr("Σ L за 3 месяца", "Σ L over 3 months"), "stock": tr("L(март, июнь, сент., дек.)", "L(Mar, Jun, Sep, Dec)"),
                       "avg": tr("Σ L за 3 мес. / 3", "Σ L over 3 months / 3")}[kind],
                      q, "bar" if kind == "flow" else "line")
    elif freq == "Q":
        y_ = aggregate(level, "Y", AGG_HOW[kind], "Q")
        out["agg"] = ({"flow": tr("Годовая сумма", "Annual sum"), "stock": tr("На конец года", "End of year"),
                       "avg": tr("Среднее за год", "Annual average")}[kind],
                      {"flow": tr("Σ L за 4 квартала", "Σ L over 4 quarters"), "stock": tr("L(4 кв.)", "L(Q4)"),
                       "avg": tr("Σ L за 4 кв. / 4", "Σ L over 4 quarters / 4")}[kind], y_, "bar")
    out["chain"] = (tr(f"Индекс, среднее {base_period} = 100", f"Index, {base_period} average = 100"),
                    f"100 · L(t) / L̄({base_period})", rebase(level, base_period), "line")
    if ccy is not None and ccy != fx_target:
        how = FX_HOW[kind]
        conv = convert(level, ccy, fx_target, freq, how, fx_table)
        if kind == "flow":
            out["fx"] = (tr(f"В {fx_target}: сумма за {win}", f"In {fx_target}: sum over {win}"),
                         tr("Σ L(t), каждый период -- по среднему курсу периода", "Σ L(t), each period at its average rate"),
                         rolling(conv, freq, "Y", "sum"), "line")
        else:
            out["fx"] = (tr(f"В {fx_target}", f"In {fx_target}"), tr("L(t) по курсу на конец периода", "L(t) at the end-of-period rate"),
                         conv, "line")
    if ccy is not None and gdp_q_units is not None:
        x_base = level if ccy == base_ccy else convert(level, ccy, base_ccy, freq, FX_HOW[kind], fx_table)
        if kind == "flow":
            out["gdp_q"] = (tr("% ВВП: квартал к ВВП квартала", "% of GDP: quarter to quarterly GDP"),
                            tr("Σ L за квартал / ВВП квартала", "Σ L over the quarter / quarterly GDP"),
                            pct_gdp(x_base, gdp_q_units, freq, kind, "q"), "bar")
            out["gdp_4q"] = (tr("% ВВП: 4 квартала к ВВП за 4 квартала", "% of GDP: 4 quarters to 4-quarter GDP"),
                             tr("Σ L за 4 кв. / Σ ВВП за 4 кв.", "Σ L over 4Q / Σ GDP over 4Q"),
                             pct_gdp(x_base, gdp_q_units, freq, kind, "4q"), "line")
        else:
            out["gdp_4q"] = (tr("% ВВП: на конец квартала к ВВП за 4 квартала", "% of GDP: end of quarter to 4-quarter GDP"),
                             tr("L(конец кв.) / Σ ВВП за 4 кв.", "L(end of quarter) / Σ GDP over 4Q"),
                             pct_gdp(x_base, gdp_q_units, freq, kind, "4q"), "line")
    return out


def plot_all_metrics(metrics, title, subtitle=None, scale=1.0, scale_txt="", start=None, ncols=2):
    """Draw the output of all_metrics() on ONE figure: a grid of panels, each with its title and
    formula. Level-type panels are divided by `scale` (e.g. 1e12 with scale_txt 'трлн руб.').

    [RU] Рисует результат all_metrics() на ОДНОЙ фигуре: сетка панелей, у каждой -- заголовок и
    формула. Панели в единицах уровня делятся на `scale` (например, 1e12 и scale_txt 'трлн руб.').
    """
    level_keys = {"level", "cmlt", "roll", "agg"}
    n = len(metrics)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 2.75 * nrows + 1.2), squeeze=False)
    cols = cycle_colors(n)
    for i, (key, (ttl, formula, s, style)) in enumerate(metrics.items()):
        ax = axes[i // ncols][i % ncols]
        y = s / scale if key in level_keys else (s / 1e9 if key == "fx" else s)
        unit = (f", {scale_txt}" if (key in level_keys and scale_txt) else
                (tr(", млрд", ", bn") if key == "fx" else ""))
        _draw(ax, _cut(y, start), cols[i], style, nd=1 if key not in ("pop", "yoy") else 2, lw=1.5)
        if key in ("pop", "yoy", "cmlt_cmlt", "ytd"):
            ax.axhline(0, color=pal["muted"], lw=0.6)
        ax.set_title(ttl + unit, loc="left", fontfamily=FONT_TITLE, fontsize=11, pad=14)
        ax.text(0, 1.02, formula, transform=ax.transAxes, fontsize=8, alpha=0.7, family=FONT_LABEL)
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")
    num, name = CURRENT_SECTION
    name = tx(name)
    if name:
        fig.text(0.01, 0.995, (f"{num}. {name}" if num else str(name)).upper(), fontsize=7.5,
                 fontweight="bold", color=pal["zoloto"], va="top")
    fig.text(0.01, 0.975, title, fontsize=16, fontfamily=FONT_TITLE, va="top")
    if subtitle:
        fig.text(0.01, 0.975 - 0.32 / (2.75 * nrows + 1.2), subtitle, fontsize=9, alpha=0.65, va="top")
    fig.text(0.01, 0.003, tr("Источник: exit10.ru", "Source: exit10.ru"), fontsize=7.5, alpha=0.6)
    plt.tight_layout(rect=(0, 0.015, 1, 1 - 0.95 / (2.75 * nrows + 1.2)))
    plt.show()


def plot_decomposition(df, title, subtitle=None, start=None, total="nominal",
                       parts=("real", "prices", "cross"), labels=None):
    """Stacked contributions (positive and negative stacked separately) plus the total as a
    line. Used for nominal growth = real growth + price growth + cross term.

    [RU] Вклады столбиками (положительные и отрицательные складываются отдельно) и итог линией.
    Используется для разложения: номинальный рост = реальный рост + рост цен + перекрёстный член.
    """
    labels = labels or {"nominal": tr("номинальный рост", "nominal growth"),
                        "real": tr("реальный рост", "real growth"),
                        "prices": tr("рост цен (дефлятор)", "price growth (deflator)"),
                        "cross": tr("перекрёстный член", "cross term")}
    d = _cut(df.dropna(), start) if start else df.dropna()
    x = _x(d.index)
    w = (np.median(np.diff(x.values)) / np.timedelta64(1, "D")) * 0.8 if len(x) > 1 else 20
    fig, ax = plt.subplots()
    up, dn = np.zeros(len(d)), np.zeros(len(d))
    for part, col in zip(parts, cycle_colors(len(parts))):
        v = d[part].values
        ax.bar(x, v, bottom=np.where(v >= 0, up, dn), width=w, color=col, alpha=0.8, label=labels.get(part, part))
        up += np.where(v >= 0, v, 0)
        dn += np.where(v < 0, v, 0)
    ax.plot(x, d[total].values, color=pal["text"], lw=1.6, marker="o", ms=2.5, label=labels.get(total, total))
    ax.text(x[-1], d[total].values[-1], " " + ru_num(d[total].values[-1]), fontsize=8, va="center")
    ax.axhline(0, color=pal["muted"], lw=0.7)
    chart_frame(ax, title, subtitle)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    plt.tight_layout()
    plt.show()


# ======================================================================
#  YEAR PROFILES AND COMPARISON OF ESTIMATES
#  ПРОФИЛИ ПО ГОДАМ И СРАВНЕНИЕ ОЦЕНОК
# ======================================================================
def year_profile(level, freq, normalize=False):
    """Reshape a level series into a table: rows -- month (quarter) of the year, columns -- years.
    normalize=True divides every year by the level at the end of the previous year and multiplies
    by 100; row 0 is then that end-of-year point (= 100) and row k is 100 x (1 + growth since
    January..k). A year without the previous year-end level is dropped (usually the first one).

    [RU] Перекладывает ряд уровней в таблицу: строки -- месяц (квартал) года, столбцы -- годы.
    normalize=True делит каждый год на уровень на конец предыдущего года и умножает на 100;
    тогда строка 0 -- эта точка конца года (= 100), а строка k -- 100 × (1 + рост с начала года
    по k-й месяц). Год без уровня на конец предыдущего года выпадает (обычно первый).
    """
    s = level.dropna()
    sub = s.index.month if freq == "M" else s.index.quarter
    tab = pd.DataFrame({"y": s.index.year, "k": sub, "v": s.values}).pivot(index="k", columns="y", values="v")
    if not normalize:
        return tab
    last = PPY[freq]
    base = tab.loc[last].shift(1)                         # end of previous year | конец предыдущего года
    out = 100 * tab / base
    out.loc[0] = 100.0
    out = out.sort_index()
    return out.loc[:, base.notna()]


def plot_year_profile(prof, freq, title, subtitle=None, years=None, hline=None, nd=1):
    """Draw year_profile(): x -- months (quarters), one line per year; the last year in coral,
    earlier years in azure fading with age. Row 0 (if present) is labelled as the previous year-end.

    [RU] Рисует year_profile(): по x -- месяцы (кварталы), по линии на год; последний год --
    кораллом, более ранние -- лазурью, тем бледнее, чем старше. Строка 0 (если есть) подписана
    как конец предыдущего года.
    """
    cols = list(prof.columns)[-years:] if years else list(prof.columns)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for i, y in enumerate(cols):
        z = prof[y].dropna()
        col = pal["korall"] if y == cols[-1] else pal["lazur"]
        ax.plot(z.index, z.values, color=col, alpha=0.25 + 0.75 * (i + 1) / len(cols), lw=1.6, marker="o", ms=2.5)
        ax.text(z.index[-1], z.values[-1], f" {y}", fontsize=7.5, va="center", color=col)
    n = 12 if freq == "M" else 4
    names = months_short() if freq == "M" else quarter_labels()
    ticks = list(range(0 if 0 in prof.index else 1, n + 1))
    ax.set_xticks(ticks)
    ax.set_xticklabels(([tr("дек*", "Dec*")] if 0 in prof.index else []) + names)
    if hline is not None:
        ax.axhline(hline, color=pal["muted"], lw=0.7)
    chart_frame(ax, title, subtitle)
    plt.tight_layout()
    plt.show()


def compare_estimates(est, ref):
    """Compare an estimate with a reference on common dates: error = est - ref.
    Returns a dict: n, mean error (bias) with its t-statistic and two-sided p-value (normal
    approximation), median error, MAE, RMSE, std of the reference, RMSE / std(ref), correlation,
    share of |error| above 0.1 and 0.2 (in the units of the series).

    [RU] Сравнивает оценку с эталоном на общих датах: ошибка = оценка − эталон.
    Возвращает словарь: n, средняя ошибка (смещение) с t-статистикой и двусторонним p-значением
    (нормальное приближение), медиана ошибки, MAE, RMSE, ст. откл. эталона, RMSE / ст.откл.,
    корреляция, доли |ошибки| больше 0,1 и 0,2 (в единицах ряда).
    """
    from math import erfc, sqrt
    j = pd.concat([est, ref], axis=1, keys=["est", "ref"]).dropna()
    e = j["est"] - j["ref"]
    n = len(e)
    sd = e.std(ddof=1)
    t = e.mean() / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan
    return {"n": n, "bias": e.mean(), "t_bias": t, "p_bias": erfc(abs(t) / sqrt(2)) if np.isfinite(t) else np.nan,
            "median": e.median(), "mae": e.abs().mean(), "rmse": float(np.sqrt((e ** 2).mean())),
            "std_ref": j["ref"].std(ddof=1), "rmse_to_std": float(np.sqrt((e ** 2).mean())) / j["ref"].std(ddof=1),
            "corr": j["est"].corr(j["ref"]), "share_gt_0.1": (e.abs() > 0.1).mean(),
            "share_gt_0.2": (e.abs() > 0.2).mean(), "error": e}


def plot_year_range(data, freq, title, subtitle=None, exclude=(), hline=None, nd=1, first_year=None):
    """Same by-year layout as season_chart / plot_year_profile, but only two lines: the last year
    (coral) and the year before (azure); all earlier years are shown as a shaded band between their
    minimum and maximum for every month (quarter). `data` -- a level series or a year_profile() table.
    exclude -- years left out of the band (e.g. a crisis year that would stretch it);
    first_year -- the earliest year that enters the band.

    [RU] Та же раскладка по годам, что в season_chart / plot_year_profile, но линий только две:
    последний год (коралл) и предпоследний (лазурь); все более ранние годы -- закрашенная область
    между их минимумом и максимумом по каждому месяцу (кварталу). `data` -- ряд уровней или таблица
    year_profile(). exclude -- годы, не входящие в область (например, кризисный год, который её
    растягивает); first_year -- самый ранний год, входящий в область.
    """
    prof = year_profile(data, freq) if isinstance(data, pd.Series) else data
    years = list(prof.columns)
    last, prev = years[-1], years[-2]
    # a year enters the band only if it covers at least half of the year | год входит в область, только если покрывает хотя бы полгода
    full = prof.notna().sum() >= (6 if freq == "M" else 2)
    band_years = [y for y in years[:-2] if y not in exclude and full[y]
                  and (first_year is None or y >= first_year)]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    if band_years:
        b = prof[band_years]
        lo, hi = b.min(axis=1), b.max(axis=1)
        ok = b.notna().sum(axis=1) > 0
        ax.fill_between(prof.index[ok], lo[ok], hi[ok], color=pal["zoloto"], alpha=0.28, lw=0,
                        label=tr(f"диапазон {band_years[0]}–{band_years[-1]} (мин–макс)",
                                 f"range {band_years[0]}–{band_years[-1]} (min–max)")
                        + (tr(f", без {', '.join(map(str, exclude))}", f", excl. {', '.join(map(str, exclude))}")
                           if exclude else ""))
    for y, col in [(prev, pal["lazur"]), (last, pal["korall"])]:
        z = prof[y].dropna()
        ax.plot(z.index, z.values, color=col, lw=2.0, marker="o", ms=3, label=str(y))
        ax.text(z.index[-1], z.values[-1], f" {ru_num(z.values[-1], nd)}", fontsize=8, va="center", color=col)
    n = 12 if freq == "M" else 4
    names = months_short() if freq == "M" else quarter_labels()
    ax.set_xticks(list(range(0 if 0 in prof.index else 1, n + 1)))
    ax.set_xticklabels(([tr("дек*", "Dec*")] if 0 in prof.index else []) + names)
    if hline is not None:
        ax.axhline(hline, color=pal["muted"], lw=0.7)
    chart_frame(ax, title, subtitle)
    ax.legend(loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.show()


_NOT_EXPORTED = {"os", "np", "pd", "mpl", "plt", "fm", "LANG"}
__all__ = sorted(n for n in globals() if not n.startswith("_") and n not in _NOT_EXPORTED)
