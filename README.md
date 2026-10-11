# cam2kml

**English** · [Português](README.pt-BR.md) · [Español](README.es.md)

Turns folders of geotagged photos into **Google Earth KMZ files**. Each photo becomes a point on the map at the place where it was taken, with a balloon that shows the picture, the camera, the date and the image size. Every album gets its own KMZ, and an `index.kml` links all of them so you can open the whole collection from a single file.

It was built for large collections (tens of thousands of photos in thousands of folders) that are served by a simple web server, but it also works for a handful of folders.

## Features

- Reads GPS, date, camera and size from the EXIF data of `.jpg`, `.jpeg` and `.png` files.
- One KMZ per album, written to a separate output folder, never into the photo folders.
- `index.kml` with one network link per album (all unchecked, so nothing is loaded until you tick it).
- Custom balloon and icon style, taken from a resources folder that is packed inside each KMZ.
- Photos without GPS can inherit the position of the previous photo, use a fixed position, or be skipped.
- Folders without photos produce nothing and do not touch the index.
- Very large images (panoramas of 100+ megapixels) are handled without warnings.
- Albums with the same folder name in different places never overwrite each other (`Samsung SM-G935F/Camera` and `Samsung SM-P205/Camera` become `Samsung SM-G935F - Camera.kmz` and `Samsung SM-P205 - Camera.kmz`).

## Requirements

