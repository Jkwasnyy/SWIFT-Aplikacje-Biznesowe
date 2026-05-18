# SWIFT Middleware Simulation

## Opis projektu

Projekt symuluje działanie sieci SWIFT jako pośrednika między bankami. Bank wysyłający przygotowuje komunikat w uproszczonym, ale realistycznym formacie ISO 20022, a system:

- waliduje komunikat,
- odczytuje dane płatności,
- sprawdza bank odbiorcy po BIC,
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

W panelu możesz:

- pobrać token demo,
- wysłać `payment.xml`,
- zobaczyć listę oczekujących przelewów,
- podejrzeć ostatnie wpisy z `logs.txt`,
- anulować przelew w oknie anulowania.

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

Docelowo symulujemy 6 banków:

- Polska: `PLBANK1XXX`, `PLBANK2XXX`
- Wielka Brytania: `UKBANK1XXX`, `UKBANK2XXX`
- USA: `USBANK1XXX`, `USBANK2XXX`

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

## Realistyczne rozszerzenia (dodane)

- **OAuth2 (mock)**: prosty endpoint `/auth/token` umożliwia wydanie tokenu typu `Bearer` dla testowego klienta. Endpointy `/swift/message` i `/swift/cancel/<uetr>` wymagają tokenu.
- **Routing wieloskokowy**: topologia sieci banków znajduje się w `app/core/config.py` i jest używana przez `app/services/router.py` do wyznaczania trasy (BFS) z banku A do banku B przez banki pośredniczące.
- **Okno anulowania**: wiadomości są teraz planowane do wysłania z opóźnieniem (`FORWARD_DELAY_SECONDS` w `app/core/config.py`). W czasie opóźnienia można anulować przelew przez `POST /swift/cancel/<uetr>`.
- **Konfiguracja**: ustawienia OAuth, sieci banków i polityki forwarding/cancel znajdują się w `app/core/config.py` dla łatwej edycji.

Zmienione pliki: [app/core/config.py](app/core/config.py), [app/core/auth.py](app/core/auth.py), [app/services/scheduler.py](app/services/scheduler.py), [app/services/router.py](app/services/router.py), [app/api/routes.py](app/api/routes.py)

## Co można jeszcze dodać, żeby było bliżej prawdziwego SWIFT-a

- Integracja z prawdziwym Identity Provider (OAuth2 Authorization Code / JWT) zamiast mocka.
- Szyfrowanie i podpis XML (XMLDSig / XMLEnc) oraz wymuszanie TLS mutual.
- Trwała kolejka (RabbitMQ / Kafka) zamiast timers/in-memory, by obsłużyć retry i skalowanie.
- Audyt i śledzenie stanu wiadomości w bazie danych (statusy, historyczne wydarzenia).
- Symulacja potwierdzeń (ACK/NACK) oraz retry/backoff dla transient errors.
- Wsparcie różnych schematów opłat i rozliczeń (np. ultimateCreditor, charges information fields).
- Bogatsze walidacje ISO 20022 (schemat XSD validation) i mapowanie na pola CBPR+.

## Autorzy

- Kacper Kowalski
- Jakub Kwaśniak
