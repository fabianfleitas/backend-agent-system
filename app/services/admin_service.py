from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from typing import Optional

from app.repositories.metrics_repository import MetricsRepository
from app.repositories.users_repository import UsersRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.core.security import AuthContext
from app.schemas.common import UserOut, UserRole
from app.schemas.system import CategoryMetricOut, DocumentMetricOut, MetricsOut


class AdminService:
    def __init__(
        self,
        users_repository: Optional[UsersRepository] = None,
        metrics_repository: Optional[MetricsRepository] = None,
        feedback_repository: Optional[FeedbackRepository] = None,
    ) -> None:
        self.users_repository = users_repository or UsersRepository()
        self.metrics_repository = metrics_repository or MetricsRepository()
        self.feedback_repository = feedback_repository or FeedbackRepository()

    def list_feedback(
        self,
        auth: Optional[AuthContext] = None,
        conversacion_id: Optional[int] = None,
        message_id: Optional[int] = None,
        rating: Optional[int] = None,
    ) -> list[dict]:
        institution_id = None
        if auth is not None and not auth.is_platform_admin:
            institution_id = auth.institucion_id
        if institution_id is None:
            return []
        return self.feedback_repository.list_feedback(
            institucion_id=institution_id,
            conversacion_id=conversacion_id,
            message_id=message_id,
            rating=rating,
        )

    def deactivate_feedback(self, auth: Optional[AuthContext] = None, feedback_id: Optional[int] = None) -> bool:
        if auth is None or auth.is_platform_admin or not auth.institucion_id:
            return False
        ok = bool(self.feedback_repository.deactivate_feedback(feedback_id, auth.institucion_id))
        if ok:
            try:
                from app.repositories.audit_repository import AuditRepository

                AuditRepository().log_action(
                    "FEEDBACK_HIDE",
                    external_auth_id=auth.external_auth_id,
                    institucion_id=auth.institucion_id,
                    detalle=f"feedback_id={feedback_id}",
                )
            except Exception:  # noqa: BLE001
                pass
        return ok

    def list_users(self, auth: Optional[AuthContext] = None) -> list[UserOut]:
        institution_id = None
        if auth is not None and not auth.is_platform_admin:
            institution_id = auth.institucion_id
        users = self.users_repository.list_users(institucion_id=institution_id)
        eids = [u["external_auth_id"] for u in users]
        memberships = self.users_repository.get_memberships_batch(eids) if hasattr(self.users_repository, "get_memberships_batch") else {}
        # Resolver nombres de institución para miembros
        inst_ids = list({m.get("institucion_id") for m in memberships.values() if m.get("institucion_id")})
        names_map = {}
        if inst_ids:
            try:
                from app.core.supabase import get_supabase_client
                resp = get_supabase_client().table("instituciones").select("id, nombre").in_("id", inst_ids).execute()
                for r in (resp.data or []):
                    names_map[r.get("id")] = r.get("nombre")
            except Exception:
                pass
        return [
            UserOut(
                external_auth_id=user["external_auth_id"],
                email=user.get("email"),
                full_name=user.get("full_name"),
                role=_role_out(user.get("role")),
                institucion_id=memberships.get(user["external_auth_id"], {}).get("institucion_id"),
                tipo_miembro=memberships.get(user["external_auth_id"], {}).get("tipo_miembro"),
                is_platform_admin=memberships.get(user["external_auth_id"], {}).get("is_platform_admin", False),
                nombre_institucion=names_map.get(memberships.get(user["external_auth_id"], {}).get("institucion_id")),
                created_at=_parse_datetime(user["created_at"]),
                updated_at=_parse_datetime(user["updated_at"] or user["created_at"]),
            )
            for user in users
        ]

    def get_metrics(
        self,
        auth: Optional[AuthContext] = None,
        desde: Optional[str] = None,
        hasta: Optional[str] = None,
        categoria_id: Optional[int] = None,
        modelo: Optional[str] = None,
        documento_id: Optional[int] = None,
        granularidad: Optional[str] = "day",
    ) -> MetricsOut:
        institution_id = None
        if auth is not None and not auth.is_platform_admin:
            institution_id = auth.institucion_id
        messages = self.metrics_repository.list_messages(institucion_id=institution_id)
        conversations = self.metrics_repository.list_conversations(institucion_id=institution_id)
        documents = self.metrics_repository.list_documents(institucion_id=institution_id)
        feedbacks = self.metrics_repository.list_feedbacks(institucion_id=institution_id)
        audit_logs = self.metrics_repository.list_audit_logs(institucion_id=institution_id)
        message_documents = self.metrics_repository.list_message_documents(institucion_id=institution_id)

        # --- BLOQUE 2: filtros ---
        # Documento / categoría → mensaje_ids
        mensaje_ids_filtro = None
        if documento_id is not None:
            mensaje_ids_filtro = {md.get("mensaje_id") for md in message_documents if md.get("documento_id") == documento_id}
            mensaje_ids_filtro = mensaje_ids_filtro - {None}
        elif categoria_id is not None:
            try:
                from app.core.supabase import get_supabase_client
                client = get_supabase_client()
                docs_resp = client.table("documentos").select("id").eq("categoria_id", categoria_id).eq("institucion_id", institution_id or (auth.institucion_id if auth else None)).execute()
                doc_ids = {d.get("id") for d in (docs_resp.data or []) if d.get("id")}
                if doc_ids:
                    mensaje_ids_filtro = {md.get("mensaje_id") for md in message_documents if md.get("documento_id") in doc_ids}
                    mensaje_ids_filtro = mensaje_ids_filtro - {None}
            except Exception:
                pass

        if mensaje_ids_filtro is not None:
            audit_logs = [log for log in audit_logs if log.get("mensaje_id") in mensaje_ids_filtro]
            message_documents = [md for md in message_documents if md.get("mensaje_id") in mensaje_ids_filtro]

        if desde or hasta:
            audit_logs = [log for log in audit_logs if _in_range(log.get("fecha_evaluacion"), desde, hasta)]
            conversations = [c for c in conversations if _in_range(c.get("fecha_creacion"), desde, hasta)]
            conv_ids = {c.get("id") for c in conversations}
            messages = [m for m in messages if m.get("conversacion_id") in conv_ids]

        if modelo:
            audit_logs = [log for log in audit_logs if modelo in (log.get("modelo_ia") or "")]
        # --- /BLOQUE 2 ---

        response_times = [
            float(message["tiempo_respuesta_ms"])
            for message in messages
            if message.get("tiempo_respuesta_ms") is not None and message.get("rol_mensaje") == "ASSISTANT"
        ]
        fidelities = [
            float(log["score_fidelidad"])
            for log in audit_logs
            if log.get("score_fidelidad") is not None
        ]
        relevances = [
            float(log["score_relevancia"])
            for log in audit_logs
            if log.get("score_relevancia") is not None
        ]

        ia = _aggregate_ia(audit_logs, message_documents)
        top_documents, documents_by_category = _build_document_metrics(message_documents)

        return MetricsOut(
            total_queries=len(messages),
            total_conversations=len(conversations),
            total_documents=len(documents),
            total_feedbacks=len(feedbacks),
            avg_response_time=round(_average(response_times), 2),
            avg_fidelity=round(_average(fidelities), 4),
            avg_relevance=round(_average(relevances), 4),
            system_status="healthy",
            total_llm_responses=ia["total_llm_responses"],
            total_guard=ia["total_guard"],
            total_llm_failed=ia["total_llm_failed"],
            guard_rate=ia["guard_rate"],
            llm_failed_rate=ia["llm_failed_rate"],
            total_tokens_input=ia["total_tokens_input"],
            total_tokens_output=ia["total_tokens_output"],
            tokens_by_model=ia["tokens_by_model"],
            avg_retrieval_similarity=ia["avg_retrieval_similarity"],
            total_voice_queries=ia["total_voice_queries"],
            total_text_queries=ia["total_text_queries"],
            avg_response_time_voice=ia["avg_response_time_voice"],
            avg_response_time_text=ia["avg_response_time_text"],
            series=_build_series(audit_logs, conversations, granularidad or "day"),
            top_documents=[
                DocumentMetricOut(documento_id=d["documento_id"], titulo=d.get("titulo"), consultas=d["consultas"])
                for d in top_documents
            ],
            documents_by_category=[
                CategoryMetricOut(categoria_id=c["categoria_id"], nombre=c.get("nombre"), consultas=c["consultas"])
                for c in documents_by_category
            ],
            desde=desde,
            hasta=hasta,
            categoria_id=categoria_id,
            modelo=modelo,
            documento_id=documento_id,
            granularidad=granularidad,
        )


