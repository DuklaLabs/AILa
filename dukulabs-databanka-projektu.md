# DuklaLabs – databanka projektových témat

Průběžně rozšiřovaný přehled témat pro ročníkové a maturitní práce v rámci budování softwarového a hardwarového zázemí DuklaLabs (mikrospace). Cílem je mít zásobník témat, ze kterých se dá postupně vybírat podle toho, kdo se přihlásí a jaká je jeho úroveň.

**Legenda:** ✅ vhodné · — spíš ne / nerelevantní

**Webový terminál (výchozí varianta)**: běžný prohlížeč v kiosk módu (starý PC, mini PC, Raspberry Pi nebo tablet) + běžná USB RFID/NFC čtečka fungující jako klávesnice (HID) – přiložení karty "napíše" UID do fokusovaného pole webové appky a rovnou se odešle na server. Žádný vlastní firmware, jde čistě o webový frontend nad sdíleným API. Vlastní embedded HW (ESP32 + relé apod.) se řeší jen tam, kde je potřeba fyzicky něco spínat (zámek dveří, napájení stroje) nebo číst ze senzoru – tam se čtečka/web stará jen o identifikaci, embedded modul dostane přes API pokyn "odemkni/zapni".

---

## 1. Docházka a přístup

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| RFID docházkový terminál (web + čtečka) | SW | ✅ | ✅ | Prohlížeč (kiosk mód na starém PC/mini PC/RPi) + USB RFID/NFC čtečka (HID) | Navazuje na Access Manager, ale bez psaní firmwaru. Mat.: offline režim (lokální cache při výpadku sítě), zabezpečení komunikace, napojení na rozvrh |
| Sdílené API jádro + autentizace přes RFID (SSO) | SW | — | ✅ | Server (Raspberry Pi / mini PC) — bez specifického HW | Architektonický základ pro všechny ostatní moduly |
| Evidence skupin ZŠ a docházka na kroužek (externí účastníci) | SW | ✅ | ✅ | Jednorázové NFC náramky/karty + webový kiosek s USB čtečkou (nebo Android tablet s Web NFC) | Děti nemají trvalou kartu školy |
| Evidence proškolení/oprávnění na stroje | HW+SW | ✅ | — | Identifikace kartou jde přes web/USB čtečku; malý embedded modul (ESP32 + relé) u stroje jen přijme přes API pokyn k odemčení | Propojitelné s docházkou a rezervacemi. Zahrnuje i veřejnost/externí zájemce, ne jen studenty — vyžaduje roli "veřejnost" v RBAC |

## 2. Sklad a materiál

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Skladový systém – web/API nad ESP32+LED | HW+SW | ✅ | ✅ | WS2812B LED pásky do šuplíků + ESP32 řadič (rozjeto), volitelně RFID tagy na bednách | HW rozjeto, chybí webová/API vrstva |
| Sledování spotřeby materiálu na ZŠ kroužek | SW/HW | ✅ | — | Volitelně váha (load cell + HX711) na hlídání zbylého množství | Propojení se skladem, reálné náklady na skupinu |
| Evidence softwarových licencí | SW | ✅ | — | — | Menší CRUD projekt |

## 3. Objednávky a rozpočet

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Jednoduchý formulář na objednávky materiálu | SW | ✅ | — | — | Bez schvalování a rozpočtu |
| Objednávkový systém se schvalovacím workflow a rozpočtem | SW | — | ✅ | — | Role, napojení na grantové rozpočty, propojení se skladem |
| Rozpočtový přehled laborky (granty + provoz + sponzoring) | SW | — | ✅ | — | Agregace z více zdrojů |
| Grantový tracker (termíny, vykazování) | SW | ✅ | — | — | CRUD + upomínky na deadliny |

## 4. Rezervace a kapacity

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Rezervační systém vybavení a laborky | SW/HW | ✅ | ✅ | Stav fronty stačí zobrazit na běžné obrazovce/tabletu webovou stránkou; volitelně malý embedded modul (ESP32 + relé) pro fyzické blokování stroje | Mat.: řešení konfliktů, notifikace, provázání s docházkou |
| Fronta na 3D tiskárny/laser | SW/HW | ✅ | — | Běžný tablet/starý monitor s webovou stránkou zobrazující frontu, volitelně USB webkamera na sledování průběhu tisku | Rezervace tisku, odhad doby dokončení |
| Kapacitní plánování strojového času | HW+SW | — | ✅ | Proudový senzor (SCT-013 / PZEM-004T) na měření reálného provozu stroje | Vytíženost, úzká hrdla — automatické měření bez ručního zápisu |
| Rotační rozvrh stanic pro ZŠ skupiny | SW | ✅ | ✅ | Volitelně tablet/kiosek s webovou stránkou na potvrzení příchodu ke stanici | Automatické rozdělení dětí do rotací po stanicích |

## 5. Řízení projektů a znalostí

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Projektový/task management systém (kanban) | SW | ✅ | ✅ | — | Mat.: time tracking, audit log, role, napojení na GitHub. **MVP implementováno** jako služba `Projects` (hierarchie, datová karta úkolu, kanban, time tracking, finanční součty, MCP napojení na AI se schvalováním rizikových akcí – §21). Zbývá: automatizace, manažerské dashboardy, GitHub. |
| Automatické zpracování zápisů schůzek → úkoly (AI) | SW | ✅ | ✅ | Volitelně mikrofon na nahrávání schůzky | Navazuje na hotový úkolový systém. Mat.: STT přepis, mapování jmen na účty, odhad projektu |
| Napojení e-mailu → automatické úkoly (AI) | SW | ✅ | ✅ | — | Sdílí extrakční logiku se zápisy ze schůzek. Mat.: víc schránek/uživatelů, feedback loop |
| Wiki/knowledge base laborky | SW | ✅ | — | — | Návody, troubleshooting, verzování stránek |
| Analytický dashboard napříč moduly | SW/HW | — | ✅ | Volitelně obrazovka/TV v laborce jako kiosk | Potřebuje data z ostatních modulů |
| Samorostoucí nástrojový systém pro AI orchestrátora (Generál) | SW | — | ✅ | — | Generál zvládne nový typ úkolu poprvé ručně (např. sestavit a poslat e-mail), pak nabídne vytvoření trvalého nástroje pro příště. Zadání jde specializovanému "tool" agentovi (napíše kód + testy), aktivace až po lidském schválení – systém tak pomalu roste sám, vždy s člověkem na konci schvalovacího řetězce. |

