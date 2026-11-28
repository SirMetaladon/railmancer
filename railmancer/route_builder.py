"""Build a Trackhammer mainline from a notepad route.

The file is comments, a few settings, and one segment per line. A line
like "8 miles 1 track" uses 8 as a weight, the same way a milepost list
does. It is not a fixed length. "fixed=0.6" stays that long. A bare
"siding" stays siding_miles.

Switch ladders are not part of a run. Each track added or removed costs
one ladder step: switches.zone_length of a single 0fw step (1536 units)
divided by 12 * 5280. That estimate comes out of target_miles, then the
weights share what is left. "ladder_allowance = 0" skips the estimate.
When both sides change together the real overlapped zone can be shorter
than this sum; the preview shows the number that was reserved.

The printout is a preview and a Mainline list to paste into railmancer.py.

    python3 -m railmancer.route_builder routes/example_vancouver_squamish.txt
"""

import argparse
import json
import os
import re
import sys

from railmancer import tools

# trackhammer._in_window treats a run as finished once plain length is
# within run_length_tolerance of the target. The shipped value is 1000
# units (railmancer/config.json). A target at or under that window
# includes 0, so the search can lay nothing and move on.
RUN_WINDOW_UNITS = 1000

# Map units are inches. tools.inches is miles * 12 * 5280.
UNITS_PER_MILE = 12 * 5280

# Keys valid_next_tracks and the run joiner actually read, plus max_radius,
# which is accepted on a run and passed through. valid_next_tracks does
# not read max_radius yet.
PARAM_ORDER = (
    "min_radius",
    "max_radius",
    "min_grade",
    "max_grade",
    "flat",
    "straight_only",
    "force_straight",
    "join",
)
PARAM_KEYS = set(PARAM_ORDER)
BOOL_PARAMS = {"flat", "straight_only", "force_straight"}
NUMBER_PARAMS = {"min_radius", "max_radius", "min_grade", "max_grade"}

SETTINGS = {
    "target_miles",
    "siding_miles",
    "ladder_allowance",
    "ladder_allowance_miles",
    "default_min_miles",
    "default_max_miles",
    "start_milepost",
    "siding_side",
    "merge",
    "direction",
}

_PAIR = re.compile(r"\((\d+)\s*,\s*(\d+)\)")
_KV = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s#]+)")
_MILES = re.compile(r"(?<![\w.])(\d*\.?\d+)\s*(?:miles|mile|mi)\b", re.I)
_NTRACK = re.compile(r"(?<![\w.])(\d+)\s*tracks?\b", re.I)
_SETTING = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\S+)")


class RouteError(Exception):
    """A route file or a length budget that cannot be built."""


class Segment:
    def __init__(self):
        self.comments = []
        self.raw = ""
        self.line_no = 0
        self.tracks = None
        self.handbuilt = False
        self.fixed = None
        self.weight = None
        self.min_miles = None
        self.max_miles = None
        self.warp = None
        self.params = {}
        self.note_miles = None
        self.miles = None
        self.mode = None
        self.min_bound = 0.0
        self.max_bound = None
        self.milepost_start = None
        self.milepost_end = None
        self.short = False


class Route:
    def __init__(self):
        self.header_comments = []
        self.footer_comments = []
        self.target_miles = None
        self.siding_miles = 0.6
        self.siding_side = "right"
        self.ladder_allowance_miles = None
        self.ladder_allowance_number = None
        self.ladders_enabled = True
        self.default_min_miles = None
        self.default_max_miles = None
        self.start_milepost = 0.0
        self.merge = True
        self.direction = "0fw"
        self.default_params = {}
        self.default_explicit = set()
        self.segments = []
        self.transitions = []
        self.fixed_total = 0.0
        self.flex_total = 0.0
        self.ladder_total = 0.0
        self.per_step_miles = 0.0
        self.ladder_step_units = 0.0
        self.warnings = []
        self.run_window = RUN_WINDOW_UNITS


