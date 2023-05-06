#!/bin/bash

## Nondisruptive commands
# check current shift totals
curl localhost:8080/api/rro/eusign/cmd/1/LastShiftTotals | python3 -m json.tool

# check particular shift full doc list
curl localhost:8080/api/rro/eusign/cmd/1/Documents/566246891 | python3 -m json.tool

## Actual work
# create a new shift
curl -H "Content-Type: application/json" -X POST -d '{"cashier":"Test2", "test_mode": "1"}' localhost:8080/api/rro/eusign/shift/1

# we need to extract the proper value here of course
SHIFTID=3

# fiscalise a few checks
curl -H "Content-Type: application/json" -X POST -d '{"doc_id":"788836", "shift_id":"$SHIFTID", "test_mode": "1" }' localhost:8080/api/rro/eusign/receipt/1
curl -H "Content-Type: application/json" -X POST -d '{"doc_id":"788837", "shift_id":"$SHIFTID", "test_mode": "1" }' localhost:8080/api/rro/eusign/receipt/1

# service cashin/cashout
curl -H "Content-Type: application/json" -X POST -d '{"doc_id":"123456", "shift_id":"$SHIFTID", "test_mode": "1" }' localhost:8080/api/rro/eusign/cashinout/1

# publish a report for shift $SHIFTID from rro id 1 in test mode
curl -H "Content-Type: application/json" -X POST -d '{"shift_id":"$SHIFTID","test_mode":"1"}' localhost:8080/api/rro/eusign/zreport/1

# close shift $SHIFTID for rro 1
curl -H "Content-Type: application/json" -X PUT -d '{"shift_id":"$SHIFTID","test_mode":"1"}' localhost:8080/api/rro/eusign/shift/1
