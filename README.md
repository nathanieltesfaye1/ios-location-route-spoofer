# iOS Location Route Spoofer

This project allows for hands-free iPhone location spoofing on a predefined route. It's mainly intended for QA where an iOS device needs to appear as if it's moving between stops (e.g. driver app) without having to manually change location each time (which is a limitation of [`GeoPort`](https://github.com/davesc63/GeoPort), our current spoofing solution).

The tool takes a route JSON file, converts it into a GPX file and then uses `pymobiledevice3` to play that GPX route on a usb-connected iPhone.
- [`pymobiledevice3`](https://github.com/doronz88/pymobiledevice3)

It supports:
- Line Routes, Timetabled Loops, Untimetabled Loops
- Continuous movement
- Multiple stops, pausing at each stop, custom pause times for each stop
- Custom drive speeds between stops
- Custom rate of location updates
- Pause/resume playback (only verified on Mac so far)
- Mac tested, need to check Windows (should work on Windows, but setup may vary slightly)

## How it works
The flow works as follows:

_`route.json`_ → _`generate_gpx.py route.json`_ → _`outputs/route.gpx`_ → _`pymobiledevice3 route.gpx playback`_ → iPhone location spoofed along route!

The Python script doesn't directly spoof the location itself. Instead, it generates the `.gpx` file, which is then passed to `pymobiledevice3`, which does the actual spoofing.

## Requirements
You need:
- Python 3
- `pymobiledevice3`
- A physical iPhone (with developer mode enabled)
- iPhone connected to laptop via USB
- `pymobiledevice3` tunnel running
- Mac or Windows

Mac's been tested, Windows tbc.

## Instructions
### Setup Environment
Create and activate a Python virtual environment. In a terminal window, execute:

```
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```
python3 -m pip install -U pip
python3 -m pip install -U pymobiledevice3
```
### Setup iPhone
Connect iPhone to the laptop with a USB cable. Tap "trust this computer" on the iPhone if prompted. Enable developer mode too if not already enabled (you may need to restart the phone after doing this).

### Start the tunnel
In a second terminal window, activate the venv and start the tunnel:
```
source .venv/bin/activate
sudo .venv/bin/python -m pymobiledevice3 remote tunneld
```

Keep this terminal open and running while spoofing location.

### Generate a GPX file
Put your JSON file inside `json_routes/` directory.

Then, run: `python3 generate_gpx.py <filename>.json`

The script will read the JSON file, and output: `outputs/<filename>.gpx`

### Spoof Location!
To spoof the location, playback the recently created GPX. In the __first__ terminal window, execute:
```
pymobiledevice3 developer dvt simulate-location play outputs/<filename>.gpx
```

The iPhone should now move along the generated GPX route.

### Pause/Resume Playback
When the GPX route is running on Mac (not yet tested on Windows):
- Pause playback: `Ctrl + Z`
- Resume playback: `fg`

These are both terminal commands.

### Clear Location
When done, clear the location from the iPhone with `Ctril + C`.

If location still hasn't cleared, run this in the first terminal:
```
pymobiledevice3 developer dvt simulate-location clear
```

Also, on the second terminal window, kill the tunnel with `Ctrl + C`.

## Route Types
3 route types are supported:
- Lines
- Timetabled Loops
- Untimetabled Loops

### Line Routes
Line routes travel from the first stop to the final stop (through a set of waypoints, if provided) once. E.g. `A -> B -> C -> done`.

Example JSON:
```json
{ "name": "Line Route 1",
  "locationUpdateIntervalSeconds": 1,
  "routeType": "line",
  "stops": [
    { "name": "Stop A",
      "lat": 51.505,
      "lon": -0.2228,
      "pauseSeconds": 30,
      "driveSecondsToNextStop": 300 },
    { "name": "Stop B",
      "lat": 51.508,
      "lon": -0.2762,
      "pauseSeconds": 30,
      "driveSecondsToNextStop": 300 },
   { "name": "Stop C",
     "lat": 51.513,
     "lon": -0.3043,
     "pauseSeconds": 30 }
 ]
}
```

For line routes, every stop except the last stop must include `driveSecondsToNextStop` (becuase there's no next stop).

### Timetabled Loops
A timetbaled loop completes a known number of full loops.

E.g. for the route `A -> B -> C`, if `totalLoops=3`, then the route becomes:
- `A -> B -> C -> A -> B -> C -> A -> B -> C -> A`

Example JSON:
```json
{ "name": "Timetabled Loop Route 1",
  "locationUpdateIntervalSeconds": 1,
  "routeType": "timetabledLoop",
  "totalLoops": 3,
  "stops": [
    { "name": "Stop A",
      "lat": 51.505,
      "lon": -0.2228,
      "pauseSeconds": 30,
      "driveSecondsToNextStop": 300 },
    { "name": "Stop B",
      "lat": 51.508,
      "lon": -0.2762,
      "pauseSeconds": 30,
      "driveSecondsToNextStop": 300 },
   { "name": "Stop C",
     "lat": 51.513,
     "lon": -0.3043,
     "pauseSeconds": 30,
     "driveSecondsToNextStop": 300 }
 ]
}
```

For timetabled loops, every stop must include `driveSecondsToNextStop`.

The final stop's `driveSecondsToNextStop` means the time taken to drive from the final stop back to the first stop.

### Untimetabled Loops
An untimetabled loop keeps running for a fixed total time. This means it might stop halfway through a loop if `totalRunSeconds` ends before the loop is complete.

Example JSON:
```json
{ "name": "Untimetabled Loop Route 1",
  "locationUpdateIntervalSeconds": 1,
  "routeType": "untimetabledLoop",
  "totalRunSeconds": 2700,
  "stops": [
    { "name": "Stop A",
      "lat": 51.505,
      "lon": -0.2228,
      "pauseSeconds": 30,
      "driveSecondsToNextStop": 300 },
    { "name": "Stop B",
      "lat": 51.508,
      "lon": -0.2762,
      "pauseSeconds": 30,
      "driveSecondsToNextStop": 300 },
   { "name": "Stop C",
     "lat": 51.513,
     "lon": -0.3043,
     "pauseSeconds": 30,
     "driveSecondsToNextStop": 300 }
 ]
}
```

Again, for untimetabled loops, every stop must include `driveSecondsToNextStop`.

`totalRunSeconds` determines the total GPX duration. E.g. `"totalRunSeconds": 2700` means the route will run for 45 mins.

### JSON Field Meanings
`name`
- The name of the route/stop.

`locationUpdateIntervalSeconds`
- How often the location should update. I find for smooth movement, a value of `1` is good.

`routeType`
- Must be either:
  - `line`
  - `timetabledLoop`
  - `untimetabledLoop`

`totalLoops`
- Only used for `untimetabledLoops`
- Controls how long the route should run for in total

`stops`
- The array containing all stops in the route

`lat`
- The stop's latitutde.

`lon`
- The stop's longitude.

`pauseSeconds`
- How long the route should stay at that stop

`driveSecondsToNextStop`
- How long it should take to travel from the current stop to the next stop.
- For loop routes (timetabled + untimetabled), the final stop's `driveSecondsToNextStop` determines the travel time back to the first stop.
- Line routes don't need `driveSecondsToNextStop` for the last stop, because there is no need to return back to the first stop.

### JSON Validation Rules
All routes must include:
- `name`
- `routeType`
- `locationUpdateIntervalSeconds`
- `stops`

Each stop must include:
- `name`
- `lat`
- `lon`
- `pauseSeconds`

Each route must have at least 2 stops.

`locationUpdateIntervalSeconds` must be > 0.

`pauseSeconds` must be >= 0.

For `line` routes:
- Every stop except the final stop must include `driveSecondsToNextStop`.
- The final stop does not need `driveSecondsToNextStop`

For `timetabledLoop` routes:
- `totalLoops is required`
- `totalLoops` must be > 0
- Every stop must include `driveSecondsToNextStop`

For `untimetabledLoop` routes:
- `totalRunSeconds` is required
- `totalRunSeconds` must be > 0
- Every stop must include `driveSecondsToNextStop`
