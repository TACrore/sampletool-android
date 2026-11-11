[app]
title = 样品查询管理工具
package.name = sampletool
package.domain = cn.wzshenyi
version = 1.3.5
icon.filename = icon.png
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
source.exclude_dirs = bin,.buildozer,__pycache__,data,.github

requirements = python3,kivy==2.3.1,certifi

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,REQUEST_INSTALL_PACKAGES
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a
android.allow_backup = True
android.add_assets = sy-cjk.ttf,feishu.json
android.accept_sdk_license = True
p4a.source_dir = /home/runner/p4a

[buildozer]
log_level = 2
warn_on_root = 1
