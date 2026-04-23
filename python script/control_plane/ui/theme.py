APP_TITLE = "Cascadya control plane"
APP_GEOMETRY = "1460x980"
MIN_WINDOW_SIZE = (1180, 780)

BG = "#050505"
PANEL = "#2f2d29"
PANEL_ALT = "#101010"
BORDER = "#5a5850"
TEXT = "#f4f1e8"
MUTED = "#b7b0a4"
MUTED_2 = "#8d877b"
BLUE = "#8cb4e6"
BLUE_DEEP = "#304e73"
GREEN = "#82cf54"
GREEN_BG = "#214d17"
AMBER = "#d3ab43"
AMBER_BG = "#6d5614"
GRAY_BG = "#323232"
GRAY_FG = "#a8a8a8"
RED = "#ff9f95"
RED_BG = "#612626"
WHITE_LINE = "#e0d7c9"
LOG_BG = "#262520"

STATUS_STYLES = {
    "active": ("#214d17", "#82cf54"),
    "healthy": ("#214d17", "#82cf54"),
    "provisioning": ("#6d5614", "#d3ab43"),
    "degraded": ("#6d5614", "#d3ab43"),
    "waiting": ("#323232", "#a8a8a8"),
    "pending": ("#323232", "#a8a8a8"),
    "pass": ("#214d17", "#82cf54"),
    "slow": ("#6d5614", "#d3ab43"),
    "failed": ("#612626", "#ff9f95"),
    "running": ("#304e73", "#8cb4e6"),
    "done": ("#214d17", "#82cf54"),
    "will wait": ("#6d5614", "#d3ab43"),
    "awaiting reboot": ("#6d5614", "#d3ab43"),
    "ready": ("#323232", "#c6ccd6"),
}