- Python 3.9 or newer.
- [ExifRead](https://pypi.org/project/ExifRead/), [simplekml](https://pypi.org/project/simplekml/) and [Pillow](https://pypi.org/project/pillow/) (installed automatically).
- Google Earth Pro (desktop) to view the result. Other clients may render the balloons differently.

## Installation

Replace `YOUR-USER` with the GitHub account that hosts the repository.

```bash
# Recommended: isolated command-line tool
pipx install "git+https://github.com/YOUR-USER/cam2kml.git"

# Or with uv
uv tool install "git+https://github.com/YOUR-USER/cam2kml.git"

# Or into the current virtual environment
pip install "git+https://github.com/YOUR-USER/cam2kml.git"

# A specific release (tag) or branch
pip install "git+https://github.com/YOUR-USER/cam2kml.git@v0.2.2"
```

Upgrade with `pipx upgrade cam2kml` or by repeating the `pip install` command with `--upgrade`. Uninstall with `pipx uninstall cam2kml` or `pip uninstall cam2kml`.

On Debian/Ubuntu and other systems where `pip` refuses to install system-wide ("externally-managed-environment"), use `pipx` or a virtual environment (`python3 -m venv ~/myenv && . ~/myenv/bin/activate`).

From a clone, for development:

```bash
git clone https://github.com/YOUR-USER/cam2kml.git
cd cam2kml
pip install -e .
```

You can also run the script without installing it: `pip install exifread simplekml pillow` and then `python3 cam2kml.py FOLDER`. After installing, `cam2kml --version` and `python3 -m cam2kml --version` both work.

## Quick start

1. **Create the configuration.** The first run creates `~/.config/cam2kml/config.ini` with default values. Edit it (see [Configuration](#configuration)), or create it by hand.
2. **Prepare the resources folder** (`pasta_recursos`): put the style KML and its icons in it (see [Style and resources](#style-and-resources)).
3. **Serve your photos** with any web server whose root is the photo root folder, for example:
   ```bash
   cd /data/photosync && python3 -m http.server 8080
   ```
4. **Generate the KMZ** of one album:
   ```bash
   cam2kml "/data/photosync/Samsung SM-G935F/Camera"
   ```
   This creates `<pasta_saida>/Samsung SM-G935F - Camera.kmz` and updates `<pasta_saida>/index.kml`.
5. **Open it in Google Earth**: open the KMZ directly, or open the index through a network link (for example `http://localhost:8080/output_kmz/index.kml`, when `pasta_saida` is inside the served folder).

## How the folders are used

```
/data/photosync/                 <- root ("raiz"): URLs and album names are relative to it
├── recursos/                    <- pasta_recursos: style + icons, copied into every KMZ
│   ├── estilos03.kml
│   └── camera.png
├── output_kmz/                  <- pasta_saida: generated KMZ files and index.kml
│   ├── index.kml
│   ├── Samsung SM-G935F - Camera.kmz
│   └── Trip X - Samsung SM-G990E - Camera.kmz
├── Samsung SM-G935F/
│   └── Camera/                  <- album: the photos are directly here
│       ├── 20230907_115442.jpg
│       └── track.kml            <- optional: becomes a clickable link point
└── Trip X/
    └── Samsung SM-G990E/
        └── Camera/
```

| Folder | Role |
|---|---|
| **Album** (the `FOLDER` you pass) | Contains the photos. Only the files directly inside it are read; sub-folders are **not** searched. Files named `*.kml` or `*.kmz` inside it become points with a link to the file. |
| **Root** (`--raiz`) | The folder the web server (or the `file` base folder) corresponds to. By default it is the closest parent folder named `photosync`; if there is none, the album folder itself. A photo's URL is built from its path relative to the root. |
| **`pasta_saida`** | Where `<album>.kmz` and `index.kml` are written. It may be anywhere, including inside the root. If left empty, a plain `<folder>.kml` is written inside the album folder instead (no KMZ, no index, no resources). |
| **`pasta_recursos`** | Everything in it goes to the root of every KMZ (the style KML and the icons). Hidden files, `*.kmz` files and a file called `doc.kml` are ignored, and it must have at most 500 files (a safeguard against pointing it at a photo folder by mistake). |

**Album name.** It is the album's path relative to the root, joined with ` - `. `photosync/sample01` gives `sample01`, and `photosync/Trip X/Samsung SM-G990E/Camera` gives `Trip X - Samsung SM-G990E - Camera`. The name is used for the KMZ file, for the document name shown in Google Earth and for the entry in the index. If the album is outside the root (or is the root), only the folder name is used.

## Configuration

File: `~/.config/cam2kml/config.ini` (on Windows: `%USERPROFILE%\.config\cam2kml\config.ini`), section `[geral]`. Missing keys fall back to the defaults below.

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

| Key | Default | Meaning |
|---|---|---|
| `metodo_protocolo` | `http` | `http`, `https` or `file`. |
| `servidor_host` | `localhost:8080` | `host[:port]` for `http`/`https`. For `file`, the **absolute local folder** that corresponds to the photo root. |
| `pasta_raiz` | `/` | Optional path prefix placed between the host and the photo's relative path. |
| `pasta_saida` | `~/tmp` | Output folder for the KMZ files and `index.kml`. Empty = write `<folder>.kml` in the album folder. |
| `pasta_recursos` | `recursos` | Folder packed into every KMZ. Use an **absolute path**: a relative one is resolved from the folder where you run the command. |
| `estilo_url` | `estilos03.kml#estiloCustomizado` | Style used by the photo points, as `<file in pasta_recursos>#<style id>`. |
| `icone_kml` | `globe-connected.png` | Icon of the points that link to other `.kml`/`.kmz` files. Its URL is built like the photo URLs, so it must be reachable at `<host>/<pasta_raiz>/<icone_kml>`. |
| `diretorio_thumb`, `qualidade_imagem` | `thumb`, `85` | Reserved for a future thumbnail feature. Currently unused. |

**How the photo URL is built:** `<metodo_protocolo>://<servidor_host>/<pasta_raiz>/<path relative to the root>`, with spaces and special characters percent-encoded. For example, with the defaults, `/data/photosync/Trip X/a.jpg` becomes `http://localhost:8080/Trip%20X/a.jpg`.

**Use a host other computers can reach.** `localhost` is the computer that opens the KMZ. If you share the KMZ or open it on another machine, set `servidor_host` to a name or address that machine can reach (for example `192.168.0.10:8080`) and generate the KMZ again.

**Local mode (`metodo_protocolo = file`).** With `servidor_host = /data/photosync` the links become `file:///data/photosync/...` and everything stays on the computer, without a web server. The KMZ then only works on the machine that has the files, and desktop clients may restrict local images in balloons. This mode has had less testing than `http`.

## Command line options

```
cam2kml [options] [FOLDER]
```

| Option | Meaning |
|---|---|
| `FOLDER` | Album folder with the photos. Default: the current directory. Not recursive. |
| `-o FILE`, `--saida FILE` | Output file, `.kml` or `.kmz`. Takes precedence over `pasta_saida`; the index is **not** updated. |
| `-r DIR`, `--raiz DIR` | Root used for URLs and album names. Default: the closest parent named `photosync`, otherwise the album folder. |
| `--sem-gps {anterior,padrao,pular}` | What to do with photos that have no GPS. `anterior` (default): use the position of the last photo that had GPS, in file-name order (the fixed default if there is none yet). `padrao`: use the fixed default position (lon -52.225732, lat -3.203054). `pular`: leave the photo out. |
| `--nome {arquivo,data,ambos}` | Label of each point: `arquivo` (default) = file name without extension, `data` = EXIF date, `ambos` = date and file name. |
| `--sem-indice` | Do not update `index.kml` after creating the KMZ. |
| `--so-indice` | Only rebuild `index.kml` from the KMZ files already present in `pasta_saida`. No photo is processed and `FOLDER` is ignored. Cannot be combined with `--sem-indice`. |
| `-V`, `--version` | Show the version. |
| `-h`, `--help` | Show the help. |

The option names are in Portuguese: `saida` = output, `raiz` = root, `sem-gps` = no GPS, `nome` = name, `sem-indice` = no index, `so-indice` = index only.

Exit codes: `0` on success (also for folders that have no photos), `1` on configuration or usage errors.

## Style and resources

Each photo point uses the style given by `estilo_url`. The style is a normal KML file that you keep in `pasta_recursos`. Inside the balloon text you can use these variables:

| Variable | Content |
|---|---|
| `$[name]` | Point label (see `--nome`). |
| `$[foto_url]` | URL of the original photo. |
| `$[camera]` | Camera make and model, or `desconhecida`. |
| `$[data]` | EXIF date, or the file's modification time when there is none. |
| `$[isize]` | Image size, such as `4000x1848`. |

Minimal example (`recursos/estilos03.kml`):

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
          <p><b>Camera:</b> $[camera] &nbsp; <b>Date:</b> $[data] &nbsp; <b>Size:</b> $[isize]</p>
        ]]></text>
      </BalloonStyle>
    </Style>
  </Document>
</kml>
```

All resources end up in the **root** of the KMZ, so icon references must be plain file names (`camera.png`), never `../icons/camera.png`.

## The index

`index.kml` lives in `pasta_saida` and has one network link per `*.kmz` in that folder, sorted by name. The links are relative, so they work wherever the index is opened from (disk or web server), as long as the KMZ files stay next to it. The index is rebuilt from what is actually in the folder, so running it again never duplicates entries, and deleting a KMZ and running `cam2kml --so-indice` removes its link.

## Processing many folders

The command handles one album at a time. For a whole collection, loop over the folders and rebuild the index once at the end:

```bash
find /data/photosync -mindepth 1 -type d \
     -not -path '*/output_kmz*' -not -path '*/recursos*' -print0 |
  while IFS= read -r -d '' dir; do
    cam2kml --sem-indice "$dir"
  done
cam2kml --so-indice
```

Folders without photos only print an informational line and create nothing.

## Troubleshooting

- **Photos do not show in the balloon.** The photo URL must be reachable from the computer running Google Earth. Check `servidor_host` (not `localhost` for other machines), the web server root and `pasta_raiz`.
- **The balloon has no custom look or the icon is missing.** The KMZ has no style. Check that `pasta_recursos` is an absolute path, that it contains the file named in `estilo_url`, and that the icons are referenced without `../`. The tool prints a warning when `pasta_recursos` yields no files.
- **Points pile up in one place.** Those photos have no GPS. Use `--sem-gps pular` to leave them out.
- **A very large photo makes the balloon slow.** The balloon loads the original file. Thumbnails are not generated yet.
- **Only `.jpg`, `.jpeg` and `.png` are read.** Other formats (HEIC, videos) are not supported.

## License

GNU General Public License, version 2 or (at your option) any later version. See [LICENSE](LICENSE). Copyright 2026 Renato Lins.
