# Vision

Tento projekt není:
- trading bot na sliby z YouTube
- systém na rychlé zbohatnutí
- black-box AI

Tento projekt je:
- laboratorní prostředí
- nástroj pro učení
- datově řízený experiment

Rozhodnutí o obchodech musí být:
- reprodukovatelné
- vysvětlitelné
- statisticky obhajitelné

Trading Constitution

market-lab – verze 1.0

0. Proč tento dokument existuje

Tento dokument definuje smysl, hranice a mravní vědomí systému.
Neřeší jak obchodujeme, ale proč, kdy a kdy ne.

Kód se může měnit.
Data se mohou měnit.
Tyto principy ne.

1. Cíl systému
Systém nikdy neoptimalizuje strategii podle jednotlivých obchodů,
ale pouze podle dlouhodobé distribuce výsledků.
Cílem systému není:
maximalizovat počet obchodů
být neustále v trhu
honit se za „zaručenými signály“

Cílem systému je:
dlouhodobě kladná expectancy
kontrolovaný risk
reprodukovatelné rozhodování
klidný spánek provozovatele

2. Co systém obchoduje

Systém obchoduje likvidní trhy, kde:
existují spolehlivá historická data
jsou jasně definovatelné poplatky
lze simulovat exekuci

Typicky:
akcie
ETF
případně crypto (sekundárně)

3. Co systém NEobchoduje

Systém neobchoduje:
sliby
marketing
„tajné signály“
strategie bez jasně definovaného risku
cokoliv, co nelze férově zpětně otestovat

4. Signál ≠ obchod

Signál je pozorování.
Obchod je rozhodnutí.

Systém:
může generovat signály
nemusí je vždy exekuovat
Pokud není splněna celá sada podmínek, obchod se nekoná.

5. Obchod je dovolen pouze tehdy, když:

potenciální zisk převyšuje:
poplatky
skluz
statistickou ztrátu
risk je kvantifikovaný
ztráta je předem akceptovaná

Pokud nelze ztrátu přijmout → obchod neexistuje.

6. Systém respektuje náhodu

Ani dobrý systém:
nevyhrává vždy
neví budoucnost
nemá pravdu v každém obchodu

Systém:
pracuje s pravděpodobností
ne s jistotou

7. Winrate není cíl

Vysoký winrate:
není nutný
není důkazem kvality

Důležitější než winrate je:
expectancy
drawdown
stabilita chování

8. Ochrana kapitálu má absolutní prioritu

Bez kapitálu:
není systém
není strategie
není budoucnost

Systém:
nikdy neriskuje vše
nikdy „nedohání ztrátu“
nikdy nezvyšuje risk z emocí

9. Systém má právo nic nedělat
Neobchodování je platný stav.

Systém:
může být dny i týdny neaktivní
neobchoduje z nudy
neobchoduje z tlaku

10. Tento dokument má vyšší váhu než kód

Pokud:
kód porušuje tyto principy
→ kód je špatně

Ne:
„trh se změnil“
„musíme to obejít“
„jen tentokrát“

11. Závazek
Tento systém je budován:
trpělivě transparentně s respektem k realitě trhu

Nechceme:
rychlé zbohatnutí
Chceme:
dlouhodobou funkčnost
