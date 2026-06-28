[app]
title = CirclesApp
package.name = circlesapp
package.domain = org.circles
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,cir
version = 0.1

requirements = python3, kivy, android
orientation = all
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE, INTERNET

android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.enable_androidx = True

[buildozer]
log_level = 2