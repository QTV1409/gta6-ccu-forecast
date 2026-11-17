"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

The program reads one case (schema makefun/twitch-ccu-case/v1) and writes,
for each of hours 2..24 of the release day, five quantiles of that hour's
mean concurrent viewers in the game's Twitch category.

How it forecasts
---------------
A launch day is mostly a shape, not a level: hour 1's print anchors the
scale, and the rest of the day follows the shape of past big launches. The
shape depends strongly on how big hour 1 already is -- a launch whose
first hour is already huge (a simultaneous global unlock, or early access)
stays near that level all day, while one whose first hour is tiny (a
rolling midnight unlock, only New Zealand and Australia awake) grows ten
to a thousand times by the evening. So for each hour the program fits a
line, over the comparables closest in size to this launch, of

    log(viewers(h) / viewers(1))  against  log(viewers(1))

and takes the fitted value as the log-ratio for that hour. The spread
around the line -- how much comparable launches actually differed -- sets
the quantiles: the fitted log-ratio plus the normal quantile at each level
times the residual standard deviation. The fitted log-ratio is kept
within a log unit of the ratios comparable launches actually showed, so a
first hour outside every comparable's range cannot send the forecast
wildly past them. Hours with too few usable comparables fall back to the
persistence forecast (every hour at hour 1's count, spread widening like
a random walk in log space).

Only the Python standard library is used, nothing is read from the
network, and the output is a pure function of the case file, so two runs
on the same case agree byte for byte.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817,
     1.6448536269514722]

# How many comparables, nearest in launch size, fit each hour's line.
NEIGHBOURS = 18
# Fewer usable neighbours than this for an hour, and the hour falls back.
MIN_NEIGHBOURS = 5
# The fallback spread, in log units per square-root hour.
BASE_SIGMA = 0.15
# A forecast never leaves this range (viewers).
LO = 1.0
HI = 1e9


def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _fit_line(xs, ys):
    """Least-squares line ys ~ a + b * xs; returns (a, b)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my, 0.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - slope * mx, slope


def _parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _release_day(comparable):
    """The comparable's 24 release-day viewer counts, None where missing."""
    start = _parse_time(comparable["day_start"])
    by_hour = {}
    for row in comparable.get("hourly") or []:
        viewers = row.get("viewers")
        if isinstance(viewers, (int, float)) and viewers > 0:
            by_hour[row.get("from")] = viewers
    day = []
    for offset in range(24):
        key = (start + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:00:00Z")
        day.append(by_hour.get(key))
    return day


def _hour_one(case):
    """Hour 1's print, at least 1 viewer."""
    known = case.get("known") or []
    for row in known:
        if row.get("hour") == 1:
            viewers = row.get("viewers")
            if isinstance(viewers, (int, float)) and viewers > 0:
                return float(viewers)
    return 1.0


def _baseline(p1, hour):
    """Persistence quantiles for one hour: every hour at hour 1's count."""
    spread = BASE_SIGMA * math.sqrt(hour - 1)
    return [p1 * math.exp(z * spread) for z in Z]


def _round2(value):
    """Round to 2 decimals, half up; whole numbers come back as ints."""
    rounded = math.floor(value * 100 + 0.5) / 100
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def _clean(values):
    """Clamp quantiles into range, round, and keep them non-decreasing."""
    cleaned = []
    floor = LO
    for value in values:
        clamped = min(max(value, LO), HI)
        rounded = _round2(clamped)
        if rounded < floor:
            rounded = floor
        cleaned.append(rounded)
        floor = rounded
    return cleaned


def forecast_case(case):
    """Return the forecast document for one case."""
    p1 = _hour_one(case)

    days = []
    for comparable in case.get("comparables") or []:
        try:
            day = _release_day(comparable)
        except (KeyError, TypeError, ValueError):
            continue
        if day[0]:
            days.append(day)

    # The launches closest in size to this one, nearest first.
    anchor = math.log(p1)
    days.sort(key=lambda day: (abs(math.log(day[0]) - anchor), day[0]))
    neighbours = days[:NEIGHBOURS]

    wanted = case.get("forecast") or []
    hours = sorted({row.get("hour") for row in wanted
                    if isinstance(row.get("hour"), int)})
    if not hours:
        hours = list(range(2, 25))

    rows = []
    for hour in hours:
        xs, ys = [], []
        for day in neighbours:
            if day[hour - 1]:
                xs.append(math.log(day[0]))
                ys.append(math.log(day[hour - 1] / day[0]))
        if len(xs) < MIN_NEIGHBOURS:
            quantiles = _baseline(p1, hour)
        else:
            intercept, slope = _fit_line(xs, ys)
            centre = intercept + slope * anchor
            # Never let the line wander past what comparable launches
            # actually did, by more than a log unit: this launch's first
            # hour may sit outside every comparable's range, and a line
            # fitted inside that range is not a licence to extrapolate
            # far beyond it.
            centre = min(max(centre, min(ys) - 1.0), max(ys) + 1.0)
            residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
            mean_resid = sum(residuals) / len(residuals)
            variance = sum((r - mean_resid) ** 2 for r in residuals) / (len(residuals) - 1)
            spread = math.sqrt(variance)
            quantiles = [p1 * math.exp(centre + z * spread) for z in Z]
        rows.append({"hour": hour, "q": _clean(quantiles)})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for case_path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(case_path.read_text())
        forecast = forecast_case(case)
        out_path = OUTPUT_DIR / (case_path.stem + ".out")
        out_path.write_text(json.dumps(forecast))


if __name__ == "__main__":
    main()
