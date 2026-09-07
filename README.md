# Wakeup Light for Home Assistant

A highly efficient and intelligent wakeup light automation for Home Assistant using AppDaemon. This script gradually increases light brightness during wakeup times, providing a natural and gentle way to wake up.

## 🌟 Features

### **Smart Scheduling**
- **Intelligent Time Management**: Only runs during active wakeup windows, not 24/7
- **Dynamic Scheduling**: Automatically schedules the next action based on current time
- **Calendar Integration**: Respects calendar exceptions to skip wakeup lights on special days
- **Daily Optimization**: Checks calendar once at 03:30 AM and caches the result

### **Efficient Performance**
- **97% CPU Reduction**: Runs ~30-50 times per day instead of 1440 times (every minute)
- **Minimal Resource Usage**: Only active during wakeup windows
- **Smart Caching**: Calendar exceptions checked once per day, not every minute
- **Optimized Scheduling**: Single timer management with proper cleanup

### **Flexible Configuration**
- **Per-Day Settings**: Different wakeup times for each day of the week
- **Customizable Brightness**: Adjustable maximum brightness (0-255)
- **Smooth Transitions**: Configurable brightness adjustment frequency
- **Weekend Support**: Easy to disable on weekends or holidays

### **Reliable Operation**
- **Fail-loud configuration** (D1): a bad config is a *failed app* in the
  AppDaemon console — which the watchdog reports to a phone — never a
  loaded-but-inert one. `initialize()` raises on: missing `entity`/`days`, an
  entity or calendar that does not exist, non-numeric or non-positive `freq`
  (four such values would otherwise hang AppDaemon's scheduler, not just this
  app), `max_brightness` outside 1..255, non-lowercase day keys, an active day
  missing any of start/end/turnoff, unparseable times (unquoted `6:30` is the
  integer 390 in YAML — the raise names this), or times out of order.
- **All times parse at startup**: nothing parses config at 06:30 on a school
  morning; `get_today_schedule` reads pre-validated `datetime.time` objects.
- **Timer hygiene**: fired handles cancel with `silent=True` (no
  false-warning per morning) and the turnoff handle lives in `turnoff_timer`.
- **Turnoff failsafe**: a cycle that starts after its own turnoff (reload
  between end and turnoff) turns the light OFF loudly instead of ramping with
  no turnoff timer.
- **DST-safe arithmetic**: all delays are epoch-seconds via
  `_seconds_between`; the wall clock is AppDaemon's `get_now()`.

## 🚀 Benefits

### **For Users**
- **Natural Wakeup**: Gradual light increase mimics natural sunrise
- **Better Sleep Quality**: Gentle wakeup process improves sleep patterns
- **Customizable**: Tailored to individual schedules and preferences
- **Reliable**: Works consistently without manual intervention

### **For System Performance**
- **Low Resource Usage**: Minimal impact on Home Assistant performance
- **Efficient Scheduling**: Smart timing reduces unnecessary executions
- **Clean Codebase**: Easy to maintain and extend
- **Scalable**: Can handle multiple lights and complex schedules

## 📋 Requirements

- **Home Assistant** with AppDaemon installed
- **Light entity** that supports brightness control
- **Calendar entity** (optional, for exceptions)

## ⚙️ Installation

1. **Copy the script** to your AppDaemon `apps` directory:
   ```
   apps/i1_wakeup_light.py
   ```

2. **Add configuration** to your AppDaemon `conf` directory:
   ```yaml
   # apps.yaml
   wakeupLight:
     module: i1_wakeup_light
     class: WakeupLight
     entity: "light.your_light_entity"
     calendar: "your_calendar"  # optional -- bare name; the full "calendar.x" id also works
     max_brightness: 255
     freq: 60
     days:
       monday:
         active: true
         start: "6:20"
         end: "6:40"
         turnoff: "6:50"
       # ... configure other days
   ```

3. **Restart AppDaemon** to load the new app

## 🔧 Configuration Options

### **Required Parameters**
- `entity`: Light entity ID to control
- `days`: Daily schedule configuration

### **Optional Parameters**
- `calendar`: Calendar entity for exceptions (default: none)
- `max_brightness`: Maximum brightness 0-255 (default: 254)
- `freq`: Brightness adjustment frequency in seconds (default: 60)

### **Day Configuration**
Each day supports:
- `active`: Enable/disable for this day (true/false)
- `start`: Start time for brightness ramp (HH:MM)
- `end`: End time for brightness ramp (HH:MM)
- `turnoff`: Time to turn off light completely (HH:MM)

