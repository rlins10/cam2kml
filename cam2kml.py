#!/usr/bin/env python3
#
#   cam2kml.py
#
#   Copyright 2026 Renato Lins <renatolins.am@gmail.com>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#   MA 02110-1301, USA.
#
#
#   cam2kml - WARNING: This program is provided "as-is"
#   This script will create a Google Earth KML file from geotagged photos and videos

"""Gera um arquivo KML (Google Earth) a partir de fotos geotagueadas.

Estrutura:
    Configuracao  -> lê/cria o config.ini do usuário
    MontadorURI   -> monta as URIs (http/https/file) dos arquivos
    DadosFoto     -> dados extraídos de uma foto (EXIF)
    LeitorExif    -> extrai um DadosFoto de um arquivo de imagem
    Estatisticas  -> contadores do processamento
    GeradorKML    -> varre o diretório e monta o KML
    EmpacotadorKMZ-> empacota o KML e a pasta de recursos (estilo, ícones) em um KMZ
    IndiceKML     -> gera o index.kml com um NetworkLink por KMZ

Configuração (~/.config/cam2kml/config.ini, seção [geral]):
    metodo_protocolo  http | https | file
    servidor_host     host[:porta] (http/https) ou pasta local das fotos (file://)
    pasta_raiz        prefixo opcional sob o host/pasta
    pasta_saida       onde salvar <álbum>.kmz e o index.kml
                      (vazio = salva <álbum>/<álbum>.kml na pasta do álbum)
    pasta_recursos    pasta com o KML de estilo e os ícones; todo o conteúdo vai para a
                      raiz do KMZ (vazio = KMZ sem estilo)
    estilo_url        <arquivo>#<id> do estilo dos pontos, relativo ao KMZ
                      (padrão: estilos03.kml#estiloCustomizado)
    icone_kml         ícone dos pontos que linkam outros KML/KMZ, montado como as
                      demais URIs (padrão: globe-connected.png)
"""

from __future__ import annotations

__version__ = "0.2.2"

try:
    import argparse
    import configparser
    import html
    import os
    import sys
    import tempfile
    import zipfile
    from dataclasses import dataclass
    from datetime import datetime
    from pathlib import Path
    from typing import Iterable, Optional
    from urllib.parse import quote
    from xml.sax.saxutils import escape as xml_escape

    import exifread
    import simplekml
    from PIL import Image
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    sys.exit(1)

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
PASTA_CONFIG = Path.home() / ".config" / "cam2kml"
ARQUIVO_CONFIG = PASTA_CONFIG / "config.ini"

EXT_IMAGEM = (".png", ".jpg", ".jpeg")
EXT_KML = (".kml", ".kmz")

# (longitude, latitude) -- o Google Earth usa a ordem invertida (lon, lat)
COORD_PADRAO = (-52.225732, -3.203054)

LARGURA_BALAO = 640
RAIZ_PADRAO_NOME = "photosync"

# Formatos do nome (rótulo) de cada placemark
FORMATOS_NOME = ("arquivo", "data", "ambos")