def _comment_body(text):
    text = text.strip()
    if text.startswith("#"):
        text = text[1:]
        if text.startswith(" "):
            text = text[1:]
    return text.rstrip()


def _split_inline(line):
    if "#" not in line:
        return line.strip(), None
    body, comment = line.split("#", 1)
    return body.strip(), _comment_body(comment)


def _num(text, label):
    try:
        value = float(text)
    except (TypeError, ValueError):
        raise RouteError(f"{label} is not a number: {text}")
    if value != value or value in (float("inf"), float("-inf")):
        raise RouteError(f"{label} is not a number: {text}")
    return value


def _bool(text, label):
    value = str(text).strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise RouteError(f"{label} should be true or false, not {text!r}")


def _whole(value):
    if abs(value - round(value)) < 1e-9:
        return int(round(value))
    return value


def _label(seg):
    if seg.comments:
        return seg.comments[0]
    if seg.raw:
        return seg.raw.strip()
    return f"line {seg.line_no}"


def _where(seg):
    name = _label(seg)
    if name.startswith("line "):
        return name
    return f"line {seg.line_no} ({name})"


def run_window_units():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle).get("run_length_tolerance", RUN_WINDOW_UNITS)
        return float(value)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return float(RUN_WINDOW_UNITS)


def ladder_step_units(direction="0fw"):
    """Units along the main for one added or removed parallel track.

    zone_length((0, 0), (0, 1), direction) is that one step. On 0fw the
    condensed siding's long leg is 1536.
    """

    from railmancer import switches

    try:
        units = switches.zone_length((0, 0), (0, 1), direction)
    except Exception as exc:
        raise RouteError(
            f"Could not read a {direction} ladder step from switches.zone_length ({exc}). "
            "Set ladder_allowance_miles, or ladder_allowance = 0 to ignore ladders."
        )
    return float(units)


def ladder_steps(before, after, join=None):
    """How many one-track ladder steps this boundary reserves.

    A stub side keeps its old count, so that side adds no step. The
    allowance is abs(dL) + abs(dR) of the counts the ladder actually builds.
    """

    left = abs(int(after[0]) - int(before[0]))
    right = abs(int(after[1]) - int(before[1]))
    if join == "stub":
        return 0
    if isinstance(join, dict):
        if join.get("left", "switch") == "stub":
            left = 0
        if join.get("right", "switch") == "stub":
            right = 0
    return left + right


def _siding_tracks(side):
    if side == "left":
        return (1, 0)
    if side == "right":
        return (0, 1)
    raise RouteError("siding_side should be left or right")


def _set_join_side(params, side, value, line_no):
    if value not in ("switch", "stub"):
        raise RouteError(f"line {line_no}: join {side} should be switch or stub")
    current = params.get("join")
    if current is not None and not isinstance(current, dict):
        raise RouteError(
            f"line {line_no}: join= is already set. Use join_left and join_right, or join=."
        )
    if not isinstance(current, dict):
        current = {"left": "switch", "right": "switch"}
    current[side] = value
    params["join"] = current


def _store_param(params, explicit, key, value, line_no):
    key = key.lower()
    if key in ("join_left", "join_right"):
        _set_join_side(params, key.split("_", 1)[1], str(value).lower(), line_no)
        explicit.add("join")
        return
    if key not in PARAM_KEYS:
        known = ", ".join(PARAM_ORDER)
        raise RouteError(
            f"line {line_no}: unknown parameter {key!r}. Trackhammer parameters are: {known}."
        )
    if key == "join":
        text = str(value).lower()
        if text not in ("switch", "stub"):
            raise RouteError(f"line {line_no}: join should be switch or stub")
        params["join"] = text
    elif key in BOOL_PARAMS:
        params[key] = _bool(value, f"line {line_no}: {key}")
    elif key in NUMBER_PARAMS:
        params[key] = _whole(_num(value, f"line {line_no}: {key}"))
    explicit.add(key)


