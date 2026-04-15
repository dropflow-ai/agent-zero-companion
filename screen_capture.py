"""Screen capture utilities using mss for cross-platform screenshot support."""
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def capture_screen(
    monitor: int = 0,
    region: Optional[Tuple[int, int, int, int]] = None,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Capture a screenshot and save it to a file.

    Args:
        monitor: Monitor index (0 = all monitors combined, 1+ = specific monitor)
        region: Optional (left, top, width, height) tuple for partial capture
        output_path: Where to save the screenshot; uses temp file if None

    Returns:
        Path to the saved screenshot, or None on failure
    """
    try:
        import mss
        import mss.tools

        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".png", prefix="a0_screenshot_")
            os.close(fd)

        with mss.mss() as sct:
            if region:
                left, top, width, height = region
                mon = {"left": left, "top": top, "width": width, "height": height}
            elif monitor == 0:
                # Capture all monitors combined
                mon = sct.monitors[0]
            else:
                # Capture specific monitor
                idx = min(monitor, len(sct.monitors) - 1)
                mon = sct.monitors[idx]

            screenshot = sct.grab(mon)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)

        logger.info(f"Screenshot saved to {output_path}")
        return output_path

    except ImportError:
        logger.error("mss not installed. Run: pip install mss")
        return None
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return None


def capture_cursor_region(
    cursor_x: int,
    cursor_y: int,
    width: int = 800,
    height: int = 600,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Capture a region centered around the cursor position.

    Args:
        cursor_x: Cursor X position
        cursor_y: Cursor Y position
        width: Width of capture region
        height: Height of capture region
        output_path: Where to save the screenshot

    Returns:
        Path to the saved screenshot, or None on failure
    """
    left = max(0, cursor_x - width // 2)
    top = max(0, cursor_y - height // 2)
    return capture_screen(region=(left, top, width, height), output_path=output_path)


def get_monitor_count() -> int:
    """Return the number of available monitors."""
    try:
        import mss
        with mss.mss() as sct:
            return len(sct.monitors) - 1  # Subtract the 'all monitors' entry
    except Exception:
        return 1


def cleanup_screenshot(path: Optional[str]) -> None:
    """Remove a temporary screenshot file."""
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass
