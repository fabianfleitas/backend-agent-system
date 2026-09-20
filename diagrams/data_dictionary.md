# Diccionario de Datos — backend-agent-system (tables.sql)

---

## Nombre de la tabla o colección: app_users

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de identificación del usuario |
| external_auth_id | text | UK | - | Identificador de autenticación externa (Supabase Auth) |
| email | text | NOT NULL | - | Correo electrónico del usuario |
| full_name | text | - | - | Nombre completo del usuario |
| role | user_role | NOT NULL | - | Rol del usuario (STUDENT por defecto) |
| is_active | boolean | NOT NULL | - | Estado activo del usuario |
| created_at | timestamptz | NOT NULL | - | Fecha de creación del registro |
| updated_at | timestamptz | NOT NULL | - | Fecha de última actualización |

---

## Nombre de la tabla o colección: instituciones

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la institución |
| nombre | text | NOT NULL | - | Nombre oficial de la institución |
| nombre_comercial | text | - | - | Nombre comercial / marca |
| codigo | text | UK | - | Código único institucional |
| email_contacto | text | - | - | Correo de contacto |
| telefono_contacto | text | - | - | Teléfono de contacto |
| direccion | text | - | - | Dirección física |
| ciudad | text | - | - | Ciudad de ubicación |
| pais | text | - | - | País (default Paraguay) |
| activo | boolean | NOT NULL | - | Estado activo de la institución |
| stripe_customer_id | text | UK | - | ID del cliente en Stripe |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |

---

## Nombre de la tabla o colección: institucion_miembros

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del miembro |
| institucion_id | bigint | FK | 10 | Institución a la que pertenece |
| external_auth_id | text | FK | - | Usuario asociado (Supabase Auth) |
| tipo_miembro | text | NOT NULL | - | Rol dentro de la institución (ADMIN, SECRETARIA, ESTUDIANTE, STUDENT) |
| activo | boolean | NOT NULL | - | Estado activo del miembro |
| fecha_ingreso | timestamptz | NOT NULL | - | Fecha de ingreso a la institución |
| fecha_salida | timestamptz | - | - | Fecha de salida (si aplica) |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |

---

## Nombre de la tabla o colección: platform_admins

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del admin global |
| external_auth_id | text | UK / FK | - | Usuario de referencia (app_users) |
| is_active | boolean | NOT NULL | - | Estado activo del administrador |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |

---

## Nombre de la tabla o colección: categorias

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la categoría |
| nombre | text | UK / NOT NULL | - | Nombre único de la categoría |
| descripcion | text | - | - | Descripción de la categoría |
| activo | boolean | NOT NULL | - | Estado activo |
| institucion_id | bigint | FK | 10 | Institución que pertenece (aislamiento) |
| orden | integer | - | - | Orden de presentación |
| fecha_creacion | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |
| fecha_baja | timestamptz | - | - | Fecha de baja lógica (si aplica) |

---

## Nombre de la tabla o colección: documentos

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del documento |
| categoria_id | bigint | FK | 10 | Categoría de clasificación |
| codigo_documento | text | UK | - | Código único del documento |
| titulo | text | NOT NULL | - | Título del documento |
| descripcion | text | - | - | Descripción del documento |
| activo | boolean | NOT NULL | - | Estado activo |
| institucion_id | bigint | FK | 10 | Institución propietaria |
| fecha_creacion | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |

---

## Nombre de la tabla o colección: documento_versiones

