# SWIFT Middleware Simulation

## Opis projektu

Projekt symuluje działanie sieci SWIFT jako pośrednika między bankami. Bank wysyłający przygotowuje komunikat w uproszczonym, ale realistycznym formacie ISO 20022, a system:

- waliduje komunikat,
- odczytuje dane płatności,
- sprawdza bank odbiorcy po BIC,
- sprawdza konto odbiorcy i odrzuca zamknięte / nieistniejące rachunki,
- wyznacza najkrótszą czasowo trasę przez banki korespondentów,
- liczy i pokazuje podział opłat zależny od `ChrgBr`,
- przekazuje wiadomość do odpowiedniego mock-banku,
- zapisuje przebieg operacji w logach.

## Jak to działa

1. Bank wysyła komunikat XML do endpointu `/swift/message`
2. System parsuje dane płatności, BIC-y, identyfikator wiadomości, referencję instrukcji i pole `ChrgBr`
3. Wykonywana jest podstawowa walidacja kontraktu i routingu
4. Na podstawie odbiorcy (BIC) wybierany jest docelowy bank
5. Wiadomość zostaje przekazana dalej (HTTP POST) z nagłówkami logistycznymi
6. Mock-bank przyjmuje, odrzuca albo potwierdza komunikat
7. Operacja jest zapisywana w logach

## Struktura

- `app/` – logika aplikacji (API, serwisy, modele)
- `mocks/` – testowe banki
- `config.py` – mapa banków (BIC → URL + metadane)
- `logs.txt` – zapis operacji

## Uruchomienie

### 1. Instalacja zależności

```
pip install -r requirements.txt
```

### 2. Start projektu

Najprościej uruchomić całość jednym plikiem:

```powershell
.\run.bat
```

To odpala mock-banki, backend i zapisuje PID-y do `scripts/pids.txt`.

### 3. Zatrzymanie projektu

```powershell
.\stop.bat
```

### 4. Wejście do frontendu

Po starcie otwórz w przeglądarce:

```text
http://localhost:3000/
```

## Uruchomienie w Dockerze (np. na uczelni)

Jeśli na danym komputerze jest już zainstalowany Docker Desktop (lub Docker Engine + Compose), możesz uruchomić cały projekt bez lokalnego Pythona i bez ręcznego odpalania wielu procesów.

### 1. Zbuduj i uruchom kontenery

```powershell
docker compose up --build -d
```

To uruchamia:

- `swift-app` (backend + frontend pod portem `3000`),
- `mock-banks` (wszystkie 6 mock-banków wewnątrz sieci Dockera).

### 2. Otwórz aplikację

```text
http://localhost:3000/
```

### 3. Podejrzyj logi

```powershell
docker compose logs -f
```

### 4. Zatrzymaj kontenery

```powershell
docker compose down
```

Jeśli chcesz dodatkowo usunąć zbudowane obrazy po zakończeniu pracy:

```powershell
docker compose down --rmi local
```

W panelu możesz:

- pobrać token demo,
- wysłać `payment.xml`,
- otworzyć Swagger UI pod `http://localhost:3000/docs`,
- zobaczyć listę oczekujących przelewów,
- podejrzeć trasę, ETA i podział opłat,
- podejrzeć ostatnie wpisy z `logs.txt`,
- anulować przelew w oknie anulowania.

Pliki scenariuszy testowych znajdziesz w `mocks/test_payments/`:

- `payment1.xml` - poprawny przelew z bezpośrednią trasą
- `payment2.xml` - poprawny przelew z trasą wieloskokową i innym `ChrgBr`
- `payment3.xml` - przelew na zamknięte konto
- `payment4.xml` - przelew na nieistniejące konto

### 5. Start ręczny (opcjonalnie)

Jeśli chcesz uruchamiać wszystko osobno:

```
python -m app.main
```

```powershell
python mocks/mock_bank.py 3001
python mocks/mock_bank.py 3002
python mocks/mock_bank.py 3003
python mocks/mock_bank.py 3004
python mocks/mock_bank.py 3005
python mocks/mock_bank.py 3006
```

