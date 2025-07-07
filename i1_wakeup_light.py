import pytz
from datetime import datetime, timedelta
import time
import json
import appdaemon.plugins.hass.hassapi as hass
import math

timezone = pytz.timezone('Europe/Stockholm')

class WakeupLight(hass.Hass):
    def initialize(self):
        self.entity=self.args.get("entity") #light.v2_barnenssovrum_vaknalampa"

        self.max_brightness=self.args.get("max_brightness", 254)

        self.days = self.args.get("days", {})
        self.log(self.days)
        self.adjust_freq=self.args.get("freq", 10)
        
        self.cal_name = self.args.get("calendar")

        self.run_every(self.adjust_lamp, "now", self.adjust_freq)

        self.log("WakeupLight started, {}".format(self.entity))

    def calendar_exception(self):
        if self.cal_name is None:
            return False

        has_exception = self.get_state("calendar.{}".format("vaknalampa_undantag"))
        if has_exception == "off":
            return False
        else:
            return True

    def day_active(self):
        dayname = datetime.now().strftime("%A").lower()
        result = self.days.get(dayname).get("active", False)
        return result

    def day_inactive(self):
        return self.day_active() == False

    def adjust_lamp(self, args):
        has_exception = self.calendar_exception()
        is_inactive = self.day_inactive()
        self.log("has_exception: {} is_inactive: {}".format(has_exception, is_inactive))
        if has_exception or is_inactive:
            return

        dayname = datetime.now().strftime("%A").lower()
        start = self.days.get(dayname, {}).get("start", "06:20").split(":")
        end = self.days.get(dayname, {}).get("end", "06:40").split(":")
        off = self.days.get(dayname, {}).get("off", "07:50").split(":")

        start_dt = datetime.now().replace(hour=int(start[0]), minute=int(start[1]), second=0, microsecond=0)
        end_dt=start_dt.replace(hour=int(end[0]), minute=int(end[1]))
        off_dt = datetime.now().replace(hour=int(off[0]), minute=int(off[1]), second=0, microsecond=0)
        start_end_len=(end_dt - start_dt).seconds
        midnight_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        sec_now = (datetime.now() - midnight_dt).seconds
        sec_start = (start_dt - midnight_dt).seconds
        sec_end = (end_dt - midnight_dt).seconds
        sec_off = (off_dt - midnight_dt).seconds

        light_state = self.get_state(self.entity)

        if sec_now > sec_off or sec_now < sec_start:
            if light_state == "on":
                self.log("Outside scope and light was on, turning off")
                self.turn_on(self.entity, brightness=0)
                self.turn_off(self.entity)
            return

        if sec_now < sec_start or sec_now > sec_end:
            self.log("time not in scope, start: {} end: {} now: {} state: {}".format(sec_start, sec_end, sec_now, light_state))
            return

        brightness = math.ceil(self.max_brightness * ((sec_now - sec_start) / start_end_len))
        self.log("ok brightness: {} now: {} st: {} end: {} size: {}".format(brightness, sec_now, sec_start, sec_end, start_end_len))
        self.turn_on(self.entity, brightness = brightness )


