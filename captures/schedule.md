Each day is represented by 6 tuples:

"sun":[[120,200],[60,250],[300,250],[300,100],[240,250],[120,200]]}]}

With each tuple meaning:

| idx 0 | idx 1 |
|-------|-------|
| Minutes since last tuple, or minutes since midnight if first tuple | Temperature to change to (div 10) |


E.g a pair of tuples [120,200], [60,250] mean:

120 minutes after midnight, change the temperature to 20.0c, and 60 minutes after that change the temperature to 25.0c