## 📅 Example Configuration

```yaml
wakeupLight:
  module: i1_wakeup_light
  class: WakeupLight

  # Light entity to control
  entity: "light.bedroom_lamp"

  # Calendar for exceptions (school holidays, etc.)
  calendar: "school_holidays"

  # Maximum brightness (0-255)
  max_brightness: 255

  # Brightness adjustment frequency (seconds)
  freq: 60

  # Daily schedule
  days:
    monday:
      active: true
      start: "6:20"      # Start brightness ramp
      end: "6:40"        # Full brightness reached
      turnoff: "6:50"    # Turn off completely
    tuesday:
      active: true
      start: "6:20"
      end: "6:40"
      turnoff: "6:50"
    wednesday:
      active: true
      start: "6:30"
      end: "6:50"
      turnoff: "7:00"
    thursday:
      active: true
      start: "6:30"
      end: "6:50"
      turnoff: "7:00"
    friday:
      active: true
      start: "6:30"
      end: "6:50"
      turnoff: "7:00"
    saturday:
      active: false      # No wakeup light on weekends
    sunday:
      active: false      # No wakeup light on weekends
```

## 🎯 How It Works

### **Daily Operation**
1. **03:30 AM**: Checks calendar for exceptions and caches the result
2. **Setup Phase**: Determines today's schedule and current time
3. **Smart Scheduling**:
   - Before start time: Schedules brightness cycle
   - During ramp time: Runs brightness adjustments
   - After end time: Schedules turnoff
   - Past turnoff: No action needed

### **Brightness Control**
- **Gradual Increase**: the first adjustment fires at `start` (not one interval
  after it), and brightness ramps toward `max_brightness` at the configured
  frequency
- **Full Brightness at `end`**: the final tick commands `max_brightness`
  explicitly, so the ramp finishes at 100% rather than one interval short
- **Automatic Turnoff**: Light turns off at the specified turnoff time; if a
  cycle ever starts after its own turnoff (a reload between `end` and
  `turnoff`), the light is turned off immediately instead of burning with no
  timer

### **Exception Handling**
- **Calendar Exceptions**: only a calendar that literally reads `on`
  suppresses the wake-up. The calendar is resolved **synchronously at
  startup** (so an AppDaemon reload mid-morning honours an active exception)
  and re-checked daily at 03:30.
- **Fail-open on ambiguity** (owner decision 2026-08-30): if the calendar
  reads `unavailable`/`unknown` — HA restarting overnight, integration not
  yet loaded — the app logs a WARNING, **wakes anyway**, and sends a phone
  notification (channel `watchdog_alerts`, once per day at most). A spurious
  wake-up on a holiday is recoverable; a missed school morning is not.
- **Inactive Days**: days with `active: false` are skipped; a *partially*
  specified active day is a startup error, never silently default-filled.
- **Missing configuration or entities**: not "recovered" — refused at
  startup, loudly (see Reliable Operation).

## 🔍 Troubleshooting

### **Common Issues**

**Light doesn't turn on:**
- Check entity ID is correct
- Verify light supports brightness control
- Check AppDaemon logs for errors

**Wrong timing:**
- Verify time format is HH:MM
- Check day names are lowercase (monday, tuesday, etc.)
- Ensure active is set to true for desired days

**Calendar exceptions not working:**
- Verify calendar entity ID
- Check calendar state (should be "on" for exceptions)
- Review AppDaemon logs at 03:30 AM

### **Logging**
The script provides detailed logging:
- Initialization messages
- Schedule setup information
- Brightness adjustment details
- Calendar exception status

## 🚀 Performance Metrics

### **Before Optimization**
- **Executions per day**: ~1,440 (every minute)
- **Calendar checks**: 1,440 per day
- **CPU usage**: High (continuous operation)

### **After Optimization**
- **Executions per day**: ~30-50 (only during active windows)
- **Calendar checks**: 1 per day
- **CPU usage**: Minimal (97% reduction)
- **Memory usage**: Optimized with single timer management

## 🤝 Contributing

This script is designed to be:
- **Maintainable**: Clean, well-documented code
- **Extensible**: Easy to add new features
- **Reliable**: Robust error handling and state management

Feel free to submit issues or pull requests for improvements!

## 📄 License

This project is open source and available under the 2-Clause BSD License.

Copyright (c) 2025 the_louie

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

---

**Enjoy your gentle, automated wakeup experience! 🌅**