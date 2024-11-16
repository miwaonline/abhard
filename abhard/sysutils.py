import logging
import yaml
import sys
from pathlib import Path


version = "3.0.0.21"


# Load configuration from YAML file
path = Path(__file__).parent.parent.absolute()
cfg = path / "etc" / "abhard.yml"
with open(cfg, "r") as f:
    config = yaml.safe_load(f)

# Set up logging
log_format = logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
Path(config["log"]["path"]).mkdir(parents=True, exist_ok=True)

# Set up main logger
main_logger = logging.getLogger("abhard")
main_file_handler = logging.FileHandler(
    Path(config["log"]["path"]) / "abhard.log"
)
main_file_handler.setFormatter(log_format)
main_logger.setLevel(logging.INFO)

# Set up scaner logger
scan_logger = logging.getLogger("scaner")
scan_file_handler = logging.FileHandler(
    Path(config["log"]["path"]) / "scaner.log"
)
scan_file_handler.setFormatter(log_format)
scan_logger.setLevel(logging.INFO)

# Set up rro logger
prro_logger = logging.getLogger("rro")
prro_file_handler = logging.FileHandler(
    Path(config["log"]["path"]) / "prro.log"
)
prro_file_handler.setFormatter(log_format)
prro_logger.setLevel(logging.INFO)

# Set up printer logger
prnt_logger = logging.getLogger("printer")
prnt_file_handler = logging.FileHandler(
    Path(config["log"]["path"]) / "printer.log"
)
prnt_file_handler.setFormatter(log_format)
prnt_logger.setLevel(logging.INFO)

# Set up logging
if sys.stdin and sys.stdin.isatty() and "unittest" not in sys.modules.keys():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    main_logger.addHandler(console_handler)
    prro_logger.addHandler(console_handler)
    scan_logger.addHandler(console_handler)
    prnt_logger.addHandler(console_handler)
    main_logger.propagate = False
    prro_logger.propagate = False
    scan_logger.propagate = False
    prnt_logger.propagate = False
else:
    main_logger.addHandler(main_file_handler)
    prro_logger.addHandler(prro_file_handler)
    scan_logger.addHandler(scan_file_handler)
    prnt_logger.addHandler(prnt_file_handler)


def make_code128(data: str) -> str:
    # Code 128 character set value table
    code128_values = {
        ' ': 0, '!': 1, '"': 2, '#': 3, '$': 4, '%': 5, '&': 6, "'": 7,
        '(': 8, ')': 9, '*': 10, '+': 11, ',': 12, '-': 13, '.': 14, '/': 15,
        '0': 16, '1': 17, '2': 18, '3': 19, '4': 20, '5': 21, '6': 22, '7': 23,
        '8': 24, '9': 25, ':': 26, ';': 27, '<': 28, '=': 29, '>': 30, '?': 31,
        '@': 32, 'A': 33, 'B': 34, 'C': 35, 'D': 36, 'E': 37, 'F': 38, 'G': 39,
        'H': 40, 'I': 41, 'J': 42, 'K': 43, 'L': 44, 'M': 45, 'N': 46, 'O': 47,
        'P': 48, 'Q': 49, 'R': 50, 'S': 51, 'T': 52, 'U': 53, 'V': 54, 'W': 55,
        'X': 56, 'Y': 57, 'Z': 58, '[': 59, '\\': 60, ']': 61, '^': 62,
        '_': 63, '`': 64, 'a': 65, 'b': 66, 'c': 67, 'd': 68, 'e': 69, 'f': 70,
        'g': 71, 'h': 72, 'i': 73, 'j': 74, 'k': 75, 'l': 76, 'm': 77, 'n': 78,
        'o': 79, 'p': 80, 'q': 81, 'r': 82, 's': 83, 't': 84, 'u': 85, 'v': 86,
        'w': 87, 'x': 88, 'y': 89, 'z': 90, '{': 91, '|': 92, '}': 93, '~': 94,
        'DEL': 95, 'FNC3': 96, 'FNC2': 97, 'SHIFT': 98, 'Code C': 99,
        'FNC4': 100, 'FNC1': 101, 'START A': 103, 'START B': 104, 'START C': 105
    }
    start_value = 104  # Assuming START B is used as in the escpos library
    start_chars = '{B'
    checksum = start_value
    for i, char in enumerate(data):
        value = code128_values[char]
        weight = i + 1
        checksum += value * weight
    checksum = checksum % 103
    checksum_char = [k for k, v in code128_values.items() if v == checksum][0]
    return start_chars + data + checksum_char
