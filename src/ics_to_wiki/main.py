#!/usr/bin/env python3
import re
from dataclasses import dataclass
from datetime import datetime, date, time as dtime
from typing import List, Optional, Dict, Any
import requests
from icalendar import Calendar
from dateutil.rrule import rrulestr, rruleset

from config import (
    CALENDAR_URL,
    WIKI_API_URL,
    WIKI_PAGE_TITLE,
    EDIT_SUMMARY,
    WIKI_USERNAME,
    WIKI_PASSWORD,
    INFO_TEXT,
    REPLACE_LINKS,
)

@dataclass
class SimpleEvent:
    name: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    recurrence_text: Optional[str] = None  # e.g. "jeden ersten Montag im Monat"
    all_day: bool = False
    link: Optional[str] = None


WEEKDAY_DE = {
    "MO": "Montag",
    "TU": "Dienstag",
    "WE": "Mittwoch",
    "TH": "Donnerstag",
    "FR": "Freitag",
    "SA": "Samstag",
    "SU": "Sonntag",
}

ORDINAL_DE = {
    1: "ersten",
    2: "zweiten",
    3: "dritten",
    4: "vierten",
    -1: "letzten",
}


def escape_wiki(text: str) -> str:
    text = text.replace("|", "&#124;") # pipe breaks table (obviously)
    text = text.replace("\n", "") # no line breaks in cells
    return text


def to_datetime_any(x: Any) -> datetime:
    # ensures we always have a datetime object (comparison breaks otherwise for all-day events)
    if isinstance(x, datetime):
        return x
    if isinstance(x, date):
        return datetime.combine(x, dtime.min)
    raise TypeError(f"Unexpected dt type: {type(x)}")


def display_naive(dt: datetime) -> datetime:
    # TODO: timezone causes problems when comparing, removing it and using local time for now
    if dt.tzinfo is None:
        return dt
    return dt.replace(tzinfo=None)


def parse_link_from_description(description: Optional[str]) -> Optional[str]:
    if not description:
        return None

    first_line = description.strip().split("\n")[0].strip()

    # internal wiki link
    internal_match = re.match(r'^\[\[([^\]]+)\]\]$', first_line)
    if internal_match:
        return first_line

    # external link
    external_match = re.match(r'^\[(https?://[^\s\]]+)(?:\s+([^\]]+))?\]$', first_line)
    if external_match:
        return first_line

    return None


def format_event_name(name: str, link: Optional[str]) -> str:
    escaped_name = escape_wiki(name or "")

    if link:
        if link.startswith("[["):
            if "|" in link:
                return link
            else:
                page = link[2:-2]
                return f"[[{page}|{escaped_name}]]"
        elif link.startswith("["):
            if " " in link[1:-1]:
                return link
            else:
                url = link[1:-1]
                return f"[{url} {escaped_name}]"

    return escaped_name


def fetch_calendar(url: str) -> Calendar:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return Calendar.from_ical(resp.content)

def parse_rrule_to_dict(vrecur: Any) -> Dict[str, Any]:
    if vrecur is None:
        return {}
    if hasattr(vrecur, "to_ical"):
        raw = vrecur.to_ical().decode()
    else:
        raw = str(vrecur)

    result: Dict[str, Any] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.upper().strip()
        val = val.strip()
        if "," in val:
            vals = [v.strip() for v in val.split(",") if v.strip()]
            result[key] = vals
        else:
            result[key] = val
    return result


def describe_recurrence(rule: Dict[str, Any]) -> Optional[str]:
    if not rule:
        return None

    freq = rule.get("FREQ")
    if not freq:
        return None
    freq = str(freq).upper()
    interval = int(rule.get("INTERVAL", 1))

    def ensure_list(v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]

    if freq == "DAILY":
        if interval == 1:
            return "täglich"
        return f"alle {interval} Tage"

    if freq == "WEEKLY":
        byday = ensure_list(rule.get("BYDAY"))
        day_names = [WEEKDAY_DE.get(d[-2:], d) for d in byday] if byday else []

        if interval == 1:
            if len(day_names) == 1:
                return f"jeden {day_names[0]}"
            elif len(day_names) > 1:
                if len(day_names) == 2:
                    day_part = f"{day_names[0]} und {day_names[1]}"
                else:
                    day_part = ", ".join(day_names[:-1]) + f" und {day_names[-1]}"
                return f"jede Woche am {day_part}"
            else:
                return "jede Woche"
        else:
            if len(day_names) == 1:
                return f"alle {interval} Wochen am {day_names[0]}"
            elif len(day_names) > 1:
                if len(day_names) == 2:
                    day_part = f"{day_names[0]} und {day_names[1]}"
                else:
                    day_part = ", ".join(day_names[:-1]) + f" und {day_names[-1]}"
                return f"alle {interval} Wochen am {day_part}"
            else:
                return f"alle {interval} Wochen"

    if freq == "MONTHLY":
        bysetpos = ensure_list(rule.get("BYSETPOS"))
        byday = ensure_list(rule.get("BYDAY"))
        bymonthday = ensure_list(rule.get("BYMONTHDAY"))

        if bysetpos and byday and len(bysetpos) == 1 and len(byday) == 1:
            pos = int(bysetpos[0])
            day_code = str(byday[0])
            day_name = WEEKDAY_DE.get(day_code[-2:], day_code)
            if pos in ORDINAL_DE:
                ordinal = ORDINAL_DE[pos]
                return f"jeden {ordinal} {day_name} im Monat"

        if bymonthday and len(bymonthday) == 1:
            mday = int(bymonthday[0])
            return f"jeden {mday}. im Monat"

        if interval == 1:
            return "jeden Monat"
        return f"alle {interval} Monate"

    return "wiederkehrend"

