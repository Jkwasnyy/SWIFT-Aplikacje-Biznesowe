#!/bin/sh
set -eu

python mocks/mock_bank.py 3001 &
python mocks/mock_bank.py 3002 &
python mocks/mock_bank.py 3003 &
python mocks/mock_bank.py 3004 &
python mocks/mock_bank.py 3005 &
python mocks/mock_bank.py 3006 &
python mocks/mock_bank.py 3007 &
python mocks/mock_bank.py 3008 &

wait
