import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET


JSON_ROUTES_FOLDER = Path("json_routes")
OUTPUTS_FOLDER = Path("outputs")

VALID_ROUTE_TYPES = ["line", "timetabledLoop", "untimetabledLoop"]


def load_route(json_file_name):
    json_path = JSON_ROUTES_FOLDER / json_file_name

    if not json_path.exists():
        raise FileNotFoundError(f"Could not find JSON route file: {json_path}")

    with open(json_path, "r", encoding="utf-8") as file:
        return json.load(file), json_path


def validate_common_route_fields(route):
    if "name" not in route:
        raise ValueError("Missing route name")

    if "routeType" not in route:
        raise ValueError("Missing routeType")

    if route["routeType"] not in VALID_ROUTE_TYPES:
        raise ValueError(
            "routeType must be one of: line, timetabledLoop, untimetabledLoop"
        )

    if "locationUpdateIntervalSeconds" not in route:
        raise ValueError("Missing locationUpdateIntervalSeconds")

    if route["locationUpdateIntervalSeconds"] <= 0:
        raise ValueError("locationUpdateIntervalSeconds must be greater than 0")

    if "stops" not in route or len(route["stops"]) < 2:
        raise ValueError("Route must have at least 2 stops")

    for index, stop in enumerate(route["stops"]):
        required_fields = ["name", "lat", "lon", "pauseSeconds"]

        for field in required_fields:
            if field not in stop:
                raise ValueError(f"Stop {index + 1} is missing: {field}")

        if stop["pauseSeconds"] < 0:
            raise ValueError(f"{stop['name']} has invalid pauseSeconds")


def validate_drive_seconds_for_stop(stop):
    if "driveSecondsToNextStop" not in stop:
        raise ValueError(f"{stop['name']} is missing driveSecondsToNextStop")

    if stop["driveSecondsToNextStop"] <= 0:
        raise ValueError(
            f"{stop['name']} must have driveSecondsToNextStop greater than 0"
        )


def validate_line_route(route):
    stops = route["stops"]

    for index, stop in enumerate(stops):
        is_final_stop = index == len(stops) - 1

        if not is_final_stop:
            validate_drive_seconds_for_stop(stop)


def validate_timetabled_loop_route(route):
    if "totalLoops" not in route:
        raise ValueError("timetabledLoop routes must include totalLoops")

    if route["totalLoops"] <= 0:
        raise ValueError("totalLoops must be greater than 0")

    for stop in route["stops"]:
        validate_drive_seconds_for_stop(stop)


def validate_untimetabled_loop_route(route):
    if "totalRunSeconds" not in route:
        raise ValueError("untimetabledLoop routes must include totalRunSeconds")

    if route["totalRunSeconds"] <= 0:
        raise ValueError("totalRunSeconds must be greater than 0")

    for stop in route["stops"]:
        validate_drive_seconds_for_stop(stop)


def validate_route(route):
    validate_common_route_fields(route)

    if route["routeType"] == "line":
        validate_line_route(route)

    elif route["routeType"] == "timetabledLoop":
        validate_timetabled_loop_route(route)

    elif route["routeType"] == "untimetabledLoop":
        validate_untimetabled_loop_route(route)


def add_track_point(track_points, name, lat, lon, current_offset):
    track_points.append({
        "name": name,
        "lat": lat,
        "lon": lon,
        "offset": current_offset
    })


def add_pause_points(
    track_points,
    stop,
    current_offset,
    update_interval,
    max_duration=None
):
    pause_seconds = stop["pauseSeconds"]
    seconds_added = 0

    while seconds_added < pause_seconds:
        if max_duration is not None and current_offset >= max_duration:
            break

        add_track_point(
            track_points,
            f"Paused at {stop['name']}",
            stop["lat"],
            stop["lon"],
            current_offset
        )

        current_offset += update_interval
        seconds_added += update_interval

    return current_offset


def add_drive_points(
    track_points,
    start_stop,
    end_stop,
    current_offset,
    update_interval,
    drive_seconds,
    max_duration=None
):
    seconds_added = 0

    while seconds_added < drive_seconds:
        if max_duration is not None and current_offset >= max_duration:
            break

        seconds_added += update_interval
        fraction = min(seconds_added / drive_seconds, 1)

        lat = start_stop["lat"] + (end_stop["lat"] - start_stop["lat"]) * fraction
        lon = start_stop["lon"] + (end_stop["lon"] - start_stop["lon"]) * fraction

        add_track_point(
            track_points,
            f"Driving from {start_stop['name']} to {end_stop['name']}",
            lat,
            lon,
            current_offset
        )

        current_offset += update_interval

    return current_offset


def build_line_track_points(route):
    stops = route["stops"]
    update_interval = route["locationUpdateIntervalSeconds"]

    track_points = []
    current_offset = 0

    for index, stop in enumerate(stops):
        current_offset = add_pause_points(
            track_points,
            stop,
            current_offset,
            update_interval
        )

        is_final_stop = index == len(stops) - 1

        if not is_final_stop:
            next_stop = stops[index + 1]

            current_offset = add_drive_points(
                track_points,
                stop,
                next_stop,
                current_offset,
                update_interval,
                stop["driveSecondsToNextStop"]
            )

    return track_points, current_offset