| Nombre del campo | Tipo dedato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la versión |
| documento_id | bigint | FK / NOT NULL | 10 | Documento al que pertenece |
| numero_version | integer | NOT NULL | - | Número secuencial de versión |
| ruta_archivo | text | NOT NULL | - | Ruta del archivo almacenado |
| storage_bucket | text | NOT NULL | - | Bucket de almacenamiento (default documents) |
| original_filename | text | - | - | Nombre original del archivo |
| mime_type | text | NOT NULL | - | Tipo MIME (default application/pdf) |
| file_size_bytes | bigint | - | - | Tamaño del archivo en bytes |
| status | document_status | NOT NULL | - | Estado (PENDING, READY, etc.) |
| es_version_activa | boolean | NOT NULL | - | Indica si es la versión activa |
| texto_extraido | text | - | - | Texto extraído del documento |
| total_chunks | integer | NOT NULL | - | Cantidad total de chunks |
| embedding_model | text | - | - | Modelo usado para embeddings |
| indexed_at | timestamptz | - | - | Fecha de indexación |
| error_message | text | - | - | Mensaje de error si falló |
| fecha_carga | timestamptz | NOT NULL | - | Fecha de carga del archivo |
| cargado_por_external_auth_id | text | FK | - | Usuario que cargó (app_users.external_auth_id) |
| updated_at | timestamptz | NOT NULL | - | Fecha de actualización |

---

## Nombre de la tabla o colección: document_chunks

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del chunk |
| documento_version_id | bigint | FK / NOT NULL | 10 | Versión del documento |
| chunk_index | integer | NOT NULL | - | Índice del chunk |
| page_number | integer | - | - | Número de página (si aplica) |
| chunk_text | text | NOT NULL | - | Texto del chunk |
| token_count | integer | - | - | Cantidad de tokens |
| created_at | timestamptz | NOT NULL | - | Fecha de creación |

---

## Nombre de la tabla o colección: document_embeddings

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del embedding |
| chunk_id | bigint | FK / NOT NULL | 10 | Chunk asociado |
| embedding | embedding | NOT NULL | - | Vector de embedding (tipo definido por usuario) |
| embedding_model | text | NOT NULL | - | Modelo utilizado |
| created_at | timestamptz | NOT NULL | - | Fecha de creación |

---

## Nombre de la tabla o colección: conversaciones

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la conversación |
| external_auth_id | text | FK / NOT NULL | - | Usuario creador (app_users) |
| title | text | NOT NULL | - | Título de la conversación |
| hidden | boolean | NOT NULL | - | Oculta (false por defecto) |
| last_interaction | timestamptz | - | - | Última interacción registrada |
| fecha_creacion | timestamptz | NOT NULL | - | Fecha de creación |
| updated_at | timestamptz | NOT NULL | - | Fecha de actualización |
| institucion_id | bigint | FK | 10 | Institución asociada |

---

## Nombre de la tabla o colección: mensajes

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del mensaje |
| conversacion_id | bigint | FK / NOT NULL | 10 | Conversación a la que pertenece |
| external_auth_id | text | FK | - | Usuario emisor (app_users) |
| rol_mensaje | message_role | NOT NULL | - | Rol del mensaje (USER, ASSISTANT, etc.) |
| contenido_texto | text | NOT NULL | - | Contenido textual |
| proveedor_ia | text | - | - | Proveedor de IA usado |
| modelo_ia | text | - | - | Modelo de IA usado |
| temperatura | numeric | - | - | Temperatura de generación |
| tokens_input | integer | - | - | Tokens de entrada |
| tokens_output | integer | - | - | Tokens de salida |
| tiempo_respuesta_ms | integer | - | - | Tiempo de respuesta en ms |
| audit_id | uuid | FK | 36 | Referencia a audit_logs |
| fecha_envio | timestamptz | NOT NULL | - | Fecha de envío |
| contenido_anonimizado | text | - | - | Versión anonimizada |

---

## Nombre de la tabla o colección: audit_logs

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | uuid | PK | 36 | UUID único del registro de auditoría |
| conversacion_id | bigint | FK | 10 | Conversación auditada |
| mensaje_id | bigint | FK | 10 | Mensaje auditado |
| external_auth_id | text | FK | - | Usuario relacionado |
| pregunta_original | text | - | - | Pregunta original |
| pregunta_anonimizada | text | - | - | Versión anonimizada |
| respuesta_texto | text | - | - | Respuesta generada |
| proveedor_ia | text | - | - | Proveedor de IA |
| modelo_ia | text | - | - | Modelo usado |
| embedding_model | text | - | - | Modelo de embeddings usado |
| tokens_input | integer | - | - | Tokens de entrada |
| tokens_output | integer | - | - | Tokens de salida |
| tiempo_respuesta_ms | integer | - | - | Tiempo de respuesta |
| score_fidelidad | numeric | - | - | Score de fidelidad |
| score_relevancia | numeric | - | - | Score de relevancia |
| score_contexto | numeric | - | - | Score de contexto |
| observaciones | text | - | - | Notas de evaluación |
| fecha_evaluacion | timestamptz | NOT NULL | - | Fecha de evaluación |
| institucion_id | bigint | FK | 10 | Institución asociada |