def build_rruleset_for_event(event, dtstart: datetime):
    rset = rruleset()

    rrule_field = event.get("rrule")
    if rrule_field:
        rrule_data = rrule_field.to_ical().decode()
        rule = rrulestr(rrule_data, dtstart=dtstart)
        rset.rrule(rule)

    exdate_field = event.get("exdate")
    if exdate_field:
        if not isinstance(exdate_field, list):
            exdate_field = [exdate_field]
        for ex in exdate_field:
            for ex_dt in ex.dts:
                rset.exdate(to_datetime_any(ex_dt.dt))

    rdate_field = event.get("rdate")
    if rdate_field:
        if not isinstance(rdate_field, list):
            rdate_field = [rdate_field]
        for rd in rdate_field:
            for rd_dt in rd.dts:
                rset.rdate(to_datetime_any(rd_dt.dt))

    return rset


def extract_events(cal: Calendar) -> List[SimpleEvent]:
    possible_events: List[SimpleEvent] = []

    # filter by RECURRENCE-ID (=moved occurrences)
    recurrence_overrides: Dict[str, List[Any]] = {}
    for event in cal.walk("VEVENT"):
        if event.get("recurrence-id"):
            uid = str(event.get("uid", ""))
            if uid:
                if uid not in recurrence_overrides:
                    recurrence_overrides[uid] = []
                recurrence_overrides[uid].append(event)

    for event in cal.walk("VEVENT"):
        if event.get("recurrence-id"): # events with RECURRENCE-ID are rec. events with changes -> handle later
            continue

        dtstart_prop = event.get("dtstart")
        if not dtstart_prop:
            continue

        dtstart_raw = dtstart_prop.dt
        is_whole_day = dtstart_prop.params.get("VALUE") == "DATE"

        dtstart = to_datetime_any(dtstart_raw)

        dtend_prop = event.get("dtend")
        if dtend_prop is not None:
            dtend_raw = dtend_prop.dt
            dtend = to_datetime_any(dtend_raw)
        else:
            dtend = dtstart

        name = str(event.get("summary") or "").strip()
        location = str(event.get("location") or "").strip() or None
        description = str(event.get("description") or "").strip() or None
        link = parse_link_from_description(description)

        is_recurring = event.get("rrule") is not None

        if is_recurring:
            rset = build_rruleset_for_event(event, dtstart)

            # add excluded dates from overrides
            uid = str(event.get("uid", ""))
            if uid in recurrence_overrides:
                for override_event in recurrence_overrides[uid]:
                    recurrence_id_prop = override_event.get("recurrence-id")
                    if recurrence_id_prop:
                        recurrence_id_dt = to_datetime_any(recurrence_id_prop.dt)
                        rset.exdate(recurrence_id_dt)

            next_occurrence = rset.after(datetime.now(dtstart.tzinfo), inc=True)
            if not next_occurrence: # event is over
                continue

            duration = dtend - dtstart
            next_end = next_occurrence + duration

            display_start = display_naive(next_occurrence)
            display_end = display_naive(next_end)

            rule_dict = parse_rrule_to_dict(event.get("rrule"))
            recurrence_text = describe_recurrence(rule_dict)

            possible_events.append(
                SimpleEvent(
                    name=name,
                    start=display_start,
                    end=display_end,
                    location=location,
                    recurrence_text=recurrence_text,
                    all_day=is_whole_day,
                    link=link,
                )
            )
        else:
            if dtend < datetime.now(dtstart.tzinfo):
                continue

            display_start = display_naive(dtstart)
            display_end = display_naive(dtend)

            possible_events.append(
                SimpleEvent(
                    name=name,
                    start=display_start,
                    end=display_end,
                    location=location,
                    recurrence_text=None,
                    all_day=is_whole_day,
                    link=link,
                )
            )

    # handle moved events -> need manual work so the date in the row isn't showed double
    recurring_rules: Dict[str, Optional[str]] = {}
    for event in cal.walk("VEVENT"):
        if event.get("recurrence-id"): # skip moved events
            continue
        if event.get("rrule"): # only care about recurring events
            uid = str(event.get("uid", ""))
            rule_dict = parse_rrule_to_dict(event.get("rrule"))
            recurring_rules[uid] = describe_recurrence(rule_dict)

    for uid, override_events in recurrence_overrides.items():
        for override_event in override_events:
            dtstart_prop = override_event.get("dtstart")
            dtstart_raw = dtstart_prop.dt
            is_whole_day = dtstart_prop.params.get("VALUE") == "DATE"
            dtstart = to_datetime_any(dtstart_raw)

            dtend_prop = override_event.get("dtend")
            if dtend_prop is not None:
                dtend_raw = dtend_prop.dt
                dtend = to_datetime_any(dtend_raw)
            else:
                dtend = dtstart

            if dtend < datetime.now(dtstart.tzinfo): # already past
                continue

            name = str(override_event.get("summary") or "").strip()
            location = str(override_event.get("location") or "").strip() or None
            description = str(override_event.get("description") or "").strip() or None
            link = parse_link_from_description(description)

            display_start = display_naive(dtstart)
            display_end = display_naive(dtend)

            recurrence_text = "verschoben"
            if uid in recurring_rules and recurring_rules[uid]:
                recurrence_text = f"verschoben, sonst {recurring_rules[uid]}"

            possible_events.append(
                SimpleEvent(
                    name=name,
                    start=display_start,
                    end=display_end,
                    location=location,
                    recurrence_text=recurrence_text,
                    all_day=is_whole_day,
                    link=link,
                )
            )

    possible_events.sort(key=lambda e: e.start)
    return possible_events

