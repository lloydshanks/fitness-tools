#!/usr/bin/env python

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

import numpy as np
import pandas as pd
from lxml import etree as ET
from scipy.interpolate import interp1d

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


TCD_NS_MAP = {
    None: "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "ns2": "http://www.garmin.com/xmlschemas/UserProfile/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns5": "http://www.garmin.com/xmlschemas/ActivityGoals/v1",
}

AX_NS = {None: "http://www.garmin.com/xmlschemas/ActivityExtension/v2"}


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(in_file: str) -> Dict[str, Any]:
    try:
        with open(in_file) as fp:
            data = json.load(fp)
        return data
    except Exception as e:
        logging.error(f"Error reading JSON file: {e}")
        sys.exit(1)


def process_samples(analitics: Dict[str, Any], start_dt: datetime) -> pd.DataFrame:
    logging.info("Processing samples array...")
    fields = [descriptor["pr"]["name"] for descriptor in analitics["descriptor"]]

    samples = []
    for sample in analitics["samples"]:
        dt = start_dt + timedelta(seconds=sample["t"])
        values = dict(zip(fields, sample["vs"]))
        values["datetime"] = dt
        values["interval"] = sample["t"]
        samples.append(values)

    df_samples = pd.DataFrame(samples)

    while not df_samples.empty:
        last_sample = df_samples.iloc[-1]
        if last_sample["Speed"] != 0 or last_sample["Power"] != 0:
            break
        df_samples = df_samples[:-1]

    return df_samples


def calculate_distances(df_samples: pd.DataFrame) -> pd.DataFrame:
    logging.info("Calculating smoothed distances...")
    # Distances in HDistance are very inaccurate.  Loading them to Strava will
    # lead to calculated speed having interchanging 0 and 72 km/h values only
    # and sawtooth graph for it.
    df_samples["SmoothDistance"] = df_samples["HDistance"].astype(float)
    dist = df_samples["HDistance"].iloc[0]

    for i in range(1, len(df_samples)):
        delta_time = (
            df_samples["datetime"].iloc[i] - df_samples["datetime"].iloc[i - 1]
        ).seconds
        dist += delta_time * df_samples["Speed"].iloc[i] / 3.6
        df_samples.at[i, "SmoothDistance"] = dist
        # print(df_samples.at[i, "HDistance"], df_samples.at[i, "SmoothDistance"])

    fact = df_samples["HDistance"].iloc[-1] / dist
    logging.info(f"- distance correction factor is {fact}")
    assert 0.94 < fact < 1.06

    dist = df_samples["HDistance"].iloc[0]
    df_samples["SmoothDistance"] = float(dist)

    for i in range(1, len(df_samples)):
        delta_time = (
            df_samples["datetime"].iloc[i] - df_samples["datetime"].iloc[i - 1]
        ).seconds
        dist += delta_time * df_samples["Speed"].iloc[i] / 3.6 * fact
        df_samples.at[i, "SmoothDistance"] = dist
        # print(df_samples.at[i, "HDistance"], df_samples.at[i, "SmoothDistance"])

    return df_samples


def interpolate_heart_rates(
    analitics: Dict[str, Any], df_samples: pd.DataFrame
) -> pd.DataFrame:
    logging.info("Interpolating heart rates...")
    hr_data = analitics["hr"]
    hr_times = [hr["t"] for hr in hr_data]
    hr_values = [hr["hr"] for hr in hr_data]

    interpolation_function = interp1d(hr_times, hr_values, fill_value="extrapolate")
    hr_intervals = np.arange(5, max(hr_times) + 1, 5)
    interpolated_heart_rates = interpolation_function(hr_intervals)
    interpolated_hr_data = {
        int(interval): int(hr)
        for interval, hr in zip(hr_intervals, interpolated_heart_rates)
    }

    df_samples["HeartRate"] = df_samples["interval"].map(interpolated_hr_data)
    df_samples["HeartRate"] = df_samples["HeartRate"].ffill()

    return df_samples


