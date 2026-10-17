# PGE Wirtualny Magazyn Energii — integracja Home Assistant

Wersja **0.1.0 (wersja testowa)**. Lokalna integracja przeznaczona dla prosumentów w systemie opustów 0,8, korzystających z narastających liczników importu i eksportu **po bilansowaniu netto** (np. [Balance Neto](https://github.com/miguelangellv/ha-balance-neto)). Dla każdego punktu rozliczeniowego należy dodać osobny wpis integracji.

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


