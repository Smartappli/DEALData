"""Django settings for the sensor service."""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dealdata_common.django_settings import configure_service_settings

configure_service_settings(
    globals(),
    base_dir=BASE_DIR,
    project_module="sensor",
    app_config="sensor_data.apps.SensorDataConfig",
    database_name="dealdata_sensor",
    include_wsgi=False,
)
