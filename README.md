# Robobloq HyperHDR USB bridge

Screen-synced lighting for a Robobloq USB monitor strip on Windows, without OpenRGB running. HyperHDR captures the screen with DirectX 11 and samples the top, left and right borders. A small Python bridge sends the colours directly to the strip over USB HID.

```text
HyperHDR screen capture -> three edge regions -> localhost UDP -> Robobloq USB strip
```

This was built for a three-sided arrangement with **37 top LEDs, 21 left LEDs and 21 right LEDs**. That mapping was checked on the physical strip. Other edge counts are configurable, but other physical wiring orders and Robobloq models have not been tested.

## Requirements

- Windows 10 or 11. Tested on Windows 11.
- Robobloq USB strip with VID `1A86`, PID `FE07`, lighting usage page `FF00`, usage `1`, interface `0`. Tested firmware: `1.8.2`.
- [Python](https://www.python.org/downloads/windows/) 3.11 or newer. The hardware tests used Python 3.14, 64-bit.
- [HyperHDR](https://github.com/awawa-dev/HyperHDR/releases). The working setup used version 22.0.0.

OpenRGB is not a dependency. Exit it completely, including its tray icon, before controlling the strip with this bridge. Keep the normal Windows HID driver; no Zadig, WinUSB replacement or firmware flashing is needed.

## Set up from a fresh checkout

1. Clone this repository or download its ZIP and extract it into a permanent writable folder. Avoid Program Files and do not run from inside a ZIP.
2. Install Python. Its Windows launcher should make `py` available; `Setup.cmd` falls back to `python` if needed.
3. Double-click **Setup.cmd**. It creates a local `.venv` and installs the pinned HIDAPI dependency from PyPI. It does not install a system-wide Python package.
4. Close OpenRGB and stop any old screen-sync bridge that uses UDP port 5568.
5. Connect the strip, then double-click **Enroll strip.cmd**. This reads device information and creates `config.json` with your strip's UUID. It does not change lighting. The file stays local and is ignored by Git.
6. If your physical LED counts differ, edit `top_leds`, `left_leds` and `right_leds` in `config.json`. The counts must match HyperHDR and your strip. Do not use the default counts on an unrelated layout.
7. Double-click **Test edges.cmd** while no bridge is streaming. It briefly shows dim red, green and blue, then holds **top green, left red, right blue**, viewed from the front. Continue only if those edges match.
8. Configure HyperHDR using the settings below, then double-click **Start screen sync.cmd**.

To stop, double-click **Stop screen sync.cmd**. It requests a graceful exit so the USB handle is closed. The strip retains its last colours until another controller takes over or USB power is removed.

## HyperHDR configuration

Open [the local HyperHDR interface](http://localhost:8090/) after starting HyperHDR. Save each section separately.

### LED Hardware -> LED Controller

| Setting | Value |
| --- | --- |
| Controller type | `udpraw` |
| RGB byte order | `RGB` |
| Target IP | `127.0.0.1` |
| Port | `5568` |

Click **Save settings**. If you change the port, also change `udp_port` in `config.json`. The bridge always binds to localhost.

### LED Hardware -> LED Layout

Use **Classic Layout / LED Frame**, not Matrix / LED Wall.

| Setting | Value |
| --- | --- |
| Top | `37` |
| Left | `21` |
| Right | `21` |
| Bottom | `0` |
| Gap length | `0` |
| Gap position | `0` |
| Input position | `0` |
| Group horizontal / vertical | `0` / `0` |
| Reverse direction | Unchecked |
| Advanced: Horizontal LED depth | `3%` |
| Advanced: Vertical LED depth | `3%` |
| Advanced: Overlap | `0%` |
| Advanced: Edge gap | `0%` |

Leave the four corner points at their defaults. The preview should show 79 regions along the top and sides, with no bottom regions. Click **Save Layout**. Custom edge counts must match `config.json`.

The depth settings sample only the outer 3% for LED colours. HyperHDR still captures a rectangular screen image internally; this is not a U-shaped capture buffer. Its GPU-accelerated capture avoided the desktop lag observed with OpenRGB Ambient on the tested PC.

### Video capturing

- **Instance USB Capture:** uncheck **Enable USB capture**, then save that section. A capture-card error can otherwise appear even though desktop capture works.
- **Software Screen Capture:** choose the monitor to sync, enable **hardware acceleration**, and set **Max. stream width** to `512`. Start with **Frames per second** at `30`, then save that section.
- Keep crop left/right/top/bottom at `0`. The border selection belongs in the LED layout, not these rectangle-crop fields.
- **Instance Screen Capture:** check **Enable system capture**, then save that section.
- HDR to SDR tone mapping was off in the tested SDR setup. If your display uses HDR, consult [HyperHDR's screen capture documentation](https://wiki.hyperhdr.eu/Software-screen-capture).

Once colours and responsiveness are correct, try `60`, then `120` FPS and save each change. The original setup ran at 120 without visible desktop lag. That result depends on the PC and USB controller. Capture FPS, UDP frame rate and actual LED updates can differ, especially when the image is unchanged.

## Reproduce the tested arrangement

Viewed from the front, the physical strip starts at the bottom of the right edge. It runs upward along the right, right to left along the top, then downward along the left. The default map uses the first 79 physical positions and makes all remaining firmware-reported positions black.

HyperHDR's default Classic Layout sends colours in a different order: top left to right, right top to bottom, then left bottom to top. The bridge reverses each segment and puts them in physical order. Changing HyperHDR's input position, reversing its direction, or editing the generated LED array invalidates that assumption.

The tested controller reports 254 addressable positions despite only 79 being used in this layout. Firmware-reported count is used for packet encoding; do not replace it with the visible LED count. The `--probe` command can inspect it.

## After reboot

Saved HyperHDR settings and local `config.json` persist. Start HyperHDR and **Start screen sync.cmd**. OpenRGB remains closed.

To start automatically at sign-in, first test the setup for a longer gaming session, then double-click **Enable startup.cmd**. It adds a startup entry for your Windows user, using the repository's windowless Python executable. No administrator rights or PowerShell execution-policy changes are needed. Setup.cmd does not enable startup by itself.

The installer keeps an existing HyperHDR startup entry. If none exists and HyperHDR is installed under `Program Files\HyperHDR\bin`, it adds one. For another installation location, run:

```powershell
.venv\Scripts\python.exe startup_install.py --install --hyperhdr "D:\Apps\HyperHDR\bin\hyperhdr.exe"
```

HyperHDR loads its saved configuration, including capture FPS, hardware acceleration, output controller and three-border layout. Click **Save settings** after changes in its web interface. The bridge waits for HyperHDR and retries if the strip is temporarily missing; startup order does not matter. If a bridge already owns the configured UDP port, the hidden launcher skips starting a second copy. `startup.log` records the launch or skip result.

Double-click **Disable startup.cmd** to remove the bridge's sign-in entry. It does not stop a running bridge or disable HyperHDR startup. Use Stop screen sync.cmd to stop the current session, and HyperHDR's own startup setting or Windows Task Manager to disable HyperHDR separately.

An earlier manual installation may use a `Robobloq screen sync.lnk` shortcut in `shell:startup`. Remove that shortcut when switching to this repository's startup installer. Do not keep both mechanisms enabled.

Keep the repository folder and `.venv` at their current locations. If you move the folder or reinstall Python, rerun Setup.cmd and Enable startup.cmd. To verify startup, sign out and back in or reboot, check that HyperHDR and the bridge are running, and inspect `status.json` for `streaming`.

OpenRGB can be uninstalled once the direct USB bridge has passed your hardware checks. It is no longer used by either HyperHDR or this bridge.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Lights do not respond | Open `status.json` and `bridge.log` in this folder. Check HyperHDR's system capture, output controller, target IP and port. |
| Device not found | Check USB connection and exit OpenRGB. The bridge opens only the lighting HID interface, excluding the keyboard interface. |
| UUID mismatch | Connect the enrolled strip, or stop the bridge and run Enroll strip.cmd to deliberately register a replacement. |
| Port in use | Stop the old OpenRGB bridge or the other direct bridge. Only one can listen on port 5568. |
| Wrong edges | Run Test edges.cmd with the bridge stopped. Check counts, wiring order, HyperHDR input position and reverse direction. |
| Colours look wrong | Check RGB byte order and HDR tone mapping. Colour calibration is not handled by the bridge. |
| Low input FPS on a static desktop | Unchanged frames may arrive less often. Move a window or play video before judging throughput. |
| Lag or delayed colours | Reduce capture FPS and check GPU load. The bridge discards queued frames and uses one-millisecond USB report pacing. |
| Start shortcut exits immediately | Run `.venv\Scripts\python.exe bridge.py` in a terminal to see errors. Check configuration and Setup.cmd output. |
| Nothing starts at sign-in | Run Enable startup.cmd again; check Windows Task Manager -> Startup apps and `startup.log`. Confirm HyperHDR startup is enabled and the repository folder has not moved. |

Opening OpenRGB causes the bridge to pause USB control after its next process check, normally within ten seconds. For a clean handoff, stop the bridge before opening another controller. Probe, enrollment and colour tests should also be run with all streaming bridges stopped.

## How it works and limits

- HID commands follow OpenRGB's Robobloq implementation. Short packets have an `RB` header; screen packets have an `SC` header and command `0x80`.
- Colours are compressed into at most 34 adjacent ranges with OpenRGB's least-error greedy algorithm. A heap reduces encoding cost while tests compare the output with a direct reference implementation.
- Every USB report is 64 bytes plus report ID 0. Full screen updates use three reports with a one-millisecond gap after each. The bridge checks write lengths and reconnects after failures.
- Identical frames skip USB writes, queued frames are dropped, and the process retries when hardware is unavailable. Logs rotate rather than growing without limit.
- Local logs and status include device information. They are not committed. The published example configuration contains no device UUID or machine-specific path.

Hardware checks covered the colour order, screen sync, stop/restart and a brief 120 FPS input test. Offline tests cover packet headers, padding, checksums, mapping, firmware reply handling, configuration validation and range compression. They do not prove long-term hardware stability or compatibility with other Robobloq firmware.

## Development

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v
.venv\Scripts\python.exe bridge.py --probe
.venv\Scripts\python.exe bridge.py --enroll
.venv\Scripts\python.exe bridge.py --test-colors
.venv\Scripts\python.exe bridge.py
.venv\Scripts\python.exe startup_install.py --install
.venv\Scripts\python.exe startup_install.py --remove
```

Use `--config PATH` to load another local config file. Probe and enrollment issue only device-info commands. Colour testing and streaming also set brightness, stop built-in animation and send screen-colour commands. There are no firmware updates or commands to open the vendor's download URL.

GitHub Actions runs offline tests on Windows with Python 3.11 and 3.14. It does not access USB hardware.

## Attribution and licence

The Robobloq protocol and range merger are adapted from [OpenRGB's RobobloqLightStripController sources](https://github.com/CalcProgrammer1/OpenRGB/tree/2a463a7a3b2a234a21629506511fa77058edaf31/Controllers/RobobloqLightStripController), retrieved 2026-10-03. See `RobobloqLightStripController.cpp`, `RobobloqLightStripController.h`, and `RobobloqRangeMerger.cpp`. This project is GPL-2.0-or-later; see [LICENSE](LICENSE). HIDAPI is installed as a separate dependency and retains its upstream licence.