Coordenadas = tuple[float, float]  # (lon, lat)


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Configuracao:
    """Configurações do usuário, persistidas em ~/.config/cam2kml/config.ini."""

    protocolo: str = "http"
    host: str = "localhost:8080"
    pasta_raiz: str = "/"
    diretorio_thumb: str = "thumb"
    qualidade: int = 85
    pasta_saida: str = "~/tmp"  # vazio = salva o .kml na própria pasta do álbum
    pasta_recursos: str = (
        "recursos"  # estilo e ícones; o conteúdo vai para a raiz do KMZ
    )
    estilo_url: str = (
        "estilos03.kml#estiloCustomizado"  # <arquivo>#<id>, relativo ao KMZ
    )
    icone_kml: str = "globe-connected.png"  # ícone dos pontos que linkam outros KML/KMZ

    SECAO = "geral"

    @property
    def dir_saida(self) -> Optional[Path]:
        texto = self.pasta_saida.strip()
        return Path(texto).expanduser() if texto else None

    @property
    def dir_recursos(self) -> Optional[Path]:
        texto = self.pasta_recursos.strip()
        return Path(texto).expanduser() if texto else None

    @classmethod
    def carregar(cls, arquivo: Path = ARQUIVO_CONFIG) -> "Configuracao":
        """Lê o arquivo de configuração, criando-o com valores padrão se não existir."""
        if not arquivo.exists():
            cls._criar_padrao(arquivo)

        parser = configparser.ConfigParser()
        parser.read(arquivo)
        padrao = cls()
        s = cls.SECAO
        return cls(
            protocolo=parser.get(s, "metodo_protocolo", fallback=padrao.protocolo),
            host=parser.get(s, "servidor_host", fallback=padrao.host),
            pasta_raiz=parser.get(s, "pasta_raiz", fallback=padrao.pasta_raiz),
            diretorio_thumb=parser.get(
                s, "diretorio_thumb", fallback=padrao.diretorio_thumb
            ),
            qualidade=parser.getint(s, "qualidade_imagem", fallback=padrao.qualidade),
            pasta_saida=parser.get(s, "pasta_saida", fallback=padrao.pasta_saida),
            pasta_recursos=parser.get(
                s, "pasta_recursos", fallback=padrao.pasta_recursos
            ),
            estilo_url=parser.get(s, "estilo_url", fallback=padrao.estilo_url),
            icone_kml=parser.get(s, "icone_kml", fallback=padrao.icone_kml),
        )

    @classmethod
    def _criar_padrao(cls, arquivo: Path) -> None:
        padrao = cls()
        parser = configparser.ConfigParser()
        parser[cls.SECAO] = {
            "metodo_protocolo": padrao.protocolo,
            "servidor_host": padrao.host,
            "pasta_raiz": padrao.pasta_raiz,
            "diretorio_thumb": padrao.diretorio_thumb,
            "qualidade_imagem": str(padrao.qualidade),
            "pasta_saida": padrao.pasta_saida,
            "pasta_recursos": padrao.pasta_recursos,
            "estilo_url": padrao.estilo_url,
            "icone_kml": padrao.icone_kml,
        }
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with open(arquivo, "w") as f:
            parser.write(f)
        print(f"[INFO] Arquivo '{arquivo}' criado com os valores padrão.")


# --------------------------------------------------------------------------- #
# URIs
# --------------------------------------------------------------------------- #
class MontadorURI:
    """Monta URIs web (http/https) ou locais (file) a partir de um caminho relativo.

    - http/https: <protocolo>://<servidor_host>/<pasta_raiz>/<caminho>
    - file:       file://<servidor_host>/<pasta_raiz>/<caminho>, onde servidor_host
                  é a pasta local equivalente à raiz das fotos. Se estiver vazio ou
                  não for um caminho absoluto, usa a raiz detectada (raiz_local).
    """

    def __init__(self, config: Configuracao):
        self.config = config
        self.raiz_local: Optional[Path] = (
            None  # alternativa quando servidor_host não serve
        )

    @property
    def modo_local(self) -> bool:
        return self.config.protocolo == "file"

    def _host_como_caminho(self) -> Optional[Path]:
        texto = self.config.host.strip()
        if not texto:
            return None
        caminho = Path(texto).expanduser()
        return Path(os.path.abspath(caminho)) if caminho.is_absolute() else None

    def base_local(self) -> Optional[Path]:
        """Pasta base do modo file (sem resolver links simbólicos)."""
        return self._host_como_caminho() or self.raiz_local

    def avisos(self) -> list[str]:
        """Problemas de configuração do modo file; lista vazia se estiver tudo certo."""
        if not self.modo_local:
            return []

        avisos = []
        host = self.config.host.strip()
        if host and self._host_como_caminho() is None:
            avisos.append(
                f"No modo 'file', 'servidor_host' deve ser um caminho absoluto (veio '{host}'); "
                f"usando a raiz das fotos: {self.raiz_local}"
            )
        base = self.base_local()
        if base is None:
            avisos.append(
                "No modo 'file', defina 'servidor_host' com a pasta raiz das fotos."
            )
        elif not base.is_dir():
            avisos.append(
                f"A pasta base '{base}' não existe; os links das fotos ficarão quebrados."
            )
        return avisos

    def montar(self, caminho_relativo: str) -> str:
        relativo = caminho_relativo.strip("/")

        if self.modo_local:
            base = self.base_local()
            if base is None:
                raise ValueError("Modo 'file' sem pasta base: defina 'servidor_host'.")
            return (base / self.config.pasta_raiz.strip("/") / relativo).as_uri()

        partes = [
            self.config.host.strip("/"),
            self.config.pasta_raiz.strip("/"),
            quote(relativo),
        ]
        return f"{self.config.protocolo}://" + "/".join(p for p in partes if p)


