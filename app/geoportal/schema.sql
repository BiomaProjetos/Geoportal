-- Geoportal Bioma — esquema do banco (PostgreSQL 16 + PostGIS 3)
-- Pode ser executado várias vezes: só cria o que ainda não existe.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS bases;

-- Usuários da equipe
CREATE TABLE IF NOT EXISTS usuarios (
  id          serial PRIMARY KEY,
  email       text UNIQUE NOT NULL,
  nome        text NOT NULL,
  senha_hash  text NOT NULL,
  perfil      text NOT NULL DEFAULT 'analista' CHECK (perfil IN ('admin','analista')),
  ativo       boolean NOT NULL DEFAULT true,
  criado_em   timestamptz NOT NULL DEFAULT now()
);

-- Imóveis: carteira da Bioma e prospecção
CREATE TABLE IF NOT EXISTS imoveis (
  car           text PRIMARY KEY,
  nome          text,
  municipio     text,
  proprietario  text,
  situacao      text NOT NULL DEFAULT 'Aguardando análise',
  origem        text NOT NULL DEFAULT 'Prospecção' CHECK (origem IN ('Carteira Bioma','Prospecção')),
  analista      text,
  observacoes   text,
  pct_rl        numeric,            -- percentual de RL definido manualmente (sobrepõe o RADAM)
  area_ha       numeric,
  geom          geometry(MultiPolygon, 4674),
  triagem       jsonb,              -- último resultado da triagem
  triagem_em    timestamptz,
  criado_em     timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS imoveis_geom_idx ON imoveis USING gist (geom);

-- Camadas do próprio imóvel vindas do Simcar (APP, ARL, AVN, área consolidada...)
CREATE TABLE IF NOT EXISTS imovel_camadas (
  id     serial PRIMARY KEY,
  car    text NOT NULL REFERENCES imoveis(car) ON DELETE CASCADE ON UPDATE CASCADE,
  tipo   text NOT NULL,
  attrs  jsonb,
  geom   geometry(Geometry, 4674)
);
CREATE INDEX IF NOT EXISTS imovel_camadas_geom_idx ON imovel_camadas USING gist (geom);
CREATE INDEX IF NOT EXISTS imovel_camadas_car_idx ON imovel_camadas (car, tipo);

-- Catálogo das bases de referência carregadas (cada base vira a tabela bases.<slug>)
CREATE TABLE IF NOT EXISTS bases.catalogo (
  slug        text PRIMARY KEY,
  arquivo     text,
  feicoes     integer,
  versao_em   timestamptz NOT NULL DEFAULT now()
);

-- Módulo fiscal por município (hectares), para a regra de até 4 MF
CREATE TABLE IF NOT EXISTS modulo_fiscal (
  municipio   text PRIMARY KEY,     -- nome normalizado: maiúsculas, sem acento
  ha          numeric NOT NULL
);

-- Registro de consultas (quem buscou o quê e quando)
CREATE TABLE IF NOT EXISTS consultas (
  id        bigserial PRIMARY KEY,
  usuario   text,
  car       text,
  acao      text,
  em        timestamptz NOT NULL DEFAULT now()
);
