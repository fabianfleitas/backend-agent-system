-- Limpieza del seed de QA (docs/qa/seed_qa.sql).
-- Elimina los datos de prueba creados con identificadores fijos 'qa-miembro-unico'
-- y las instituciones 'QA-INST-A' / 'QA-INST-B'. El borrado de instituciones
-- elimina en cascada sus membresías.

DELETE FROM institucion_miembros WHERE external_auth_id = 'qa-miembro-unico';
DELETE FROM instituciones WHERE codigo IN ('QA-INST-A', 'QA-INST-B');
DELETE FROM app_users WHERE external_auth_id = 'qa-miembro-unico';