# --------------------------------------------------------------------------- #
# Leitura de EXIF
# --------------------------------------------------------------------------- #
@dataclass
class DadosFoto:
    """Informações extraídas de uma foto."""

    arquivo: Path
    data: str
    camera: str
    largura: Optional[int]
    altura: Optional[int]
    coordenadas: Optional[Coordenadas]  # (lon, lat) ou None se não houver GPS

    @property
    def dimensoes(self) -> str:
        if self.largura and self.altura:
            return f"{self.largura}x{self.altura}"
        return "desconhecida"

    @property
    def lado_balao(self) -> str:
        """Atributo HTML do <img> que fixa o lado maior em LARGURA_BALAO."""
        retrato = bool(self.largura and self.altura and self.altura > self.largura)
        return "height" if retrato else "width"

    def nome(self, formato: str = "arquivo") -> str:
        """Nome do placemark: 'arquivo' (sem extensão), 'data' ou 'ambos'."""
        if formato == "data":
            return self.data
        if formato == "ambos":
            return f"{self.data} - {self.arquivo.stem}"
        return self.arquivo.stem


class LeitorExif:
    """Extrai um DadosFoto de um arquivo de imagem."""

    FORMATO_DATA = "%Y:%m:%d %H:%M:%S"

    def ler(self, caminho: Path) -> DadosFoto:
        with open(caminho, "rb") as f:
            tags = exifread.process_file(f, details=False)

        largura, altura = self._dimensoes(caminho, tags)
        return DadosFoto(
            arquivo=caminho,
            data=self._data(caminho, tags),
            camera=self._camera(tags),
            largura=largura,
            altura=altura,
            coordenadas=self._coordenadas(tags),
        )

    # -- GPS ---------------------------------------------------------------- #
    def _coordenadas(self, tags: dict) -> Optional[Coordenadas]:
        lat_ref = tags.get("GPS GPSLatitudeRef")
        lat = tags.get("GPS GPSLatitude")
        lon_ref = tags.get("GPS GPSLongitudeRef")
        lon = tags.get("GPS GPSLongitude")

        if any(t is None for t in (lat_ref, lat, lon_ref, lon)):
            return None

        try:
            lat_valor = self._para_graus(lat)
            lon_valor = self._para_graus(lon)
        except (IndexError, ValueError, ZeroDivisionError):
            return None

        if str(lat_ref).strip().upper().startswith("S"):
            lat_valor = -lat_valor
        if str(lon_ref).strip().upper().startswith("W"):
            lon_valor = -lon_valor

        if not (-90 <= lat_valor <= 90 and -180 <= lon_valor <= 180):
            return None
        return lon_valor, lat_valor  # Google Earth: lon primeiro

    @classmethod
    def _para_graus(cls, tag) -> float:
        """Converte graus/minutos/segundos do EXIF para graus decimais."""
        d, m, s = (cls._razao(r) for r in tag.values[:3])
        return round(d + m / 60.0 + s / 3600.0, 6)

    @staticmethod
    def _razao(r) -> float:
        try:
            return float(r.num) / float(r.den) if r.den else 0.0
        except AttributeError:  # versões do exifread cujo Ratio é um Fraction
            return float(r)

    # -- Dimensões ---------------------------------------------------------- #
    def _dimensoes(
        self, caminho: Path, tags: dict
    ) -> tuple[Optional[int], Optional[int]]:
        largura = altura = None

        try:
            with Image.open(caminho) as img:
                largura, altura = img.size
        except Exception:
            largura = self._inteiro(tags.get("EXIF ExifImageWidth"))
            altura = self._inteiro(tags.get("EXIF ExifImageLength"))

        # Orientações 5-8 giram a imagem em 90 graus
        orientacao = self._inteiro(tags.get("Image Orientation"))
        if orientacao in (5, 6, 7, 8) and largura and altura:
            largura, altura = altura, largura

        return largura, altura

    @staticmethod
    def _inteiro(tag) -> Optional[int]:
        try:
            return int(tag.values[0])
        except (AttributeError, IndexError, TypeError, ValueError):
            return None

    # -- Metadados ---------------------------------------------------------- #
    def _data(self, caminho: Path, tags: dict) -> str:
        tag = tags.get("EXIF DateTimeOriginal")
        if tag is not None:
            return str(tag)
        mtime = datetime.fromtimestamp(caminho.stat().st_mtime)
        return mtime.strftime(self.FORMATO_DATA)

    @staticmethod
    def _camera(tags: dict) -> str:
        partes = (
            str(tags[k]).strip() for k in ("Image Make", "Image Model") if k in tags
        )
        return " ".join(p for p in partes if p) or "desconhecida"