---

## Nombre de la tabla o colección: message_documents

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la referencia |
| mensaje_id | bigint | FK / NOT NULL | 10 | Mensaje que referencia documentos |
| audit_id | uuid | FK | 36 | Auditoría relacionada |
| documento_id | bigint | FK | 10 | Documento mencionado |
| documento_version_id | bigint | FK | 10 | Versión específica |
| chunk_id | bigint | FK | 10 | Chunk recuperado |
| similarity_score | double | - | - | Puntaje de similitud (retrieval) |
| page_number | integer | - | - | Número de página |
| fecha_creacion | timestamptz | NOT NULL | - | Fecha de creación |

---

## Nombre de la tabla o colección: feedback

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del feedback |
| message_id | bigint | FK / NOT NULL | 10 | Mensaje calificado |
| audit_id | uuid | FK | 36 | Registro de auditoría asociado |
| external_auth_id | text | FK | - | Usuario que califica |
| rating | integer | NOT NULL | - | Calificación (1-5) |
| comment | text | - | - | Comentario adicional |
| created_at | timestamptz | NOT NULL | - | Fecha de creación |
| institucion_id | bigint | FK | 10 | Institución asociada |

---

## Nombre de la tabla o colección: audio_interactions

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la interacción de audio |
| conversacion_id | bigint | FK | 10 | Conversación asociada |
| mensaje_id | bigint | FK | 10 | Mensaje asociado |
| external_auth_id | text | FK | - | Usuario relacionado |
| ruta_audio_original | text | - | - | Ruta del archivo de audio original |
| ruta_audio_respuesta | text | - | - | Ruta del audio de respuesta sintetizada |
| transcripcion | text | - | - | Texto transcrito |
| transcription_model | text | - | - | Modelo de transcripción usado |
| duracion_segundos | numeric | - | - | Duración en segundos |
| formato_audio | text | - | - | Formato (mp3, wav, etc.) |
| tamano_bytes | bigint | - | - | Tamaño en bytes |
| fecha_creacion | timestamptz | NOT NULL | - | Fecha de creación |
| institucion_id | bigint | FK | 10 | Institución asociada |

---

## Nombre de la tabla o colección: pii_mappings

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del mapeo PII |
| audit_id | uuid | FK | 36 | Registro de auditoría |
| external_auth_id | text | FK | - | Usuario relacionado |
| token | text | NOT NULL | - | Token anonimizado |
| pii_type | text | NOT NULL | - | Tipo de dato sensible (nombre, DNI, etc.) |
| original_value | text | NOT NULL | - | Valor original (almacenado de forma segura) |
| created_at | timestamptz | NOT NULL | - | Fecha de creación |
| institucion_id | bigint | FK | 10 | Institución |
| expires_at | timestamptz | - | - | Fecha de expiración del token |

---

## Nombre de la tabla o colección: planes

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del plan |
| codigo | text | UK / NOT NULL | - | Código del plan |
| nombre | text | NOT NULL | - | Nombre del plan |
| descripcion | text | - | - | Descripción del plan |
| precio | numeric | NOT NULL | - | Precio del plan (>=0) |
| moneda | bpchar | NOT NULL | - | Moneda (USD por defecto) |
| intervalo | text | NOT NULL | - | Intervalo de facturación (MONTH/YEAR) |
| max_documentos | integer | - | - | Máximo de documentos |
| max_usuarios | integer | - | - | Máximo de usuarios |
| max_estudiantes | integer | - | - | Máximo de estudiantes |
| features | jsonb | NOT NULL | - | Características del plan (JSON) |
| stripe_product_id | text | UK | - | ID de producto en Stripe |
| stripe_price_id | text | UK | - | ID de precio en Stripe |
| activo | boolean | NOT NULL | - | Estado activo |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |

