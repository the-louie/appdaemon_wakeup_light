import appdaemon.plugins.hass.hassapi as hass
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

    def get_today_schedule(self, now: datetime = None) -> Optional[Dict]:
        """Get today's schedule times as datetime objects"""
        if now is None:
            now = datetime.now()

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

    def setup_day_schedule(self):
        """Setup the schedule for the current day"""
        # Cancel existing timers
        for timer in [self.active_timer, self.turnoff_timer]:
            if timer:
                self.cancel_timer(timer)
        self.active_timer = self.turnoff_timer = None

        if self.calendar_exception_cached:
            return

        now = datetime.now()
        schedule = self.get_today_schedule(now)
        if not schedule:
            return

        start_time, end_time, turnoff_time = schedule['start'], schedule['end'], schedule['turnoff']

        if now >= turnoff_time:
            return
        elif now < start_time:
            delay = (start_time - now).total_seconds()
            self.log(f"Scheduling start in {delay:.0f} seconds")
            self.active_timer = self.run_in(self.start_brightness_cycle, delay, schedule=schedule)
        elif now <= end_time:
            self.log("Starting brightness cycle")
            self.start_brightness_cycle(schedule=schedule)
        else:
            delay = (turnoff_time - now).total_seconds()
            self.active_timer = self.run_in(self.turn_off_light, delay)

    def start_brightness_cycle(self, kwargs=None, schedule=None):
        """Start the brightness adjustment cycle"""
        if schedule is None:
            schedule = self.get_today_schedule()
            if not schedule:
                return

        start_time, end_time, turnoff_time = schedule['start'], schedule['end'], schedule['turnoff']
        ramp_duration = (end_time - start_time).total_seconds()

        if ramp_duration <= 0:
            self.log("Error: Invalid ramp duration", level="ERROR")
            return

        self.active_timer = self.run_every(
            self.adjust_brightness, "now", self.adjust_freq,
            ramp_duration=ramp_duration, start_time=start_time, end_time=end_time
        )

        turnoff_delay = (turnoff_time - datetime.now()).total_seconds()
        if turnoff_delay > 0:
            self.turnoff_timer = self.run_in(self.turn_off_light, turnoff_delay)

    def adjust_brightness(self, kwargs):
        """Adjust brightness based on time progression"""
        ramp_duration = kwargs['ramp_duration']
        start_time = kwargs['start_time']
        end_time = kwargs['end_time']

        now = datetime.now()
        elapsed = (now - start_time).total_seconds()

        if now >= end_time:
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