def _in_range(value: Optional[str], desde: Optional[str], hasta: Optional[str]) -> bool:
    if value is None:
        return False if (desde or hasta) else True
    if desde and value < desde[:10]:
        return False
    if hasta and value > hasta[:10]:
        return False
    return True

def _build_series(audit_logs: list[dict], conversations: list[dict], granularidad: str = "day") -> list:
    from collections import defaultdict
    series = defaultdict(lambda: {"conversaciones": 0, "tokens_input": 0, "tokens_output": 0, "llm": 0, "guard": 0, "llm_failed": 0})
    # Audit-derived buckets
    for log in audit_logs:
        fecha = (log.get("fecha_evaluacion") or "")[:10]
        if not fecha:
            continue
        if granularidad == "week":
            # Simple week bucket by first day of week (Mon)
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(fecha)
                fecha = (dt - __import__("datetime").timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
            except Exception:
                pass
        series[fecha]["tokens_input"] += int(log.get("tokens_input") or 0)
        series[fecha]["tokens_output"] += int(log.get("tokens_output") or 0)
        obs = (log.get("observaciones") or "")
        if "LLM_FAILED" in obs:
            series[fecha]["llm_failed"] += 1
        elif "GUARD" in obs:
            series[fecha]["guard"] += 1
        elif "LLM" in obs:
            series[fecha]["llm"] += 1
    # Conversations bucket
    for c in conversations:
        fecha = (c.get("fecha_creacion") or "")[:10]
        if fecha:
            if granularidad == "week":
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(fecha)
                    fecha = (dt - __import__("datetime").timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
                except Exception:
                    pass
            series[fecha]["conversaciones"] += 1
    return [
        {
            "fecha": k,
            "conversaciones": v["conversaciones"],
            "tokens_input": v["tokens_input"],
            "tokens_output": v["tokens_output"],
            "llm": v["llm"],
            "guard": v["guard"],
            "llm_failed": v["llm_failed"],
        }
        for k, v in sorted(series.items())
    ]

def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _build_document_metrics(message_documents: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deriva "documentos más consultados" y "distribución por categoría".

    Dedupe por (mensaje_id, documento_id): un documento usado N veces en un mismo
    mensaje cuenta una única consulta. Los títulos/categorías se resuelven con
    lookups a Supabase; si la DB no está disponible, se devuelven listas vacías.
    """
    deduped = {(md.get("mensaje_id"), md.get("documento_id")) for md in message_documents if md.get("documento_id")}
    if not deduped:
        return [], []

    doc_usage: dict[int, int] = defaultdict(int)
    doc_ids: set[int] = set()
    for _, doc_id in deduped:
        doc_usage[doc_id] += 1
        doc_ids.add(doc_id)

    docs: dict[int, dict] = {}
    cats: dict[int, Optional[str]] = {}
    try:
        from app.core.supabase import get_supabase_client
        client = get_supabase_client()
        docs_resp = client.table("documentos").select("id, titulo, categoria_id").in_("id", list(doc_ids)).execute()
        for d in (docs_resp.data or []):
            docs[d.get("id")] = d
            cid = d.get("categoria_id")
            if cid is not None:
                cats.setdefault(cid, None)
        cids = [c for c in cats if c is not None]
        if cids:
            cat_resp = client.table("categorias").select("id, nombre").in_("id", cids).execute()
            for c in (cat_resp.data or []):
                cats[c.get("id")] = c.get("nombre")
    except Exception:
        pass

    top_documents = sorted(
        (
            {"documento_id": doc_id, "titulo": docs.get(doc_id, {}).get("titulo"), "consultas": count}
            for doc_id, count in doc_usage.items()
        ),
        key=lambda x: x["consultas"],
        reverse=True,
    )[:10]

    cat_usage: dict[Optional[int], int] = defaultdict(int)
    for doc_id, count in doc_usage.items():
        cid = docs.get(doc_id, {}).get("categoria_id")
        cat_usage[cid] += count

    documents_by_category = sorted(
        (
            {"categoria_id": cid, "nombre": cats.get(cid) if cid is not None else None, "consultas": count}
            for cid, count in cat_usage.items()
        ),
        key=lambda x: x["consultas"],
        reverse=True,
    )
    return top_documents, documents_by_category


def _aggregate_ia(audit_logs: list[dict], message_documents: list[dict]) -> dict:
    outcomes = defaultdict(int)
    tokens_by_model: dict[str, dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0})
    total_tokens_input = 0
    total_tokens_output = 0
    total_voice = 0
    total_text = 0
    voice_times: list[float] = []
    text_times: list[float] = []

    for log in audit_logs:
        observaciones = log.get("observaciones") or ""
        outcomes[_classify_outcome(observaciones)] += 1
        channel = _classify_channel(observaciones)
        if channel == "voice":
            total_voice += 1
        elif channel == "text":
            total_text += 1
        model = log.get("modelo_ia")
        if model:
            tokens_by_model[model]["input"] += int(log.get("tokens_input") or 0)
            tokens_by_model[model]["output"] += int(log.get("tokens_output") or 0)
        total_tokens_input += int(log.get("tokens_input") or 0)
        total_tokens_output += int(log.get("tokens_output") or 0)
        if log.get("tiempo_respuesta_ms") is not None:
            if channel == "voice":
                voice_times.append(float(log["tiempo_respuesta_ms"]))
            elif channel == "text":
                text_times.append(float(log["tiempo_respuesta_ms"]))

    denominator = outcomes["llm"] + outcomes["guard"] + outcomes["llm_failed"]
    guard_rate = (outcomes["guard"] / denominator) if denominator else 0.0
    llm_failed_rate = (outcomes["llm_failed"] / denominator) if denominator else 0.0

    similarities = [
        float(row["similarity_score"])
        for row in message_documents
        if row.get("similarity_score") is not None
    ]

    return {
        "total_llm_responses": outcomes["llm"],
        "total_guard": outcomes["guard"],
        "total_llm_failed": outcomes["llm_failed"],
        "guard_rate": round(guard_rate, 4),
        "llm_failed_rate": round(llm_failed_rate, 4),
        "total_tokens_input": total_tokens_input,
        "total_tokens_output": total_tokens_output,
        "tokens_by_model": dict(tokens_by_model),
        "avg_retrieval_similarity": round(_average(similarities), 4),
        "total_voice_queries": total_voice,
        "total_text_queries": total_text,
        "avg_response_time_voice": round(_average(voice_times), 2),
        "avg_response_time_text": round(_average(text_times), 2),
    }


def _classify_outcome(observaciones: str) -> str:
    if observaciones.startswith("LLM:"):
        return "llm"
    if observaciones.startswith("GUARD:"):
        return "guard"
    if observaciones.startswith("LLM_FAILED:"):
        return "llm_failed"
    return "mock"


def _classify_channel(observaciones: str) -> Optional[str]:
    if "[voice]" in observaciones:
        return "voice"
    if "[text]" in observaciones:
        return "text"
    return None


def _role_out(role: Optional[str]) -> UserRole:
    mapping = {"ADMIN": UserRole.ADMIN, "STAFF": UserRole.STAFF, "STUDENT": UserRole.STUDENT}
    return mapping.get(role or "", UserRole.STUDENT)


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    match = re.search(r"\.(\d+)([+-]\d{2}:\d{2})$", normalized)
    if match:
        fraction, offset = match.groups()
        normalized = normalized.replace(f".{fraction}{offset}", f".{fraction.ljust(6, '0')[:6]}{offset}")
    return datetime.fromisoformat(normalized)
