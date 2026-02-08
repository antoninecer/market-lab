## Thematic Overlay (optional)


# Assumptions

## Trh
- Trhy nejsou efektivní na všech timeframech
- Střednědobé trendy (dny–týdny) jsou detekovatelné
- Likvidní akcie a ETF umožňují realistickou simulaci

## Timeframe
- Základní timeframe: 1D
- Alternativní timeframe: 4H
- Intraday (<15m) je mimo scope v1

## Fee & slippage
- Každý obchod musí mít edge > fee + slippage
- Fee jsou modelovány konzervativně
- Pokud edge nepřevýší náklady → NO_TRADE

## Chování systému
- Většina času systém neobchoduje
- NO_TRADE je validní výstup
- Systém není povinen být neustále v trhu

## Riziko
- Risk na jeden obchod ≤ X % kapitálu (zatím TBD)
- Max drawdown je důležitější než winrate


Vedle core instrumentů může systém pracovat
s tematickými ETF reprezentujícími dlouhodobé trendy:

- AI / robotika (BOTZ, IRBO)
- Biotechnologie / zdravotnictví (IBB, XLV)
- Technologie (XLK)
- Zdroje / energie (GNR, XLE)

Tyto instrumenty:
- nepoužívají jiná pravidla
- slouží k testu robustness signálů
- nejsou optimalizovány samostatně

- Výkonnost systému musí být porovnávána s SPY

❌ intraday (1h, 5m)

❌ arbitrage / HFT

❌ predikce zpráv

❌ optimalizace winrate

❌ „zkusíme to, třeba to vyjde“

➡️ Akce:
Dopsat explicitní NOT IN SCOPE (v1).

# Assumptions

## Tržní
- Trhy mají dlouhodobě trendující fáze
- Ne všechny dny jsou obchodovatelné
- Většina pohybů je šum

## Nákladové
- Každý obchod má fixní i skryté náklady
- Malé pohyby nejsou obchodovatelné
- Fee je součást signálu, ne dodatek

## Psychologické
- Systém nesmí vyžadovat neustálý dohled
- Neobchodování je validní stav
- Konzistence > adrenalin

## Technické
- Data mohou být zpožděná
- Exekuce nikdy není ideální
- Systém musí fungovat i „ošklivě“

