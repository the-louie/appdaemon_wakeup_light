import appdaemon.plugins.hass.hassapi as hass
# datetime is imported for the type hint only. The CLOCK is self.get_now():
# datetime.now() is naive local time on the container, which is a different
# thing from Home Assistant's configured timezone and, across the autumn
# fold on 25 October, a different thing from real elapsed time. A wake-up
# light an hour late is not a rounding error to the person it wakes.
from datetime import datetime
import math
from typing import Dict, Optional


class WakeupLight(hass.Hass):
    def initialize(self):
        """Initialize the wakeup light app with configuration and scheduling"""
        # Validate required configuration early
        if not self.args.get("entity") or not self.args.get("days"):
            self.log("Error: 'entity' and 'days' parameters are required", level="ERROR")
            return

        self.entity = self.args["entity"]
        self.max_brightness = self.args.get("max_brightness", 254)
        self.days = self.args["days"]
        self.adjust_freq = self.args.get("freq", 60)
        self.cal_name = self.args.get("calendar")
        self.calendar_exception_cached = False
        self.active_timer = None
        self.turnoff_timer = None

        self.log(f"WakeupLight started for {self.entity}")
        self.run_in(self.setup_day_schedule, 0)
        self.run_daily(self.check_calendar_exception, "03:30:00")

    def check_calendar_exception(self, kwargs):
        """Check calendar exception once at 03:30 and cache result"""
        self.calendar_exception_cached = (
            bool(self.cal_name) and self.get_state(f"calendar.{self.cal_name}") != "off"
        )
        if self.calendar_exception_cached:
            self.log("Calendar exception active")
        self.setup_day_schedule()

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

        try:
            times = {}
            for key in ["start", "end", "turnoff"]:
                time_str = day_config.get(key, "06:20" if key == "start" else "06:40" if key == "end" else "06:50")
                hour, minute = map(int, time_str.split(":"))
                times[key] = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return times
        except (ValueError, AttributeError):
            self.log(f"Error parsing time format for {dayname}", level="ERROR")
            return None

    def setup_day_schedule(self, kwargs=None):
        """Setup the schedule for the current day"""
        # Cancel existing timers
        for timer in [self.active_timer, self.turnoff_timer]:
            if timer:
                self.cancel_timer(timer)
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
            self.active_timer = self.run_in(self.turn_off_light, delay)

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

        self.active_timer = self.run_every(
            self.adjust_brightness, "now", self.adjust_freq,
            ramp_duration=ramp_duration, start_time=start_time, end_time=end_time
        )

        turnoff_delay = self._seconds_between(turnoff_time, self.get_now())
        if turnoff_delay > 0:
            self.turnoff_timer = self.run_in(self.turn_off_light, turnoff_delay)

    def adjust_brightness(self, kwargs):
        """Adjust brightness based on time progression"""
        ramp_duration = kwargs['ramp_duration']
        start_time = kwargs['start_time']
        end_time = kwargs['end_time']

        now = self.get_now()
        elapsed = self._seconds_between(now, start_time)

        if self._seconds_between(end_time, now) <= 0:
            if self.active_timer:
                self.cancel_timer(self.active_timer)
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
                self.cancel_timer(timer)
        self.active_timer = self.turnoff_timer = None


