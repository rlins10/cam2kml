# cam2kml

[English](README.md) · [Português](README.pt-BR.md) · **Español**

Convierte carpetas de fotos con geoetiquetas en **archivos KMZ de Google Earth**. Cada foto se convierte en un punto del mapa, en el lugar donde fue tomada, con un globo que muestra la imagen, la cámara, la fecha y el tamaño. Cada álbum recibe su propio KMZ, y un `index.kml` enlaza todos ellos para abrir la colección completa desde un único archivo.

Fue pensado para colecciones grandes (decenas de miles de fotos en miles de carpetas) servidas por un servidor web sencillo, pero también funciona con pocas carpetas.

## Características

- Lee GPS, fecha, cámara y tamaño de los datos EXIF de archivos `.jpg`, `.jpeg` y `.png`.
- Un KMZ por álbum, guardado en una carpeta de salida aparte, nunca dentro de las carpetas de fotos.
- `index.kml` con un enlace de red por álbum (todos sin marcar, así que no se carga nada hasta que usted los marque).
- Estilo de globo e icono personalizados, tomados de una carpeta de recursos que se empaqueta dentro de cada KMZ.
- Las fotos sin GPS pueden heredar la posición de la foto anterior, usar una posición fija u omitirse.
- Las carpetas sin fotos no generan nada y no tocan el índice.
- Las imágenes muy grandes (panorámicas de más de 100 megapíxeles) se procesan sin advertencias.
- Los álbumes con el mismo nombre de carpeta en lugares distintos nunca se sobrescriben (`Samsung SM-G935F/Camera` y `Samsung SM-P205/Camera` pasan a ser `Samsung SM-G935F - Camera.kmz` y `Samsung SM-P205 - Camera.kmz`).

## Requisitos