def _finalize_params(params, explicit):
    # flat replaces the grade band. Drop grades inherited from the header
    # so the paste does not carry a floor the run will ignore. A grade
    # written on this same line stays.
    if (
        params.get("flat")
        and "min_grade" not in explicit
        and "max_grade" not in explicit
    ):
        params.pop("min_grade", None)
        params.pop("max_grade", None)
    for key in BOOL_PARAMS:
        if key in params and not params[key]:
            params.pop(key, None)


def _copy_params(params):
    copied = dict(params)
    if isinstance(copied.get("join"), dict):
        copied["join"] = dict(copied["join"])
    return copied


def _apply_setting(route, key, value, line_no):
    key = key.lower()
    if key == "target_miles":
        route.target_miles = _num(value, f"line {line_no}: target_miles")
    elif key == "siding_miles":
        route.siding_miles = _num(value, f"line {line_no}: siding_miles")
    elif key == "ladder_allowance_miles":
        route.ladder_allowance_miles = _num(
            value, f"line {line_no}: ladder_allowance_miles"
        )
    elif key == "ladder_allowance":
        route.ladder_allowance_number = _num(value, f"line {line_no}: ladder_allowance")
    elif key == "default_min_miles":
        route.default_min_miles = _num(value, f"line {line_no}: default_min_miles")
    elif key == "default_max_miles":
        route.default_max_miles = _num(value, f"line {line_no}: default_max_miles")
    elif key == "start_milepost":
        route.start_milepost = _num(value, f"line {line_no}: start_milepost")
    elif key == "siding_side":
        side = str(value).strip().lower()
        if side not in ("left", "right"):
            raise RouteError(f"line {line_no}: siding_side should be left or right")
        route.siding_side = side
    elif key == "merge":
        route.merge = _bool(value, f"line {line_no}: merge")
    elif key == "direction":
        route.direction = str(value).strip().lower()
    elif key in PARAM_KEYS or key in ("join_left", "join_right"):
        _store_param(route.default_params, route.default_explicit, key, value, line_no)
    else:
        known = ", ".join(sorted(SETTINGS))
        raise RouteError(
            f"line {line_no}: unknown setting {key!r}. Settings are: {known}."
        )


def _finish_settings(route):
    if route.target_miles is None:
        raise RouteError(
            "target_miles is missing. Put it at the top, for example target_miles = 6.0."
        )
    if route.target_miles < 0:
        raise RouteError("target_miles cannot be negative.")
    if route.siding_miles < 0:
        raise RouteError("siding_miles cannot be negative.")
    allowance = route.ladder_allowance_number
    miles = route.ladder_allowance_miles
    if allowance == 0 or miles == 0:
        route.ladders_enabled = False
        route.ladder_allowance_miles = 0.0
        return
    if miles is not None and allowance is not None and abs(miles - allowance) > 1e-9:
        raise RouteError(
            "ladder_allowance and ladder_allowance_miles are both set and they differ."
        )
    if miles is None and allowance is not None:
        route.ladder_allowance_miles = allowance
    route.ladders_enabled = True


def _is_setting_line(body):
    match = _SETTING.fullmatch(body)
    if not match:
        return None
    key = match.group(1).lower()
    if key in SETTINGS or key in PARAM_KEYS or key in ("join_left", "join_right"):
        return key, match.group(2)
    return None


