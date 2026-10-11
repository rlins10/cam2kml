# cam2kml

[English](README.md) · **Português** · [Español](README.es.md)

Transforma pastas de fotos geotagueadas em **arquivos KMZ do Google Earth**. Cada foto vira um ponto no mapa, no local onde foi tirada, com um balão que mostra a imagem, a câmera, a data e o tamanho. Cada álbum ganha o seu próprio KMZ, e um `index.kml` liga todos eles, para abrir a coleção inteira a partir de um único arquivo.

Foi feito para coleções grandes (dezenas de milhares de fotos em milhares de pastas) servidas por um servidor web simples, mas também funciona para poucas pastas.

## Recursos

- Lê GPS, data, câmera e tamanho do EXIF de arquivos `.jpg`, `.jpeg` e `.png`.
- Um KMZ por álbum, gravado numa pasta de saída separada, nunca dentro das pastas de fotos.
- `index.kml` com um link de rede por álbum (todos desmarcados, então nada é carregado até você marcar).
- Estilo de balão e ícone personalizados, vindos de uma pasta de recursos que é empacotada dentro de cada KMZ.
- Fotos sem GPS podem herdar a posição da foto anterior, usar uma posição fixa ou ser puladas.
- Pastas sem fotos não geram nada e não mexem no índice.
- Imagens muito grandes (panoramas de mais de 100 megapixels) são tratadas sem avisos.
- Álbuns com o mesmo nome de pasta em lugares diferentes nunca se sobrescrevem (`Samsung SM-G935F/Camera` e `Samsung SM-P205/Camera` viram `Samsung SM-G935F - Camera.kmz` e `Samsung SM-P205 - Camera.kmz`).

## Requisitos

