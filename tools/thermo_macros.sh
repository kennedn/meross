thermostat_status() {
  curl -sX POST "https://api.kennedn.com/v2/thermostat?code=status" \
    | jq -r '
      (["NAME","ONOFF","MODE","CURRENT","TARGET","HEATING","OPEN_WINDOW"] | @tsv),
      ([
        "THERMOSTAT",
        .data.onoff,
        .data.mode,
        .data.temperature.current,
        .data.temperature.target,
        (.data.temperature.heating    | tostring | ascii_upcase),
        (.data.temperature.openWindow | tostring | ascii_upcase)
      ] | @tsv)
    ' | column -t
}

bthome_status() {
  curl -sX POST "https://api.kennedn.com/v2/bthome?hosts=office,bedroom,livingroom,kitchen&code=status" \
    | jq -r '
      [
        (.data.devices[]
         | .status = { name: (.name | ascii_upcase) } + .status
        )
      ]
      | (.[0].status | keys_unsorted | map(ascii_upcase) | @tsv),
        (.[] | [.status[]] | @tsv)
    ' | column -t
}

radiator_status() {
  curl -sX POST "https://api.kennedn.com/v2/radiator?hosts=kitchen,livingroom,office&code=status" \
    | jq -r '
      (["NAME","ID","ONOFF","MODE","CURRENT","TARGET","HEATING","OPEN_WINDOW"] | @tsv),
      (
        .data[]
        | [
            (.name | ascii_upcase),
            .status.id,
            .status.onoff,
            .status.mode,
            .status.temperature.current,
            .status.temperature.target,
            (.status.temperature.heating | tostring | ascii_upcase),
            (.status.temperature.openWindow | tostring | ascii_upcase)
          ]
        | @tsv
      )
    ' | column -t
}

radiator_battery() {
  curl -sX POST "https://api.kennedn.com/v2/radiator?hosts=kitchen,livingroom,office&code=battery" \
    | jq -r '
      (["NAME","ID","BATTERY(%)"] | @tsv),
      (
        .data[]
        | [
            .name,
            .status.id,
            .status.value
          ]
        | @tsv
      )
    ' | column -t
}

radiator_schedule() {
  jq -r '
    (["NAME","DAY","ID","START","END","TEMPERATURE(°C)"] | @tsv),
    (
      {
        "03000BDF":"OFFICE",
        "0300B980":"LIVING1",
        "0300B1F7":"LIVING2",
        "0300CA57":"KITCHEN"
      } as $device_names
      |
      [
        .schedule[] as $sched
        | ["mon","tue","wed","thu","fri","sat","sun"][] as $day
        | ($sched[$day] // []) as $arr
        | foreach $arr[] as $it
            (0;
             . + ($it[0] * 60);
             {
               name:  $device_names[$sched.id],
               day:   ($day | ascii_upcase),
               id:    $sched.id,
               start: (. - ($it[0] * 60) | strftime("%H:%M")),
               end:   (. | strftime("%H:%M")),
               temp:  ($it[1] / 10)
             })
      ]
      | map([.name, .day, .id, .start, .end, (.temp | tostring)] | @tsv)[]
    )
  ' | column -t
}

