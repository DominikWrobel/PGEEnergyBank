# PGE Wirtualny Magazyn Energii — integracja Home Assistant

Wersja **0.1.0 (wersja testowa)**. Lokalna integracja przeznaczona dla prosumentów w systemie opustów 0,8, korzystających z narastających liczników importu i eksportu **po bilansowaniu netto** (np. [Balance Neto](https://github.com/miguelangellv/ha-balance-neto)). Dla każdego punktu rozliczeniowego należy dodać osobny wpis integracji.

## Instalacja

1. Zrób kopię zapasową Home Assistant.
2. Rozpakuj archiwum. Skopiuj folder `custom_components/pge_energy_bank` do `/config/custom_components/pge_energy_bank` w HA.
3. Uruchom ponownie Home Assistant.
4. Wejdź w **Ustawienia → Urządzenia i usługi → Dodaj integrację → PGE Wirtualny Magazyn Energii**.
5. Dla **Góry** wybierz:
   - import: `sensor.energia_gora_import`
   - eksport: `sensor.energia_gora_eksport`
   - nazwę: `PGE Góra`
   - saldo początkowe w kWh i **datę pochodzenia tej energii**.
6. Ponownie dodaj tę samą integrację dla **Dołu**:
   - import: `sensor.energia_dol_import`
   - eksport: `sensor.energia_dol_eksport`
   - nazwę: `PGE Dół`
   - saldo początkowe i datę pochodzenia.
7. HA utworzy po **jednym sensorze** na wpis: „Stan magazynu” (kWh). Jeśli chcesz, zmień ich ID w ustawieniach encji, np. na `sensor.pge_magazyn_gora` i `sensor.pge_magazyn_dol`.

Nie ma potrzeby tworzyć helperów, skryptów, dodatkowych sensorów ani automatyzacji.

## Działanie

- Śledzi **narastające** liczniki netto wyrażone w kWh lub Wh, nie wartości chwilowe i nie liczniki zerowane co dobę/miesiąc.
- Naliczanie: wzrost salda = 80% nowego eksportu netto minus nowy import netto. Rozlicza zmiany obu liczników w jednym kroku po 40 sekundach od ich ostatniej zmiany (dodatkowo kontrola co godzinę).
- Pobór energii zużywa najstarsze dostępne partie (FIFO). Saldo nie spada poniżej **0 kWh** i nie przenosi ujemnego długu.
- Energia oddana w miesiącu otrzymuje jego datę rozliczeniową. Partie są usuwane **pierwszego dnia miesiąca następującego po 12-miesięcznym okresie wykorzystania** (na podstawie założenia o datowaniu wprowadzanej energii na ostatni dzień miesiąca, zgodnie z art. 4 ust. 5 i 5a ustawy o OZE).
- Dane FIFO, poprzednie wskazania liczników i korekty są zapisywane w `/config/.storage/` — nie należy edytować ich ręcznie.
- Jeden sensor na magazyn ma `state_class: measurement`, co pozwala HA tworzyć statystyki długoterminowe **min/średnia/maks. salda**. Żadna dodatkowa encja nie jest tworzona.
- Przy zaniku liczników źródłowych naliczanie jest wstrzymane do powrotu prawidłowych odczytów. Przy spadku narastającego licznika (jego resecie) następuje trwałe wstrzymanie danej instancji do ręcznej korekty, aby nie naliczać błędnych różnic.

## Korekta po rachunku

W **Ustawienia → Urządzenia i usługi** wejdź do odpowiedniej instancji i wybierz **Konfiguruj**. Podaj nowy stan w kWh oraz datę pochodzenia salda. Zatwierdzenie zastępuje cały dotychczasowy rozkład partii FIFO **jedną partią** (o wskazanej dacie), ustawia odczyty liczników źródłowych jako nową bazę oraz nie przenosi dawnego deficytu. Przy korekcie należy wpisać stan magazynu **na dzisiaj**; jeśli faktura dotyczy wcześniejszej daty, trzeba najpierw uwzględnić późniejsze zużycie i oddanie.

**Ważne ograniczenie historyczne:** Jeżeli obecne saldo składa się z nadwyżek z wielu miesięcy, pojedyncza liczba z faktury nie wystarczy do rekonstrukcji ich terminów wygaśnięcia. Podana data jest więc przybliżeniem dla początkowego salda i korekty. Aby uzyskać ścisłe FIFO historyczne, konieczne byłyby miesięczne partie energii z faktur. Po rozpoczęciu śledzenia nowych nadwyżek integracja prowadzi ich FIFO automatycznie.

## Ograniczenia / testy

- To samodzielny projekt demonstracyjny, **nieoficjalny** i **nieprzetestowany w uruchomionej instancji HA 2026.10**. Testy automatyczne obejmują samą matematykę salda/FIFO, nie cykl życia integracji w HA.
- Nie uwzględnia złożonych reguł taryf wielostrefowych, rozbieżności między danymi licznika a odczytami operatora, korekt operatora ani rekonstrukcji historii z dnia faktury.
- Dla krótkich przedziałów, kiedy import i eksport źródłowy zmieniają się z dużym przesunięciem czasowym, wyniki mogą być przejściowo inne; użyto opóźnienia 40 s.
- Długoterminowe statystyki tworzy `recorder` HA. HA może przechowywać krótkoterminowe stany przez standardowy czas retencji; integracja nie zapisuje importu, eksportu ani partii FIFO w jego historii jako dodatkowych encji.
- Zrób backup folderu `.storage` przed ponowną instalacją/eksperymentami.

## Weryfikacja

Po uruchomieniu sprawdź: 1) saldo początkowe; 2) zwiększenie po nowym eksporcie netto; 3) spadek po imporcie; 4) brak wartości ujemnych; 5) korektę salda i restart HA; 6) po kilku godzinach obecność sensora w **Narzędzia deweloperskie → Statystyki**.