def _parse_segment(body, inline, route, line_no):
    seg = Segment()
    seg.raw = body
    seg.line_no = line_no
    if inline:
        seg.comments.append(inline)

    pairs = [(int(left), int(right)) for left, right in _PAIR.findall(body)]
    rest = _PAIR.sub(" ", body)
    pairs_kv = _KV.findall(rest)
    rest = _KV.sub(" ", rest)
    mile_values = [float(item) for item in _MILES.findall(rest)]
    rest = _MILES.sub(" ", rest)
    track_values = [int(item) for item in _NTRACK.findall(rest)]
    rest = _NTRACK.sub(" ", rest)
    words = [word.lower() for word in rest.split()]

    known_words = {"siding", "double", "straight", "flat", "handbuilt", "skip"}
    for word in words:
        if word not in known_words:
            raise RouteError(
                f"line {line_no}: don't know {word!r} in {body!r}. "
                "Track counts look like '1 track', 'siding', 'double', or '(0, 1)'. "
                "Lengths look like '8 miles', 'weight=8', or 'fixed=0.6'."
            )

    specs = []
    if len(pairs) > 1:
        raise RouteError(f"line {line_no}: give one (left, right) track count.")
    if pairs:
        specs.append(pairs[0])
    if len(track_values) > 1:
        raise RouteError(f"line {line_no}: give one track count.")
    if track_values:
        count = track_values[0]
        if count < 1:
            raise RouteError(f"line {line_no}: track count has to be at least 1.")
        # 1 track is the main alone. 2 track is the main plus one on the right.
        specs.append((0, 0) if count == 1 else (0, count - 1))
    if "siding" in words:
        specs.append(_siding_tracks(route.siding_side))
    if "double" in words:
        specs.append((0, 1))
    if len(specs) > 1:
        raise RouteError(f"line {line_no}: give one track count, not {len(specs)}.")
    if specs:
        seg.tracks = specs[0]

    if "handbuilt" in words or "skip" in words:
        seg.handbuilt = True
    if len(mile_values) > 1:
        raise RouteError(f"line {line_no}: give one weight, like '8 miles'.")

    explicit = set()
    params = _copy_params(route.default_params)
    fixed = None
    weight = mile_values[0] if mile_values else None
    for key, value in pairs_kv:
        key = key.lower()
        if key == "fixed":
            fixed = _num(value, f"line {line_no}: fixed")
        elif key == "weight":
            if weight is not None:
                raise RouteError(
                    f"line {line_no}: give '8 miles' or weight=, not both."
                )
            weight = _num(value, f"line {line_no}: weight")
        elif key == "min":
            seg.min_miles = _num(value, f"line {line_no}: min")
        elif key == "max":
            seg.max_miles = _num(value, f"line {line_no}: max")
        elif key == "warp":
            seg.warp = str(value)
        else:
            _store_param(params, explicit, key, value, line_no)

    if "straight" in words and "straight_only" not in explicit:
        params["straight_only"] = True
        explicit.add("straight_only")
    if "flat" in words and "flat" not in explicit:
        params["flat"] = True
        explicit.add("flat")
    _finalize_params(params, explicit)
    seg.params = params

    if fixed is not None and weight is not None:
        raise RouteError(
            f"line {line_no}: {_label(seg)} has a fixed length and a weight. Use one."
        )
    if fixed is not None and fixed < 0:
        raise RouteError(f"line {line_no}: fixed length cannot be negative.")
    if weight is not None and weight <= 0:
        raise RouteError(f"line {line_no}: weight has to be greater than zero.")
    if seg.min_miles is not None and seg.min_miles < 0:
        raise RouteError(f"line {line_no}: min cannot be negative.")
    if seg.max_miles is not None and seg.max_miles < 0:
        raise RouteError(f"line {line_no}: max cannot be negative.")

    if seg.handbuilt:
        if seg.warp:
            raise RouteError(
                f"line {line_no}: a handbuilt segment is not in the run, so it cannot carry warp=."
            )
        seg.note_miles = fixed if fixed is not None else weight
        seg.mode = "handbuilt"
        return seg

    if seg.tracks is None:
        raise RouteError(
            f"line {line_no}: {_label(seg)} needs a track count, for example '1 track' or '(0, 1)'."
        )
    if fixed is None and weight is None:
        if "siding" in words:
            fixed = route.siding_miles
        else:
            raise RouteError(
                f"line {line_no}: {_label(seg)} needs a weight ('8 miles' or weight=) "
                "or a fixed length (fixed=)."
            )
    if fixed is not None:
        if seg.min_miles is not None or seg.max_miles is not None:
            raise RouteError(
                f"line {line_no}: min and max clamp a flexible segment. {_label(seg)} is fixed."
            )
        seg.fixed = fixed
        seg.mode = "fixed"
    else:
        seg.weight = weight
        seg.mode = "flex"
    return seg


