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


## 2026-09-20 — Read-only controller source investigation and public research

### Scope and evidence

Inspected the owner's Touch HD-16 over SSH, using the existing RSA identity and known host key. Controller reports Android 4.3/API 18, Linux 3.2.0 ARMv7 and Python 2.7.8. `/rainmachine-app` is a symlink to `/system/rainmachine-app`. The requested frameworks contain readable Python source and matching Python 2.7 bytecode. Selected source was parsed/read in place using `python -B -S`; no application modules were imported or executed. No controller files were copied, edited, deleted or installed; no service was restarted. The prohibition on copying controller files remains in effect pending review. These notes are an authored summary, not a source export.

### Installed computation path

Source references below are relative to `/rainmachine-app`, at the time of inspection.

- `RMFormulaFramework/formula.py:29`: `asceDaily` calculates reference evapotranspiration. The parser/mixer and simulator infrastructure already handles forecasts, observed weather and historical fallbacks.
- `RMSimulatorFramework/rmSimulator.py:496–510`: selects estimated/historical ET, computes future demand and past forecast correction, reads carried available water, and computes net water need. Conceptually: future demand + past correction − available-water carryover.
- `rmSimulator.py:549–616`: future demand uses crop-adjusted ET and precipitation; past correction reconciles actual versus previously used weather, including rain sensitivity and limits.
- `rmSimulator.py:619–682`: turns need into a watering coefficient relative to future days × crop coefficient × average ET. Coefficient limits and the hot-days-extra-watering option apply. Estimated duration is coefficient × user/base duration.
- Adaptive Frequency specifically skips when `freq_modified > 0`, coefficient < `freq_modified / 100`, AND need < half the value returned by `getFieldCapacity(True)`. A skipped deficit is carried forward as negative available water. Minimum-runtime skips also carry deficit. This remains variable-duration irrigation with small-event suppression, not a direct fixed-refill-event, depletion-threshold policy.
- `RMDataFramework/rmMainDataRecords.py:398–408`: despite its name, `getFieldCapacity` returns (soil field capacity − permanent wilting) × root depth × allowed depletion, optionally multiplied by the user's savings coefficient. Thus the simulator's further division by two is half an already depletion-adjusted amount, not simply half the full soil reservoir.
- `rmMainDataRecords.py:528–536`: reference runtime uses average ET, maximum crop coefficient, precipitation/application rate and application efficiency. `rmPrograms.py:619–626` uses an explicit positive user duration when supplied, otherwise a reference duration.
- `rmSimulator.py:947–978`: available water is retrieved using BOTH program ID and zone ID, first from the main database and otherwise simulator data; carryover is bounded. This is not plainly a single physical moisture ledger per zone across all programs.
- `rmSimulator.py:687–733`: multiplies zone coefficient by base duration and duration coefficient to produce simulated watering time.

### Queue behavior and the overlap problem

- `RMProgramsFramework/rmProgramScheduler.py:86–121`: normal automatic scheduling uses the configured start opportunity and simulator result; manual runs follow a separate path.
- `rmProgramScheduler.py:173–207`: computed durations become valve queue records, appended in the normal automatic path.
- `rmValveQueue.py:15–95`: ordered queue, default one concurrent run, checks nominal start times and delay/master-valve entries. No soil-urgency ordering is evident in this path.
- `rmProgramSchedulerWatering.py:218–269`: starts a ready record at its actual dispatch time. `:114–120` finishes by actual start + machine duration. Consequently waiting behind another run does not, by itself, shorten the calculated runtime.
- `rmProgramSchedulerWatering.py:307–427` and `rmPrograms.py:1098–1122`: hourly restrictions can postpone a run; postponement beyond the day can remove queued automatic work. These are restriction safeguards, not evidence of an optimizer that packs all programs into an overall preferred window or chooses the least-stressed zone to defer.
- `rmProgramSchedulerWatering.py:277–296` persists the record's available water when removing an automatic record. Before changing the water ledger, audit partial/manual watering, rain interruptions and restriction removal end to end; physical application must not be inferred solely from a planned runtime.

This was static source inspection, not a live scheduling experiment. Actual configured program flags, water balances and historical overlaps have not yet been audited. No claim is made that all installations or firmware versions behave identically.

### Public RainMachine work: correction to the earlier notes

