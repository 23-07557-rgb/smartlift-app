[app]

# Title of your application
title = SmartLift

# Package name (no spaces, lowercase)
package.name = smartlift

# Package domain (reverse domain style, doesn't need to be a real domain)
package.domain = org.smartlift

# Source code where the main.py lives
source.dir = .

# Source files to include
source.include_exts = py,png,jpg,kv,atlas

# Application version
version = 1.0

# Application requirements — comma separated python modules
# pyjnius is required for the Android status bar color fix in main.py
# (it lets Python call native Android APIs). Without it, that fix
# silently no-ops and the status bar stays default black.
requirements = python3,kivy,requests,certifi,charset-normalizer,idna,urllib3,pyjnius

# Supported orientation: landscape, portrait, all
orientation = portrait

# (list) Permissions your app needs.
# INTERNET is required since this app fetches data from your Flask server.
android.permissions = INTERNET

# Android API levels to target/build against.
# These are reasonable, widely-compatible defaults as of 2026.
android.api = 33
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (bool) Indicate whether the screen should stay on
android.wakelock = False

# (list) The Android archs to build for.
# arm64-v8a covers virtually all modern Android phones.
android.archs = arm64-v8a

[buildozer]

# Log level: 0 = error only, 1 = info, 2 = debug
log_level = 2

# Display warning if running as root
warn_on_root = 1