---

## Nombre de la tabla o colección: suscripciones

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la suscripción |
| institucion_id | bigint | FK / NOT NULL | 10 | Institución suscrita |
| plan_id | bigint | FK / NOT NULL | 10 | Plan contratado |
| estado | text | NOT NULL | - | Estado (TRIAL, ACTIVE, etc.) |
| fecha_inicio | timestamptz | - | - | Inicio de la suscripción |
| fecha_vencimiento | timestamptz | - | - | Fecha de vencimiento |
| fecha_cancelacion | timestamptz | - | - | Fecha de cancelación |
| cancelacion_programada | boolean | NOT NULL | - | Indica cancelación futura |
| stripe_subscription_id | text | UK | - | ID de suscripción Stripe |
| stripe_customer_id | text | - | - | ID de cliente Stripe |
| auto_renovacion | boolean | NOT NULL | - | Renovación automática |
| periodo_prueba_inicio | timestamptz | - | - | Inicio del período de prueba |
| periodo_prueba_fin | timestamptz | - | - | Fin del período de prueba |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |
| stripe_price_id | text | - | - | ID de precio Stripe |
| periodo_actual_inicio | timestamptz | - | - | Inicio del período actual |
| periodo_actual_fin | timestamptz | - | - | Fin del período actual |

---

## Nombre de la tabla o colección: suscripcion_historial

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del evento |
| suscripcion_id | bigint | FK / NOT NULL | 10 | Suscripción afectada |
| tipo_evento | text | NOT NULL | - | Tipo (CREATED, ACTIVATED, RENEWED, etc.) |
| plan_anterior_id | bigint | FK | 10 | Plan anterior |
| plan_nuevo_id | bigint | FK | 10 | Plan nuevo |
| estado_anterior | text | - | - | Estado anterior |
| estado_nuevo | text | - | - | Estado nuevo |
| descripcion | text | - | - | Descripción del evento |
| external_auth_id | text | FK | - | Usuario que generó el evento |
| created_at | timestamptz | NOT NULL | - | Fecha del evento |

---

## Nombre de la tabla o colección: pagos

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del pago |
| institucion_id | bigint | FK / NOT NULL | 10 | Institución que paga |
| suscripcion_id | bigint | FK | 10 | Suscripción relacionada |
| importe | numeric | NOT NULL | - | Monto del pago (>=0) |
| moneda | bpchar | NOT NULL | - | Moneda (USD) |
| estado | text | NOT NULL | - | Estado (PENDING, COMPLETED, FAILED, REFUNDED) |
| proveedor | text | NOT NULL | - | Proveedor (STRIPE) |
| stripe_payment_intent_id | text | UK | - | ID de PaymentIntent Stripe |
| stripe_checkout_session_id | text | UK | - | ID de Checkout Session Stripe |
| stripe_charge_id | text | - | - | ID del cargo Stripe |
| idempotency_key | text | UK | - | Clave de idempotencia |
| descripcion | text | - | - | Descripción del pago |
| fecha_pago | timestamptz | - | - | Fecha del pago efectivo |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |
| stripe_invoice_id | text | - | - | ID de factura Stripe |

---

## Nombre de la tabla o colección: stripe_eventos

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del evento |
| stripe_event_id | text | UK / NOT NULL | - | ID del evento en Stripe |
| tipo_evento | text | NOT NULL | - | Tipo de evento Stripe |
| payload | jsonb | NOT NULL | - | Payload completo del evento |
| procesado | boolean | NOT NULL | - | Indicador de procesamiento |
| procesado_at | timestamptz | - | - | Fecha de procesamiento |
| error | text | - | - | Mensaje de error si falló |
| created_at | timestamptz | NOT NULL | - | Fecha de recepción |

---