# --------------------------------------------------------------------------- #
# Geração do KML
# --------------------------------------------------------------------------- #
@dataclass
class Estatisticas:
    total: int = 0
    com_gps: int = 0
    sem_gps: int = 0
    puladas: int = 0
    erros: int = 0
    links_kml: int = 0

    @property
    def placemarks(self) -> int:
        return self.com_gps + self.sem_gps - self.puladas + self.links_kml


class GeradorKML:
    """Varre um diretório e gera um KML com um placemark por foto."""

    POLITICAS_SEM_GPS = ("anterior", "padrao", "pular")

    def __init__(
        self,
        config: Configuracao,
        raiz: Optional[Path] = None,
        politica_sem_gps: str = "anterior",
        formato_nome: str = "arquivo",
        leitor: Optional[LeitorExif] = None,
    ):
        if politica_sem_gps not in self.POLITICAS_SEM_GPS:
            raise ValueError(f"Política inválida: {politica_sem_gps!r}")
        if formato_nome not in FORMATOS_NOME:
            raise ValueError(f"Formato de nome inválido: {formato_nome!r}")

        self.config = config
        self.uris = MontadorURI(config)
        self.raiz = raiz
        self.politica_sem_gps = politica_sem_gps
        self.formato_nome = formato_nome
        self.leitor = leitor or LeitorExif()

        self._ultima_coord: Optional[Coordenadas] = None
        self._estilo_kml: Optional[simplekml.Style] = (
            None  # criado em gerar(), com a raiz já conhecida
        )

    # -- API pública -------------------------------------------------------- #
    def gerar(
        self, diretorio: Path, saida: Path, ignorar: Iterable[Path] = ()
    ) -> Estatisticas:
        diretorio = diretorio.resolve()
        saida = saida.resolve()
        ignorados = {saida, *(Path(p).resolve() for p in ignorar)}
        if self.raiz is None:
            self.raiz = self.detectar_raiz(diretorio)

        self.uris.raiz_local = self.raiz
        for aviso in self.uris.avisos():
            print(f"[AVISO] {aviso}", file=sys.stderr)
        self._estilo_kml = self._criar_estilo_kml()

        stats = Estatisticas()
        kml = simplekml.Kml(name=diretorio.name)

        for arquivo in self._listar_arquivos(diretorio, ignorados):
            stats.total += 1
            sufixo = arquivo.suffix.lower()
            try:
                if sufixo in EXT_IMAGEM:
                    self._processar_foto(kml, arquivo, stats)
                elif sufixo in EXT_KML:
                    self._adicionar_link_kml(kml, arquivo)
                    stats.links_kml += 1
            except Exception as e:  # uma imagem corrompida não derruba tudo
                stats.erros += 1
                print(f"[AVISO] Ignorando '{arquivo.name}': {e}", file=sys.stderr)

        kml.document.description = self._descricao_documento(diretorio, stats)
        kml.save(str(saida))
        return stats

    @staticmethod
    def detectar_raiz(diretorio: Path) -> Path:
        """Sobe a árvore procurando a pasta 'photosync'; senão usa o próprio diretório."""
        for pasta in (diretorio, *diretorio.parents):
            if pasta.name == RAIZ_PADRAO_NOME:
                return pasta
        return diretorio

    # -- Varredura ---------------------------------------------------------- #
    @staticmethod
    def _listar_arquivos(diretorio: Path, ignorar: set[Path]) -> list[Path]:
        return sorted(
            p for p in diretorio.iterdir() if p.is_file() and p.resolve() not in ignorar
        )

    def _uri_arquivo(self, arquivo: Path) -> str:
        try:
            relativo = arquivo.relative_to(self.raiz)
        except ValueError:
            relativo = Path(arquivo.name)
        return self.uris.montar(relativo.as_posix())

    # -- Fotos -------------------------------------------------------------- #
    def _processar_foto(
        self, kml: simplekml.Kml, arquivo: Path, stats: Estatisticas
    ) -> None:
        dados = self.leitor.ler(arquivo)
        coord = self._resolver_coordenadas(dados, stats)
        if coord is None:
            stats.puladas += 1
            return
        self._adicionar_foto(kml, dados, coord)

    def _resolver_coordenadas(
        self, dados: DadosFoto, stats: Estatisticas
    ) -> Optional[Coordenadas]:
        if dados.coordenadas:
            stats.com_gps += 1
            self._ultima_coord = dados.coordenadas
            return dados.coordenadas

        stats.sem_gps += 1
        if self.politica_sem_gps == "pular":
            return None
        if self.politica_sem_gps == "anterior" and self._ultima_coord:
            return self._ultima_coord
        return COORD_PADRAO

    def _adicionar_foto(
        self, kml: simplekml.Kml, dados: DadosFoto, coord: Coordenadas
    ) -> None:
        uri = self._uri_arquivo(dados.arquivo)

        pnt = kml.newpoint(
            name=dados.nome(self.formato_nome),
            coords=[coord],
            description=self._html_balao(uri, dados),
        )

        # A API pública do simplekml não expõe styleUrl/extendedData neste objeto
        placemark = pnt._placemark
        placemark.styleurl = self.config.estilo_url
        extra = placemark.extendeddata
        extra.newdata(name="isize", value=dados.dimensoes)
        extra.newdata(name="camera", value=dados.camera)
        extra.newdata(name="data", value=dados.data)
        extra.newdata(name="foto_url", value=uri)

    @staticmethod
    def _html_balao(uri: str, dados: DadosFoto) -> str:
        src = html.escape(uri, quote=True)
        return f"<![CDATA[<img src='{src}' {dados.lado_balao}='{LARGURA_BALAO}'>]]>"

    # -- Links para outros KML/KMZ ------------------------------------------ #
    def _adicionar_link_kml(self, kml: simplekml.Kml, arquivo: Path) -> None:
        href = html.escape(self._uri_arquivo(arquivo), quote=True)
        texto = html.escape(arquivo.name)
        pnt = kml.newpoint(
            name=arquivo.name,
            coords=[COORD_PADRAO],
            description=f"<![CDATA[<a href='{href}'>link to {texto}</a>]]>",
        )
        pnt.style = self._estilo_kml

    def _criar_estilo_kml(self) -> simplekml.Style:
        estilo = simplekml.Style()
        estilo.iconstyle.icon.href = self.uris.montar(self.config.icone_kml)
        estilo.iconstyle.scale = 0.8
        estilo.labelstyle.scale = 0.8
        return estilo

    # -- Documento ---------------------------------------------------------- #
    @staticmethod
    def _descricao_documento(diretorio: Path, stats: Estatisticas) -> str:
        agora = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        return (
            f"Criado em: {agora} (cam2kml {__version__})\n"
            f"Diretorio: {diretorio}\n"
            f"Imagens  : {stats.com_gps} com GPS, {stats.sem_gps} sem GPS "
            f"({stats.total} arquivos)"
        )


