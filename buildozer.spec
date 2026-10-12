[app]
title = Abismo de Sangre
package.name = abismodesangre
# CAMBIA "tuusuario" por tu nombre (no se puede cambiar tras publicar)
package.domain = com.tuusuario
source.dir = .
source.include_exts = py,png,jpg,mp3,ogg,wav,json
source.exclude_dirs = .github,bin,.buildozer
version = 1.0.0
requirements = python3,pygame
# icon.filename = %(source.dir)s/icono.png        # 512x512, descomenta cuando lo tengas
orientation = landscape
fullscreen = 1

# Sin permisos: el juego guarda solo en su almacenamiento privado
android.permissions =

# Play Store exige apuntar a un API reciente (revisa el requisito vigente al publicar)
android.api = 35
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
# el workflow sube este número solo en cada compilación
android.numeric_version = 1
# el workflow cambia a aab para Google Play
android.release_artifact = apk
android.debug_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
