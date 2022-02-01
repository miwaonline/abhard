#!/bin/bash

# create a new shift
curl -H "Content-Type: application/json" -X POST -d '{"cashier":"Test2", "test_mode": "1"}' localhost:8080/api/rro/eusign/shift/1

# fiscalise check
curl -H "Content-Type: application/json" -X POST -d '{"doc_id":"788836", "shift_id":"3", "test_mode": "1" }' localhost:8080/api/rro/eusign/receipt/1
curl -H "Content-Type: application/json" -X POST -d '{"doc_id":"788837", "shift_id":"3", "test_mode": "1" }' localhost:8080/api/rro/eusign/receipt/1

# publish a report for shift id 2 from rro id 1 in a test mode
curl -H "Content-Type: application/json" -X POST -d '{"shift_id":"3","test_mode":"1"}' localhost:8080/api/rro/eusign/zreport/1

# close shift #2 for rro 1
curl -H "Content-Type: application/json" -X PUT -d '{"shift_id":"3","test_mode":"1"}' localhost:8080/api/rro/eusign/shift/1
