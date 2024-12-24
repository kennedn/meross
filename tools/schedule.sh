#!/bin/bash

jq -r '
.schedule | 
    map(((.id // .channel) | tostring) as $id | {mon,tue,wed,thu,fri,sat,sun} | to_entries |
            map( 
                .key as $day |
                .value | 
                    (map(.[0]) | reduce .[] as $item ([[0,0]]; . += [[.[-1][1], $item + .[-1][1]]]) | .[1:]) as $min | 
                    map(.[1] * 10.01 | round / 100 | tostring) as $temp | 
                    {$day,$min, $temp}
            ) as $data |
        {$id, $data}
    ) |
.[] |
[
    .id + ":",(.data | map(
        [
            ("  " + .day | ascii_upcase),
            .min as $min | .temp | to_entries | map(
                "    \(.value[:-1])°C between \($min[.key][0] | tonumber * 60 | strftime("%H:%M")) - \($min[.key][1] | tonumber * 60 | strftime("%H:%M"))") | join("\n")
        ] | join("\n")
    ) | join("\n"))
] | join("\n") 
'