- Python 3.9 ou mais novo.
- [ExifRead](https://pypi.org/project/ExifRead/), [simplekml](https://pypi.org/project/simplekml/) e [Pillow](https://pypi.org/project/pillow/) (instalados automaticamente).
- Google Earth Pro (desktop) para ver o resultado. Outros clientes podem exibir os balões de forma diferente.

## Instalação

Troque `YOUR-USER` pela conta do GitHub que hospeda o repositório.

```bash
# Recomendado: ferramenta de linha de comando isolada
pipx install "git+https://github.com/YOUR-USER/cam2kml.git"

# Ou com uv
uv tool install "git+https://github.com/YOUR-USER/cam2kml.git"

# Ou no ambiente virtual atual
pip install "git+https://github.com/YOUR-USER/cam2kml.git"

# Uma versão específica (tag) ou um branch
pip install "git+https://github.com/YOUR-USER/cam2kml.git@v0.2.2"
```

Para atualizar, use `pipx upgrade cam2kml` ou repita o comando `pip install` com `--upgrade`. Para desinstalar, `pipx uninstall cam2kml` ou `pip uninstall cam2kml`.

No Debian/Ubuntu e em outros sistemas em que o `pip` se recusa a instalar no sistema ("externally-managed-environment"), use `pipx` ou um ambiente virtual (`python3 -m venv ~/myenv && . ~/myenv/bin/activate`).

A partir de um clone, para desenvolvimento:

```bash
git clone https://github.com/YOUR-USER/cam2kml.git
cd cam2kml
pip install -e .
```

Também dá para rodar o script sem instalar: `pip install exifread simplekml pillow` e depois `python3 cam2kml.py PASTA`. Depois de instalado, `cam2kml --version` e `python3 -m cam2kml --version` funcionam.

## Início rápido

1. **Crie a configuração.** A primeira execução cria `~/.config/cam2kml/config.ini` com valores padrão. Edite-o (veja [Configuração](#configuração)) ou crie-o à mão.
2. **Prepare a pasta de recursos** (`pasta_recursos`): coloque nela o KML de estilo e os ícones (veja [Estilo e recursos](#estilo-e-recursos)).
3. **Sirva suas fotos** com qualquer servidor web cuja raiz seja a pasta raiz das fotos, por exemplo:
   ```bash
   cd /data/photosync && python3 -m http.server 8080
   ```
4. **Gere o KMZ** de um álbum:
   ```bash
   cam2kml "/data/photosync/Samsung SM-G935F/Camera"
   ```
   Isso cria `<pasta_saida>/Samsung SM-G935F - Camera.kmz` e atualiza `<pasta_saida>/index.kml`.
5. **Abra no Google Earth**: abra o KMZ diretamente, ou abra o índice por um link de rede (por exemplo `http://localhost:8080/output_kmz/index.kml`, quando `pasta_saida` está dentro da pasta servida).

## Como as pastas são usadas

```
/data/photosync/                 <- raiz ("raiz"): URLs e nomes de álbum são relativos a ela
├── recursos/                    <- pasta_recursos: estilo + ícones, copiados para todo KMZ
│   ├── estilos03.kml
│   └── camera.png
├── output_kmz/                  <- pasta_saida: KMZ gerados e index.kml
│   ├── index.kml
│   ├── Samsung SM-G935F - Camera.kmz
│   └── Viagem X - Samsung SM-G990E - Camera.kmz
├── Samsung SM-G935F/
│   └── Camera/                  <- álbum: as fotos ficam diretamente aqui
│       ├── 20230907_115442.jpg
│       └── trilha.kml           <- opcional: vira um ponto com link clicável
└── Viagem X/
    └── Samsung SM-G990E/
        └── Camera/
```

| Pasta | Função |
|---|---|
| **Álbum** (a `PASTA` que você informa) | Contém as fotos. Só os arquivos diretamente dentro dela são lidos; subpastas **não** são percorridas. Arquivos `*.kml` ou `*.kmz` dentro dela viram pontos com um link para o arquivo. |
| **Raiz** (`--raiz`) | A pasta que corresponde à raiz do servidor web (ou à pasta base do modo `file`). Por padrão é a pasta pai mais próxima chamada `photosync`; se não houver, o próprio álbum. A URL de uma foto é montada a partir do caminho dela relativo à raiz. |
| **`pasta_saida`** | Onde `<álbum>.kmz` e `index.kml` são gravados. Pode ficar em qualquer lugar, inclusive dentro da raiz. Se ficar vazia, é gravado um `<pasta>.kml` simples dentro da pasta do álbum (sem KMZ, sem índice e sem recursos). |
| **`pasta_recursos`** | Tudo o que está nela vai para a raiz de cada KMZ (o KML de estilo e os ícones). Arquivos ocultos, arquivos `*.kmz` e um arquivo chamado `doc.kml` são ignorados, e ela pode ter no máximo 500 arquivos (uma proteção contra apontá-la para uma pasta de fotos por engano). |

**Nome do álbum.** É o caminho do álbum relativo à raiz, unido por ` - `. `photosync/sample01` vira `sample01`, e `photosync/Viagem X/Samsung SM-G990E/Camera` vira `Viagem X - Samsung SM-G990E - Camera`. O nome é usado no arquivo KMZ, no nome do documento exibido no Google Earth e na entrada do índice. Se o álbum estiver fora da raiz (ou for a própria raiz), usa-se só o nome da pasta.

## Configuração

Arquivo: `~/.config/cam2kml/config.ini` (no Windows: `%USERPROFILE%\.config\cam2kml\config.ini`), seção `[geral]`. Chaves ausentes usam os valores padrão abaixo.

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

| Chave | Padrão | Significado |
|---|---|---|
| `metodo_protocolo` | `http` | `http`, `https` ou `file`. |
| `servidor_host` | `localhost:8080` | `host[:porta]` para `http`/`https`. Para `file`, a **pasta local absoluta** que corresponde à raiz das fotos. |
| `pasta_raiz` | `/` | Prefixo opcional colocado entre o host e o caminho relativo da foto. |
| `pasta_saida` | `~/tmp` | Pasta de saída dos KMZ e do `index.kml`. Vazia = grava `<pasta>.kml` na pasta do álbum. |
| `pasta_recursos` | `recursos` | Pasta empacotada em todo KMZ. Use um **caminho absoluto**: um relativo é resolvido a partir da pasta onde você roda o comando. |
| `estilo_url` | `estilos03.kml#estiloCustomizado` | Estilo usado pelos pontos das fotos, no formato `<arquivo em pasta_recursos>#<id do estilo>`. |
| `icone_kml` | `globe-connected.png` | Ícone dos pontos que linkam outros arquivos `.kml`/`.kmz`. A URL dele é montada como a das fotos, então ele precisa estar acessível em `<host>/<pasta_raiz>/<icone_kml>`. |
| `diretorio_thumb`, `qualidade_imagem` | `thumb`, `85` | Reservadas para uma futura função de miniaturas. Hoje não são usadas. |

**Como a URL da foto é montada:** `<metodo_protocolo>://<servidor_host>/<pasta_raiz>/<caminho relativo à raiz>`, com espaços e caracteres especiais codificados. Por exemplo, com os valores padrão, `/data/photosync/Viagem X/a.jpg` vira `http://localhost:8080/Viagem%20X/a.jpg`.

**Use um host que os outros computadores alcancem.** `localhost` é o computador que abre o KMZ. Se você compartilhar o KMZ ou abri-lo em outra máquina, ponha em `servidor_host` um nome ou endereço que essa máquina alcance (por exemplo `192.168.0.10:8080`) e gere o KMZ de novo.

**Modo local (`metodo_protocolo = file`).** Com `servidor_host = /data/photosync`, os links viram `file:///data/photosync/...` e tudo fica no computador, sem servidor web. O KMZ então só funciona na máquina que tem os arquivos, e clientes desktop podem restringir imagens locais em balões. Este modo foi menos testado que o `http`.

## Opções de linha de comando

```
cam2kml [opções] [PASTA]
```

| Opção | Significado |
|---|---|
| `PASTA` | Pasta do álbum com as fotos. Padrão: o diretório atual. Não é recursiva. |
| `-o ARQUIVO`, `--saida ARQUIVO` | Arquivo de saída, `.kml` ou `.kmz`. Tem prioridade sobre `pasta_saida`; o índice **não** é atualizado. |
| `-r DIR`, `--raiz DIR` | Raiz usada para URLs e nomes de álbum. Padrão: a pasta pai mais próxima chamada `photosync`, senão o próprio álbum. |
| `--sem-gps {anterior,padrao,pular}` | O que fazer com fotos sem GPS. `anterior` (padrão): usa a posição da última foto que tinha GPS, na ordem dos nomes de arquivo (a posição fixa padrão, se ainda não houve nenhuma). `padrao`: usa a posição fixa padrão (lon -52.225732, lat -3.203054). `pular`: deixa a foto de fora. |
| `--nome {arquivo,data,ambos}` | Rótulo de cada ponto: `arquivo` (padrão) = nome do arquivo sem extensão, `data` = data do EXIF, `ambos` = data e nome do arquivo. |
| `--sem-indice` | Não atualiza o `index.kml` depois de criar o KMZ. |
| `--so-indice` | Apenas recria o `index.kml` a partir dos KMZ que já estão em `pasta_saida`. Nenhuma foto é processada e `PASTA` é ignorada. Não pode ser combinada com `--sem-indice`. |
| `-V`, `--version` | Mostra a versão. |
| `-h`, `--help` | Mostra a ajuda. |

Os nomes das opções estão em português: `saida` = saída, `raiz` = raiz, `sem-gps` = sem GPS, `nome` = nome, `sem-indice` = sem índice, `so-indice` = só o índice.

Códigos de saída: `0` em caso de sucesso (inclusive para pastas sem fotos), `1` para erros de configuração ou de uso.

## Estilo e recursos

Cada ponto de foto usa o estilo indicado em `estilo_url`. O estilo é um arquivo KML comum, que você guarda em `pasta_recursos`. No texto do balão você pode usar estas variáveis:

| Variável | Conteúdo |
|---|---|
| `$[name]` | Rótulo do ponto (veja `--nome`). |
| `$[foto_url]` | URL da foto original. |
| `$[camera]` | Marca e modelo da câmera, ou `desconhecida`. |
| `$[data]` | Data do EXIF, ou a data de modificação do arquivo quando não há. |
| `$[isize]` | Tamanho da imagem, como `4000x1848`. |

Exemplo mínimo (`recursos/estilos03.kml`):

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
          <p><b>Câmera:</b> $[camera] &nbsp; <b>Data:</b> $[data] &nbsp; <b>Tamanho:</b> $[isize]</p>
        ]]></text>
      </BalloonStyle>
    </Style>
  </Document>
</kml>
```

Todos os recursos vão para a **raiz** do KMZ, então as referências a ícones devem ser nomes de arquivo simples (`camera.png`), nunca `../icons/camera.png`.

## O índice

O `index.kml` fica em `pasta_saida` e tem um link de rede para cada `*.kmz` dessa pasta, em ordem de nome. Os links são relativos, então funcionam de onde o índice for aberto (disco ou servidor web), desde que os KMZ continuem ao lado dele. O índice é refeito a partir do que realmente existe na pasta, então rodar de novo nunca duplica entradas, e apagar um KMZ e rodar `cam2kml --so-indice` remove o link dele.

## Processando muitas pastas

O comando trata um álbum por vez. Para uma coleção inteira, percorra as pastas e refaça o índice uma única vez no final:

```bash
find /data/photosync -mindepth 1 -type d \
     -not -path '*/output_kmz*' -not -path '*/recursos*' -print0 |
  while IFS= read -r -d '' dir; do
    cam2kml --sem-indice "$dir"
  done
cam2kml --so-indice
```

Pastas sem fotos só imprimem uma linha informativa e não criam nada.

## Solução de problemas

- **As fotos não aparecem no balão.** A URL da foto precisa ser alcançável a partir do computador que roda o Google Earth. Confira `servidor_host` (não use `localhost` para outras máquinas), a raiz do servidor web e `pasta_raiz`.
- **O balão não tem o visual personalizado ou falta o ícone.** O KMZ está sem estilo. Confira se `pasta_recursos` é um caminho absoluto, se contém o arquivo citado em `estilo_url` e se os ícones são referenciados sem `../`. A ferramenta avisa quando `pasta_recursos` não resulta em nenhum arquivo.
- **Os pontos se acumulam num único lugar.** Essas fotos não têm GPS. Use `--sem-gps pular` para deixá-las de fora.
- **Uma foto muito grande deixa o balão lento.** O balão carrega o arquivo original. Miniaturas ainda não são geradas.
- **Só `.jpg`, `.jpeg` e `.png` são lidos.** Outros formatos (HEIC, vídeos) não são suportados.

## Licença

GNU General Public License, versão 2 ou (a seu critério) qualquer versão posterior. Veja [LICENSE](LICENSE). Copyright 2026 Renato Lins.
