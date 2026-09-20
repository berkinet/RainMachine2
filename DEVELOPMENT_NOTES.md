# Development Notes

## 2026-09-20 — RainMachine internal scheduling and future software development

### Background

RainMachine hardware development appears to have largely stopped, and controller firmware development appears dormant. The purpose of this investigation is **not** to move irrigation scheduling into Indigo or RainMachine2. The preferred architecture is deliberately distributed: the RainMachine should remain an autonomous irrigation appliance that can continue to operate independently, while RainMachine2 communicates asynchronously with it for status, monitoring, and supervisory/control functions.

The concern is therefore the long-term maintainability and possible modification of the **internal RainMachine irrigation algorithms**, especially scheduling, ETo/weather adjustment, soil-water accounting, and handling of schedule conflicts.

### Scheduling behavior of interest

RainMachine's normal weather-adaptive approach primarily varies watering duration according to calculated weather/ET demand. A practical problem is that high ETo can extend program durations enough that watering programs overlap, collide with later programs, or run outside the originally intended watering window.

Rachio provides an interesting alternative model. Its Flex-style scheduling uses a soil-moisture/depletion model to vary **watering frequency** rather than simply increasing or decreasing the duration of every scheduled irrigation. Conceptually:

- RainMachine-style duration adjustment: scheduled day remains relatively fixed; runtime changes according to weather demand.
- Rachio-style adaptive frequency: soil-water deficit determines whether watering is needed; a zone may be skipped until depletion reaches the watering threshold.

A future RainMachine modification could potentially retain the controller's ET and soil calculations while changing the policy that turns those calculations into watering events.

### What RainMachine has made available

RainMachine published several components as open source, including mobile/web software, developer resources, weather-parser support, and the OpenWrt build used by the Mini-8. However, no public repository has yet been found containing the complete internal controller scheduling application.

RainMachine does support Python weather parsers running directly on the controller, demonstrating that portions of the controller software stack are Python and are designed to be extensible.

### Evidence about the internal controller application

RainMachine firmware notes, logs, support discussions, and developer material expose internal Python framework/module names including:

- `RMSimulatorFramework`
- `RMProgramsFramework`
- `rmProgramScheduler`
- `rmProgramSchedulerWatering`
- `rmProgramSchedulerCore`
- `RMParserFramework`
- `RMUtilsFramework`

Observed paths include `/rainmachine-app/RMParserFramework/...`, suggesting that the irrigation application itself resides under `/rainmachine-app`.

Firmware release notes also describe changes to scheduler and simulator modules, including calculations involving available water, ET0 and precipitation.

This strongly suggests that important parts of the irrigation engine may exist on the controller as Python code rather than solely as opaque native firmware.

### Adaptive Frequency

RainMachine itself added an **Adaptive Frequency** capability. Its documentation describes skipping non-optimal watering cycles based on calculated soil moisture.

The controller therefore already appears to maintain much of the state needed for a Rachio-like approach, including concepts such as:

- available water / soil-water balance
- field capacity and allowed depletion
- root depth
- crop coefficient
- application rate
- irrigation efficiency
- soil intake rate
- ET0
- precipitation / forecast precipitation

This raises the possibility that a future modification would not require implementing an irrigation model from scratch. It may instead be possible to modify the policy by which RainMachine's existing soil-water model determines watering frequency and duration.

### Schedule collision handling

A separate area for investigation is RainMachine's internal scheduler behavior when weather adjustment extends watering beyond the available time.

Questions include:

- How are overlapping programs serialized or prioritized?
- Does a program delayed by another program retain its full calculated runtime?
- What happens when total calculated irrigation exceeds the available watering window?
- Can zones/programs be deferred rather than extended into subsequent schedules?
- Does Adaptive Frequency participate in resolving these conflicts?
- Could a modified scheduler prioritize zones according to soil-water depletion and defer zones that can safely wait?

### Third-party/reverse-engineering status

Third-party RainMachine development found so far is primarily API integration and monitoring/control software rather than replacement firmware or a replacement internal scheduler. No publicly maintained fork of the complete RainMachine irrigation engine has yet been identified.

However, RainMachine provides SSH access on at least some controller families, and field logs expose Python filenames, line numbers, class/module names and internal watering state. It is therefore plausible that additional editable or recoverable code exists directly on the installed controller even though RainMachine has never published it in a source repository.

### Next investigation

The next step should be **read-only inspection of the actual RainMachine controller** before designing any replacement algorithm.

Via SSH, inventory `/rainmachine-app` and determine:

1. Which scheduler/simulator/framework modules are installed.
2. Whether they are ordinary `.py` source files, `.pyc` bytecode, packaged Python modules, or native binaries.
3. The Python version used by the controller.
4. Where the ET/weather adjustment is converted into zone runtime.
5. How available-water/soil-depletion state is maintained.
6. How Adaptive Frequency makes skip/run decisions.
7. How simultaneous or overlapping programs are queued and resolved.

No controller files should initially be modified. If readable source is present, copy the relevant application tree for offline analysis and version control.

### Architectural constraint

Any future work should preserve the existing design principle:

**RainMachine remains independently capable of irrigation scheduling and valve control. RainMachine2/Indigo observes status and provides supervisory control, but normal irrigation must not depend on Indigo, the Indigo host, or another external scheduler being available.**

The objective is therefore to investigate whether the autonomous RainMachine scheduler itself can be understood, preserved, and eventually modified or replaced in-place.
