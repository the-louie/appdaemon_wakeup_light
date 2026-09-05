import appdaemon.plugins.hass.hassapi as hass
# datetime is imported for the type hint and %H:%M parsing only. The CLOCK is
# self.get_now(): datetime.now() is naive local time on the container, which
# is a different thing from Home Assistant's configured timezone and, across
# the autumn fold on 25 October, a different thing from real elapsed time. A
# wake-up light an hour late is not a rounding error to the person it wakes.
from datetime import datetime
import math
from typing import Dict, Optional

WEEKDAYS = frozenset({"monday", "tuesday", "wednesday", "thursday",
                      "friday", "saturday", "sunday"})
TIME_FORMATS = ("%H:%M", "%H:%M:%S")


class WakeupLight(hass.Hass):
    def initialize(self):
        """Initialize the wakeup light app with configuration and scheduling"""
        # T-32 (S9-03): config errors RAISE (policy D1). The old check
        # logged ERROR and returned, leaving a loaded-but-inert app that
        # looks green in the admin console and never wakes anyone. A raise
        # is a failed app, which the watchdog reads, which reaches a phone.
        # Every rule below is preflight-proven against the live config
        # (tools/wakeup_light_preflight.py, ALL RULES PASS 2026-09-05).
        self.entity = self.args.get("entity")
        if not self.entity:
            raise ValueError("'entity' is required")
        if not self.entity_exists(self.entity):
            raise ValueError(f"entity {self.entity!r} does not exist in "
                             f"Home Assistant -- waiting will not fix it")

        mb = self.args.get("max_brightness", 254)
        if (isinstance(mb, bool) or not isinstance(mb, (int, float))
                or not 1 <= mb <= 255):
            raise ValueError(f"'max_brightness' must be a number in 1..255, "
                             f"got {mb!r}")
        self.max_brightness = mb

        self.days = self.args.get("days")
        if not isinstance(self.days, dict) or not self.days:
            raise ValueError(f"'days' must be a non-empty dict of weekday "
                             f"configs, got {self.days!r}")
        # Parse and check every day at startup, so no runtime path parses
        # config: a capital-M "Monday" used to be a silent daily no-op
        # (C10), a partial day silently mixed user values with defaults
        # into end-before-start (C8), and the parser rejected forms the
        # platform accepts while an unquoted 6:30 arrived as the int 390
        # (C9). All four are now startup raises that name the problem.
        self._weekday_times = {}
        for day, cfg in self.days.items():
            if day not in WEEKDAYS:
                raise ValueError(
                    f"day key {day!r} is not a lowercase weekday name -- "
                    f"a 'Monday' would never match strftime('%A').lower() "
                    f"and that morning would silently not exist")
            if not isinstance(cfg, dict):
                raise ValueError(f"{day}: config must be a dict, got {cfg!r}")
            if not cfg.get("active", False):
                continue
            missing = [k for k in ("start", "end", "turnoff") if k not in cfg]
            if missing:
                raise ValueError(
                    f"{day}: active day is missing {missing} -- a partially "
                    f"specified day is a config error, not something to "
                    f"fill with defaults")
            parsed = {}
            for key in ("start", "end", "turnoff"):
                parsed[key] = self._parse_time_of_day(day, key, cfg[key])
            if not (parsed["start"] < parsed["end"] < parsed["turnoff"]):
                raise ValueError(
                    f"{day}: times must satisfy start < end < turnoff, got "
                    f"{cfg['start']} / {cfg['end']} / {cfg['turnoff']} -- "
                    f"out of order, the turnoff timer is never created and "
                    f"the light burns until someone notices")
            self._weekday_times[day] = parsed
        # T-31 (S9-02): freq reaches run_every, and AD 4.5.13's scheduler
        # resolves the next period in a sync while-loop on the MAIN event
        # loop: `while aware_next <= now: aware_next += interval`. Four
        # config values make that loop never terminate and hang all of
        # AppDaemon: 0, a negative, an empty value (the key present makes
        # args.get return None, and parse_timedelta(None) is timedelta(0)),
        # and an unparseable string (also timedelta(0)). A raise here is a
        # failed app in the admin console; a hang is every app dead with
        # nothing in the log. Preflight-proven against the live config
        # (int 60): tools/wakeup_light_preflight.py, ALL RULES PASS.
        freq = self.args.get("freq", 60)
        if (isinstance(freq, bool) or not isinstance(freq, (int, float))
                or freq <= 0):
            raise ValueError(
                f"'freq' must be a number of seconds > 0, got {freq!r} "
                f"({type(freq).__name__}); an empty or unparseable value "
                f"would hang AppDaemon's scheduler, not just this app"
            )
        self.adjust_freq = freq
        # T-33 step 1 (S9-06): accept the bare name or the full entity id.
        # The code builds "calendar.<name>" itself, but the README taught
        # "calendar.your_calendar" -- following it produced
        # get_state("calendar.calendar.x") -> None -> exception permanently
        # "active" -> the light never runs, silently. The sibling
        # (i1_wakeup_music) has carried this normalisation for months; it
        # was never back-ported. A no-op for the deployed config, which
        # uses the bare name.
        cal_name = self.args.get("calendar")
        self.cal_entity = (
            None if not cal_name
            else cal_name if str(cal_name).startswith("calendar.")
            else f"calendar.{cal_name}"
        )
        self.calendar_exception_cached = False
        self.active_timer = None
        self.turnoff_timer = None

        self.log(f"WakeupLight started for {self.entity}")
        self.run_in(self.setup_day_schedule, 0)
        self.run_daily(self.check_calendar_exception, "03:30:00")

    def check_calendar_exception(self, kwargs):
        """Check calendar exception once at 03:30 and cache result"""
        self.calendar_exception_cached = (
            bool(self.cal_entity) and self.get_state(self.cal_entity) != "off"
        )
        if self.calendar_exception_cached:
            self.log("Calendar exception active")
        self.setup_day_schedule()

    @staticmethod
    def _parse_time_of_day(day, key, value):
        """A str in %H:%M or %H:%M:%S -> datetime.time, or a raise that
        names the trap. Non-str is rejected explicitly: unquoted YAML
        `start: 6:30` arrives as the int 390 (PyYAML 1.1 sexagesimal).
        Same rule as tools/wakeup_light_preflight.py -- change both."""
        if not isinstance(value, str):
            raise ValueError(
                f"{day}: {key} must be a quoted string like \"6:30\", got "
                f"{value!r} ({type(value).__name__}) -- an unquoted 6:30 in "
                f"YAML is the integer 390")
        for fmt in TIME_FORMATS:
            try:
                return datetime.strptime(value, fmt).time()  # noqa: DTZ007 -- time of day, no zone
            except ValueError:
                continue
        raise ValueError(f"{day}: {key} must be HH:MM or HH:MM:SS, got "
                         f"{value!r}")

    @staticmethod
    def _seconds_between(later: datetime, earlier: datetime) -> float:
        """Real elapsed seconds, via epoch. NOT `later - earlier`.

        Python does NAIVE subtraction when both operands carry the same tzinfo
        object: "the common tzinfo attribute is ignored". Every datetime here
        descends from one `self.get_now()` by `.replace()`, so they all share a
        tzinfo and `later - earlier` returns the WALL-CLOCK difference.

        On 2026-10-25 the clock goes back at 03:00. From 01:00 to 07:20 local
        is 6h20m on the wall and 7h20m in reality -- 22800s against 26400s.
        `run_in()` takes real seconds, so the naive form schedules the wake-up
        light an hour early on that night. Making the datetimes aware does not
        fix it on its own; computing in epoch seconds does.
        """
        return later.timestamp() - earlier.timestamp()

    def get_today_schedule(self, now: datetime = None) -> Optional[Dict]:
        """Get today's schedule times as datetime objects.

        `now` must be timezone-aware. Every caller passes `self.get_now()`,
        AppDaemon's own clock, so the times derived here by `.replace()` are
        aware too and the arithmetic downstream stays consistent.
        """
        if now is None:
            now = self.get_now()

        dayname = now.strftime("%A").lower()
        day_config = self.days.get(dayname, {})

        if not day_config.get("active", False):
            return None

        # Times were parsed and ordered at startup (T-32); nothing here
        # can fail at 06:30 on a school morning any more.
        parsed = self._weekday_times[dayname]
        return {key: now.replace(hour=t.hour, minute=t.minute,
                                 second=t.second, microsecond=0)
                for key, t in parsed.items()}

    def setup_day_schedule(self, kwargs=None):
        """Setup the schedule for the current day"""
        # Cancel existing timers
        # silent=True (T-34): a non-repeating handle is popped when it
        # fires, so cancelling it afterwards is routine -- the un-silenced
        # WARNING appeared every morning and trained the operator to
        # ignore the one log where real failures surface.
        for timer in [self.active_timer, self.turnoff_timer]:
            if timer:
                self.cancel_timer(timer, silent=True)
        self.active_timer = self.turnoff_timer = None

        if self.calendar_exception_cached:
            return

        now = self.get_now()
        schedule = self.get_today_schedule(now)
        if not schedule:
            return

        start_time, end_time, turnoff_time = schedule['start'], schedule['end'], schedule['turnoff']

        if self._seconds_between(turnoff_time, now) <= 0:
            return
        elif self._seconds_between(start_time, now) > 0:
            delay = self._seconds_between(start_time, now)
            self.log(f"Scheduling start in {delay:.0f} seconds")
            self.active_timer = self.run_in(self.start_brightness_cycle, delay, schedule=schedule)
        elif self._seconds_between(end_time, now) >= 0:
            self.log("Starting brightness cycle")
            self.start_brightness_cycle(schedule=schedule)
        else:
            delay = self._seconds_between(turnoff_time, now)
            self.turnoff_timer = self.run_in(self.turn_off_light, delay)

    def start_brightness_cycle(self, kwargs=None, schedule=None):
        """Start the brightness adjustment cycle"""
        if schedule is None:
            schedule = self.get_today_schedule()
            if not schedule:
                return

        start_time, end_time, turnoff_time = schedule['start'], schedule['end'], schedule['turnoff']
        ramp_duration = self._seconds_between(end_time, start_time)

        if ramp_duration <= 0:
            self.log("Error: Invalid ramp duration", level="ERROR")
            return

        # C7 failsafe (T-32), checked BEFORE the ramp starts: if the
        # turnoff is already past when we get here (an app reload between
        # end and turnoff, or clock skew), starting a ramp with no turnoff
        # timer leaves the light burning until someone notices. Turn it
        # off now, loudly, instead.
        turnoff_delay = self._seconds_between(turnoff_time, self.get_now())
        if turnoff_delay <= 0:
            self.log(
                f"turnoff {turnoff_time.strftime('%H:%M')} is already past "
                f"at cycle start -- not ramping, turning {self.entity} off "
                f"now rather than leaving it lit with no turnoff timer",
                level="ERROR",
            )
            self.turn_off_light()
            return

        # "immediate" (T-35): with "now" the first fire lands at
        # now + freq, so the lamp sat dark for the first minute of a ramp
        # the README says starts at `start`.
        self.active_timer = self.run_every(
            self.adjust_brightness, "immediate", self.adjust_freq,
            ramp_duration=ramp_duration, start_time=start_time, end_time=end_time
        )
        self.turnoff_timer = self.run_in(self.turn_off_light, turnoff_delay)

    def adjust_brightness(self, kwargs):
        """Adjust brightness based on time progression"""
        ramp_duration = kwargs['ramp_duration']
        start_time = kwargs['start_time']
        end_time = kwargs['end_time']

        now = self.get_now()
        elapsed = self._seconds_between(now, start_time)

        if self._seconds_between(end_time, now) <= 0:
            # Final tick (T-35): the loop used to cancel itself here WITHOUT
            # a last turn_on, so the ramp topped out one interval short --
            # 238 of 255 on the live schedule, every morning, and the top
            # of the range had never actually been exercised. Command full
            # brightness before stopping. (brightness=255 verified against
            # a ZHA lamp 2026-09-05: the service accepts it and the lamp
            # clamps to its ZigBee ceiling of 254 -- no error.)
            self.turn_on(self.entity, brightness=self.max_brightness)
            if self.active_timer:
                self.cancel_timer(self.active_timer, silent=True)
                self.active_timer = None
            return

        brightness = (
            0 if elapsed <= 0 else
            self.max_brightness if elapsed >= ramp_duration else
            math.ceil(self.max_brightness * (elapsed / ramp_duration))
        )

        self.turn_on(self.entity, brightness=brightness)

    def turn_off_light(self, kwargs=None):
        """Turn off the light and cleanup"""
        self.log("Light turned off")
        self.turn_off(self.entity)
        for timer in [self.active_timer, self.turnoff_timer]:
            if timer:
                self.cancel_timer(timer, silent=True)
        self.active_timer = self.turnoff_timer = None


