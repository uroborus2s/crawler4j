import random
from typing import Any


class FingerprintGenerator:
    """Generates random browser fingerprint configurations."""

    OS_VERSIONS = {
        "Windows": ["Windows 10", "Windows 11"],
        "macOS": ["macOS 13", "macOS 14", "macOS 15"],
    }

    PLATFORMS = {
        "Windows": "Win32",
        "macOS": "MacIntel",
    }

    USER_AGENTS = {
        "Windows": [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36 Edg/{version}.0.0.0"
            ),
        ],
        "macOS": [
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
            ),
        ],
    }

    CHROME_VERSIONS = [120, 121, 122, 123, 124, 125, 126]

    RESOLUTIONS = [
        "1920x1080",
        "1366x768",
        "1440x900",
        "1536x864",
        "2560x1440",
    ]

    @classmethod
    def generate(cls, os_type: str = "Windows") -> dict[str, Any]:
        """Generate a random fingerprint configuration.

        Args:
            os_type: "Windows" or "macOS"

        Returns:
            Dict containing fingerprint parameters.
        """
        # Select version
        chrome_version = random.choice(cls.CHROME_VERSIONS)

        # Select OS Version (for display/metadata, though often implicit in UA)
        os_ver = random.choice(cls.OS_VERSIONS.get(os_type, ["Unknown"]))

        # Generate UA
        ua_template = random.choice(
            cls.USER_AGENTS.get(os_type, cls.USER_AGENTS["Windows"])
        )
        ua = ua_template.format(version=chrome_version)

        # Resolution
        res = random.choice(cls.RESOLUTIONS)

        return {
            "os": os_type,
            "os_version": os_ver,
            "browser_version": str(chrome_version),
            "user_agent": ua,
            "resolution": res,
            "platform": cls.PLATFORMS.get(os_type, "Win32"),
            "language": "zh-CN,zh;q=0.9,en;q=0.8",
            "hardware_concurrency": random.choice([4, 8, 12, 16]),
            "device_memory": random.choice([4, 8, 16, 32]),
        }
