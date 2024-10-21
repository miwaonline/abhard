import logging
import yaml
import sys
from pathlib import Path


version = "3.0.0.18"


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
