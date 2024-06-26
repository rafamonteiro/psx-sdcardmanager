#!/usr/bin/env python3
# Example usage:
# try:
#     serial = get_serial('path_to_your_psx_bin_file')
#     print(f'Serial: {serial}')
# except Exception as e:
#     print(f'Error: {e}')

from fileinput import filename
import re

serial_regex = re.compile(r'((SLPS|SLES|SLUS|SCPS|SCUS|SCES|SIPS|SLPM|SLEH|SLED|SCED|ESPM|PBPX|LSP|DTL|PUPX|PEPX)[_P\-])|(LSP9|907127)')
serial_code_dot_position = 8
serial_code_length = 11
buffer_size = 1024 * 1024

class SerialNotFoundError(Exception):
    pass

serial_exceptions = {
    "SLUSP": "SLUS_",
    "LSP9": "LSP_9",
    "907127": "LSP_907127",
}

def get_serial(filepath):
    try:
        with open(filepath, 'rb') as file:
            while True:
                buffer = file.read(buffer_size)
                if not buffer:
                    break
                serial = find_serial(buffer.decode(errors='ignore'))
                if serial:
                    serial = normalize_serial(serial)
                    return serial
    except FileNotFoundError as e:
        raise e
    raise SerialNotFoundError("Serial not found for file: $filename")

def find_serial(s):
    match = serial_regex.search(s)
    if match:
        start = match.start()
        return s[start:start + serial_code_length]
    return ""

def normalize_serial(s):
    s = s.replace(".", "", 1).replace("-", "_", 1).replace("-", "", 1)
    for key, value in serial_exceptions.items():
        if key in s:
            s = s.replace(key, value, 1)
    return s[:serial_code_dot_position] + "." + s[serial_code_dot_position:serial_code_length-1]


