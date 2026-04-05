#!/usr/bin/bash

# shellcheck disable=SC2034
for i in 1 2 3 4; do
  curl -s -X POST http://0.0.0.0:8000/api/auth/otp/send/ \
    -H "Content-Type: application/json" \
    -d '{"phone_number": "+1234567899"}'
  echo ""
done