def parse(text):
    route = Route()
    pending = []
    seen_segment = False
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            pending.append(_comment_body(stripped))
            continue
        body, inline = _split_inline(stripped)
        if not body:
            if inline:
                pending.append(inline)
            continue
        setting = _is_setting_line(body)
        if setting is not None:
            if seen_segment:
                raise RouteError(
                    f"line {line_no}: settings go at the top, before the segments."
                )
            _apply_setting(route, setting[0], setting[1], line_no)
            if inline:
                pending.append(inline)
            if pending:
                route.header_comments.extend(pending)
                pending = []
            continue
        seen_segment = True
        seg = _parse_segment(body, inline, route, line_no)
        if pending:
            seg.comments = pending + seg.comments
            pending = []
        route.segments.append(seg)
    if pending:
        route.footer_comments.extend(pending)
    _finish_settings(route)
    if not route.segments:
        raise RouteError("The route has no segments.")
    _finalize_params(route.default_params, route.default_explicit)
    return route


def _emitted(route):
    return [seg for seg in route.segments if not seg.handbuilt]


def _resolve_ladder(route):
    if not route.ladders_enabled:
        route.per_step_miles = 0.0
        route.ladder_step_units = 0.0
        return
    if route.ladder_allowance_miles is None:
        route.ladder_step_units = ladder_step_units(route.direction)
        route.per_step_miles = tools.miles(route.ladder_step_units)
        route.ladder_allowance_miles = route.per_step_miles
        return
    route.per_step_miles = float(route.ladder_allowance_miles)
    route.ladder_step_units = route.per_step_miles * UNITS_PER_MILE


def _bound_hit(seg, share):
    if share < seg.min_bound - 1e-9:
        return "min"
    if seg.max_bound is not None and share > seg.max_bound + 1e-9:
        return "max"
    return None


def _share_flex(flex, budget):
    """Give each free segment budget * weight / weight_sum.

    A segment that falls outside min or max locks at that bound. One lock
    per pass, the worst miss first, then the remainder is shared again.
    Locking every violator in the same pass can stick a min and a max that
    would have fit if only the larger miss were fixed.
    """

    free = list(flex)
    remaining = float(budget)
    while free:
        weight = sum(seg.weight for seg in free)
        if weight <= 0:
            raise RouteError("Flexible segments need a weight greater than zero.")
        proposed = [remaining * seg.weight / weight for seg in free]
        worst = None
        for index, (seg, share) in enumerate(zip(free, proposed)):
            kind = _bound_hit(seg, share)
            if kind is None:
                continue
            bound = seg.min_bound if kind == "min" else seg.max_bound
            overshoot = abs(share - bound)
            if worst is None or overshoot > worst[0] + 1e-15:
                worst = (overshoot, index, seg, kind, bound)
        if worst is None:
            for seg, share in zip(free, proposed):
                seg.miles = share
                seg.mode = "flex"
            return
        _overshoot, index, seg, kind, bound = worst
        seg.miles = bound
        seg.mode = "clamped min" if kind == "min" else "clamped max"
        remaining -= bound
        del free[index]
        if remaining < -1e-6:
            raise RouteError(
                "The minimums and maximums cannot share the miles that are left. "
                f"{_miles_text(remaining)} miles would be left over after locking a bound."
            )
    if remaining > 1e-6:
        raise RouteError(
            f"{_miles_text(remaining)} miles are still unplaced and every flexible "
            "segment is already at its maximum."
        )


def _miles_text(value):
    return f"{value:.4f}"


