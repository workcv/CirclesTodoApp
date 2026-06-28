[app]

# (str) Название вашего приложения на экране телефона
title = CirclesApp

# (str) Имя пакета (только маленькие латинские буквы, без символов)
package.name = circlesapp

# (str) Домен пакета
package.domain = org.circles

# (str) Где лежит ваш файл main.py (. означает текущий корень папки /content/)
source.dir = .

# (list) Расширения файлов, которые будут упакованы внутрь APK
source.include_exts = py,png,jpg,kv,atlas,cir

# (str) Версия вашего приложения
version = 0.1

# (list) Зависимости (только самое необходимое для интерфейса)
requirements = python3, kivy, android

# ИСПРАВЛЕНО: Полная поддержка любого поворота экрана на 360 градусов
orientation = all

# (bool) Полноэкранный режим (0 — показывать панель уведомлений сверху)
fullscreen = 0

# ==========================================
# Настройки для сборки под Android
# ==========================================

# (list) Разрешения разделены строго через запятую
android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE, INTERNET

# (int) Целевое Android API (актуальное для современных телефонов)
android.api = 33

# (int) Минимальная версия Android, которую поддерживает приложение
android.minapi = 24

# (str) Проверенная и стабильная версия NDK для API 33
android.ndk = 25b

# (list) Сборка только под одну архитектуру (arm64), чтобы Colab успел всё собрать
android.archs = arm64-v8a

# (bool) Автоматически принимать лицензии Android SDK при сборке
android.accept_sdk_license = True

# (bool) Включение поддержки AndroidX (необходимо для новых Gradle библиотек)
android.enable_androidx = True

[buildozer]
# Уровень логирования 2 (максимально подробный вывод всех этапов)
log_level = 2
