#!/bin/bash
ACCESS_TOKEN=$(cat .access_token)
APP_TOKEN="1095803192492789|4855d6cabdffb2b5fbc12ad8520e2847"
curl -X GET "https://graph.facebook.com/debug_token?input_token=$ACCESS_TOKEN&access_token=$APP_TOKEN" 