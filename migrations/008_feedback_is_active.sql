-- 008_feedback_is_active.sql
-- Moderación de feedback: marcar feedback como inactivo (oculto) en lugar de borrarlo.
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;