def solve(route):
    _resolve_ladder(route)
    route.run_window = run_window_units()
    emitted = _emitted(route)
    route.transitions = []
    ladder_total = 0.0
    for before, after in zip(emitted, emitted[1:]):
        steps = ladder_steps(before.tracks, after.tracks, after.params.get("join"))
        miles = steps * route.per_step_miles
        route.transitions.append(
            {"before": before, "after": after, "steps": steps, "miles": miles}
        )
        ladder_total += miles

    fixed = [seg for seg in emitted if seg.fixed is not None]
    flex = [seg for seg in emitted if seg.fixed is None]
    fixed_total = sum(seg.fixed for seg in fixed)
    for seg in fixed:
        seg.miles = seg.fixed
        seg.mode = "fixed"

    budget = route.target_miles - fixed_total - ladder_total
    if fixed_total + ladder_total > route.target_miles + 1e-6:
        raise RouteError(
            f"Fixed segments ({_miles_text(fixed_total)} miles) plus switch ladders "
            f"({_miles_text(ladder_total)} miles) are {_miles_text(fixed_total + ladder_total)} miles, "
            f"already over the {_miles_text(route.target_miles)} mile target."
        )

    for seg in flex:
        if seg.min_miles is None:
            seg.min_bound = (
                0.0 if route.default_min_miles is None else route.default_min_miles
            )
        else:
            seg.min_bound = seg.min_miles
        if seg.max_miles is None:
            seg.max_bound = route.default_max_miles
        else:
            seg.max_bound = seg.max_miles
        if seg.max_bound is not None and seg.min_bound > seg.max_bound + 1e-9:
            raise RouteError(
                f"{_where(seg)} has min {seg.min_bound} above max {seg.max_bound}."
            )

    if flex:
        need = sum(seg.min_bound for seg in flex)
        if need > budget + 1e-6:
            raise RouteError(
                f"Flexible segments need at least {_miles_text(need)} miles to meet their minimums, "
                f"but only {_miles_text(budget)} miles are left after fixed segments and switch ladders."
            )
        if all(seg.max_bound is not None for seg in flex):
            room = sum(seg.max_bound for seg in flex)
            if room < budget - 1e-6:
                raise RouteError(
                    f"Flexible segments can take at most {_miles_text(room)} miles, "
                    f"but {_miles_text(budget)} miles still have to be placed."
                )
        _share_flex(flex, budget)
    elif budget > 1e-6:
        raise RouteError(
            f"{_miles_text(budget)} miles are left and there is no flexible segment to take them."
        )

    route.fixed_total = fixed_total
    route.flex_total = sum(seg.miles for seg in flex)
    route.ladder_total = ladder_total
    cursor = route.start_milepost
    window_miles = tools.miles(route.run_window)
    route.warnings = []
    for seg in route.segments:
        if seg.handbuilt:
            seg.milepost_start = None
            seg.milepost_end = None
            seg.short = False
            continue
        seg.milepost_start = cursor
        cursor += seg.miles
        seg.milepost_end = cursor
        seg.short = tools.inches(seg.miles) <= route.run_window + 1e-6
        if seg.short:
            route.warnings.append(
                f"{_label(seg)} is {_miles_text(seg.miles)} miles, at or under the "
                f"{_whole(route.run_window)}-unit run window ({_miles_text(window_miles)} miles). "
                "Trackhammer can count that run as already finished and lay nothing."
            )
    return route


def merged_runs(route):
    """Group adjacent emitted segments that Trackhammer would treat as one run.

    A handbuilt line is a gap in the file. The segments on either side stay
    separate even when their tracks and params match, so the note between
    them is not swallowed.
    """

    groups = []
    barrier = False
    for seg in route.segments:
        if seg.handbuilt:
            barrier = True
            continue
        same = (
            route.merge
            and not barrier
            and groups
            and groups[-1][-1].tracks == seg.tracks
            and groups[-1][-1].params == seg.params
        )
        if same:
            groups[-1].append(seg)
        else:
            groups.append([seg])
        barrier = False
    return groups


