-- Alineación de checks de estado con la migración 001 y el código de la app (Opción A)
ALTER TABLE suscripciones DROP CONSTRAINT IF EXISTS suscripciones_estado_check;
ALTER TABLE suscripciones ADD CONSTRAINT suscripciones_estado_check
  CHECK (estado IN ('TRIAL','ACTIVE','PENDING_PAYMENT','SUSPENDED','CANCELLED','EXPIRED'));

ALTER TABLE pagos DROP CONSTRAINT IF EXISTS pagos_estado_check;
ALTER TABLE pagos ADD CONSTRAINT pagos_estado_check
  CHECK (estado IN ('PENDING','COMPLETED','FAILED','REFUNDED'));

ALTER TABLE comprobantes DROP CONSTRAINT IF EXISTS comprobantes_estado_check;
ALTER TABLE comprobantes ADD CONSTRAINT comprobantes_estado_check
  CHECK (estado IN ('PENDING','COMPLETED','FAILED','REFUNDED'));