# --------------------------------------------------------------------------- #
# Empacotamento (KMZ) e índice
# --------------------------------------------------------------------------- #
class EmpacotadorKMZ:
    """Empacota um KML (como doc.kml) e o conteúdo da pasta de recursos em um KMZ.

    Cada arquivo entra com o mesmo caminho relativo que tem na pasta de recursos
    (ex.: <recursos>/estilos03.kml vira estilos03.kml na raiz do KMZ).
    """

    # Proteção contra apontar pasta_recursos para a pasta das fotos por engano
    LIMITE_ARQUIVOS = 500

    def __init__(self, pasta_recursos: Optional[Path]):
        self.pasta_recursos = pasta_recursos

    def empacotar(self, kml: Path, kmz: Path) -> int:
        """Cria o KMZ e devolve quantos arquivos de recursos foram incluídos."""
        kmz.parent.mkdir(parents=True, exist_ok=True)
        temporario = kmz.with_name(kmz.name + ".tmp")
        recursos = (
            self._recursos()
        )  # antes de criar o arquivo: falha cedo se for suspeita
        incluidos = 0
        try:
            with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(kml, "doc.kml")  # o KML principal fica na raiz do KMZ
                for arquivo in recursos:
                    nome = arquivo.relative_to(self.pasta_recursos).as_posix()
                    zf.write(arquivo, nome)
                    incluidos += 1
            os.replace(temporario, kmz)  # troca atômica: nunca deixa KMZ pela metade
        finally:
            temporario.unlink(missing_ok=True)
        return incluidos

    def _recursos(self) -> list[Path]:
        base = self.pasta_recursos
        if base is None or not base.is_dir():
            return []

        arquivos: list[Path] = []
        for p in base.rglob(
            "*"
        ):  # percorre aos poucos, para parar cedo ao passar do limite
            relativo = p.relative_to(base)
            if (
                not p.is_file()
                or any(parte.startswith(".") for parte in relativo.parts)  # ocultos
                or p.suffix.lower() == ".kmz"
                or relativo.as_posix() == "doc.kml"  # nome reservado do KMZ
            ):
                continue
            arquivos.append(p)
            if len(arquivos) > self.LIMITE_ARQUIVOS:
                raise ValueError(
                    f"'{base}' tem mais de {self.LIMITE_ARQUIVOS} arquivos; confira "
                    "'pasta_recursos' (ela deve conter só o estilo e os ícones)."
                )
        return sorted(arquivos)


