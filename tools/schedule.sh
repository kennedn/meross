#!/bin/bash
jq -r '
  (["NAME","DAY","START","END","TEMPERATURE(°C)"] | @tsv),
  (
    {
      "03000BDF":"OFFICE",
      "0300B980":"LIVRM1",
      "0300B1F7":"LIVRM2",
      "0300CA57":"KITCHE"
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
             name: $device_names[$sched.id],
             day:  ($day | ascii_upcase),
             start: (. - ($it[0] * 60) | strftime("%H:%M")),
             end:   (. | strftime("%H:%M")),
             temp:  ($it[1] / 10)
           })
    ]
    | map([.name, .day, .start, .end, (.temp|tostring)] | @tsv)[]
  )
'

