-- Seed para conectar price existente (Opción A).
-- Usar institución existente (id=1: Universidad de Prueba A) o crear una nueva.
-- Nota: el campo 'intervalo' en esta DB tiene una restricción de check;
-- si falla, consultar el valor permitido (probablemente 'monthly' / 'year').

-- Institución (usar existente 1 para evitar duplicar; si se crea nueva, actualizar INST_ID en test)
-- INSERT INTO instituciones (nombre, activo) VALUES ('Inst Stripe Test', true) RETURNING id;

-- Plan con tu price/product existentes (Opción A: checkout usa directo)
INSERT INTO planes (codigo, nombre, precio, moneda, intervalo, activo,
                    stripe_product_id, stripe_price_id)
VALUES ('basico-stripe', 'Plan Básico', 1200000, 'PYG', 'MONTH', true,
        'prod_V9UwUlAKdmtofv', 'price_1U9BwkHVmTPbjjVgOf7GIprr')
RETURNING id;
