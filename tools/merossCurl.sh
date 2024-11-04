#!/bin/bash
SCRIPT_NAME=$(basename "$0")
help() {
  echo -e "usage: $SCRIPT_NAME IP_ADDR METHOD ABILITY KEY JSON\n"
  echo -e "simple shell wrapper for making REST calls to meross devices\n"
  echo -e "arguments:"
  echo -e "IP_ADDR\t\tmeross device ip"
  echo -e "METHOD\t\tmeross ability method, [GET|SET]"
  echo -e "ABILITY\tmeross ability"
  echo -e "KEY\t\tkey setup during device onboarding"
  echo -e "JSON\t\tpayload to send to ability"
  exit 1
} 1>&2

[ "${#}" != 5 ] && help

ts=0 # Supposed to be a unix epoch of the current time but can be any value
key=${4} # Must match the key configured during onboarding (can be left blank on older firmware)
messageID=$(dd if=/dev/urandom bs=1 count=16 2>/dev/null | xxd -p) # Can be any value but must be unique on newer devices
sign=$(printf "%s%s%s" "${messageID}" "${key}" "${ts}" | md5sum | awk -F\  '{print $1}')

# Argfile removed after jq-1.6
JSON=
if jq --help | grep -q -- --slurpfile; then
  JSON=$(jq -cn \
        --arg messageID "$messageID" \
        --arg method "$2" \
        --arg namespace "$3" \
        --arg sign "$sign" \
        --arg ts "$ts" \
        --slurpfile payload <(echo "${5}") \
        '{header: {from: "http://10.10.10.1/config", messageId: $messageID, method: $method, namespace: $namespace, payloadVersion: 1, sign: $sign, timestamp: $ts }, payload: $payload[0]}' )
else
  JSON=$(jq -cn \
        --arg messageID "$messageID" \
        --arg method "$2" \
        --arg namespace "$3" \
        --arg sign "$sign" \
        --arg ts "$ts" \
        --argfile payload <(echo "${5}") \
        '{header: {from: "http://10.10.10.1/config", messageId: $messageID, method: $method, namespace: $namespace, payloadVersion: 1, sign: $sign, timestamp: $ts }, payload: $payload}' )
fi



curl --connect-timeout 3 \
--header "Content-Type: application/json" \
--data "${JSON}" "http://${1}/config"
