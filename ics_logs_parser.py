#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import csv
import re
import argparse
import string
from datetime import datetime, timezone

def load_message_map(mapping_csv_path: str) -> dict:
    """
    Reads a CSV file mapping message codes to their type and description.
    The CSV is expected to contain exactly three columns:
      1. MessageCode
      2. MessageType
      3. Description

    Returns a dictionary of the form:
      {
        "ADM23247": ("AdminChange", "addServer"),
        ...
      }
    """
    message_map = {}
    try:
        with open(mapping_csv_path, mode="r", encoding="utf-8") as map_file:
            reader = csv.reader(map_file)
            for row in reader:
                # Ensure each line has exactly three columns
                if len(row) != 3:
                    continue

                code = row[0].strip()
                msg_type = row[1].strip()
                desc = row[2].strip()

                if code:
                    message_map[code] = (msg_type, desc)

    except OSError as e:
        print(f"Error opening or reading the message map file '{mapping_csv_path}': {e}")

    return message_map

def replace_and_clean_line(line: str) -> str:
    """
    Performs replacements on the input line to remove or transform non-printing characters,
    returning a cleaned string. Specifically:
      - Certain control characters (e.g., STX, SOH) are replaced with '\n'.
      - The bell character '\x07' is replaced with a space.
      - Other non-printing control characters are removed.
      - Any remaining unprintable characters are replaced with '?'.
    """
    # Replace STX, SOH, etc. with newline
    line = re.sub(r'[\x17\x15\x13\x12\x05\x04\x03\x02\x01\x00]', '\n', line)

    # Replace the bell character with a space
    line = re.sub(r'[\x07]', ' ', line)

    # Remove other unwanted control characters
    line = re.sub(r'[\x0B\x1C\x0F\x06\x1E\x08\x10\x1D\x0E\x11\x14\x16\x17\x18\x19\x1F\x7F\x1A\x1B\x0C\uFFFD]', '', line)

    # Replace remaining unprintable chars with '?'
    printable = set(string.printable)
    return ''.join(char if char in printable else '?' for char in line)

def process_subline(subline: str, message_map: dict) -> list:
    """
    Splits a sub-line into CSV columns, extracting:
      - Hex timestamp as columns[0]
      - Hex line ID as columns[1]
      - Potential message code from columns[3]
    Looks up the message code in 'message_map' to fill in columns[4] (MsgType) and [5] (Description).

    Returns a list of columns if successful, or None if the sub-line is invalid.
    """
    # Convert tabs to commas, then split
    subline = subline.replace("\t", ",")
    columns = subline.split(",")

    # Handle cases where the last column may be a single extra character
    if len(columns[-1]) == 1:
        columns[-1] = ""

    # Check if the first column is valid and contains a "."
    # Example: <hexTimestamp>.<hexLineID>
    if len(columns) < 1 or "." not in columns[0]:
        return None

    first_col = columns[0].split(".", 1)
    if len(first_col) < 2:
        return None

    raw_hex_timestamp, hex_line_id = first_col[0], first_col[1]

    # Ensure there's at least a columns[3] for the message code
    if len(columns) < 4:
        return None

    code = columns[3].strip()

    # Convert from hex epoch timestamp
    try:
        epoch_int = int(raw_hex_timestamp, 16)
        dt_obj = datetime.fromtimestamp(epoch_int, tz=timezone.utc)
        dt_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        dt_str = raw_hex_timestamp  # fallback if parsing fails

    # Prepend the parsed timestamp and hex line ID
    columns[0] = dt_str
    columns.insert(1, hex_line_id)

    # Map message code to message type and description if available
    msg_type, msg_desc = '', ''
    if code in message_map:
        msg_type, msg_desc = message_map[code]

    # Ensure columns[4] is 'Msg Description' and columns[5] is 'Msg Category'
    while len(columns) < 6:
        columns.append('')

    columns[4] = msg_type
    columns[5] = msg_desc

    return columns

def get_vc0_content(vc0_path: str, message_map: dict) -> list:
    """
    Reads and processes a .vc0 file starting from byte offset 8192.
    Decodes lines, cleans them, and splits any inserted newlines to sub-lines.
    Each valid sub-line is converted to columns via 'process_subline()'.

    Returns a list of processed rows suitable for CSV output.
    """
    rows = []
    try:
        with open(vc0_path, "rb") as f_in:
            # Skip the first 8192 bytes
            f_in.seek(8192)

            for raw_line in f_in:
                try:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                except UnicodeDecodeError as e:
                    print(f"Error decoding line from '{vc0_path}': {e}")
                    continue

                line = replace_and_clean_line(line)

                # If a single line contained certain control chars replaced by '\n'
                # we split it into separate sub-lines
                sub_lines = line.split('\n')
                for sub in sub_lines:
                    sub = sub.strip()
                    if len(sub) < 3:
                        # Skip short or empty sub-lines
                        continue

                    row = process_subline(sub, message_map)
                    if row:
                        rows.append(row)
    except OSError as e:
        print(f"Failed to open or read the file '{vc0_path}': {e}")
    return rows

