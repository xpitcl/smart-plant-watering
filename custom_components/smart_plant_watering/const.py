DOMAIN = "smart_plant_watering"
PLATFORMS = ["sensor"]

CONF_NAME = "name"
CONF_MOISTURE_ENTITY = "moisture_entity"

CONF_MODE = "mode"
MODE_DELTA = "delta"
MODE_THRESHOLD = "threshold"

CONF_MIN_DELTA = "min_delta"
CONF_DRY_THRESHOLD = "dry_threshold"
CONF_WET_THRESHOLD = "wet_threshold"
CONF_COOLDOWN_MINUTES = "cooldown_minutes"
CONF_CONFIRM_MINUTES = "confirm_minutes"

DEFAULT_MODE = MODE_DELTA
DEFAULT_MIN_DELTA = 5.0
DEFAULT_DRY_THRESHOLD = 0.0
DEFAULT_WET_THRESHOLD = 0.0
DEFAULT_COOLDOWN_MINUTES = 360
DEFAULT_CONFIRM_MINUTES = 0

ATTR_LAST_WATERING = "last_watering"
ATTR_MODE = "mode"
ATTR_MIN_DELTA = "min_delta"
ATTR_DRY_THRESHOLD = "dry_threshold"
ATTR_WET_THRESHOLD = "wet_threshold"
ATTR_COOLDOWN_MINUTES = "cooldown_minutes"
ATTR_CONFIRM_MINUTES = "confirm_minutes"
