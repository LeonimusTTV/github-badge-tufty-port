import sys

badge.poll()

# The System app's C button toggles this and persists it via State (same
# "system" store System uses for its timezone) - read it back here to decide
# whether to play the boot cinematic.
_system_config = {"startup_enabled": True}
try:
    State.load("system", _system_config)
except (OSError, ValueError):
    pass
SKIP_CINEMATIC = not bool(_system_config.get("startup_enabled", True))
del _system_config

if not SKIP_CINEMATIC:
    startup = launch("/system/apps/startup")

    if startup is not None:
        launch(startup)

    if sys.path[0].startswith("/system/apps"):
        sys.path.pop(0)

    del startup

app_to_launch = launch("/system/apps/menu")

# Stopping in Thonny can cause launch("/system/apps/menu") to return None
if app_to_launch is not None:

    # Don't pass menu button presses into the newly launched app
    while badge.pressed() or badge.held() or badge.released():
        badge.poll()

    launch(app_to_launch)

# Catch any exit and reset back to the launcher
reset()