A public engine port DOES exist: [aroberts/rainmachine-rpi](https://github.com/aroberts/rainmachine-rpi). Its README describes firmware 4.0.1144 ported to Python 3 for Raspberry Pi 4, with the application, web UI, services and GPIO bridge. The repository contains simulator, scheduler, data and utility frameworks. The inspected `app/RMSimulatorFramework/rmSimulator.py` retains the same coefficient/Adaptive Frequency decision branch described above. It is valuable as a portability and offline-study reference, but does not establish a Rachio-like policy replacement or suitability for installation on this Android controller. No independent operational verification was performed. The README names a different clone owner; provenance and licensing need checking before reuse/distribution (GitHub reports no root license).

Other public work inspected:

- [Official developer resources](https://github.com/sprinkler/rainmachine-developer-resources): actual ET formula source, parser SDK, API clients and examples; not the complete scheduling engine.
- [dataoscar/rainmachine-fixes](https://github.com/dataoscar/rainmachine-fixes): contains a NOAA parser fix, not a scheduler replacement.
- [regenmaschine](https://github.com/bachya/regenmaschine): an API integration library, not an internal irrigation algorithm.

Searches of public repositories and documentation did not identify a verified, maintained RainMachine depletion-first/window-budget scheduler. This is a search result, not proof that no such work exists.

### What is public about Rachio

[Rachio's schedule overview](https://support.rachio.com/en_us/rachio-irrigation-schedule-overview-HJrFP8yYD) describes Flex Daily as daily, zone-by-zone decisions based on modeled soil moisture. Its [duration/frequency guide](https://support.rachio.com/en_us/adjust-watering-duration-frequency-of-flex-schedules-r10FDLkFw) distinguishes root depth, available water and allowed depletion (affecting event size and interval) from crop coefficient (affecting consumption/frequency). That guide contains contradictory prose about the direction of allowed-depletion changes; do not treat every sentence as an executable specification.

A [2018 support explanation](https://community.rachio.com/t/irrigation-on-field-capacity-chart-not-consistent-with-watering-times/15548) gives explicit formulas: event depth = root depth × allowed depletion × available water capacity; efficiency/distribution multiplier = 1/(0.4 + 0.6 × efficiency); runtime in minutes = 60 × event depth × user adjustment × multiplier / nozzle precipitation rate. These are historical disclosed formulas, not verified current production source or a complete specification of forecast/skip/queue behavior.

No production Flex Daily engine source was located in Rachio's public repositories or the searches performed. Public API clients should not be mistaken for the algorithm. Rachio's [offline behavior](https://support.rachio.com/en_us/offline-device-functionality-SyboPIkFv) also differs from the desired permanently autonomous RainMachine architecture; imitate the agronomic policy, not a cloud dependency.

### Independent, inspectable algorithm foundation

[FAO-56 chapter 8](https://www.fao.org/4/x0490e/x0490e0e.htm) documents total available water, readily available water and daily root-zone depletion. [pyfao56](https://github.com/kthorp/pyfao56) supplies actual model and automatic-irrigation source plus examples and scientific references. Its AutoIrrigate options include depletion thresholds, permitted weekdays, forecast rain handling, fixed application depths and minimum/maximum irrigation amounts. Source inspection confirmed model states for total available water and depletion, and threshold parameters in `src/pyfao56/autoirrigate.py`. This is NOT Rachio code and is best considered an offline reference model, not a drop-in package for Python 2.7 on the controller.

### Proposed direction, not an approved controller change

Preserve RainMachine's weather acquisition, autonomous operation and established valve/safety handling. Separate two decisions:

1. A per-zone soil-depletion policy determines whether watering is needed before the next permitted opportunity and chooses a bounded refill depth/runtime.
2. A capacity-aware planner fits needed runs, cycle/soak and valve delays into the allowed window; safely defers eligible zones while retaining deficit, and reports infeasible demand instead of silently extending the window or starving plants.

Frequency adjustment alone cannot guarantee that all zones fit on a high-demand day. The main deeper work is reconciling a physical per-zone balance across multiple programs and actual/manual/partial watering, preserving restriction and manual-control semantics, and defining what happens when required watering exceeds capacity. Prototype/replay this offline before any controller change. Copying controller source/data still requires the owner's separate go-ahead.