class IndiceKML:
    """Gera o index.kml com um NetworkLink (desmarcado) para cada KMZ da pasta."""

    NOME_ARQUIVO = "index.kml"

    def __init__(self, pasta: Path, titulo: str = "Álbuns"):
        self.pasta = pasta
        self.titulo = titulo

    def gerar(self) -> Path:
        """(Re)gera o índice a partir dos KMZ existentes; pode rodar quantas vezes quiser."""
        kmzs = sorted(
            (
                p
                for p in self.pasta.iterdir()
                if p.is_file() and p.suffix.lower() == ".kmz"
            ),
            key=lambda p: p.name.lower(),
        )
        agora = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        descricao = (
            f"Atualizado em: {agora} (cam2kml {__version__})\nÁlbuns: {len(kmzs)}"
        )

        linhas = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            "  <Document>",
            f"    <name>{xml_escape(self.titulo)}</name>",
            f"    <description>{xml_escape(descricao)}</description>",
            "    <open>1</open>",
            *(self._link(kmz) for kmz in kmzs),
            "  </Document>",
            "</kml>",
            "",
        ]

        destino = self.pasta / self.NOME_ARQUIVO
        temporario = destino.with_name(destino.name + ".tmp")
        temporario.write_text("\n".join(linhas), encoding="utf-8")
        os.replace(temporario, destino)
        return destino

    @staticmethod
    def _link(kmz: Path) -> str:
        # href relativo: resolvido a partir de onde o index.kml for aberto (disco ou HTTP)
        return (
            "    <NetworkLink>\n"
            f"      <name>{xml_escape(kmz.stem)}</name>\n"
            "      <visibility>0</visibility>\n"
            f"      <Link><href>{xml_escape(quote(kmz.name))}</href></Link>\n"
            "    </NetworkLink>"
        )


