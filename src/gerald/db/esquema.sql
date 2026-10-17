-- Esquema PostgreSQL de Gerald Sport. Los checkpoints de LangGraph los crea PostgresSaver.setup().

-- ===================== Pedidos =====================
CREATE TABLE IF NOT EXISTS pedidos (
    pedido_id          TEXT PRIMARY KEY,
    cliente_id         TEXT NOT NULL,
    clave_idempotencia CHAR(64) NOT NULL UNIQUE,
    carga              JSONB NOT NULL,
    estado             TEXT NOT NULL DEFAULT 'recibido',
    creado_en          TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos (estado, actualizado_en);

CREATE TABLE IF NOT EXISTS contratos (
    pedido_id       TEXT PRIMARY KEY REFERENCES pedidos(pedido_id),
    calculo         JSONB NOT NULL,
    costo_total_pen NUMERIC(12,2) NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===================== Colas (carga completa para reproceso) =====================
CREATE TABLE IF NOT EXISTS cola_pendientes (
    id          BIGSERIAL PRIMARY KEY,
    pedido_id   TEXT NOT NULL UNIQUE,
    carga       JSONB NOT NULL,
    motivo      TEXT NOT NULL,
    reprocesos  INT NOT NULL DEFAULT 0,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===================== Almacén de materiales (proveedores) =====================
CREATE TABLE IF NOT EXISTS materiales (
    material_id         TEXT PRIMARY KEY,
    nombre              TEXT NOT NULL,
    tipo                TEXT NOT NULL CHECK (tipo IN ('tela','insumo')),
    unidad              TEXT NOT NULL CHECK (unidad IN ('m','m2','kg','und')),
    precio_unitario_pen NUMERIC(12,2) NOT NULL CHECK (precio_unitario_pen >= 0),
    activo              BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS recetas (
    prenda      TEXT NOT NULL,
    talla       TEXT NOT NULL,
    material_id TEXT NOT NULL REFERENCES materiales(material_id),
    cantidad    NUMERIC(10,3) NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (prenda, talla, material_id)
);

CREATE TABLE IF NOT EXISTS inventario (
    material_id TEXT PRIMARY KEY REFERENCES materiales(material_id),
    disponible  NUMERIC(12,3) NOT NULL CHECK (disponible >= 0),
    reservado   NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (reservado >= 0)
);

CREATE TABLE IF NOT EXISTS reservas (
    pedido_id   TEXT NOT NULL,
    material_id TEXT NOT NULL REFERENCES materiales(material_id),
    cantidad    NUMERIC(12,3) NOT NULL,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (pedido_id, material_id)
);

CREATE TABLE IF NOT EXISTS requerimientos_abastecimiento (
    id             BIGSERIAL PRIMARY KEY,
    pedido_id      TEXT NOT NULL,
    material_id    TEXT NOT NULL REFERENCES materiales(material_id),
    faltante       NUMERIC(12,3) NOT NULL,
    estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','atendido')),
    fecha_estimada DATE,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===================== Parámetros, calibración y auditoría =====================
CREATE TABLE IF NOT EXISTS parametros (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS etiquetas_calibracion (
    id        BIGSERIAL PRIMARY KEY,
    pedido_id TEXT NOT NULL,
    etiqueta  JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auditoria (
    id        BIGSERIAL PRIMARY KEY,
    actor     TEXT NOT NULL,
    accion    TEXT NOT NULL,
    pedido_id TEXT,
    detalle   JSONB NOT NULL DEFAULT '{}',
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===================== Mínimo privilegio (P07) =====================
-- Ejecutar como superusuario una sola vez:
-- CREATE ROLE gerald_app LOGIN PASSWORD '***';
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO gerald_app;
-- GRANT DELETE ON cola_pendientes TO gerald_app;                -- limpiar pedidos recuperados
-- REVOKE UPDATE, DELETE ON auditoria FROM gerald_app;           -- auditoría solo inserción
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO gerald_app;
