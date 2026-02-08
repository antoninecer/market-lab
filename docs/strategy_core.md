# Strategy Core – Market-Lab

Tento dokument definuje základní principy obchodního systému.
Neřeší implementaci, API ani konkrétní platformu.
Popisuje pouze rozhodovací logiku a omezení.
# Strategy Core (v1)

## Typ strategie
- Multi-asset
- Swing / position trading
- Time-based rozhodování

## Co je signál
- Kombinace trendu + volatility + kontextu
- Signál ≠ povinnost obchodovat

## Co NENÍ signál
- Jeden indikátor
- Náhodný spike
- Emoce trhu

## Výstupy strategie
- BUY
- SELL
- NO_TRADE

## Poznámka
Tato verze strategie musí fungovat bez ML.
ML je až nadstavba, ne základ.

---

## 1. Základní pozorování trhu
KROK 1 — Zafixujeme 7 aktiv (teď hned)
Kotva už padla, takže žádné handrkování.
Navržený startovní koš (1D, likvidní, smysluplná diverzita):
S&P 500 (SPY / ^GSPC) – kotva trhu ✅
NASDAQ 100 (QQQ) – technologie / AI
Healthcare ETF (XLV) – léky, demografie
Energy ETF (XLE) – zdroje, geopolitika
Industrials ETF (XLI) – reálná ekonomika
Gold (GLD) – defenziva / risk-off
Cash / Money Market – aktivní rozhodnutí „neobchodovat“
Trh se pohybuje ve třech stavech:
- trend
- konsolidace
- šum

## Core Signal (v0.1)

Timeframe: 1D

Entry allowed if:
- price > MA200
- momentum condition met

Exit:
- stop-loss = ATR based
- exit on trend invalidation

No signal = no trade

Systém smí obchodovat pouze tehdy, pokud:
- existuje pohyb větší než transakční náklady
- pohyb není náhodný šum

---

## 2. Minimální smysluplný pohyb (edge threshold)

Obchod je povolen pouze tehdy, pokud:

abs(pohyb ceny) > (poplatky + bezpečnostní rezerva)

Bez splnění této podmínky je obchod zakázán.

---

## 3. Referenční bod (price anchor)

Systém si udržuje referenční cenu (anchor), která reprezentuje:
- poslední rozhodovací cenu
- nikoliv nutně poslední obchod

Anchor se aktualizuje pouze tehdy, pokud:
- došlo k významnému pohybu
- nebo byl proveden obchod

---

## 4. Směr není signál

Směr pohybu (nahoru / dolů) sám o sobě není důvod k obchodu.

Rozhodující je:
- vzdálenost od anchoru
- rychlost a konzistence pohybu
- vztah k nákladům

---

## 5. Stavy systému

Systém může být pouze v jednom ze stavů:
- IDLE (čekám)
- READY_TO_BUY
- READY_TO_SELL
- IN_TRADE

Stav se mění pouze na základě pravidel, nikoliv emocí.

---

## 6. Eskalace pozice (controlled exposure)

Opakovaný signál ve stejném směru:
- zvyšuje expozici
- ale pouze do předem daného maxima

Nikdy:
- ne celý kapitál
- ne exponenciálně
- ne bez limitu

---

## 7. Denní kontext

Systém sleduje:
- průměrnou nákupní cenu dne
- průměrnou prodejní cenu dne

Obchod proti dennímu průměru je povolen pouze s nižší váhou
nebo je zcela zakázán.

---

## 8. Ochrana před overtradingem

Systém aktivně hledá důvody:
- proč NEobchodovat

Pokud:
- pohyb je malý
- volatilita je chaotická
- signály si odporují

→ systém zůstává v IDLE.

---

## 9. Neexistuje povinnost obchodovat

Žádný obchod je platný výsledek.

Cílem systému není aktivita,
ale pozitivní dlouhodobá očekávaná hodnota.

---

## 10. Systém musí přežít bez optimalizace

Strategie musí:
- dávat smysl bez ML
- fungovat s konzervativními parametry
- selhávat pomalu, ne náhle

Optimalizace je povolena až po stabilitě.
## Market Regime Anchor

Systém používá S&P 500 (SPY) jako:
- benchmark výkonnosti
- filtr tržního režimu (risk-on / risk-off)
- referenci pro drawdowny

SPY není primární obchodní instrument,
ale řídicí signál trhu.