### Detailní rozpis: samorostoucí nástrojový systém pro Generála

**Motivace:** Generál (`General/`) dnes reaguje na uživatelovy příkazy přes
pevně zadrátovanou sadu akcí v systémovém promptu (CHECK_STOCK,
CREATE_ORDER, DRAFT_EMAIL, ...) – nový typ úkolu (např. "napiš studentům, že
je zavřeno") vyžaduje ruční zásah do kódu. Cíl: když Generál poprvé zvládne
něco nového (i jen tím, že mu člověk krok za krokem poradí), umí nabídnout
"chceš, ať z tohohle příště udělám nástroj?" a zadání předá specializovanému
agentovi na tvorbu nástrojů.

**Postup (návrh, k rozpracování):** Generál rozpozná/nabídne novou
schopnost → zadání (popis úkolu + ukázka z reálné konverzace) jde tool-agentovi
→ ten napíše kód nového nástroje (nová akce/modul) + testy → nástroj běží
v sandboxu/testovacím prostředí, ne rovnou v produkci → člověk projde návrh
(kód, testy, co nástroj smí) a schválí → teprve pak se nástroj stane trvale
dostupnou akcí Generála.

**Klíčová otevřená rozhodnutí:** co přesně je "nástroj" v týhle codebase –
nový Python soubor v `General/app/agents/` vyžadující redeploy, nebo něco
dynamičtějšího (registrovatelné za běhu, bez redeploy); kdo/co je
"tool-agent" – samostatně spouštěná AI-coding agent instance nad tímhle
repem, nebo šablonovaný generátor s omezenou sadou stavebních bloků; jak
přesně vypadá schvalovací krok a kde se sleduje (podobně jako
`agent.proposals`, ale to je dnes svázané s modulem `access`, viz
`AccessRequest/app/agent_review.py`); jak se nový nástroj bezpečně otestuje,
než dostane přístup k reálným datům/e-mailům/objednávkám.

- Maturitní: návrh a implementace celého schvalovacího a nasazovacího
  pipeline (bezpečné generování kódu, sandbox, testování, aktivace),
  minimálně pro jeden typ nástroje (např. nová "akce" v Generálově
  orchestrátoru).

Závislost: staví na hotovém Generálovi (orchestrátor + akce, viz sekce 5
výše a `General/Readme`) a na principu schvalování z §21 (`agent.proposals`)
→ řadí se až po něm.

### Detailní rozpis: AI zpracování zápisů schůzek

**Postup:** vložení zápisu (text, později i audio → STT) → LLM extrahuje úkoly (název, popis, navržený řešitel, termín, projekt) → návrh se zobrazí k potvrzení/úpravě → po potvrzení zápis do sdílené DB úkolů

**Klíčové pro minimum ruční práce:** fuzzy mapování jmen ze zápisu na existující uživatele, automatický odhad projektu podle kontextu/klíčových slov

- Ročníková: textový vstup, volání LLM na extrakci, návrh k ručnímu potvrzení/přiřazení
- Maturitní navíc: STT přepis nahrávky schůzky, automatické mapování jmen na účty, automatický odhad projektu

Závislost: potřebuje hotový úkolový systém (tabulky úkolů/projektů/uživatelů) → řadí se do vlny 2

**Status:** STT vrstva vzniká souběžně jako samostatná sdílená služba ("stenograf"), ne zakopaná uvnitř tohoto modulu — může ji tak využít i příprava na hodiny (automatický zápis zkušenosti z výuky) a briefingový agent (sekce 21), ne jen tenhle modul

### Detailní rozpis: napojení e-mailu na úkolníček

**Postup:** OAuth napojení schránky (IMAP/Gmail/Outlook API) → nový email se vyhodnotí LLM klasifikátorem, jestli obsahuje pravděpodobný úkol → při vysoké jistotě návrh k potvrzení (odkaz na původní email), při nízké jistotě do fronty k ručnímu přehledu

**Klíčové věci:** víc lidí = víc samostatně připojených schránek (ne jedna sdílená), práh jistoty pro automatické vytvoření vs. jen návrh, bezpečnost čtení emailů (citlivá oprávnění)

- Ročníková: jedna schránka, jednoduchá klasifikace, návrh k potvrzení
- Maturitní navíc: víc schránek/uživatelů, automatické přiřazení podle příjemce, feedback loop, týdenní souhrn

**Pilotní provoz a ladění klasifikátoru:**
1. Sběr dat: po nějakou dobu (např. měsíc) se každý příchozí email ručně označí ano/ne "je to úkol" → anotovaná sada
2. Analýza vzorů: z označených emailů se vytáhnou opakující se klíčová slova/fráze, typičtí odesílatelé, struktura zprávy
3. Sestavení "skillu": klíčoslovný filtr (jasné případy) + LLM prompt s few-shot příklady z pilotu (nejednoznačné případy)
4. Vyhodnocení přesnosti (kolik úkolů se chytlo, kolik uniklo, kolik falešných poplachů) a iterativní ladění
5. Průběžné dolaďování i po nasazení — případy z fronty ke schválení se dál používají jako další data

Sběr dat a vyhodnocení přesnosti jde i jako samostatná menší ročníková práce vedle vlastní technické integrace

Závislost: staví na stejné extrakční logice jako AI zpracování zápisů schůzek → řadí se do vlny 3

### Detailní rozpis: úkolový systém (rozšíření kanbanu)

**Entita Úkol:** id, název, popis, projekt_id (FK na projekt), stav (enum: zadaný / probíhající / hotový), termín, vytvořeno, dokončeno (auto při přechodu na hotový)

**Řešitelé:** samostatná M:N vazební tabulka úkol_id ↔ uživatel_id — jeden úkol může mít víc řešitelů, člověk může mít víc úkolů

**Upozorňování na termíny:** naplánovaná úloha (cron), denně kontroluje úkoly se stavem ≠ hotový: blížící se termín (2–3 dny předem) → upozornění řešitelům; prošlý termín → eskalační/opakované upozornění. Posílá se přes modul notifikační bot (závislost).

- Ročníková: CRUD, 3 stavy, kanban board, vazba na projekt, víc řešitelů
- Maturitní navíc: upozorňovací systém na termíny, historie změn stavu, report otevřených/prošlých úkolů

## 6. Bezpečnost a údržba

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Plánování údržby/kalibrace strojů | HW+SW | ✅ | ✅ | Vibrační senzor/akcelerometr, počítadlo motohodin | Mat.: prediktivní údržba z provozních dat |
| BOZP/revizní dokumentace a přeškolení | HW+SW | ✅ | — | Dveřní kontakty na skříních s nebezpečnými nástroji, propojení nouzového zastavení na systém | Termíny revizí a školení |
| Wiki na údržbu a řešení závad | SW | ✅ | ✅ | Volitelně mobil/tablet s fotoaparátem pro zápis u stroje | Historie závad a postupů oprav. Mat.: AI návrh řešení podle podobných případů |

### Detailní rozpis: wiki na údržbu a řešení závad

**Datový model:**
- Zařízení — vazba na evidenci strojů (modul plánování údržby)
- Záznam závady — co se rozbilo, projev poruchy, datum, kdo hlásil
- Postup řešení — diagnostika, zjištěná příčina, jak se opravilo, potřebné díly
- Preventivní poznámka — co dělat, aby se to neopakovalo

**Přínos:** historie závad u konkrétního stroje na jednom místě (opakovaná závada = signál k výměně), studenti zvládnou drobné opravy podle návodu bez ptaní, napojení na sklad (je díl skladem? → případně rovnou objednávka), propojení s ticketingem poruch (hlášení a vyřešení jsou dva konce téhož procesu)

**Aby se wiki reálně plnila:** zápis musí jít rychle, ideálně z mobilu přímo u stroje s fotkou; volitelně nadiktovat hlasem a nechat AI naformátovat do struktury (napojení na modul hlasového zadávání)

- Ročníková: evidence závad a postupů, vazba na zařízení, vyhledávání, fotky
- Maturitní navíc: AI návrh řešení podle podobných minulých závad, propojení se skladem a objednávkami, statistiky poruchovosti strojů

## 7. Partneři, granty, CRM

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| CRM na partnery/sponzory | SW | ✅ | — | — | Kontakty, zápůjčky (např. Festo Didactic), historie spolupráce |
| Evidence zápůjček vybavení mimo laborku | SW/HW | ✅ | — | Volitelně RFID tag na vybavení pro rychlé skenování při výdeji/vrácení | Kdo má co půjčené a dokdy |
| Evidence dobrovolnických/mentorských hodin | SW | ✅ | — | — | Podklad pro vykazování grantům (DuklaLabs z.s.) |

## 8. ZŠ kroužek „Technická škola nanečisto"

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Přihlašovací formulář a kapacity kroužku | SW | ✅ | ✅ | — | Potvrzení, upomínky, hlídání kapacity stanic |
| Generování podkladů (docházkové listy, certifikáty) | SW/HW | ✅ | — | Volitelně tiskárna štítků/karet | Automatický export z dat systému |
| Zpětná vazba/dotazník po kroužku | SW | ✅ | — | — | Agregovaná data pro vyhodnocení a granty |

## 9. Ostatní / hardwarově zajímavé

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Kiosk dashboard pro laborku (TV displej) | HW+SW | ✅ | — | Raspberry Pi + TV/monitor | Frontend nad hotovým API |
| Notifikační bot (Telegram/Discord) | SW | ✅ | — | — | Malý integrační projekt |
| Mobilní appka pro studenty | SW | — | ✅ | — | Docházka, rezervace, stav objednávek |
| OTA update a zabezpečení ESP32 firmware (sklad) | HW+SW | — | ✅ | Existující ESP32 skladový HW (rozjeto) | Embedded-security rovina nad rozjetým projektem |
| Sledování energií/prostředí v laborce (senzory) | HW+SW | ✅ | ✅ | BME280/SCD30 (teplota, vlhkost, CO2), PZEM-004T (spotřeba), volitelně PMS5003 (prach) | Grafy v čase — hezká kombinace HW+data pro maturitní |

## 10. Vylepšení a rozšíření na úsporu času

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Synchronizace docházky se školním systémem (Bakaláři/ŠkolaOnline) | SW | ✅ | ✅ | — | Roč.: jednosměrný export. Mat.: obousměrná synchronizace a řešení konfliktů |
| OCR čtení účtenek a faktur (objednávky/rozpočet) | SW | ✅ | ✅ | Volitelně skener/kamera na doklady | Roč.: OCR přes hotové API. Mat.: strukturování položek přímo do rozpočtu |
| Chatbot nad wiki laborky | SW | ✅ | ✅ | — | Roč.: jednoduchý FAQ bot na klíčová slova. Mat.: RAG nad obsahem wiki (embeddings). Dvojí využití: i jako příprava na školení/test — kandidát se doptá na konkrétní stroj podle reálného obsahu wiki |
| Hlasové zadávání do skladu/úkolů (vstup i výstup) | HW+SW | ✅ | ✅ | Mikrofon + reproduktor u stanice skladu | Roč.: STT (přes stenografa) + jednoduché parsování příkazu, hlasové potvrzení. Mat.: robustnější rozpoznávání, víc položek najednou, offline STT |

### Detailní rozpis: hlasové zadávání do skladu

**Postup:** vysloví se příkaz ("Potřebuji 10 200ohmových odporů") → stenograf (sdílený STT) přepíše na text → rozpoznání typu požadavku, položky a množství — fuzzy match na název položky v DB, stejný princip jako mapování jmen u AI zápisů → rozsvítí se LED u příslušné zásuvky, množství se odečte ze skladové evidence → hlasové potvrzení (TTS): umístění a stav skladu po odečtení, případně upozornění na nízký zbytek

- Ročníková: jedna položka, jedno množství, jednoduché textové/hlasové potvrzení
- Maturitní navíc: víc položek v jednom příkazu, odhad při nepřesně vysloveném názvu, hlasový výstup (TTS), napojení na skladového agenta (sekce 21) místo přímého zápisu do DB
| Automatický generátor výkazů a reportů | SW | — | ✅ | — | Agregace dat napříč docházkou, skladem a rozpočtem do hotového dokumentu pro granty/vedení |
| Generátor zadání ročníkových/maturitních prací z databanky | SW | ✅ | — | — | Vyplní šablonu zadání z popisu tématu v databance |
| Centralizovaný kalendář termínů (granty, revize, rezervace) | SW | ✅ | — | — | Sync do Google/Outlook kalendáře napříč moduly |
| Sledovač grantových výzev | SW | ✅ | ✅ | — | Roč.: scraper + email. Mat.: filtrování relevance (NLP) |
| Porovnávač cen u dodavatelů elektroniky/materiálu | SW | ✅ | — | — | Porovnání cen (GME, TME, Mouser apod.) před objednáním |
| Týdenní souhrnný digest | SW | ✅ | — | — | Jeden přehled napříč moduly místo kontroly každého zvlášť |
| Onboarding nových studentů (wizard) | SW | ✅ | ✅ | — | Roč.: checklist + založení účtu/karty. Mat.: napojení na všechny moduly, self-service portál |
| Vzdálený monitoring strojů/tiskáren | HW+SW | ✅ | ✅ | Kamera/senzor u stroje | Roč.: kamera + stream. Mat.: detekce chyby tisku obrazovou analýzou |
| Generátor testů na proškolení strojů | SW | ✅ | — | — | Otázky generuje z obsahu wiki a reálné historie závad (přes chatbot/knowledge base agenta), ne z ručně psané banky — aktualizuje se samo s tím, jak roste wiki |
| Automatické zpracování omluvenek | SW | ✅ | — | — | Formulář od rodiče/studenta se propíše rovnou do docházky |
| Šablonovač opakované komunikace | SW | ✅ | — | — | Předpřipravené texty s auto-doplněnými údaji (pozvánky, potvrzení, žádosti) |
| Automatické generování rozpisů služeb/dozorů | SW | ✅ | ✅ | — | Roč.: ruční rozvrh + přehled. Mat.: automatické rozvržení podle dostupnosti a pravidel |
| Evidence a přiřazení klíčů/přístupových karet | SW | ✅ | — | — | Kdo má jaký klíč, historie předání — místo papírové knihy |
| Automatická archivace hotových prací | SW | ✅ | — | — | Dokumentace, kód a fotky se po odevzdání uloží strukturovaně samy |
| Fotodokumentace akcí s automatickým tříděním | SW | ✅ | — | — | Třídění podle data a akce, použitelné rovnou pro grantové vykazování |
| Sledování spotřebního materiálu u tiskáren | HW+SW | ✅ | — | Volitelně senzor/váha na filament | Hlásí samo, kdy doplnit filament, tonery, čočky |
| Hromadné operace nad daty (import tříd) | SW | ✅ | — | — | Přidání celé třídy z exportu místo zakládání po jednom |
| Automatické zálohování systému | SW | ✅ | — | Volitelně NAS/externí disk | Infrastrukturní téma, jednou nastaveno a funguje samo |
| Sledování expirace materiálu | SW | ✅ | — | — | Lepidla, chemikálie, baterie — hlídání trvanlivosti |

## 11. Výuka a hodnocení

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Odevzdávací systém s automatickým hodnocením | SW | ✅ | ✅ | — | Navazuje na existující pytest/Hypothesis autograder, napojení na sdílenou platformu |
| Banka zadání úloh a projektů | SW | ✅ | — | — | Místo vymýšlení nových zadání pokaždé znova |
| Kontrola podobnosti odevzdaných prací | SW | — | ✅ | — | Detekce plagiátů mezi odevzdanými pracemi |
| Generátor podkladů pro klasifikaci | SW | ✅ | — | — | Souhrn z docházky, odevzdání a hodnocení do podkladu pro známkování |
| Přípravy na hodiny s evidencí zkušeností z výuky | SW | ✅ | ✅ | Volitelně mikrofon pro nadiktování poznámky po hodině | Uchovává, kde studenti narazili a jak se to vyřešilo. Mat.: AI shrnutí opakujících se problémů |

### Detailní rozpis: přípravy na hodiny s evidencí zkušeností

**Datový model (sdílený s úkolovým systémem, sekce 5):**
- Příprava na hodinu = `Projekt` — stejná entita jako u kanbanu, ne samostatná tabulka (téma, ročník/předmět, materiály, cíle hodiny jako popis/atributy projektu)
- Realizace hodiny a poznámka z ní = `Úkol`/poznámka navěšená na ten projekt — sdílí tabulku s běžnými úkoly
- Přepis poznámky po hodině může jít přímo přes stenografa (sdílený STT), ne jen ručním zápisem

**Postup:** po hodině krátká poznámka (psaná nebo přes stenografa) → navěsí se na konkrétní projekt/přípravu → při další přípravě na stejné téma se zobrazí historie všech minulých poznámek → volitelně AI shrne opakující se problémy napříč lety a navrhne úpravu přípravy

**Napojení na zbytek platformy:** sdílí datový model s úkolovým systémem (žádná duplicitní tabulka), banka zadání úloh (problematická místa → návrh doplňkového cvičení), odevzdávací systém s autograderem (objektivní data, u kterých úloh studenti padají), metodiky ZŠ kroužku (vrstva zkušeností nad hotovými materiály)

- Ročníková: rozšíření kanbanu o typ "příprava na hodinu", zobrazení historie poznámek u přípravy
- Maturitní navíc: AI shrnutí opakujících se problémů, návrhy úprav přípravy, propojení s daty z autograderu

Závislost: sdílí schéma s úkolovým systémem — staví se společně s ním, ne odděleně

## 12. Provoz školy mimo laborku

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Suplování a zástupy | SW | ✅ | — | — | Kdo koho zastupuje, propojení s rozvrhem |
| Exkurze a výjezdy | SW | ✅ | — | — | Přihlášky, souhlasy rodičů, seznamy, doprava na jednom místě |
| Evidence spolupráce s firmami | SW | ✅ | — | — | Praxe studentů, odborné stáže, kontakty — navazuje na CRM |

## 13. Osobní produktivita a chod týmu

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Automatický zápis času nad projekty | SW | ✅ | — | — | Místo dohadování, kolik času co reálně zabralo |
| Prioritizace úkolů podle termínů a vytížení | SW | — | ✅ | — | Systém navrhne, co dělat dnes |
| Evidence rozhodnutí a jejich zdůvodnění | SW | ✅ | — | — | Aby se stejná věc nediskutovala pořád dokola |
| Předávací protokoly při změnách | SW | ✅ | — | — | Nový správce laborky, odcházející student |

## 14. Soutěžní příprava (CzechSkills/EuroSkills)

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Evidence tréninků a výsledků soutěžících | SW | ✅ | ✅ | — | Mat.: statistiky a vizualizace progresu v čase |
| Generátor tréninkových zadání podle disciplín | SW | ✅ | — | — | Navazuje na banku zadání |
| Logistika soutěží (ubytování, doprava, seznamy) | SW | ✅ | — | — | Vše na jednom místě místo rozházených tabulek |

## 15. Provoz spolku (DuklaLabs z.s.)

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Evidence členů a členských příspěvků | SW | ✅ | — | — | Kdo je člen, kdo zaplatil, upomínky |
| Automatické podklady pro účetnictví a výroční zprávu | SW | — | ✅ | — | Agregace z rozpočtu, hodin a akcí |
| Zápisy ze schůzí spolku s archivem usnesení | SW | ✅ | — | — | Propojitelné s AI zpracováním zápisů (sekce 5) |

## 16. Komunikace navenek a nábor

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Automatické publikování novinek na web/sociální sítě | SW | ✅ | ✅ | — | Z akcí evidovaných v systému |
| Hromadná komunikace s rodiči ZŠ dětí | SW | ✅ | — | — | Rozesílka s personalizací |
| Přehled zájemců o studium a jejich kontaktů | SW | ✅ | — | — | Nábor navazující na „Technická škola nanečisto" |

## 17. Provoz laborky – doplňky

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Evidence odpadu a recyklace | SW | ✅ | — | — | Elektroodpad, filament — i pro vykazování |
| Sledování nákladů na provoz jednotlivých strojů | HW+SW | ✅ | ✅ | Proudový senzor (PZEM-004T) | Elektřina + spotřebák → reálná cena hodiny tisku |
| Evidence darů a přijatého vybavení | SW | ✅ | — | — | Vazba na CRM i na účetnictví spolku |

## 18. Řízení lidí, rolí a týmů

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Jednotný systém rolí a oprávnění (RBAC) | SW | — | ✅ | — | Rozšíření sdíleného API jádra o granulární oprávnění napříč všemi moduly — patří do vlny 0, ne jako dodatek |
| Self-service profil uživatele | SW | ✅ | — | — | Každý si sám spravuje svoje údaje, docházku, úkoly bez nutnosti ptát se vedoucího |
| Organizace do týmů/skupin s vedoucími | SW | ✅ | ✅ | — | Přiřazení do soutěžních týmů/ročníků/kroužků. Mat.: delegace schvalování na vedoucí skupin |
| Hromadné onboardingy a offboardingy | SW | ✅ | ✅ | — | Roč.: hromadný import. Mat.: automatické odebrání přístupů a přeřazení rozdělané práce při odchodu |
| Kapacitní plánování lidí (workload) | SW | — | ✅ | — | Kdo má kolik rozdělané práce, aby se nepřetěžoval jeden člověk |
| Matice dovedností a kompetencí | SW | ✅ | ✅ | — | Kdo umí co — usnadní sestavování týmů. Mat.: napojení na hodnocení a autograder |

## 19. Komunikace a koordinace komunity

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Segmentovaná hromadná komunikace | SW | ✅ | — | — | Zpráva jen konkrétní skupině (soutěžící, rodiče, ročník), ne všem najednou |
| Nástěnka/feed novinek pro komunitu | SW | ✅ | — | — | Jedno místo "co se děje" místo opakovaného rozesílání |
| Nástroj na rychlé ankety/hlasování | SW | ✅ | — | — | Rychlé rozhodnutí napříč skupinou bez svolávání schůzky |
| Eskalace upozornění podle hierarchie | SW | — | ✅ | — | Nevyřešený úkol jde na řešitele → vedoucího týmu → teprve pak na vedení |

## 20. Propojení lidí a zdrojů

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Přiřazování zdrojů k týmům/projektům | SW | ✅ | ✅ | — | Mat.: kontrola limitů a upozornění na přečerpání rozpočtu/vybavení |
| Konfigurovatelné schvalovací řetězce | SW | — | ✅ | — | Obecný engine pro schvalování (ne jen objednávky) — routing podle typu žádosti a role |
| Auditní log napříč celým systémem | SW | ✅ | — | — | Kdo co změnil a kdy — nutné pro důvěru při větším počtu lidí s přístupem |
| Zástupná/proxy oprávnění | SW | ✅ | — | — | Zastoupení vedoucího při nepřítomnosti bez změny celé struktury rolí |
| Automatizované sestavování týmů | SW | — | ✅ | — | Matching podle dovedností a dostupnosti — navazuje na matici kompetencí |
| Plánování kapacity prostoru + fronta při omezené kapacitě | SW | ✅ | — | — | Učebny/dílna/výjezdy — kolik lidí se kam reálně vejde |
| Jednotné přihlášení (SSO) s externími systémy | SW | — | ✅ | — | Google Workspace, GitHub, Bakaláři — jeden účet místo hesla pro každý systém |
| Interní helpdesk pro IT požadavky | SW | ✅ | — | — | Žádosti o přístup, reset hesla, podpora na jednom místě |
| Prediktivní odhad potřeby zdrojů podle počtu lidí | SW | — | ✅ | — | Plánování materiálu/rozpočtu dopředu podle očekávaného růstu |
| Nouzové kontakty pro výjezdy a soutěže | SW | ✅ | — | — | Rychlý přístup ke kontaktům při mimoškolní akci |

## 21. Agentní vrstva nad platformou

Vrstva nad hotovými moduly, ne náhrada za ně — agent bez fungujícího zdrojového modulu (sklad, servis, objednávky...) nemá nad čím rozhodovat. Vzor podobný existujícímu multi-agentnímu AI Dev Teamu (hybridní model, schvalování rizikových akcí), jen v operační doméně místo vývojářské.

**Úrovně lidské kontroly (platí napříč všemi agenty níže):**
- Informuje — agent jen upozorní, nic nemění (nízký stav, blížící se termín)
- Navrhuje — připraví návrh/koncept, člověk musí schválit nebo odeslat
- Koná vratnou akci sám — nízké riziko, snadno se to vrátí zpět, vždy zalogováno
- Nikdy bez schválení — cokoliv nevratného, bezpečnostně citlivého nebo týkajícího se dětí jde vždy přes člověka

| Téma | Typ | Ročníková | Maturitní | Hardware | Poznámka |
|---|---|:---:|:---:|---|---|
| Obecný vzor agenta (trigger → data → LLM rozhodnutí → akce/návrh → audit log) | SW | — | ✅ | — | Společný základ pro všechny agenty níže, ne samostatný kód pro každého — implementuje i úrovně kontroly výše |
| Skladový agent | SW | — | ✅ | — | Stav skladu jen hlásí; objednávku při nízkém stavu navrhuje, neodesílá |
| Objednávkový agent | SW | — | ✅ | — | Zkontroluje rozpočet a navrhne objednávku; k dodavateli jde až po schválení člověkem |
| Provozní/databázový agent | SW | — | ✅ | — | Hlídá zálohy, výkon a anomálie v datech — čistě informuje |
| Bezpečnostní agent | SW | — | ✅ | — | Prochází audit log a přístupy, hledá neobvyklé vzorce, hlídá termíny revizí. Vždy jen navrhuje, nikdy sám nerozhoduje — zejména kvůli datům o nezletilých v ZŠ kroužku |
| Servisní/údržbový agent | SW | — | ✅ | — | Hlídá servisní intervaly, propojuje se s wiki na opravy — čistě informuje, opakující se závada je jen signál |
| Rezervační/koordinátorský agent | SW | — | ✅ | — | Nesporné rezervace potvrdí sám (vratná akce), sporné případy vždy eskaluje na člověka |
| Onboardingový/HR agent | SW | — | ✅ | — | Založení účtu je automatické; přidělení citlivější role nebo přístupu potvrzuje člověk |
| Účetní/grantový agent | SW | — | ✅ | — | Spárování dokladů dělá samo; podklad k vykazování před odesláním ven schvaluje člověk |
| Helpdesk agent | SW | — | ✅ | — | Běžné dotazy řeší sám, cokoliv neobvyklého předá člověku beze změny |
| Nábor/komunikační agent | SW | — | ✅ | — | Potvrzení a upomínky automaticky; zamítnutí nebo pořadník vždy schvaluje člověk — týká se i dětí ze ZŠ kroužku |
| Agent na první revizi odevzdaných prací | SW | — | ✅ | — | Připraví návrh hodnocení, nikdy nenahrazuje finální rozhodnutí učitele |
| Agent pro plánování školení | SW | — | ✅ | — | Vstupní brána k použití stroje: řeší prvotní i opakované školení, včetně veřejnosti/externích zájemců — bez úspěšného testu se oprávnění na kartě neaktivuje. Podklady i test čerpá z chatbota/knowledge base agenta nad wiki (sekce 10). Aktivace po testu automatická, ruční zrušení oprávnění má vždy k dispozici i člověk |
| Briefingový agent | SW | — | ✅ | — | Před pravidelnou schůzí (spolek, vedení) sestaví shrnutí ze všech modulů a zvýrazní, co potřebuje rozhodnutí — pouze informuje |
| Prediktivní/plánovací agent | SW | — | ✅ | — | Vyhodnotí trendy (spotřeba, vytížení, růst počtu lidí) a navrhne, co připravit dopředu — pouze navrhuje |
| Agent pro vyhodnocování soutěžní přípravy | SW | — | ✅ | — | Analyzuje tréninková data soutěžících a navrhne úpravu plánu — návrh, trenér rozhoduje |
| Monitorovací (SRE) agent | SW | — | ✅ | — | Hlídá, jestli platforma (API, DB, senzory) skutečně běží, upozorní na výpadek — pouze informuje |
| PR/komunikační agent | SW | — | ✅ | — | Navrhne příspěvek na sociální sítě z proběhlé akce; zveřejnění vždy schvaluje člověk |
| Agent na návrh odpovědí na běžné emaily | SW | — | ✅ | — | Připraví odpověď na opakující se dotazy (rodiče, dodavatelé, zájemci); odeslání jen po schválení |
| Energetický/optimalizační agent | SW | — | ✅ | Proudový senzor (PZEM-004T) | Navrhne úsporu (stroj běží naprázdno) a přesun energeticky náročné práce mimo špičku — pouze navrhuje |
| Agent na organizaci projektových souborů | SW | ✅ | ✅ | — | Roztřídí a otaguje nahrané CAD/STL/zdrojové soubory podle projektu a studenta, upozorní na duplicity — koná vratnou akci sám |
| Agent na přípravu podkladů k inspekci/auditu | SW | — | ✅ | — | Sestaví dokumentaci pro ČŠI nebo grantovou kontrolu z existujících dat; odeslání/podpis vždy člověk |
| Agent na domlouvání schůzek | SW | ✅ | — | — | Najde společný čas napříč kalendáři a navrhne termín; pozvánka jde ven až po potvrzení |
---

## Poznámky k pořadí realizace

- **Nejdřív:** sdílené API jádro + RFID SSO, RFID docházkový terminál — na nich stojí většina ostatních modulů.
- **Napojitelné rovnou:** skladový systém (HW už rozjeto), rezervace, kanban.
- **Až nakonec:** analytický dashboard, mobilní appka, kapacitní plánování — potřebují data z už fungujících modulů.

## Posloupnost realizace a závislosti

**Vlna 0 – základ (musí být hotovo první)**
- Sdílené API jádro + RFID SSO — definuje DB schéma (uživatelé, karty, položky, transakce) a jednotný systém rolí a oprávnění (RBAC) napříč všemi moduly — bez toho se role řeší izolovaně v každém modulu zvlášť

**Vlna 1 – startuje hned po jádru, mezi sebou paralelně**
- RFID docházkový terminál (web+čtečka) — potřebuje tabulku uživatelé/karty z jádra
- Skladový systém – web/API vrstva — potřebuje tabulku položek z jádra (HW už rozjeto nezávisle)
- Přihlašovací formulář a kapacity kroužku ZŠ — jen volná vazba na jádro

*Zcela nezávislé, lze pustit kdykoli souběžně s čímkoli:* wiki/knowledge base, CRM na partnery/sponzory, kanban/task management, grantový tracker, evidence SW licencí, evidence dobrovolnických/mentorských hodin, sledování energií/prostředí (senzory), nástěnka/feed novinek, nástroj na ankety/hlasování, interní helpdesk pro IT požadavky, nouzové kontakty pro výjezdy a soutěže

*Napojuje se přímo na jádro/RBAC z vlny 0:* auditní log napříč systémem, zástupná/proxy oprávnění, jednotné přihlášení (SSO) s externími systémy

**Vlna 2 – potřebují hotovou vlnu 1**
- Evidence skupin ZŠ a docházka na kroužek — potřebuje docházkový terminál + přihlašovací formulář
- Evidence proškolení/oprávnění na stroje — potřebuje identifikační mechanismus z vlny 1
- Objednávkový systém se schvalováním a rozpočtem — potřebuje skladový systém
- Rezervační systém vybavení a laborky — potřebuje jádro, ideálně i evidenci oprávnění
- Rotační rozvrh stanic pro ZŠ skupiny — potřebuje přihlašovací formulář
- Notifikační bot — potřebuje aspoň jeden modul generující události (sklad/objednávky)
- Generování podkladů (docházkové listy, certifikáty) — potřebuje formulář + ZŠ docházku
- Automatické zpracování zápisů schůzek → úkoly (AI) — potřebuje hotový úkolový systém (kanban)
- Self-service profil uživatele — potřebuje jádro + RBAC
- Organizace do týmů/skupin s vedoucími — potřebuje jádro + RBAC
- Segmentovaná hromadná komunikace — potřebuje jádro + RBAC (definice skupin)
- Plánování kapacity prostoru + fronta při omezené kapacitě — potřebuje jádro, souvisí s rezervačním systémem

**Vlna 3 – navazují na vlnu 2**
- Fronta na 3D tiskárny/laser — navazuje na rezervační systém
- Kapacitní plánování strojového času — navazuje na rezervace + senzor dat
- Plánování údržby/kalibrace strojů — navazuje na evidenci oprávnění na stroje
- BOZP/revizní dokumentace — navazuje na evidenci oprávnění na stroje
- Evidence zápůjček vybavení mimo laborku — navazuje na skladový systém
- Rozpočtový přehled laborky — navazuje na objednávkový systém + grantový tracker
- Kiosk dashboard pro laborku — potřebuje aspoň 2 fungující moduly s daty
- Zpětná vazba/dotazník po kroužku — navazuje na ZŠ docházku
- OTA update a zabezpečení ESP32 firmware (sklad) — navazuje na fungující skladový HW
- Napojení e-mailu → automatické úkoly (AI) — navazuje na AI zpracování zápisů schůzek
- Hromadné onboardingy a offboardingy — navazuje na jádro + RBAC (rozšiřuje jednotlivý onboarding o hromadnost a odchody)
- Kapacitní plánování lidí (workload) — navazuje na úkolový systém a týmy
- Matice dovedností a kompetencí — navazuje na týmy, ideálně i na hodnocení/autograder
- Eskalace upozornění podle hierarchie — navazuje na týmy/vedoucí skupin + úkolový systém
- Přiřazování zdrojů k týmům/projektům — navazuje na týmy + objednávkový/rozpočtový systém
- Konfigurovatelné schvalovací řetězce — navazuje na objednávkový systém, zobecňuje jeho schvalování

**Vlna 4 – finální/agregační**
- Analytický dashboard napříč moduly — potřebuje docházku + sklad + objednávky
- Mobilní appka pro studenty — potřebuje stabilní API napříč moduly (docházka, rezervace, objednávky)
- Automatizované sestavování týmů — potřebuje hotovou matici kompetencí a organizaci do týmů
- Prediktivní odhad potřeby zdrojů podle počtu lidí — potřebuje historická data ze skladu a objednávek

V rámci jedné vlny lze zadat víc projektů souběžně různým studentům — mezi sebou nekolidují, jen čekají na stejný předstupeň.

## Poznámka k hardwaru

Kde je to možné, řeší se identifikace/rozhraní jako webová appka na běžném HW (starý PC, mini PC, Raspberry Pi, tablet) + komerční USB RFID/NFC čtečka (HID) – viz webový terminál výše. Vlastní embedded vývoj (ESP32 + firmware) se šetří jen na případy, kdy je potřeba fyzicky něco spínat (zámek, napájení stroje) nebo číst ze senzoru. U senzorových modulů (energie, prostředí, vibrace) zvážit komunikaci přes MQTT místo přímého HTTP, hlavně v odlehlejších částech dílny se slabším WiFi signálem.

## Shrnutí přínosů – co odpadne z ruční práce

**Docházka:** papírové/ruční zapisování na hodiny i kroužky, ruční sčítání u ZŠ kroužku
**Sklad a materiál:** hledání věcí a ruční inventury, ruční odhadování co dochází
**Objednávky a rozpočet:** papírování a chození za schválením, ruční sčítání zůstatků grantů, hlídání termínů vykazování
**Rezervace a stroje:** domlouvání "kdo má kdy stroj" ústně/na tabuli, ruční kontrola oprávnění
**Údržba:** hlídání servisních intervalů v hlavě/kalendáři
**Úkoly a projekty:** ruční psaní kdo co dělá, přepisování úkolů ze schůzky/emailu do systému ručně
**ZŠ kroužek:** ruční přihlašovací tabulka a kapacity, ruční rozdělování dětí do rotací, ruční docházkové listy a certifikáty
**Ostatní:** ruční evidence zápůjček, pamatování kontaktů/historie se sponzory

**Hrubý odhad úspory času (kvalifikovaný odhad, ke zpřesnění po ostrém provozu):**

| Oblast | Odhad úspory/měsíc | Proč |
|---|---|---|
| Docházka (hodiny + kroužky) | 2–4 hod | odpadá ruční zapisování a sčítání |
| Sklad a inventury | 2–3 hod | odpadá hledání a ruční počítání zásob |
| Objednávky a rozpočet | 2–4 hod | odpadá papírování a ruční sčítání grantů |
| Rezervace strojů | 1–2 hod | odpadá domlouvání a řešení kolizí |
| Údržba strojů | 1–3 hod | hlídání servisních intervalů + wiki závad (odpadá opakovaná diagnostika téhož problému) |
| Úkoly + AI ze zápisů/emailu | 3–6 hod | nejvyšší dopad – odpadá ruční přepisování akčních bodů |
| ZŠ kroužek (přihlášky, rotace, certifikáty) | 2–4 hod | hlavně sezónně kolem startu kroužku |
| Zápůjčky a CRM partnerů | ~1 hod | menší, ale eliminuje "kdo má co půjčené" |
| Sync s Bakaláři/ŠkolaOnline | 1–2 hod | odpadá dvojí zapisování docházky |
| OCR účtenek a faktur | 1–3 hod | odpadá ruční přepis dokladů |
| Chatbot nad wiki | 2–4 hod | ubude opakovaných dotazů řešených osobně |
| Hlasové zadávání do skladu/úkolů | ~1 hod | rychlejší zápis přímo u stroje |
| Generátor výkazů a reportů | 3–5 hod | odpadá ruční sestavování podkladů pro granty/vedení |
| Generátor zadání prací z databanky | ~2–3 hod/rok | sezónní, jednou ročně |
| Centralizovaný kalendář termínů | 1–2 hod | odpadá kontrola víc systémů zvlášť |
| Sledovač grantových výzev | 1–2 hod | odpadá ruční procházení webů grantů |
| Porovnávač cen dodavatelů | 1–2 hod | odpadá ruční porovnávání cen před objednáním |
| Týdenní souhrnný digest | 1–2 hod | jeden přehled místo kontroly víc systémů |
| Onboarding nových studentů | ~1 hod | sezónní, na začátku semestru |
| Vzdálený monitoring strojů | 2–3 hod | odpadá chození kontrolovat, jestli tisk běží |
| Generátor testů na stroje | ~1 hod | odpadá ruční vymýšlení testů pokaždé znova |
| Automatické zpracování omluvenek | 1–2 hod | odpadá ruční přepisování do docházky |
| Šablonovač opakované komunikace | 2–3 hod | odpadá psaní podobných emailů pořád dokola |
| Rozpisy služeb/dozorů | ~1 hod | odpadá ruční rozvrhování |
| Evidence klíčů a karet | ~0,5 hod | odpadá papírová kniha předání |
| Automatická archivace prací | ~2 hod | sezónní nárazová práce jednou ročně |
| Fotodokumentace s tříděním | ~1 hod | fotky rovnou použitelné pro vykazování |
| Spotřební materiál u tiskáren | ~1 hod | odpadá ruční kontrola stavu |
| Hromadné operace nad daty | ~1 hod | sezónní, začátek roku |
| Automatické zálohování | ~0,5 hod | odpadá ruční zálohování |
| Sledování expirace materiálu | ~0,5 hod | odpadá ruční kontrola trvanlivosti |
| **Výuka a hodnocení** | 4–8 hod | odevzdávání, automatické hodnocení, banka zadání, podklady pro klasifikaci, přípravy s evidencí zkušeností |
| **Provoz školy mimo laborku** | 1–3 hod | suplování, exkurze, evidence spolupráce s firmami |
| **Osobní produktivita a chod týmu** | 1–2 hod | zápis času, prioritizace, evidence rozhodnutí, předávací protokoly |
| **Soutěžní příprava** | 1–3 hod | evidence tréninků, generování zadání, logistika soutěží |
| **Provoz spolku** | 2–4 hod | členové, příspěvky, podklady pro účetnictví, zápisy ze schůzí |
| **Komunikace navenek a nábor** | 2–4 hod | publikování novinek, rozesílky rodičům, evidence zájemců |
| **Provoz laborky – doplňky** | 1–2 hod | odpad, náklady na stroje, evidence darů |

Součet všech položek vychází na **50–80 hodin měsíčně**, ale to je horní strop za předpokladu, že vše běží a nic se nepřekrývá. Realisticky:
- Část položek se překrývá (digest vs. kalendář, kanban vs. AI extrakce úkolů)
- Systémy samy potřebují údržbu — část úspory se vrátí zpět jako provozní režie
- Ne všechno bude nasazeno současně

**Pro grantové zdůvodnění doporučeno uvádět konzervativní spodní hranici** (např. 20 hodin měsíčně) — je obhajitelná a i tak jde o půl pracovního týdne měsíčně, který lze věnovat výuce, projektům a přípravě soutěžících místo administrativy.

## Jak dokument rozšiřovat

Nová témata přidávat do odpovídající kategorie (případně založit novou). U každého tématu udržovat: typ (HW/SW/HW+SW), vhodnost pro ročníkovou/maturitní práci, konkrétní hardware (pokud relevantní) a poznámku k rozsahu nebo závislostem na jiných modulech.