- Python 3.9 o superior.
- [ExifRead](https://pypi.org/project/ExifRead/), [simplekml](https://pypi.org/project/simplekml/) y [Pillow](https://pypi.org/project/pillow/) (se instalan automáticamente).
- Google Earth Pro (escritorio) para ver el resultado. Otros clientes pueden mostrar los globos de forma diferente.

## Instalación

Cambie `YOUR-USER` por la cuenta de GitHub que aloja el repositorio.

```bash
# Recomendado: herramienta de línea de comandos aislada
pipx install "git+https://github.com/YOUR-USER/cam2kml.git"

# O con uv
uv tool install "git+https://github.com/YOUR-USER/cam2kml.git"

# O en el entorno virtual actual
pip install "git+https://github.com/YOUR-USER/cam2kml.git"

# Una versión concreta (etiqueta) o una rama
pip install "git+https://github.com/YOUR-USER/cam2kml.git@v0.2.2"
```

Para actualizar, use `pipx upgrade cam2kml` o repita el comando `pip install` con `--upgrade`. Para desinstalar, `pipx uninstall cam2kml` o `pip uninstall cam2kml`.

En Debian/Ubuntu y otros sistemas donde `pip` se niega a instalar en el sistema ("externally-managed-environment"), use `pipx` o un entorno virtual (`python3 -m venv ~/myenv && . ~/myenv/bin/activate`).

Desde un clon, para desarrollo:

```bash
git clone https://github.com/YOUR-USER/cam2kml.git
cd cam2kml
pip install -e .
```

También puede ejecutar el script sin instalarlo: `pip install exifread simplekml pillow` y luego `python3 cam2kml.py CARPETA`. Una vez instalado, funcionan `cam2kml --version` y `python3 -m cam2kml --version`.

## Inicio rápido

1. **Cree la configuración.** La primera ejecución crea `~/.config/cam2kml/config.ini` con valores predeterminados. Edítelo (vea [Configuración](#configuración)) o créelo a mano.
2. **Prepare la carpeta de recursos** (`pasta_recursos`): ponga en ella el KML de estilo y los iconos (vea [Estilo y recursos](#estilo-y-recursos)).
3. **Sirva sus fotos** con cualquier servidor web cuya raíz sea la carpeta raíz de las fotos, por ejemplo:
   ```bash
   cd /data/photosync && python3 -m http.server 8080
   ```
4. **Genere el KMZ** de un álbum:
   ```bash
   cam2kml "/data/photosync/Samsung SM-G935F/Camera"
   ```
   Esto crea `<pasta_saida>/Samsung SM-G935F - Camera.kmz` y actualiza `<pasta_saida>/index.kml`.
5. **Ábralo en Google Earth**: abra el KMZ directamente, o abra el índice mediante un enlace de red (por ejemplo `http://localhost:8080/output_kmz/index.kml`, cuando `pasta_saida` está dentro de la carpeta servida).

## Cómo se usan las carpetas

```
/data/photosync/                 <- raíz ("raiz"): las URL y los nombres de álbum son relativos a ella
├── recursos/                    <- pasta_recursos: estilo + iconos, copiados a cada KMZ
│   ├── estilos03.kml
│   └── camera.png
├── output_kmz/                  <- pasta_saida: KMZ generados e index.kml
│   ├── index.kml
│   ├── Samsung SM-G935F - Camera.kmz
│   └── Viaje X - Samsung SM-G990E - Camera.kmz
├── Samsung SM-G935F/
│   └── Camera/                  <- álbum: las fotos están directamente aquí
│       ├── 20230907_115442.jpg
│       └── ruta.kml             <- opcional: se convierte en un punto con enlace
└── Viaje X/
    └── Samsung SM-G990E/
        └── Camera/
```

| Carpeta | Función |
|---|---|
| **Álbum** (la `CARPETA` que usted indica) | Contiene las fotos. Solo se leen los archivos que están directamente dentro; las subcarpetas **no** se recorren. Los archivos `*.kml` o `*.kmz` que haya dentro se convierten en puntos con un enlace al archivo. |
| **Raíz** (`--raiz`) | La carpeta que corresponde a la raíz del servidor web (o a la carpeta base del modo `file`). Por defecto es la carpeta superior más cercana llamada `photosync`; si no existe, el propio álbum. La URL de una foto se construye con su ruta relativa a la raíz. |
| **`pasta_saida`** | Donde se guardan `<álbum>.kmz` e `index.kml`. Puede estar en cualquier lugar, incluso dentro de la raíz. Si se deja vacía, se guarda un `<carpeta>.kml` simple dentro de la carpeta del álbum (sin KMZ, sin índice y sin recursos). |
| **`pasta_recursos`** | Todo lo que contiene va a la raíz de cada KMZ (el KML de estilo y los iconos). Se ignoran los archivos ocultos, los archivos `*.kmz` y un archivo llamado `doc.kml`, y puede tener como máximo 500 archivos (una protección contra apuntarla por error a una carpeta de fotos). |

**Nombre del álbum.** Es la ruta del álbum relativa a la raíz, unida con ` - `. `photosync/sample01` da `sample01`, y `photosync/Viaje X/Samsung SM-G990E/Camera` da `Viaje X - Samsung SM-G990E - Camera`. El nombre se usa para el archivo KMZ, para el nombre del documento que se muestra en Google Earth y para la entrada del índice. Si el álbum está fuera de la raíz (o es la propia raíz), se usa solo el nombre de la carpeta.

## Configuración

Archivo: `~/.config/cam2kml/config.ini` (en Windows: `%USERPROFILE%\.config\cam2kml\config.ini`), sección `[geral]`. Las claves que falten usan los valores predeterminados de abajo.

```ini
[geral]
metodo_protocolo = http
servidor_host = localhost:8080
pasta_raiz = /
pasta_saida = /data/photosync/output_kmz
pasta_recursos = /data/photosync/recursos
estilo_url = estilos03.kml#estiloCustomizado
icone_kml = globe-connected.png
```

| Clave | Predeterminado | Significado |
|---|---|---|
| `metodo_protocolo` | `http` | `http`, `https` o `file`. |
| `servidor_host` | `localhost:8080` | `host[:puerto]` para `http`/`https`. Para `file`, la **carpeta local absoluta** que corresponde a la raíz de las fotos. |
| `pasta_raiz` | `/` | Prefijo opcional que se coloca entre el host y la ruta relativa de la foto. |
| `pasta_saida` | `~/tmp` | Carpeta de salida de los KMZ y del `index.kml`. Vacía = escribe `<carpeta>.kml` en la carpeta del álbum. |
| `pasta_recursos` | `recursos` | Carpeta que se empaqueta en cada KMZ. Use una **ruta absoluta**: una relativa se resuelve desde la carpeta donde ejecuta el comando. |
| `estilo_url` | `estilos03.kml#estiloCustomizado` | Estilo que usan los puntos de las fotos, con el formato `<archivo en pasta_recursos>#<id del estilo>`. |
| `icone_kml` | `globe-connected.png` | Icono de los puntos que enlazan a otros archivos `.kml`/`.kmz`. Su URL se construye como la de las fotos, así que debe ser accesible en `<host>/<pasta_raiz>/<icone_kml>`. |
| `diretorio_thumb`, `qualidade_imagem` | `thumb`, `85` | Reservadas para una futura función de miniaturas. Actualmente no se usan. |

**Cómo se construye la URL de la foto:** `<metodo_protocolo>://<servidor_host>/<pasta_raiz>/<ruta relativa a la raíz>`, con los espacios y caracteres especiales codificados. Por ejemplo, con los valores predeterminados, `/data/photosync/Viaje X/a.jpg` pasa a ser `http://localhost:8080/Viaje%20X/a.jpg`.

**Use un host que los demás equipos puedan alcanzar.** `localhost` es el equipo que abre el KMZ. Si comparte el KMZ o lo abre en otra máquina, ponga en `servidor_host` un nombre o dirección que esa máquina pueda alcanzar (por ejemplo `192.168.0.10:8080`) y genere el KMZ de nuevo.

**Modo local (`metodo_protocolo = file`).** Con `servidor_host = /data/photosync`, los enlaces pasan a ser `file:///data/photosync/...` y todo permanece en el equipo, sin servidor web. El KMZ entonces solo funciona en la máquina que tiene los archivos, y los clientes de escritorio pueden restringir las imágenes locales en los globos. Este modo se ha probado menos que `http`.

## Opciones de línea de comandos

```
cam2kml [opciones] [CARPETA]
```

| Opción | Significado |
|---|---|
| `CARPETA` | Carpeta del álbum con las fotos. Predeterminado: el directorio actual. No es recursiva. |
| `-o ARCHIVO`, `--saida ARCHIVO` | Archivo de salida, `.kml` o `.kmz`. Tiene prioridad sobre `pasta_saida`; el índice **no** se actualiza. |
| `-r DIR`, `--raiz DIR` | Raíz usada para las URL y los nombres de álbum. Predeterminado: la carpeta superior más cercana llamada `photosync`, si no, el propio álbum. |
| `--sem-gps {anterior,padrao,pular}` | Qué hacer con las fotos sin GPS. `anterior` (predeterminado): usa la posición de la última foto que tenía GPS, en el orden de los nombres de archivo (la posición fija predeterminada si todavía no hubo ninguna). `padrao`: usa la posición fija predeterminada (lon -52.225732, lat -3.203054). `pular`: deja la foto fuera. |
| `--nome {arquivo,data,ambos}` | Etiqueta de cada punto: `arquivo` (predeterminado) = nombre del archivo sin extensión, `data` = fecha EXIF, `ambos` = fecha y nombre del archivo. |
| `--sem-indice` | No actualiza `index.kml` después de crear el KMZ. |
| `--so-indice` | Solo recrea `index.kml` a partir de los KMZ que ya están en `pasta_saida`. No se procesa ninguna foto y `CARPETA` se ignora. No se puede combinar con `--sem-indice`. |
| `-V`, `--version` | Muestra la versión. |
| `-h`, `--help` | Muestra la ayuda. |

Los nombres de las opciones están en portugués: `saida` = salida, `raiz` = raíz, `sem-gps` = sin GPS, `nome` = nombre, `sem-indice` = sin índice, `so-indice` = solo el índice.

Códigos de salida: `0` si todo va bien (también para carpetas sin fotos), `1` para errores de configuración o de uso.

## Estilo y recursos

Cada punto de foto usa el estilo indicado en `estilo_url`. El estilo es un archivo KML normal que usted guarda en `pasta_recursos`. En el texto del globo puede usar estas variables:

| Variable | Contenido |
|---|---|
| `$[name]` | Etiqueta del punto (vea `--nome`). |
| `$[foto_url]` | URL de la foto original. |
| `$[camera]` | Marca y modelo de la cámara, o `desconhecida`. |
| `$[data]` | Fecha EXIF, o la fecha de modificación del archivo cuando no hay. |
| `$[isize]` | Tamaño de la imagen, como `4000x1848`. |

Ejemplo mínimo (`recursos/estilos03.kml`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Style id="estiloCustomizado">
      <IconStyle>
        <scale>0.8</scale>
        <Icon><href>camera.png</href></Icon>
      </IconStyle>
      <BalloonStyle>
        <text><![CDATA[
          <h3>$[name]</h3>
          <a href="$[foto_url]"><img src="$[foto_url]" style="max-width:640px;max-height:480px"></a>
          <p><b>Cámara:</b> $[camera] &nbsp; <b>Fecha:</b> $[data] &nbsp; <b>Tamaño:</b> $[isize]</p>
        ]]></text>
      </BalloonStyle>
    </Style>
  </Document>
</kml>
```

Todos los recursos quedan en la **raíz** del KMZ, así que las referencias a iconos deben ser nombres de archivo simples (`camera.png`), nunca `../icons/camera.png`.

## El índice

`index.kml` está en `pasta_saida` y tiene un enlace de red para cada `*.kmz` de esa carpeta, ordenados por nombre. Los enlaces son relativos, así que funcionan desde donde se abra el índice (disco o servidor web), siempre que los KMZ sigan a su lado. El índice se rehace a partir de lo que realmente hay en la carpeta, así que ejecutarlo de nuevo nunca duplica entradas, y borrar un KMZ y ejecutar `cam2kml --so-indice` elimina su enlace.

## Procesar muchas carpetas

El comando trata un álbum a la vez. Para una colección completa, recorra las carpetas y rehaga el índice una sola vez al final:

```bash
find /data/photosync -mindepth 1 -type d \
     -not -path '*/output_kmz*' -not -path '*/recursos*' -print0 |
  while IFS= read -r -d '' dir; do
    cam2kml --sem-indice "$dir"
  done
cam2kml --so-indice
```

Las carpetas sin fotos solo imprimen una línea informativa y no crean nada.

## Solución de problemas

- **Las fotos no aparecen en el globo.** La URL de la foto debe ser alcanzable desde el equipo que ejecuta Google Earth. Revise `servidor_host` (no use `localhost` para otras máquinas), la raíz del servidor web y `pasta_raiz`.
- **El globo no tiene el aspecto personalizado o falta el icono.** El KMZ no tiene estilo. Compruebe que `pasta_recursos` sea una ruta absoluta, que contenga el archivo indicado en `estilo_url` y que los iconos se referencien sin `../`. La herramienta avisa cuando `pasta_recursos` no aporta ningún archivo.
- **Los puntos se amontonan en un solo lugar.** Esas fotos no tienen GPS. Use `--sem-gps pular` para dejarlas fuera.
- **Una foto muy grande hace lento el globo.** El globo carga el archivo original. Todavía no se generan miniaturas.
- **Solo se leen `.jpg`, `.jpeg` y `.png`.** No se admiten otros formatos (HEIC, vídeos).

## Licencia

GNU General Public License, versión 2 o (a su elección) cualquier versión posterior. Vea [LICENSE](LICENSE). Copyright 2026 Renato Lins.
