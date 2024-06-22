import logging
import yaml
import sys
import pathlib

# Load configuration from YAML file
path = pathlib.Path(__file__).parent.parent.absolute()
cfg = path / "etc" / "abhard.yml"
with open(cfg, 'r') as f:
    config = yaml.safe_load(f)

# Set up logging
logger = logging.getLogger('abhard')
log_format = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
file_handler = logging.FileHandler(config['log']['filename'])
file_handler.setFormatter(log_format)

if sys.stdin and sys.stdin.isatty() and 'unittest' not in sys.modules.keys():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
else:
    logger.addHandler(file_handler)

logger.setLevel(logging.INFO)