Docelowo symulujemy 6 banków (BIC-like IDs):

- Polska: `PLBKPL01XXX`, `PLBKPL02XXX`
- Wielka Brytania: `UKBKGB01XXX`, `UKBKGB02XXX`
- USA: `USBKUS01XXX`, `USBKUS02XXX`

## Test

Przykładowe wywołanie API z PowerShell:

```powershell
$tokenResponse = Invoke-WebRequest -Uri http://localhost:3000/auth/token -Method POST -Body @{client_id='test-client'; client_secret='test-secret'} -UseBasicParsing
$token = (ConvertFrom-Json $tokenResponse.Content).access_token

Invoke-WebRequest -Uri http://localhost:3000/swift/message -Method POST -Headers @{ Authorization = "Bearer $token" } -ContentType "application/xml" -InFile payment.xml -UseBasicParsing
```

## Przykładowy komunikat

System używa uproszczonego, ale bardziej realistycznego XML inspirowanego ISO 20022 z nagłówkiem wiadomości, identyfikatorem instrukcji, BIC-ami banków, informacją o przelewie i polem `ChrgBr`, które określa kto ponosi opłatę.

## Pola komunikatu

- `MsgId` - identyfikator całej wiadomości
- `CreDtTm` - czas utworzenia wiadomości
- `InstrId` - identyfikator instrukcji płatniczej
- `Dbtr` - nazwa zleceniodawcy
- `DbtrAgt` - bank zleceniodawcy
- `Cdtr` - nazwa odbiorcy
- `CdtrAgt` - bank odbiorcy
- `InstdAmt` - kwota i waluta przelewu
- `ChrgBr` - sposób podziału opłat za przelew
- `RmtInf` - opis / tytuł przelewu

## Podział opłat

Pole `ChrgBr` mówi, kto płaci za przelew:

- `DEBT` - płaci nadawca
- `CRED` - płaci odbiorca
- `SHAR` - koszty są dzielone
- `SLEV` - zasady opłat są ustalane przez schemat usługi

W tym symulatorze to pole ustawia bank wysyłający jeszcze przed wysłaniem wiadomości do systemu.

## Kto za co odpowiada

- bank wysyłający tworzy komunikat i ustawia `ChrgBr`, BIC-y oraz kwotę,
- nasz system sprawdza poprawność i routuje wiadomość,
- mock-bank symuluje odpowiedź banku docelowego,
- logi pokazują cały przebieg transmisji.

## Funkcjonalności

- odbiór komunikatów XML
- parsowanie danych płatności
- routing między bankami
- forward wiadomości
- logowanie operacji

## Realistyczne rozszerzenia

- **OAuth2 (mock)**: prosty endpoint `/auth/token` umożliwia wydanie tokenu typu `Bearer` dla testowego klienta. Endpointy `/swift/message` i `/swift/cancel/<uetr>` wymagają tokenu.
- **Routing wieloskokowy**: topologia sieci banków znajduje się w `app/core/config.py` i jest używana przez `app/services/router.py` do wyznaczania najszybszej trasy przez banki pośredniczące.
- **Podział opłat**: `app/services/settlement.py` oblicza opłatę całkowitą i rozbija ją zgodnie z `ChrgBr`.
- **Walidacja rachunków**: system sprawdza, czy rachunek odbiorcy istnieje i ma status `open`; zamknięte lub brakujące konto kończy się błędem.
- **Okno anulowania**: wiadomości są teraz planowane do wysłania z opóźnieniem (`FORWARD_DELAY_SECONDS` w `app/core/config.py`). W czasie opóźnienia można anulować przelew przez `POST /swift/cancel/<uetr>`.
- **Konfiguracja**: ustawienia OAuth, sieci banków i polityki forwarding/cancel znajdują się w `app/core/config.py` dla łatwej edycji.

## Autorzy

- Kacper Kowalski
- Jakub Kwaśniak
