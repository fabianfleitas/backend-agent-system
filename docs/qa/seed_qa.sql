-- QA seed: Institución A (1) vs B (2) para prueba manual cross-tenant
INSERT INTO instituciones (codigo, nombre, activo) VALUES
('INST-A', 'Institución A', true),
('INST-B', 'Institución B', true)
ON CONFLICT (codigo) DO NOTHING;

-- Usuarios de prueba (ya deben existir en auth.users; aquí solo app_users y membresías)
-- Ajustar external_auth_id real según los JWT de prueba disponibles
INSERT INTO app_users (external_auth_id, email, role, full_name, is_active)
VALUES ('qa-admin-a', 'a@test', 'STUDENT', 'Admin A', true),
       ('qa-stud-a', 'a-stud@test', 'STUDENT', 'Student A', true),
       ('qa-admin-b', 'b@test', 'STUDENT', 'Admin B', true)
ON CONFLICT (external_auth_id) DO NOTHING;

-- Membresías únicas (una por usuario)
INSERT INTO institucion_miembros (institucion_id, external_auth_id, tipo_miembro, activo)
VALUES (1, 'qa-admin-a', 'ADMIN', true),
       (1, 'qa-stud-a', 'ESTUDIANTE', true),
       (2, 'qa-admin-b', 'ADMIN', true)
ON CONFLICT DO NOTHING; -- si hay restricción parcial, no duplicar

-- Documentos exclusivos por institución (meta solo; archivos reales por carga manual)
-- Nota: los documentos requieren versión activa y chunks si se quiere probar RAG
