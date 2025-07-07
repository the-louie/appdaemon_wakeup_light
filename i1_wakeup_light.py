from datetime import datetime
import appdaemon.plugins.hass.hassapi as hass
import math

class WakeupLight(hass.Hass):
    def initialize(self):
        """Initialize the wakeup light app with configuration and scheduling"""
        self.entity = self.args.get("entity")
        self.max_brightness = self.args.get("max_brightness", 254)
        self.days = self.args.get("days", {})
        self.adjust_freq = self.args.get("freq", 60)
        self.cal_name = self.args.get("calendar")

        # State tracking
        self.calendar_exception_cached = False
        self.active_timer = None

        self.log("WakeupLight started, {}".format(self.entity))

        # Schedule initial setup and daily calendar check
        self.run_in(self.setup_day_schedule, 0)
        self.run_daily(self.check_calendar_exception, "03:30:00")

    def check_calendar_exception(self, kwargs):
        """Check calendar exception once at 03:30 and cache the result"""
        if self.cal_name:
            has_exception = self.get_state("calendar.{}".format(self.cal_name))
            self.calendar_exception_cached = (has_exception != "off")
            self.log("Calendar exception: {}".format(self.calendar_exception_cached))
        else:
            self.calendar_exception_cached = False

        self.setup_day_schedule()

    def get_today_schedule(self):
        """Get today's schedule times as datetime objects"""
        dayname = datetime.now().strftime("%A").lower()
        day_config = self.days.get(dayname, {})

        if not day_config.get("active", False):
            return None

        now = datetime.now()
        start_str = day_config.get("start", "06:20")
        end_str = day_config.get("end", "06:40")
        turnoff_str = day_config.get("turnoff", "06:50")

        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))
        turnoff_h, turnoff_m = map(int, turnoff_str.split(":"))

        return {
            'start': now.replace(hour=start_h, minute=start_m, second=0, microsecond=0),
            'end': now.replace(hour=end_h, minute=end_m, second=0, microsecond=0),
            'turnoff': now.replace(hour=turnoff_h, minute=turnoff_m, second=0, microsecond=0)
        }

    def setup_day_schedule(self):
        """Setup the schedule for the current day"""
        # Cancel any existing timer
        if self.active_timer:
            self.cancel_timer(self.active_timer)
            self.active_timer = None

        # Check if we should run today
        if self.calendar_exception_cached:
            self.log("Skipping today - calendar exception")
            return

        schedule = self.get_today_schedule()
        if not schedule:
            self.log("Skipping today - day inactive")
            return

        now = datetime.now()
        start_time = schedule['start']
        end_time = schedule['end']
        turnoff_time = schedule['turnoff']

        # Determine what to schedule based on current time
        if now >= turnoff_time:
            self.log("Past turnoff time, no scheduling needed")
        elif now < start_time:
            # Schedule start
            delay = (start_time - now).total_seconds()
            self.log("Scheduling start in {:.0f} seconds".format(delay))
            self.active_timer = self.run_in(self.start_brightness_cycle, delay)
        elif start_time <= now <= end_time:
            # Start immediately
            self.log("Starting brightness cycle immediately")
            self.start_brightness_cycle()
        else:
            # Schedule turnoff
            delay = (turnoff_time - now).total_seconds()
            self.log("Scheduling turnoff in {:.0f} seconds".format(delay))
            self.active_timer = self.run_in(self.turn_off_light, delay)

    def start_brightness_cycle(self, kwargs=None):
        """Start the brightness adjustment cycle"""
        schedule = self.get_today_schedule()
        if not schedule:
            return

        start_time = schedule['start']
        end_time = schedule['end']
        turnoff_time = schedule['turnoff']

        # Calculate ramp duration and schedule brightness adjustments
        ramp_duration = (end_time - start_time).total_seconds()
        self.active_timer = self.run_every(
            self.adjust_brightness,
            "now",
            self.adjust_freq,
            ramp_duration=ramp_duration,
            start_time=start_time
        )

        # Schedule turnoff
        turnoff_delay = (turnoff_time - datetime.now()).total_seconds()
        if turnoff_delay > 0:
            self.run_in(self.turn_off_light, turnoff_delay)

    def adjust_brightness(self, kwargs):
        """Adjust brightness based on time progression"""
        ramp_duration = kwargs.get('ramp_duration', 1200)
        start_time = kwargs.get('start_time')

        if not start_time:
            return

        elapsed = (datetime.now() - start_time).total_seconds()

        # Calculate brightness
        if elapsed <= 0:
            brightness = 0
        elif elapsed >= ramp_duration:
            brightness = self.max_brightness
        else:
            brightness = math.ceil(self.max_brightness * (elapsed / ramp_duration))

        self.log("Brightness: {} (elapsed: {:.0f}s)".format(brightness, elapsed))
        self.turn_on(self.entity, brightness=brightness)

    def turn_off_light(self, kwargs):
        """Turn off the light and cleanup"""
        self.log("Turning off light")
        self.turn_off(self.entity)

        # Cancel brightness adjustments
        if self.active_timer:
            self.cancel_timer(self.active_timer)
            self.active_timer = None