def main():
    print(
    """

    ██▓ ▄████▄    ██████     ██▓     ▒█████    ▄████   ██████     ██▓███   ▄▄▄       ██▀███    ██████ ▓█████  ██▀███  
    ▓██▒▒██▀ ▀█  ▒██    ▒    ▓██▒    ▒██▒  ██▒ ██▒ ▀█▒▒██    ▒    ▓██░  ██▒▒████▄    ▓██ ▒ ██▒▒██    ▒ ▓█   ▀ ▓██ ▒ ██▒
    ▒██▒▒▓█    ▄ ░ ▓██▄      ▒██░    ▒██░  ██▒▒██░▄▄▄░░ ▓██▄      ▓██░ ██▓▒▒██  ▀█▄  ▓██ ░▄█ ▒░ ▓██▄   ▒███   ▓██ ░▄█ ▒
    ░██░▒▓▓▄ ▄██▒  ▒   ██▒   ▒██░    ▒██   ██░░▓█  ██▓  ▒   ██▒   ▒██▄█▓▒ ▒░██▄▄▄▄██ ▒██▀▀█▄    ▒   ██▒▒▓█  ▄ ▒██▀▀█▄  
    ░██░▒ ▓███▀ ░▒██████▒▒   ░██████▒░ ████▓▒░░▒▓███▀▒▒██████▒▒   ▒██▒ ░  ░ ▓█   ▓██▒░██▓ ▒██▒▒██████▒▒░▒████▒░██▓ ▒██▒
    ░▓  ░ ░▒ ▒  ░▒ ▒▓▒ ▒ ░   ░ ▒░▓  ░░ ▒░▒░▒░  ░▒   ▒ ▒ ▒▓▒ ▒ ░   ▒▓▒░ ░  ░ ▒▒   ▓▒█░░ ▒▓ ░▒▓░▒ ▒▓▒ ▒ ░░░ ▒░ ░░ ▒▓ ░▒▓░
    ▒ ░  ░  ▒   ░ ░▒  ░ ░   ░ ░ ▒  ░  ░ ▒ ▒░   ░   ░ ░ ░▒  ░ ░   ░▒ ░       ▒   ▒▒ ░  ░▒ ░ ▒░░ ░▒  ░ ░ ░ ░  ░  ░▒ ░ ▒░
    ▒ ░░        ░  ░  ░       ░ ░   ░ ░ ░ ▒  ░ ░   ░ ░  ░  ░     ░░         ░   ▒     ░░   ░ ░  ░  ░     ░     ░░   ░ 
    ░  ░ ░            ░         ░  ░    ░ ░        ░       ░                    ░  ░   ░           ░     ░  ░   ░     
        ░                                                                                                              

    """)

    print("\nICS Logs Parser v0.1 - by Maurice Fielenbach (grimlockx) - Hexastrike Cybersecurity UG (haftungsbeschränkt)\n")

    parser = argparse.ArgumentParser(description="Process .vc0 files and convert them to .csv files.")
    parser.add_argument("--input", required=True, help="Directory containing .vc0 files")
    parser.add_argument("--output", required=True, help="Directory to save .csv files")
    parser.add_argument("--mapfile", required=True, help="CSV file mapping [MessageCode, MessageType, Description]")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output
    map_file = args.mapfile

    # Load the mapping from message code to message type and description
    message_map = load_message_map(map_file)

    # Validate input directory
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    # Ensure the output directory exists or create it
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    # Identify all .vc0 files (ignoring lock files)
    vc0_files = [f for f in os.listdir(input_dir)
                 if f.endswith(".vc0") and not f.startswith("lck.")]

    if not vc0_files:
        print(f"No .vc0 files found in '{input_dir}'.")
        sys.exit(0)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    for vc0_file in vc0_files:
        vc0_path = os.path.join(input_dir, vc0_file)

        # Skip if the file is exactly 8192 bytes (often indicating an empty .vc0)
        if os.path.getsize(vc0_path) == 8192:
            print(f"Skipping '{vc0_file}': file is empty (8192 bytes).")
            continue

        # Construct output CSV path
        csv_filename = f"{timestamp_str}_{vc0_file}.csv"
        output_path = os.path.join(output_dir, csv_filename)

        # Process the .vc0 file
        rows = get_vc0_content(vc0_path, message_map)

        # Write the resulting rows to a CSV
        with open(output_path, "w", newline="", encoding="utf-8") as csv_out:
            csv_writer = csv.writer(csv_out, delimiter=",", lineterminator="\n")

            # Example header row
            csv_writer.writerow([
                'Timestamp',
                'Line ID',
                'Device Hostname',
                'Msg Code',
                'Msg Description',
                'Msg Category',
                'Log Source Type',
                'Device Network',
                'Source IP',
                'Msg Data 10',
                'Msg Data 11',
                'Msg Data 12',
                'Msg Data 13',
                'Msg Data 14',
                'Msg Data 15',
                'Msg Data 16',
                'Msg Data 17',
                'Msg Data 18',
                'Msg Data 19',
                'Msg Data 20',
                'Msg Data 21',
                'Msg Data 22',
                'Msg Data 23',
                'Msg Data 24',
                'Msg Data 25',
                'Msg Data 26',
                'Msg Data 27',
                'Msg Data 28',
                'Msg Data 29',
                'Msg Data 30'
            ])

            for row in rows:
                csv_writer.writerow(row)

        print(f"Processed and wrote CSV: {output_path}")

if __name__ == "__main__":
    main()
