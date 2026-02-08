# market-lab

Experimentální laboratoř pro návrh, testování a vyhodnocování
systematických obchodních strategií **bez reálných peněz**.

Cílem není „vydělat rychle“, ale:
- pochopit trhy,
- naučit se správně vyhodnocovat strategie,
- a teprve poté případně přejít na reálné obchodování.

---

## Základní principy

- ❌ žádné reálné peníze (paper trading only)
- ❌ žádné „AI rozhoduje místo nás“
- ✅ vše je měřitelné a zpětně vysvětlitelné
- ✅ každý krok má jasný důvod a metriky

---

## Cíl projektu

Vytvořit systém, který:
- dlouhodobě dosahuje **kladné expectancy**
- má **kontrolovaný drawdown**
- je stabilní napříč časem a trhy

Teprve při splnění těchto podmínek je možné uvažovat o reálném nasazení.

---

## Stav projektu

- [x] Inicializace projektu
- [x] Definice trhu a dat
- [ ] Labeling dat (BUY / SELL / NO_TRADE)
- [ ] Backtest
- [ ] Paper trading
- [ ] Vyhodnocení


-----
## Quick start

```bash
git clone https://github.com/antoninecer/market-lab.git
cd market-lab

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

source ./startvenv.sh

python cli/daily_update.py && python cli/make_report.py



8.2.1:54
Záznam stavu (checkpoint)

Repo: ~/work/market-lab
Venv: .venv (spouštíš přes bin/daily_update.sh, který používá ./.venv/bin/python)

Universe (7 aktiv): GLD, JNJ, MSFT, NVDA, QQQ, SPY, XLE

Pipeline běží OK (7/7):

engine/datasource/download_yahoo.py → data/raw/*.csv

engine/datasource/normalize_yahoo.py → data/processed/*.csv

engine/datasource/sanitize_ohlc.py → data/processed_sanitized/*.csv + log _sanitizer_log.csv

engine/evaluation/data_quality.py --calendar spy → Result: OK

engine/datasource/build_panel.py →

data/processed_sanitized/panel_close.csv (rows=5308)

data/processed_sanitized/panel_returns.csv (rows=5307)

engine/evaluation/basic_stats.py → tabulka CAGR/Vol/DD

engine/evaluation/baseline_portfolio.py →

data/processed_sanitized/baseline_equity.csv

data/processed_sanitized/baseline_trades.csv

Baseline výsledky (equal-weight, monthly rebalance, costs 5bps fee + 2bps slippage):

start ≈ 999.30

end ≈ 30501.77

years ≈ 21.09

CAGR ≈ 17.59%

Vol ≈ 18.67%

MaxDD ≈ -47.84%

Důležitá oprava, která se stala: baseline_portfolio.py byl omylem přepsaný obsahem z data_quality.py → opraveno, teď bere --panel --initial --fee-bps ... a krok 7 běží.

Jak mě příště oslovit (hotový „naladění“ prompt)

Zkopíruj si tohle a příště to vlož jako první zprávu:

Jdeme pokračovat v projektu market-lab.

Kontext:
- Repo: ~/work/market-lab
- Venv: .venv (spouštím přes bin/daily_update.sh)
- Universe (7 aktiv): GLD, JNJ, MSFT, NVDA, QQQ, SPY, XLE
- Data flow:
  raw -> processed -> processed_sanitized -> panel_close/panel_returns -> baseline_equity/baseline_trades
- Gate: engine/evaluation/data_quality.py se spouští jen na OHLCV v data/processed_sanitized a používá --calendar spy.
- Baseline: equal-weight monthly rebalance s náklady fee=5 bps, slippage=2 bps, fixed=0; výstupy baseline_equity.csv a baseline_trades.csv.

Pravidla spolupráce:
1) Postupuj po malých krocích. Vždy navrhni jen jeden další krok a čekej na moje „OK“ nebo log výstup.
2) Když dáváš kód, dej celý soubor (ne útržky) a řekni přesnou cestu kam ho uložit.
3) Když dáváš bash příkaz, předpokládej macOS/zsh a venv.
4) Když narazíme na chybu, nejdřív navrhni 1–2 diagnostické příkazy a až pak opravu.

Teď: řekni mi JEDEN další krok, který dává smysl po úspěšném daily_update (bez skákání dopředu).


Až to příště pošleš, navážu přesně tím stylem: jeden krok, žádné „utíkání“ o tři kapitoly napřed.
