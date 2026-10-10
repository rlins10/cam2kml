#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
*********************************** LICENSE ***********************************
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You can view the GNU General Public License at <https://www.gnu.org/licenses/>
*******************************************************************************

cam2kml - WARNING: This program is provided "as-is"

Author    : Renato Lins 
Blog post : 

This script will create a Google Earth KML file from geotagged photos and videos

"""

import os
import sys
import configparser
import exifread
import simplekml
from urllib.parse import quote
from PIL import Image
from datetime import datetime

# Nome do arquivo de configuração
ARQUIVO_CONFIG = "config.ini"

# Inicializa o leitor de configuração
config = configparser.ConfigParser()

# Verifica se o arquivo existe; se não existir, cria um com valores padrão
if not os.path.exists(ARQUIVO_CONFIG):
    config["geral"] = {
        "metodo_protocolo": "http",
        "servidor_host": "localhost:8080",
        "pasta_raiz" : "/",
        "diretorio_thumb": "thumb",
        "qualidade_imagem": "85"
    }
    with open(ARQUIVO_CONFIG, "w") as configfile:
        config.write(configfile)
    print(f"[INFO] Arquivo '{ARQUIVO_CONFIG}' criado com os valores padrão.")
else:
    # Lê o arquivo existente
    config.read(ARQUIVO_CONFIG)

# Carrega os valores para variáveis do arquivo de configuração
# FIX-ME: padronizar os nomes das variáveis e config.ini
PROTOCOLO = config.get("geral", "metodo_protocolo", fallback="http")
HOST = config.get("geral", "servidor_host", fallback="localhost:8080")
BASE = config.get("geral", "pasta_raiz", fallback="/")
QUALIDADE = config.getint("geral", "qualidade_imagem", fallback=85)
DIR_THUMB=config.get("geral","diretorio_thumb")

# montagem da URI dinamicamente
def montar_uri(nome_arquivo):
    if PROTOCOLO == "file":
        # Formato de arquivo local absoluto/relativo
        caminho_absoluto = os.path.abspath(os.path.join(DIR_THUMB, nome_arquivo))
        return f"file://{caminho_absoluto}"
    else:
        # Formato web (http ou https)
        return f"{PROTOCOLO}://{HOST}/{BASE}/{nome_arquivo}"

def _convert_to_degress(value):
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value:
    :type value: exifread.utils.Ratio
    :rtype: float
    """
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)

    return round(d + (m / 60.0) + (s / 3600.0),6)


def get_geolocation(img_path):
    with open(img_path, 'rb') as f:
        tags = exifread.process_file(f, details=False)

    lat_ref = tags.get('GPS GPSLatitudeRef')
    lat = tags.get('GPS GPSLatitude')
    lon_ref = tags.get('GPS GPSLongitudeRef')
    lon = tags.get('GPS GPSLongitude')

    if lat and lon and lat_ref and lon_ref:
        lat_value = _convert_to_degress(lat) * (-1 if lat_ref.values == 'S' else 1)
        lon_value = _convert_to_degress(lon) * (-1 if lon_ref.values == 'W' else 1)
        # for google earth ... it's inverted
        return lon_value,lat_value
    else:
        return None

def create_kml(directory_path, kml_file):
    n=0 # geo tagged
    t=0 # total
    now = datetime.now()
    kml = simplekml.Kml(name=kml_file)
    
    # estilo para os kml internos
    est02=simplekml.Style()
    est02.iconstyle.icon.href = montar_uri("/icons/globe-connected.png")
    est02.iconstyle.scale = 0.8
    est02.labelstyle.scale = 0.8
    
    
    # no place to go
    default_geo = (-52.225732,-3.203054)
    

    #FIX-ME: Should use mime instead of file extension
	# pesquisa as imagens
    for filename in os.listdir(directory_path):
        t=t+1
        img_path = os.path.join(directory_path, filename) 
        
        #FIX-ME: isso tá errado
        path=montar_uri(quote(img_path[img_path.index('photosync')+9::]))
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # geolocation = get_geolocation(img_path)
            # 
            with open(img_path, 'rb') as f:
               tags = exifread.process_file(f, details=False)
 
#            for tag in tags:
#             print(tag, ":", tags[tag])

            # trabalha a localização do gps 
            lat_ref = tags.get('GPS GPSLatitudeRef')
            lat = tags.get('GPS GPSLatitude')
            lon_ref = tags.get('GPS GPSLongitudeRef')
            lon = tags.get('GPS GPSLongitude')

            if lat and lon and lat_ref and lon_ref:
                lat_value = _convert_to_degress(lat) * (-1 if lat_ref.values == 'S' else 1)
                lon_value = _convert_to_degress(lon) * (-1 if lon_ref.values == 'W' else 1)
            else:
				#FIX-ME: tem pegar o GEO da foto anterior 
                lat_value = -3.203054
                lon_value = -52.225732

            geolocation=(lon_value,lat_value)
            
            if geolocation:
				# id do placemark
                n=n+1

                # Trabalha no nome
                # FIX-ME precisa melhorar, pode repetir
                nome=f"{tags.get('EXIF DateTimeOriginal')}"
                
                #trabalha as dimensões
                w=int(tags.get('Image ImageWidth').values[0])
                h=int(tags.get('Image ImageLength').values[0])
                
                # mostra dimensões no ballon.
                isize=f"{w}x{h}"

                # FIX-ME: should be a parameter, to match user preference, que tem que ir para 
                # FIX-ME: o estilo, e para o img src
                cdata = f"<![CDATA[<img src='{path}' {'width' if w > h else 'height'}='640'>]]>"
                
                # Local da Foto
                pnt=kml.newpoint(name=nome,coords=[geolocation],description=cdata)

                # contornando a falta da api publica para styleUrl e extendedData
                placemark = pnt._placemark
                placemark.styleurl="styles/estilos03.kml#estiloCustomizado"
                placemark.extendeddata.newdata(name="isize",value=isize)
                placemark.extendeddata.newdata(name="camera",value=f"{tags.get('Image Make')} {tags.get('Image Model')}" )
                placemark.extendeddata.newdata(name="data",value=tags.get("EXIF DateTimeOriginal") )
                placemark.extendeddata.newdata(name="foto_url", value=path)
                
        elif filename.lower().endswith(('.kml','.kmz')):
			# pode incluir kmz e/ou kml direto com <a>
            n=n+1
            cdata = f"<![CDATA[<a href='{path}'>link to {filename}</a>]]>"
            pnt=kml.newpoint(name=filename, coords=[default_geo],description=cdata)
            pnt.style=est02

    #
    kml.document.description=f"Criado em: {now.strftime('%m/%d/%Y, %H:%M:%S')}\nDiretorio: {directory_path}\nImagens  : {n} de {t}"
    kml.save(kml_file)

if __name__ == "__main__":
    # Diretório onde as imagens estão localizadas
    # image_directory = "caminho/para/o/diretorio/das/imagens"
    # Verifica se o usuário passou um argumento na linha de comando

    # sys.argv[1] é o primeiro argumento passado.
    if len(sys.argv) > 1:
       image_directory = sys.argv[1]
    else:
       image_directory = os.getcwd()
    

    # Nome do arquivo KML a ser criado, tem o mesmo nome da pasta, fica dentro da pasta com a estenssão kml
    kml_output_file = f"{image_directory}/{os.path.basename(image_directory)}.kml"

    create_kml(image_directory, kml_output_file)
    print(f"KML criado com sucesso em '{kml_output_file}' com as geolocalizações das imagens no diretório '{image_directory}'.")