def _py_num(value):
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    if text in ("", "-0"):
        return "0"
    return text


def _py_literal(value):
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _py_num(value)
    if isinstance(value, dict):
        parts = [
            f"{json.dumps(str(key))}: {_py_literal(val)}" for key, val in value.items()
        ]
        return "{" + ", ".join(parts) + "}"
    raise RouteError(f"cannot write {value!r} into the mainline")


def _format_params(params):
    if not params:
        return "{}"
    keys = [key for key in PARAM_ORDER if key in params]
    keys.extend(key for key in params if key not in PARAM_ORDER)
    parts = [f"{json.dumps(key)}: {_py_literal(params[key])}" for key in keys]
    return "{" + ", ".join(parts) + "}"


def _run_comment(group):
    parts = []
    for seg in group:
        if seg.comments:
            parts.append(" / ".join(seg.comments))
    return " + ".join(parts)


def _params_phrase(params):
    if not params:
        return "-"
    bits = []
    for key in PARAM_ORDER:
        if key not in params:
            continue
        value = params[key]
        if value is True:
            bits.append(key)
        else:
            bits.append(f"{key}={_py_literal(value)}")
    return " ".join(bits)


def _segment_name(seg):
    if seg.comments:
        return " / ".join(seg.comments)
    return seg.raw.strip() or "(unnamed)"


def render(route):
    if (
        route.segments
        and route.segments[0].miles is None
        and not route.segments[0].handbuilt
    ):
        raise RouteError("solve the route before rendering it.")

    lines = ["Route preview", ""]
    for comment in route.header_comments:
        lines.append(f"# {comment}")
    if route.header_comments:
        lines.append("")
    step = (
        "off"
        if not route.ladders_enabled
        else f"{_py_num(route.per_step_miles)} miles ({_py_num(route.ladder_step_units)} units)"
    )
    lines.append(
        f"target {_py_num(route.target_miles)} miles"
        f"    start milepost {_py_num(route.start_milepost)}"
        f"    ladder step {step}"
        f"    merge {'on' if route.merge else 'off'}"
    )
    lines.append(
        "milepost is the solved end of the segment, not the prototype mile in the comment. "
        "A warp sits at the start. Ladders are not part of it."
    )
    lines.append("")

    rows = []
    for seg in route.segments:
        if seg.handbuilt:
            miles = "-" if seg.note_miles is None else _miles_text(seg.note_miles)
            weight = "-"
            tracks = "-" if seg.tracks is None else str(tuple(seg.tracks))
            params = "not in the run"
            milepost = "-"
        else:
            miles = _miles_text(seg.miles) + (" !" if seg.short else "")
            weight = "-" if seg.weight is None else _py_num(seg.weight)
            tracks = str(tuple(seg.tracks))
            params = _params_phrase(seg.params)
            milepost = _miles_text(seg.milepost_end)
            if seg.warp:
                params = f"{params}    warp {seg.warp} at {_miles_text(seg.milepost_start)}".strip()
        rows.append(
            (_segment_name(seg), tracks, seg.mode, weight, miles, milepost, params)
        )

    headers = ("segment", "tracks", "mode", "weight", "miles", "milepost", "params")
    widths = []
    for index, header in enumerate(headers):
        widths.append(max(len(header), max(len(row[index]) for row in rows)))

    def format_row(row):
        return "  ".join(
            row[index].ljust(widths[index]) for index in range(len(headers))
        ).rstrip()

    lines.append(format_row(headers))
    into = {id(item["after"]): item for item in route.transitions}
    warnings = {id(seg): seg.short for seg in route.segments}
    for seg, row in zip(route.segments, rows):
        transition = into.get(id(seg))
        if transition and transition["steps"]:
            before = transition["before"].tracks
            after = transition["after"].tracks
            lines.append(
                f"  ladder {before} -> {after}, {transition['steps']} step"
                f"{'' if transition['steps'] == 1 else 's'}, {_miles_text(transition['miles'])} miles"
            )
        lines.append(format_row(row))
        if warnings.get(id(seg)):
            lines.append(
                f"  WARNING: {_miles_text(seg.miles)} miles is at or under the "
                f"{_whole(route.run_window)}-unit run window. This run can collapse to zero length."
            )

    weight_sum = sum(
        seg.weight for seg in route.segments if seg.weight and not seg.handbuilt
    )
    lines.append("")
    lines.append(f"fixed total     {_miles_text(route.fixed_total)}")
    lines.append(f"flex total      {_miles_text(route.flex_total)}")
    lines.append(f"ladder total    {_miles_text(route.ladder_total)}")
    grand = route.fixed_total + route.flex_total + route.ladder_total
    lines.append(
        f"grand total     {_miles_text(grand)}    target {_miles_text(route.target_miles)}"
    )
    if weight_sum:
        lines.append(
            f"compression     {_miles_text(route.flex_total / weight_sum)} map miles per weight"
        )
    groups = merged_runs(route)
    emitted_count = sum(len(group) for group in groups)
    if route.merge and emitted_count != len(groups):
        lines.append(
            f"merged          {emitted_count} segments into {len(groups)} runs"
        )
    if route.warnings:
        lines.append("")
        lines.append("Warnings")
        for warning in route.warnings:
            lines.append(f"- {warning}")
    for comment in route.footer_comments:
        lines.append(f"# {comment}")

    lines.append("")
    lines.append("Paste into railmancer.py")
    lines.append("------------------------")
    lines.extend(_python_lines(route))
    lines.append("")
    return "\n".join(lines)


