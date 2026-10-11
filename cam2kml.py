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
"""

from __future__ import annotations

import argparse
import configparser
import html
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import exifread
import simplekml
from PIL import Image

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
PASTA_CONFIG = Path.home() / ".local" / "cam2kml"
ARQUIVO_CONFIG = PASTA_CONFIG / "config.ini"

EXT_IMAGEM = (".png", ".jpg", ".jpeg")
EXT_KML = (".kml", ".kmz")

# (longitude, latitude) -- o Google Earth usa a ordem invertida (lon, lat)
COORD_PADRAO = (-52.225732, -3.203054)

LARGURA_BALAO = 640
ESTILO_URL = "styles/estilos03.kml#estiloCustomizado"
ICONE_KML = "icons/globe-connected.png"
RAIZ_PADRAO_NOME = "photosync"

Coordenadas = tuple[float, float]  # (lon, lat)


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Configuracao:
    """Configurações do usuário, persistidas em ~/.local/cam2kml/config.ini."""

    protocolo: str = "http"
    host: str = "localhost:8080"
    pasta_raiz: str = "/"
    diretorio_thumb: str = "thumb"
    qualidade: int = 85

    SECAO = "geral"

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
        }
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with open(arquivo, "w") as f:
            parser.write(f)
        print(f"[INFO] Arquivo '{arquivo}' criado com os valores padrão.")


# --------------------------------------------------------------------------- #
# URIs
# --------------------------------------------------------------------------- #
class MontadorURI:
    """Monta URIs web (http/https) ou locais (file) a partir de um caminho relativo."""

    def __init__(self, config: Configuracao):
        self.config = config

    def montar(self, caminho_relativo: str) -> str:
        relativo = caminho_relativo.strip("/")

        if self.config.protocolo == "file":
            absoluto = (Path(self.config.diretorio_thumb) / relativo).resolve()
            return absoluto.as_uri()

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

    @property
    def nome(self) -> str:
        return f"{self.data} - {self.arquivo.stem}"


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
    def _dimensoes(self, caminho: Path, tags: dict) -> tuple[Optional[int], Optional[int]]:
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
        partes = (str(tags[k]).strip() for k in ("Image Make", "Image Model") if k in tags)
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
        leitor: Optional[LeitorExif] = None,
    ):
        if politica_sem_gps not in self.POLITICAS_SEM_GPS:
            raise ValueError(f"Política inválida: {politica_sem_gps!r}")

        self.uris = MontadorURI(config)
        self.raiz = raiz
        self.politica_sem_gps = politica_sem_gps
        self.leitor = leitor or LeitorExif()

        self._ultima_coord: Optional[Coordenadas] = None
        self._estilo_kml = self._criar_estilo_kml()

    # -- API pública -------------------------------------------------------- #
    def gerar(self, diretorio: Path, saida: Path) -> Estatisticas:
        diretorio = diretorio.resolve()
        saida = saida.resolve()
        if self.raiz is None:
            self.raiz = self.detectar_raiz(diretorio)

        stats = Estatisticas()
        kml = simplekml.Kml(name=saida.name)

        for arquivo in self._listar_arquivos(diretorio, saida):
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
    def _listar_arquivos(diretorio: Path, saida: Path) -> list[Path]:
        return sorted(
            p for p in diretorio.iterdir() if p.is_file() and p.resolve() != saida
        )

    def _uri_arquivo(self, arquivo: Path) -> str:
        try:
            relativo = arquivo.relative_to(self.raiz)
        except ValueError:
            relativo = Path(arquivo.name)
        return self.uris.montar(relativo.as_posix())

    # -- Fotos -------------------------------------------------------------- #
    def _processar_foto(self, kml: simplekml.Kml, arquivo: Path, stats: Estatisticas) -> None:
        dados = self.leitor.ler(arquivo)
        coord = self._resolver_coordenadas(dados, stats)
        if coord is None:
            stats.puladas += 1
            return
        self._adicionar_foto(kml, dados, coord)

    def _resolver_coordenadas(self, dados: DadosFoto, stats: Estatisticas) -> Optional[Coordenadas]:
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

    def _adicionar_foto(self, kml: simplekml.Kml, dados: DadosFoto, coord: Coordenadas) -> None:
        uri = self._uri_arquivo(dados.arquivo)

        pnt = kml.newpoint(
            name=dados.nome,
            coords=[coord],
            description=self._html_balao(uri, dados),
        )

        # A API pública do simplekml não expõe styleUrl/extendedData neste objeto
        placemark = pnt._placemark
        placemark.styleurl = ESTILO_URL
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
        estilo.iconstyle.icon.href = self.uris.montar(ICONE_KML)
        estilo.iconstyle.scale = 0.8
        estilo.labelstyle.scale = 0.8
        return estilo

    # -- Documento ---------------------------------------------------------- #
    @staticmethod
    def _descricao_documento(diretorio: Path, stats: Estatisticas) -> str:
        agora = datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        return (
            f"Criado em: {agora}\n"
            f"Diretorio: {diretorio}\n"
            f"Imagens  : {stats.com_gps} com GPS, {stats.sem_gps} sem GPS "
            f"({stats.total} arquivos)"
        )


# --------------------------------------------------------------------------- #
# Linha de comando
# --------------------------------------------------------------------------- #
def interpretar_argumentos(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um KML (Google Earth) a partir de fotos geotagueadas."
    )
    parser.add_argument(
        "diretorio",
        nargs="?",
        default=os.getcwd(),
        help="diretório com as fotos (padrão: diretório atual)",
    )
    parser.add_argument(
        "-o", "--saida",
        help="arquivo KML de saída (padrão: <diretorio>/<nome-do-diretorio>.kml)",
    )
    parser.add_argument(
        "-r", "--raiz",
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
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = interpretar_argumentos(argv)

    diretorio = Path(args.diretorio).resolve()
    if not diretorio.is_dir():
        print(f"[ERRO] '{diretorio}' não é um diretório.", file=sys.stderr)
        return 1

    saida = Path(args.saida) if args.saida else diretorio / f"{diretorio.name}.kml"
    raiz = Path(args.raiz).resolve() if args.raiz else None

    gerador = GeradorKML(
        Configuracao.carregar(),
        raiz=raiz,
        politica_sem_gps=args.sem_gps,
    )
    stats = gerador.gerar(diretorio, saida)

    print(
        f"KML criado em '{saida}': {stats.com_gps} fotos com GPS, "
        f"{stats.sem_gps} sem GPS ({stats.puladas} puladas), "
        f"{stats.erros} erros, {stats.total} arquivos no diretório."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
