# Abismo de Sangre → APK con link de descarga + Google Play

## Qué hay en esta carpeta
| Archivo | Para qué |
|---|---|
| `main.py` | Tu juego (nombre obligatorio para Android) con 3 ajustes para APK |
| `buildozer.spec` | Configuración de la app (nombre, versión, API) |
| `.github/workflows/build.yml` | Compila el APK/AAB en la nube, gratis, sin necesitar Linux |
| `musica_de_fondo.mp3` | (opcional) pónla junto a main.py, **sin espacios en el nombre** |

## PASO 0 — Una sola vez: crear tu clave de firma
Sin una clave fija, cada versión tendría firma distinta y Android **no dejaría actualizar**.
```
keytool -genkey -v -keystore abismo.keystore -alias abismo -keyalg RSA -keysize 2048 -validity 10000
```
Guarda `abismo.keystore` y la contraseña en 2 lugares seguros. Si la pierdes, no podrás actualizar la app nunca más.

Conviértela a texto:  
Windows PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("abismo.keystore")) | Set-Clipboard`  
Linux/Mac: `base64 -w0 abismo.keystore`

## PASO 1 — Link de descarga del APK (GitHub, gratis)
1. Crea cuenta en github.com → **New repository** (puede ser privado si usas Play; público si quieres link abierto).
2. Sube el contenido de esta carpeta (incluida `.github`).
3. Repo → Settings → Secrets and variables → Actions → New secret:
   - `KEYSTORE_B64` = el texto del paso 0
   - `KEYSTORE_PASSWORD` = tu contraseña
4. Para publicar una versión: Releases → "Create a new release" → etiqueta `v1.0.0` → Publish.  
   (o `git tag v1.0.0 && git push --tags`)
5. En ~25-40 min (la primera vez) aparece en Releases `AbismoDeSangre.apk`. **Ese es tu link**:  
   `https://github.com/TU_USUARIO/TU_REPO/releases/latest/download/AbismoDeSangre.apk`  
   (siempre apunta a la última versión).

**Actualizar:** edita `main.py` → crea la etiqueta `v1.0.1` → el link se actualiza solo. Los jugadores descargan e instalan encima y **conservan su progreso** (misma firma + guardado en carpeta privada).

## PASO 2 — Google Play (instalación y actualización automática)
1. Cuenta de desarrollador: https://play.google.com/console (pago único de 25 USD, verificación de identidad).
2. Crear app → subir `AbismoDeSangre.aab` (Play ya no acepta APK para apps nuevas) a *Prueba cerrada*.
3. Rellenar: política de privacidad (URL), clasificación de contenido (es violento: responde con honestidad), capturas, icono 512×512, imagen 1024×500.
4. Las cuentas personales nuevas deben tener **12 testers durante 14 días** antes de pasar a Producción.
5. Después de publicar, cada `vX.Y.Z` nuevo → subes el nuevo `.aab` en Play Console y los usuarios se actualizan solos.
   Link final: `https://play.google.com/store/apps/details?id=com.tuusuario.abismodesangre`

## Probar antes de nada
Si la compilación falla, abre la pestaña **Actions** → el paso rojo → copia las últimas ~40 líneas del log y pásamelas.
