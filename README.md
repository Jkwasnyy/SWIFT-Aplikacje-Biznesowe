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

### 2. Start serwera SWIFT

```
python -m app.main
```

### 3. Start mock banków

```
python mocks/mock_bank.py 3001
...
python mocks/mock_bank.py 3006
```

Docelowo symulujemy 6 banków:

- Polska: `PLBANK1XXX`, `PLBANK2XXX`
- Wielka Brytania: `UKBANK1XXX`, `UKBANK2XXX`
- USA: `USBANK1XXX`, `USBANK2XXX`

## Test

### PowerShell:

```
Invoke-WebRequest -Uri http://localhost:3000/swift/message `
  -Method POST `
  -ContentType "application/xml" `
  -InFile payment.xml
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

## Autorzy

- Kacper Kowalski
- Jakub Kwaśniak