def _python_lines(route):
    lines = []
    for comment in route.header_comments:
        lines.append(f"# {comment}")
    if route.header_comments:
        lines.append("")
    warps = [
        (seg.milepost_start, seg.warp)
        for seg in route.segments
        if seg.warp and not seg.handbuilt
    ]
    if warps:
        lines.append("# trackhammer.generate_mainline(start_node, Mainline, Warps)")
    else:
        lines.append("# trackhammer.generate_mainline(start_node, Mainline)")
    lines.append("# Miles are plain track. Switch ladders are not included.")
    lines.append("Mainline = [")
    for group in merged_runs(route):
        comment = _run_comment(group)
        miles = sum(seg.miles for seg in group)
        head = "[" if not comment else f"[  # {comment}"
        tracks = tuple(group[0].tracks)
        lines.append(f"    {head}")
        lines.append(f"        {tracks},")
        lines.append(f"        {_py_num(miles)},")
        lines.append(f"        {_format_params(group[0].params)},")
        lines.append("    ],")
    lines.append("]")
    if warps:
        lines.append("")
        lines.append("Warps = [")
        for mile, name in warps:
            lines.append(
                "    {" + f'"mile": {_py_num(mile)}, "name": {json.dumps(name)}' + "},"
            )
        lines.append("]")
    for comment in route.footer_comments:
        lines.append(f"# {comment}")
    return lines


def build(text, no_merge=False):
    route = parse(text)
    if no_merge:
        route.merge = False
    solve(route)
    return route, render(route)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a Trackhammer mainline from a notepad route file."
    )
    parser.add_argument("route_file")
    parser.add_argument(
        "--out", help="Also write the preview and the pasteable list here."
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Keep adjacent segments with the same tracks and params as separate runs.",
    )
    args = parser.parse_args(argv)
    try:
        with open(args.route_file, "r", encoding="utf-8") as handle:
            _route, text = build(handle.read(), no_merge=args.no_merge)
        sys.stdout.write(text)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(text)
        return 0
    except OSError as exc:
        print(f"route builder: {exc}", file=sys.stderr)
        return 1
    except RouteError as exc:
        print(f"route builder: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