def replace_links(text: str) -> str:
    for entry in REPLACE_LINKS:
        keyword = entry.get("keyword")
        link = entry.get("link")
        if keyword and link:
            text = text.replace(keyword, link)
    return text

def build_mediawiki_table(events: List[SimpleEvent]) -> str:
    lines: List[str] = []

    if INFO_TEXT:
        lines.append(f"<!--\n{INFO_TEXT}\n-->\n")

    lines.append('{| class="termine sortable" border="1" cellspacing="0" cellpadding="5" width="100%" style="border-collapse:collapse;"')
    lines.append('! data-sort-type="date" style="text-align:left; width:250px;" | Datum '
                 '!! style="text-align:left; width: 75px;" | Zeit '
                 '!! style="text-align:left;" | Ort '
                 '!! style="text-align:left;" | Beschreibung')

    for ev in events:
        date_str = ev.start.strftime("%d.%m.%Y")

        if ev.all_day:
            time_cell = ""
        else:
            start_str = ev.start.strftime("%H:%M")
            end_str = ev.end.strftime("%H:%M") if ev.end else ""
            if end_str and end_str != start_str:
                time_cell = f"{start_str} - {end_str}"
            else:
                time_cell = start_str

        loc = replace_links(escape_wiki(ev.location or ""))
        name = format_event_name(ev.name, ev.link)

        if ev.recurrence_text:
            date_cell = (
                f"'''{date_str}'''"
                f"<br><small>({ev.recurrence_text})</small>"
            )
        else:
            date_cell = f"'''{date_str}'''"

        lines.append("|-")
        lines.append(f"| {date_cell} || {time_cell} || {loc} || {name}")

    lines.append("|}")
    return "\n".join(lines)

def update_mediawiki_page(text: str) -> None:
    if not (WIKI_API_URL and WIKI_PAGE_TITLE and WIKI_USERNAME and WIKI_PASSWORD):
        print(text)
        return

    session = requests.Session()

    # 1. get login token
    r1 = session.get(
        WIKI_API_URL,
        params={"action": "query", "meta": "tokens", "type": "login", "format": "json"},
        timeout=30,
    )
    r1.raise_for_status()
    login_token = r1.json()["query"]["tokens"]["logintoken"]

    # 2. log in
    r2 = session.post(
        WIKI_API_URL,
        data={
            "action": "login",
            "lgname": WIKI_USERNAME,
            "lgpassword": WIKI_PASSWORD,
            "lgtoken": login_token,
            "format": "json",
        },
        timeout=30,
    )
    r2.raise_for_status()
    login_result = r2.json()
    if login_result.get("login", {}).get("result") != "Success":
        raise RuntimeError(f"Login failed: {login_result}")

    # 3. get CSRF token
    r3 = session.get(
        WIKI_API_URL,
        params={"action": "query", "meta": "tokens", "format": "json"},
        timeout=30,
    )
    r3.raise_for_status()
    csrf_token = r3.json()["query"]["tokens"]["csrftoken"]

    # 4. edit page
    r4 = session.post(
        WIKI_API_URL,
        data={
            "action": "edit",
            "title": WIKI_PAGE_TITLE,
            "text": text,
            "summary": EDIT_SUMMARY,
            "bot": 1,
            "token": csrf_token,
            "format": "json",
        },
        timeout=30,
    )
    r4.raise_for_status()
    print("Edit response:", r4.json())

def main():
    cal = fetch_calendar(CALENDAR_URL)
    events = extract_events(cal)
    table_text = build_mediawiki_table(events)
    update_mediawiki_page(table_text)

if __name__ == "__main__":
    main()
