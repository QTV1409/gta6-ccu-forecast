# gta6-ccu-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/QTV1409/gta6-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/QTV1409/gta6-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast how many people watch Grand Theft Auto VI live on Twitch in each
hour of its release day (19 November 2026, UTC), from the first hour's
count. For hours 2..24 the program writes five quantiles (5%, 25%, 50%,
75%, 95%) of that hour's mean concurrent viewers.

## How it works

A launch day is mostly a shape, not a level: hour 1 anchors the scale and
the rest of the day follows the shape of past big launches. The shape
depends strongly on how big hour 1 already is -- a launch whose first
hour is already huge (a simultaneous global unlock, or early access) stays
near that level all day, while one whose first hour is tiny (a rolling
midnight unlock, only New Zealand and Australia awake) grows ten to a
thousand times by the evening.

So for each hour the program fits a line, over the 18 comparables closest
in launch size to this one, of `log(viewers(h) / viewers(1))` against
`log(viewers(1))`, and takes the fitted value as that hour's log-ratio.
The spread around the line sets the quantiles: the fitted log-ratio plus
the normal quantile at each level times the residual standard deviation.
The fitted log-ratio is kept within a log unit of the ratios comparable
launches actually showed, so a first hour outside every comparable's range
cannot send the forecast wildly past them. Hours with too few usable
comparables fall back to persistence (every hour at hour 1's count, with a
spread widening like a random walk in log space).

Python 3.13, standard library only, no network, deterministic: two runs
on the same case agree byte for byte.

## Validation

Leave-one-out over the 38 comparable launches in the kit (each launch
forecast from the other 37, scored by the contest's pinball loss on the
log scale): mean loss **0.367**, worst launch 1.568, median 0.249. The
house persistence baseline scores 0.930 mean / 3.941 worst on the same
folds, and a global median-shape model scores 0.714 mean. The program
runs in about 0.1 s per case.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