def build_one_full_loop(track_points, route, current_offset):
    stops = route["stops"]
    update_interval = route["locationUpdateIntervalSeconds"]

    for index, stop in enumerate(stops):
        next_stop = stops[(index + 1) % len(stops)]

        current_offset = add_pause_points(
            track_points,
            stop,
            current_offset,
            update_interval
        )

        current_offset = add_drive_points(
            track_points,
            stop,
            next_stop,
            current_offset,
            update_interval,
            stop["driveSecondsToNextStop"]
        )

    return current_offset


def build_timetabled_loop_track_points(route):
    track_points = []
    current_offset = 0

    for _ in range(route["totalLoops"]):
        current_offset = build_one_full_loop(
            track_points,
            route,
            current_offset
        )

    return track_points, current_offset


def build_untimetabled_loop_track_points(route):
    stops = route["stops"]
    update_interval = route["locationUpdateIntervalSeconds"]
    total_run_seconds = route["totalRunSeconds"]

    track_points = []
    current_offset = 0
    current_stop_index = 0

    while current_offset < total_run_seconds:
        current_stop = stops[current_stop_index]
        next_stop_index = (current_stop_index + 1) % len(stops)
        next_stop = stops[next_stop_index]

        current_offset = add_pause_points(
            track_points,
            current_stop,
            current_offset,
            update_interval,
            max_duration=total_run_seconds
        )

        if current_offset >= total_run_seconds:
            break

        current_offset = add_drive_points(
            track_points,
            current_stop,
            next_stop,
            current_offset,
            update_interval,
            current_stop["driveSecondsToNextStop"],
            max_duration=total_run_seconds
        )

        current_stop_index = next_stop_index

    return track_points, current_offset


def build_track_points(route):
    if route["routeType"] == "line":
        return build_line_track_points(route)

    if route["routeType"] == "timetabledLoop":
        return build_timetabled_loop_track_points(route)

    if route["routeType"] == "untimetabledLoop":
        return build_untimetabled_loop_track_points(route)

    raise ValueError("Unsupported routeType")


def create_gpx(route, track_points):
    start_time = datetime.now(timezone.utc)

    gpx = ET.Element("gpx", {
        "version": "1.1",
        "creator": "spoof-iOS-location",
        "xmlns": "http://www.topografix.com/GPX/1/1",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": (
            "http://www.topografix.com/GPX/1/1 "
            "http://www.topografix.com/GPX/1/1/gpx.xsd"
        ),
    })

    metadata = ET.SubElement(gpx, "metadata")
    metadata_name = ET.SubElement(metadata, "name")
    metadata_name.text = route["name"]

    track = ET.SubElement(gpx, "trk")
    track_name = ET.SubElement(track, "name")
    track_name.text = route["name"]

    track_segment = ET.SubElement(track, "trkseg")

    for point in track_points:
        track_point = ET.SubElement(track_segment, "trkpt", {
            "lat": f"{point['lat']:.7f}",
            "lon": f"{point['lon']:.7f}",
        })

        elevation = ET.SubElement(track_point, "ele")
        elevation.text = "0"

        time_element = ET.SubElement(track_point, "time")
        time_element.text = (
            start_time + timedelta(seconds=point["offset"])
        ).isoformat().replace("+00:00", "Z")

        description = ET.SubElement(track_point, "desc")
        description.text = point["name"]

    ET.indent(gpx, space="  ", level=0)

    return ET.tostring(gpx, encoding="utf-8", xml_declaration=True).decode("utf-8")


def save_gpx(gpx_content, json_path):
    OUTPUTS_FOLDER.mkdir(exist_ok=True)

    output_file_name = json_path.stem + ".gpx"
    output_path = OUTPUTS_FOLDER / output_file_name

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(gpx_content)

    return output_path


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("python generate_gpx.py <json-file-name>")
        print()
        print("Examples:")
        print("python generate_gpx.py line_route_1.json")
        print("python generate_gpx.py timetabled_loop_route_1.json")
        print("python generate_gpx.py untimetabled_loop_route_1.json")
        sys.exit(1)

    json_file_name = sys.argv[1]

    try:
        route, json_path = load_route(json_file_name)
        validate_route(route)

        track_points, duration_seconds = build_track_points(route)
        gpx_content = create_gpx(route, track_points)
        output_path = save_gpx(gpx_content, json_path)

        print("GPX generated successfully")
        print(f"Route type: {route['routeType']}")
        print(f"Input: {json_path}")
        print(f"Output: {output_path}")
        print(f"Trackpoints: {len(track_points)}")
        print(f"Duration: {duration_seconds} seconds")

    except Exception as error:
        print("Failed to generate GPX")
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()