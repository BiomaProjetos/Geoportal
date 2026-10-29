# Geoportal Bioma

Geoportal interno da **Bioma Soluções Agroambientais** para consultar os SIMCARs da carteira e triar CARs de prospecção.
A partir do perímetro do CAR, o sistema cruza o imóvel com as bases de referência e mostra, numa ficha:

- embargos (SEMA-MT, SIGA, IBAMA, ICMBio) e alertas (MapBiomas, DETER);
- desmatamento PRODES ano a ano, separando antes e depois de 22/07/2008;
- área consolidada declarada × base de uso consolidado da SEMA-MT;
- percentual e saldo de Reserva Legal (fitofisionomia RADAM, AVN e APP do CAR, art. 15 e art. 67);
- georreferenciamento (SIGEF/SNCI) e diferença de área com o CAR;
- sobreposição com outros CARs, TI, UC, assentamentos e florestas públicas;
- glebas de crédito rural do Sicor sobre o imóvel, com alerta quando tocam desmate pós-2008 ou embargo.

Funciona no computador e no celular (pode ser instalado na tela inicial e mostra a posição do GPS no mapa).

> A triagem é preliminar, feita por geoprocessamento. Não substitui a análise do analista nem a validação da SEMA-MT.

---

## 1. O que você precisa

| Item | Recomendação |
| --- | --- |
| VPS | Ubuntu 24.04, 4 vCPU, 8 GB de RAM, 160 GB de SSD (cresce com as bases estaduais) |
| Endereço | Um subdomínio, ex.: `geo.solucoesagroambientais.com`, com registro **A** apontando para o IP da VPS |
| Acesso | SSH na VPS (no Windows: PowerShell `ssh root@IP` ou o PuTTY) e WinSCP para copiar arquivos |

## 2. Instalação (uma vez)

```bash
ssh root@IP_DA_VPS
git clone https://github.com/BiomaProjetos/Geoportal.git /opt/geoportal
cd /opt/geoportal
bash install.sh
```

Se o repositório estiver privado, o `git clone` pede usuário e um *token* do GitHub
(GitHub → Settings → Developer settings → Personal access tokens, permissão só de leitura no repositório).

O instalador:

1. instala o Docker (se faltar);
2. pergunta o endereço do geoportal e gera o `.env` com senhas novas;
3. sobe o banco PostGIS, a aplicação e o HTTPS automático (Caddy + Let's Encrypt);
4. agenda o backup diário (2h30) e a retriagem da carteira (segunda, 5h).

Depois crie o seu usuário de administrador (a senha é pedida na tela, mínimo de 10 caracteres):

```bash
docker compose exec app python -m geoportal criar-usuario seu@email.com "Seu Nome" --admin
```

Abra `https://geo.solucoesagroambientais.com` e entre. Os demais usuários você cria pela tela **Equipe**.

## 3. Importar as bases de referência

Copie os arquivos para `/opt/geoportal/dados/bases/` (WinSCP) com o **nome do arquivo começando pelo slug** da camada.
Pode ser `.zip` com shapefile, `.shp` (com `.dbf`, `.shx`, `.prj`, `.cpg` ao lado), `.gpkg` ou `.geojson`.
Vários arquivos com o mesmo slug entram juntos na mesma camada (ex.: `prodes_amazonia.zip` e `prodes_cerrado.zip`).

```bash
bash scripts/importar-bases.sh                 # importa tudo, recalcula a triagem e lista as bases
bash scripts/importar-bases.sh --encoding latin1   # se acentos aparecerem errados
```

| Slug | Camada | De onde vem |
| --- | --- | --- |
| `embargo_sema` | Embargos SEMA-MT | Geoportal SEMA-MT |
| `embargo_siga` | Área embargada SIGA | Geoportal SEMA-MT |
| `embargo_ibama` | Embargos IBAMA | Dados abertos do IBAMA |
| `embargo_icmbio` | Embargos ICMBio | Dados abertos do ICMBio |
| `auto_infracao_sema` | Autos de infração | Geoportal SEMA-MT |
| `mapbiomas_alerta` | Alertas MapBiomas | MapBiomas Alerta |
| `prodes` | PRODES Amazônia e Cerrado | INPE / TerraBrasilis |
| `deter` | DETER | INPE / TerraBrasilis |
| `uso_consolidado` | Uso consolidado | Geoportal SEMA-MT (BASES GERAL do QGIS) |
| `radam` | RADAM Brasil (campo `FITOECOLOG`) | SEMA-MT / IBGE |
| `arl_lau` | ARL averbada LAU | Geoportal SEMA-MT |
| `autorizacao_desmate` | Autorizações de desmate | Geoportal SEMA-MT |
| `terra_indigena`, `ti_entorno` | TI e entorno de 10 km | SEMA-MT / FUNAI |
| `unidade_conservacao`, `uc_amortecimento` | UC e zona de amortecimento | SEMA-MT / ICMBio |
| `assentamento`, `quilombola` | Assentamentos e quilombolas | INCRA / INTERMAT |
| `floresta_publica` | CNFP | Serviço Florestal Brasileiro |
| `sigef`, `snci` | Parcelas certificadas | INCRA (acervo fundiário) |
| `car_estadual`, `sicar_federal` | CAR de outros imóveis | SEMA-MT / SFB |
| `sicor_glebas` | Glebas de crédito rural | Banco Central (microdados do Sicor) |

**Antes de importar**, confira no QGIS os nomes dos campos que a triagem usa e ajuste em `app/geoportal/camadas.yaml`:
`campo_ano` do PRODES (padrão `year`), `campo_fito` do RADAM (`FITOECOLOG`), `campo_codigo` do SIGEF/SNCI/CAR e
`campos_custeio` do Sicor. Nomes cortados em 10 caracteres pelo shapefile (ex.: `NUMEROESTA`) são reconhecidos.
Depois de mudar o `camadas.yaml`: `docker compose restart app`.

**Módulos fiscais** (regra de até 4 MF): monte um CSV `municipio;ha` com os municípios de MT e rode

```bash
docker compose exec app python -m geoportal importar-mf /dados/modulo_fiscal.csv
```

## 4. Cadastrar CARs

Pela tela: **Importar CAR** → escolha o `.zip` exportado do Geoportal SEMA (ou um KML/KMZ do perímetro).
O sistema reconhece pelo nome de cada arquivo dentro do zip o perímetro (ATP), APP, ARL, AVN, área consolidada, AUAS e hidrografia
(regras em `imovel_tipos` no `camadas.yaml`). Se o número do CAR não vier nos atributos, informe no formulário.

Pela linha de comando (vários de uma vez):

```bash
for f in dados/cars/*.zip; do docker compose exec -T app python -m geoportal importar-car "/dados/cars/$(basename "$f")" --carteira; done
```

## 5. Fase 2 — busca automática na SEMA-MT

Fica **desligada** até confirmar com a SEMA-MT o uso automatizado da authkey. Para ligar, preencha no `.env`
`SEMA_WFS_URL` e `SEMA_AUTHKEY` (estão no `wfsrequest.txt` dentro de qualquer exportação SHP do Geoportal) e rode
`docker compose up -d`. A authkey fica só no servidor; o navegador nunca a vê.
Com a busca ligada, digitar um CAR que não está na carteira faz o servidor baixá-lo da SEMA e triar.

## 6. Rotina e manutenção

| Tarefa | Comando |
| --- | --- |
| Ver as bases e a data de cada uma | `docker compose exec app python -m geoportal bases` |
| Recalcular a triagem de todos | `docker compose exec app python -m geoportal retriar` |
| Backup agora | `bash scripts/backup.sh` (cópias em `backups/`, 14 dias) |
| Restaurar backup | `bash scripts/restaurar.sh backups/geoportal-AAAA-MM-DD.dump` |
| Atualizar o sistema | `git pull && docker compose up -d --build` |
| Ver erros | `docker compose logs -f app` |

Copie a pasta `backups/` para fora da VPS com frequência (Google Drive, HD externo).

## 7. Segurança

- Só entra quem tem usuário criado pelo administrador; a sessão expira em 12 h (`SESSAO_HORAS`).
- Senhas guardadas com bcrypt; 8 tentativas erradas bloqueiam o IP por 5 minutos.
- HTTPS obrigatório; o `.env` (senhas e authkey) nunca vai para o GitHub (`.gitignore`).
- Cada consulta e importação fica registrada na tabela `consultas` (usuário, CAR, data).
- LGPD: dados de proprietários de CARs de prospecção que não virarem contrato devem ser apagados no prazo definido pela Bioma
  (administrador pode apagar o imóvel pela API `DELETE /api/imovel?car=…`).

## 8. Desenvolvimento e testes

```bash
cd app
pip install -r requirements.txt pytest httpx
python tests/gerar_exemplo.py /tmp/exemplo              # dados fictícios
export DATABASE_URL=postgresql://geoportal:SENHA@localhost:5432/geoportal SEGREDO_JWT=$(openssl rand -hex 32) COOKIE_SEGURO=0
python -m geoportal migrar
python -m geoportal importar-pasta /tmp/exemplo/bases
for f in /tmp/exemplo/cars/*.zip; do python -m geoportal importar-car $f; done
pytest tests/
uvicorn geoportal.main:app --reload
```

Estrutura: `app/geoportal/` (API FastAPI, triagem em PostGIS, importadores, `static/` com a interface),
`docker-compose.yml` (PostGIS 16 + app + Caddy), `scripts/` (backup, restauração, importação).
