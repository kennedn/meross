#!/bin/bash
SCRIPT_NAME=$(basename "$0")
cd "$(dirname "$0")" || exit

help() {
cat << EOF
usage: $SCRIPT_NAME [-hPkuspbceC] [TERM]...
Onboard a meross device to the network
Example: $SCRIPT_NAME --wifi

Options:
  -d,--host HOST
        specify the MQTT host to connect to, optional
  -P,--port PORT
        specify the MQTT port to connect to, optional
  -u,--userid USERID
        specify a meross cloud user ID, optional
  -k,--key KEY
        specify a key, which will then be required to query the device after onboarding, optional for older devices
  -s,--ssid SSID
        specify the SSID of the WiFi network
  -p,--password PASSWORD
        specify the password for the WiFi network
  -b,--bssid BSSID
        specify the BSSID of the WiFi network
  -c,--channel CHANNEL
        specify the channel of the WiFi network
  -e,--encryption ENCRYPTION
        specify the encryption type of the WiFi network
  -C,--cipher CIPHER
        specify the cipher type of the WiFi network
  -w,--wifi
        list available WiFi networks
  -j,--from-json
        specify a wifi json object obtained from running --wifi
  -h,--help
        print this message
EOF
exit 1
} 1>&2

[ "$#" -eq 0 ] && help

list_wifi() {
  echo "Wifi scan initiated (takes around 10 seconds)..." 1>&2
  ./merossCurl.sh 10.10.10.1 GET Appliance.Config.WifiList "" '{}' | jq --arg ssid "$1" -r '.payload.wifiList[] | select (($ssid == "") or (.ssid | @base64d == $ssid)) | {"ssid": .ssid | @base64d, "bssid":.bssid, "channel": .channel, "encryption": .encryption, "cipher": .cipher, "signal strength": .signal}'
}

configure() {
  host=$1
  port=$2
  key=$3
  userid=$4
  
  CONFIG_JSON=$(jq -cn \
         --arg host "$host" \
         --arg port "$port" \
         --arg key "$key" \
         --arg userid "$userid" \
        '{
          "key": {
            "gateway": {
              "host": $host,
              "port": $port,
            },
            "key": $key,
            "userId": $userid
          }
        }')

  ./merossCurl.sh 10.10.10.1 SET Appliance.Config.Key "" "$CONFIG_JSON" | jq -c && echo "Key configured" 1>&2
}

wifi_connect() {
  ssid=$(printf "%s" "$1" | base64 -w0)
  password=$(printf "%s" "$2" | base64 -w0)
  bssid=$3
  channel=$4
  encryption=$5
  cipher=$6
  
  WIFI_JSON=$(jq -cn \
         --arg ssid "$ssid" \
         --arg password "$password" \
         --arg bssid "$bssid" \
         --arg channel "$channel" \
         --arg encryption "$encryption" \
         --arg cipher "$cipher" \
        '{
          "wifi": {
            "ssid": $ssid,
            "password": $password,
            "bssid": $bssid,
            "channel": $channel,
            "encryption": $encryption,
            "cipher": $cipher
            }
        }')
  ./merossCurl.sh 10.10.10.1 SET Appliance.Config.Wifi "" "$WIFI_JSON" | jq -c && echo "Wifi configured" 1>&2
}

POSITIONAL=()
arg_count=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    -j|--from-json)
      JSON=$2
      shift 2
      ((arg_count++))
      ;;
    -d|--host)
      HOST=$2
      shift 2
      ((arg_count++))
      ;;
    -P|--port)
      PORT=$2
      shift 2
      ((arg_count++))
      ;;
    -k|--key)
      KEY=$2
      shift 2
      ((arg_count++))
      ;;
    -u|--userid)
      USERID=$2
      shift 2
      ((arg_count++))
      ;;
    -s|--ssid)
      SSID=$2
      shift 2
      ((arg_count++))
      ;;
    -p|--password)
      PASSWORD=$2
      shift 2
      ((arg_count++))
      ;;
    -b|--bssid)
      BSSID=$2
      shift 2
      ((arg_count++))
      ;;
    -c|--channel)
      CHANNEL=$2
      shift 2
      ((arg_count++))
      ;;
    -e|--encryption)
      ENCRYPTION=$2
      shift 2
      ((arg_count++))
      ;;
    -C|--cipher)
      CIPHER=$2
      shift 2
      ((arg_count++))
      ;;
    -w|--wifi)
      WIFI=$2
      shift 2
      list_wifi "${WIFI}"
      exit 0
      ;;
    -h|--help)
      help
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done
set -- "${POSITIONAL[@]}"

[ -z "$HOST" ] && HOST=127.0.0.1
[ -z "$PORT" ] && PORT=8883

if [ -n "${JSON}" ]; then
  [ -z "${SSID}" ] && SSID=$(jq -r '.ssid' <<<"${JSON}")
  [ -z "${BSSID}" ] && BSSID=$(jq -r '.bssid' <<<"${JSON}")
  [ -z "${CHANNEL}" ] && CHANNEL=$(jq -r '.channel' <<<"${JSON}")
  [ -z "${ENCRYPTION}" ] && ENCRYPTION=$(jq -r '.encryption' <<<"${JSON}")
  [ -z "${CIPHER}" ] && CIPHER=$(jq -r '.cipher' <<<"${JSON}")
fi

if [ -z "$SSID" ] || [ -z "$PASSWORD" ] || [ -z "$BSSID" ] || [ -z "$CHANNEL" ] || [ -z "$ENCRYPTION" ] || [ -z "$CIPHER" ]; then
  echo "Error: Required WiFi connection parameters are missing."
  help
fi

configure "$HOST" "$PORT" "$KEY" "$USERID"
wifi_connect "$SSID" "$PASSWORD" "$BSSID" "$CHANNEL" "$ENCRYPTION" "$CIPHER"
