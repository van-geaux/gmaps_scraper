"""Proxy configuration shared by remote Selenium and aiohttp."""

from __future__ import annotations

from urllib.parse import quote


def disable_unconfigured_proxy(config: dict) -> dict:
    """Disable optional proxy settings when no upstream proxy is configured."""
    proxy = config.get("Proxy") or {}
    required = ("Scheme", "Host", "Port")
    if proxy.get("Enabled") is True and any(not proxy.get(key) for key in required):
        proxy["Enabled"] = False
        browser_proxy = config.get("Browser_proxy")
        if isinstance(browser_proxy, dict):
            browser_proxy["Enabled"] = False
    return config


def _proxy(config: dict) -> dict:
    proxy = config.get("Proxy") or {}
    if proxy.get("Enabled") is not True:
        return {}
    required = ("Scheme", "Host", "Port")
    missing = [key for key in required if not proxy.get(key)]
    if missing:
        raise ValueError(f"Proxy is enabled but missing: {', '.join(missing)}")
    return proxy


def proxy_server(config: dict) -> str | None:
    proxy = _proxy(config)
    if not proxy:
        return None
    return f"{proxy['Scheme']}://{proxy['Host']}:{proxy['Port']}"


def selenium_proxy_server(config: dict) -> str | None:
    proxy = config.get("Browser_proxy") or _proxy(config)
    if not proxy:
        return None
    if proxy.get("Enabled") is not True:
        return None
    required = ("Scheme", "Host", "Port")
    missing = [key for key in required if not proxy.get(key)]
    if missing:
        raise ValueError(f"Browser proxy is enabled but missing: {', '.join(missing)}")
    return f"{proxy['Host']}:{proxy['Port']}"


def aiohttp_proxy(config: dict) -> str | None:
    proxy = _proxy(config)
    if not proxy:
        return None
    user = proxy.get("User")
    password = proxy.get("Password")
    credentials = ""
    if user or password:
        if not user or not password:
            raise ValueError("Authenticated proxy requires both User and Password")
        credentials = f"{quote(str(user), safe='')}:{quote(str(password), safe='')}@"
    return f"{proxy['Scheme']}://{credentials}{proxy['Host']}:{proxy['Port']}"


def configure_selenium(options, config: dict) -> None:
    """Route Chrome through the unauthenticated local proxy gateway."""
    proxy = _proxy(config)
    server = selenium_proxy_server(config)
    if server:
        browser_proxy = config.get("Browser_proxy") or proxy
        options.add_argument(f"--proxy-server={browser_proxy['Scheme']}://{server}")
        options.add_argument("--proxy-bypass-list=localhost;127.0.0.1")
        options.add_argument("--disable-quic")

        from selenium.webdriver.common.proxy import Proxy

        options.proxy = Proxy(
            {
                "proxyType": "manual",
                "httpProxy": server,
                "sslProxy": server,
            }
        )
