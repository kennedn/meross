bthome_status() {
  curl -sX POST "https://api.kennedn.com/v2/radiator?hosts=kitchen,livingroom_back,livingroom_front,office&code=status" | jq -r "([\"NAME\",\"ONOFF\",\"MODE\",\"CURRENT\",\"TARGET\"] | @tsv),(.data[] | [.name,.status.onoff,.status.mode,.status.temperature.current,.status.temperature.target] | @tsv)" | column -t
}
radiator_status() {
  curl -sX POST "https://api.kennedn.com/v2/bthome?hosts=office,bedroom,livingroom,kitchen&code=status" | jq -r "[(.data.devices[] | .status = {name: (.name | ascii_upcase)} + .status)] | (.[0].status | keys_unsorted | map(ascii_upcase) | @tsv),(.[] | [.status[]] | @tsv)" | column -t
}

