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
- **Enterprise-Grade Code**: Clean, maintainable, and well-documented
- **Error Handling**: Graceful handling of missing configuration
- **State Management**: Proper timer cleanup and state consistency
- **Defensive Programming**: Robust null checks and validation

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
     calendar: "calendar.your_calendar"  # optional
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
  calendar: "calendar.school_holidays"

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
- **Gradual Increase**: Brightness ramps from 0 to max over the specified time window
- **Smooth Transitions**: Adjustments occur at the configured frequency
- **Automatic Turnoff**: Light turns off at the specified turnoff time

### **Exception Handling**
- **Calendar Exceptions**: Respects calendar events to skip wakeup lights
- **Inactive Days**: Automatically skips days marked as inactive
- **Error Recovery**: Graceful handling of missing configuration or entities

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

Copyright (c) 2024 the_louie

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

---

**Enjoy your gentle, automated wakeup experience! 🌅**