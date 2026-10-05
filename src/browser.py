"""Remote Selenium driver factory."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from src.logger import logger
from src.proxy import configure_selenium


def get_driver(config):
    """Connect to the Selenium server configured in Browser_remote_url."""
    remote_url = config.get("Browser_remote_url")
    if not remote_url:
        raise ValueError("Browser_remote_url must be set for remote Selenium")

    options = Options()
    options.page_load_strategy = "eager"
    if config.get("Headless") is None or config.get("Headless") is True:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    configure_selenium(options, config)

    logger.info("Connecting to remote Selenium at %s", remote_url)
    return webdriver.Remote(command_executor=remote_url, options=options)