def calculate_metrics(df_samples: pd.DataFrame) -> Dict[str, Any]:
    logging.info("Calculating summary metrics...")
    total_time_seconds = (
        df_samples["interval"].iloc[-1] - df_samples["interval"].iloc[0]
    )
    total_distance_meters = df_samples["SmoothDistance"].iloc[-1]
    max_speed = df_samples["Speed"].max()
    avg_heart_rate_bpm = df_samples["HeartRate"].mean()
    max_heart_rate_bpm = df_samples["HeartRate"].max()

    return {
        "total_time_seconds": total_time_seconds,
        "total_distance_meters": total_distance_meters,
        "max_speed": max_speed,
        "avg_heart_rate_bpm": avg_heart_rate_bpm,
        "max_heart_rate_bpm": max_heart_rate_bpm,
    }


def create_tcx(
    df_samples: pd.DataFrame, metrics: Dict[str, Any], start_dt: datetime, out_file: str
):
    logging.info("Creating TCX XML file...")
    tcd = ET.Element("TrainingCenterDatabase", nsmap=TCD_NS_MAP)
    activities = ET.SubElement(tcd, "Activities")
    activity = ET.SubElement(activities, "Activity", Sport="Biking")
    ET.SubElement(activity, "Id").text = iso(start_dt)
    lap = ET.SubElement(activity, "Lap", StartTime=iso(start_dt))

    ET.SubElement(lap, "TotalTimeSeconds").text = str(metrics["total_time_seconds"])
    ET.SubElement(
        lap, "DistanceMeters"
    ).text = f"{metrics['total_distance_meters']:.1f}"
    ET.SubElement(lap, "MaximumSpeed").text = f"{metrics['max_speed']:.1f}"
    ET.SubElement(lap, "Calories").text = "0"
    avg_hr = ET.SubElement(lap, "AverageHeartRateBpm")
    ET.SubElement(avg_hr, "Value").text = f"{metrics['avg_heart_rate_bpm']:.0f}"
    max_hr = ET.SubElement(lap, "MaximumHeartRateBpm")
    ET.SubElement(max_hr, "Value").text = f"{metrics['max_heart_rate_bpm']:.0f}"
    ET.SubElement(lap, "Intensity").text = "Active"
    ET.SubElement(lap, "TriggerMethod").text = "Manual"

    track = ET.SubElement(lap, "Track")

    for _, sample in df_samples.iterrows():
        trackpoint = ET.SubElement(track, "Trackpoint")
        ET.SubElement(trackpoint, "Time").text = iso(sample["datetime"])
        ET.SubElement(trackpoint, "DistanceMeters").text = str(
            round(sample["SmoothDistance"], 1)
        )
        heart_rate_bpm = ET.SubElement(trackpoint, "HeartRateBpm")
        ET.SubElement(heart_rate_bpm, "Value").text = str(int(sample["HeartRate"]))
        ET.SubElement(trackpoint, "Cadence").text = str(sample["Rpm"])
        extensions = ET.SubElement(trackpoint, "Extensions")
        tpx = ET.SubElement(extensions, "TPX", nsmap=AX_NS)
        ET.SubElement(tpx, "Speed").text = str(round(sample["Speed"] / 3.6, 1))
        ET.SubElement(tpx, "Watts").text = str(sample["Power"])

    xml_str = ET.tostring(
        tcd, pretty_print=True, xml_declaration=True, encoding="utf-8"
    )
    with open(out_file, "wb") as f:
        f.write(xml_str)


def main():
    parser = argparse.ArgumentParser(description="Convert MyWellness JSON to TCX.")
    parser.add_argument("in_file", help="Input JSON file")
    parser.add_argument("start_dt", help="Start datetime in format YYYY-MM-DDTHH:MM")
    args = parser.parse_args()

    base_name = (
        args.in_file[:-5] if args.in_file.lower().endswith(".json") else args.in_file
    )
    out_file = base_name + ".tcx"

    start_dt = datetime.strptime(args.start_dt, "%Y-%m-%dT%H:%M")

    data = load_json(args.in_file)
    df_samples = process_samples(data["data"]["analitics"], start_dt)
    df_samples = calculate_distances(df_samples)
    df_samples = interpolate_heart_rates(data["data"]["analitics"], df_samples)
    metrics = calculate_metrics(df_samples)
    create_tcx(df_samples, metrics, start_dt, out_file)


if __name__ == "__main__":
    main()