## Nombre de la tabla o colección: comprobantes

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del comprobante |
| institucion_id | bigint | FK / NOT NULL | 10 | Institución emisión |
| pago_id | bigint | FK | 10 | Pago asociado |
| tipo_comprobante | text | NOT NULL | - | Tipo (CONFIRMACION_PAGO, RECIBO, FACTURA, etc.) |
| numero | text | - | - | Número del comprobante |
| estado | text | NOT NULL | - | Estado del comprobante |
| importe | numeric | - | - | Monto |
| moneda | bpchar | - | - | Moneda (USD) |
| archivo_path | text | - | - | Ruta del archivo |
| proveedor | text | - | - | Proveedor |
| referencia_externa | text | - | - | Referencia externa |
| fecha_emision | timestamptz | - | - | Fecha de emisión |
| created_at | timestamptz | NOT NULL | - | Fecha de creación |

---

## Nombre de la tabla o colección: notificaciones

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de notificación |
| institucion_id | bigint | FK | 10 | Institución destino |
| suscripcion_id | bigint | FK | 10 | Suscripción relacionada |
| tipo | text | NOT NULL | - | Tipo (SUBSCRIPTION_EXPIRING, PAYMENT_SUCCESS, etc.) |
| canal | text | NOT NULL | - | Canal (IN_APP, EMAIL) |
| destinatario | text | NOT NULL | - | Destinatario |
| asunto | text | - | - | Asunto |
| contenido | text | - | - | Contenido |
| estado | text | NOT NULL | - | Estado (PENDING, SENT, FAILED, CANCELED) |
| fecha_programada | timestamptz | - | - | Fecha programada |
| fecha_envio | timestamptz | - | - | Fecha de envío real |
| error | text | - | - | Mensaje de error si falló |
| clave_idempotencia | text | UK | - | Clave para idempotencia |
| created_at | timestamptz | NOT NULL | - | Fecha de creación |
| datos | jsonb | - | - | Datos adicionales (JSON) |

---

## Nombre de la tabla o colección: configuracion_smtp

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de la config |
| institucion_id | bigint | FK | 10 | Institución a la que aplica |
| servidor | text | NOT NULL | - | Servidor SMTP |
| puerto | integer | NOT NULL | - | Puerto (587 por defecto) |
| cifrado | text | NOT NULL | - | Tipo de cifrado (NONE/SSL/TLS/STARTTLS) |
| usuario | text | - | - | Usuario SMTP |
| password_secret_ref | text | - | - | Referencia al secreto de contraseña |
| correo_remitente | text | NOT NULL | - | Correo remitente |
| nombre_remitente | text | - | - | Nombre remitente |
| timeout_segundos | integer | NOT NULL | - | Timeout de conexión |
| activo | boolean | NOT NULL | - | Estado activo |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |

---

## Nombre de la tabla o colección: plantillas_email

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único de plantilla |
| institucion_id | bigint | FK | 10 | Institución propietaria |
| codigo | text | NOT NULL | - | Código de la plantilla |
| nombre | text | NOT NULL | - | Nombre de la plantilla |
| asunto | text | NOT NULL | - | Asunto del correo |
| contenido_html | text | NOT NULL | - | Contenido HTML |
| contenido_texto | text | - | - | Versión texto plano |
| activo | boolean | NOT NULL | - | Estado activo |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |

---

## Nombre de la tabla o colección: config_parametros

| Nombre del campo | Tipo de dato | Llave | (Tamaño) | Breve descripción del campo |
|---|---|---|---|---|
| id | bigint | PK | 10 | Código único del parámetro |
| institucion_id | bigint | FK | 10 | Institución (o global si null) |
| clave | text | NOT NULL | - | Nombre/clave del parámetro |
| valor | text | NOT NULL | - | Valor configurado |
| tipo | text | NOT NULL | - | Tipo (string, etc.) |
| descripcion | text | - | - | Descripción del parámetro |
| editable_desde_dashboard | boolean | NOT NULL | - | Editable desde dashboard |
| activo | boolean | NOT NULL | - | Estado activo |
| created_at | timestamptz | - | - | Fecha de creación |
| updated_at | timestamptz | - | - | Fecha de actualización |
