from dotenv import load_dotenv

from src.input import input_worker
from src.logger import logger
from src.proxy import disable_unconfigured_proxy

import argparse
import os
import psutil
import re
import sys
import signal
import yaml

def terminate_subprocesses():
    current_process = psutil.Process()
    for child in current_process.children(recursive=True):
        child.terminate()
    _, still_alive = psutil.wait_procs(current_process.children(recursive=True), timeout=5)
    for child in still_alive:
        child.kill()

def signal_handler(sig, frame):
    print("\nSignal received, terminating subprocesses, waiting to finish last query processed...")
    terminate_subprocesses()
    sys.exit(0)

def env_var_constructor(loader, node):
    value = loader.construct_scalar(node)
    pattern = re.compile(r'\$\{(\w+)\}')
    match = pattern.findall(value)
    for var in match:
        value = value.replace(f'${{{var}}}', os.getenv(var, ''))
    return value

def main():
    parser = argparse.ArgumentParser(description="Scrape Google Maps queries from a CSV file.")
    parser.add_argument(
        "--csvinput",
        required=True,
        help="Path to a CSV file containing a required query column.",
    )
    args = parser.parse_args()

    load_dotenv()
    yaml.SafeLoader.add_constructor('!env_var', env_var_constructor)

    config = {}
    try:
        with open('config.yml', 'r') as file:
            config_content = file.read()
            config_content = re.sub(r'\$\{(\w+)\}', lambda match: os.getenv(match.group(1), ''), config_content)
            config = disable_unconfigured_proxy(yaml.safe_load(config_content) or {})
            if not config.get("Proxy", {}).get("Enabled", False):
                logger.info("No complete proxy configuration found; running without proxy")
    except Exception as e:
        logger.debug(f'Failed opening configuration file: {e}')

    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        input_worker(config, args.csvinput)

    except KeyboardInterrupt:
        logger.info('Script stopped manually.')
    except Exception:
        logger.exception('Scraper failed.')
        raise
    finally:
        logger.info('Cleaning processes...')
        terminate_subprocesses()

if __name__ == "__main__":    
    main()