def gerar_kmz(
    gerador: GeradorKML, config: Configuracao, diretorio: Path, saida: Path
) -> Estatisticas:
    """Gera o KML numa pasta temporária e o empacota, com a pasta de recursos, em KMZ."""
    with tempfile.TemporaryDirectory(prefix="cam2kml_") as tmp:
        kml_temporario = Path(tmp) / "doc.kml"
        stats = gerador.gerar(diretorio, kml_temporario, ignorar=(saida,))
        recursos = config.dir_recursos
        incluidos = EmpacotadorKMZ(recursos).empacotar(kml_temporario, saida)

    if incluidos == 0:
        print(
            f"[AVISO] Nenhum arquivo de recursos encontrado (pasta_recursos = '{recursos or ''}'); "
            "o KMZ ficou sem estilo e ícones. Ajuste 'pasta_recursos' no config.ini.",
            file=sys.stderr,
        )
    return stats


# --------------------------------------------------------------------------- #
# Linha de comando
# --------------------------------------------------------------------------- #
def interpretar_argumentos(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um KML (Google Earth) a partir de fotos geotagueadas."
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "diretorio",
        nargs="?",
        default=os.getcwd(),
        help="diretório com as fotos (padrão: diretório atual)",
    )
    parser.add_argument(
        "-o",
        "--saida",
        help="arquivo de saída, .kml ou .kmz (padrão: <pasta_saida>/<álbum>.kmz se "
        "'pasta_saida' estiver no config.ini; senão <diretorio>/<álbum>.kml)",
    )
    parser.add_argument(
        "-r",
        "--raiz",
        help="raiz usada para montar as URLs relativas "
        f"(padrão: pasta '{RAIZ_PADRAO_NOME}' se existir no caminho, senão o diretório)",
    )
    parser.add_argument(
        "--sem-gps",
        choices=GeradorKML.POLITICAS_SEM_GPS,
        default="anterior",
        help="o que fazer com fotos sem GPS: herdar a posição da anterior, "
        "usar a coordenada padrão ou pular (padrão: anterior)",
    )
    parser.add_argument(
        "--nome",
        choices=FORMATOS_NOME,
        default="arquivo",
        help="nome exibido em cada ponto: nome do arquivo sem extensão, "
        "data do EXIF ou ambos (padrão: arquivo)",
    )
    parser.add_argument(
        "--sem-indice",
        action="store_true",
        help="não atualiza o index.kml da pasta_saida após gerar o KMZ",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = interpretar_argumentos(argv)

    diretorio = Path(args.diretorio).resolve()
    if not diretorio.is_dir():
        print(f"[ERRO] '{diretorio}' não é um diretório.", file=sys.stderr)
        return 1

    config = Configuracao.carregar()
    raiz = Path(args.raiz).resolve() if args.raiz else None

    # Destino: -o tem prioridade; depois a pasta_saida do config.ini
    # (<pasta_saida>/<álbum>.kmz); por fim, a própria pasta do álbum (.kml)
    usa_pasta_saida = not args.saida and config.dir_saida is not None
    if args.saida:
        saida = Path(args.saida).expanduser()
    elif config.dir_saida is not None:
        saida = config.dir_saida / f"{diretorio.name}.kmz"
    else:
        saida = diretorio / f"{diretorio.name}.kml"
    saida = saida.resolve()
    saida.parent.mkdir(parents=True, exist_ok=True)

    gerador = GeradorKML(
        config,
        raiz=raiz,
        politica_sem_gps=args.sem_gps,
        formato_nome=args.nome,
    )

    eh_kmz = saida.suffix.lower() == ".kmz"
    try:
        if eh_kmz:
            stats = gerar_kmz(gerador, config, diretorio, saida)
        else:
            stats = gerador.gerar(diretorio, saida)
    except ValueError as erro:  # configuração inválida (ex.: pasta_recursos suspeita)
        print(f"[ERRO] {erro}", file=sys.stderr)
        return 1

    if eh_kmz and usa_pasta_saida and not args.sem_indice:
        indice = IndiceKML(saida.parent).gerar()
        print(f"[INFO] Índice atualizado: '{indice}'")

    print(
        f"{saida.suffix[1:].upper()} criado em '{saida}': {stats.com_gps} fotos com GPS, "
        f"{stats.sem_gps} sem GPS ({stats.puladas} puladas), "
        f"{stats.erros} erros, {stats.total} arquivos no diretório."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
