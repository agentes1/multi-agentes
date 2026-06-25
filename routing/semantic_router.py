from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from langchain_ollama import OllamaEmbeddings

from routing.routes import RouteDefinition, discard_route, routes
from shared.config import OLLAMA_BASE_URL, OLLAMA_MODEL, ROUTER_EMBED_MODEL, ROUTER_EMBEDDINGS_ENABLED


# Palabras sin valor para comparar intención.
STOPWORDS = {
    "a", "al", "con", "de", "del", "el", "en", "es", "esta", "este", "la", "las",
    "lo", "los", "mi", "necesito", "necesitamos", "para", "por", "que", "queremos",
    "se", "sin", "su", "un", "una", "y",
}

# Presupuesto solo debe activarse si hay intención económica clara.
BUDGET_COMMERCIAL_TERMS = {
    "presupuesto", "precio", "coste", "costo", "cotizacion", "cotización",
    "propuesta", "propuesta económica", "cuanto cuesta", "cuánto cuesta",
}

# Alcance típico de un presupuesto, pero no basta por sí solo.
BUDGET_SCOPE_TERMS = {
    "crm", "erp", "odoo", "implantar", "implantacion", "implantación", "modulos",
    "módulos", "automatizacion", "automatización", "formacion", "formación",
    "desarrollo", "soporte mensual",
}

# Acciones claras de ventas. Estas deben ganar antes que discard.
SALES_ACTION_TERMS = {
    "crear lead", "nuevo lead", "crear oportunidad", "nueva oportunidad",
    "pipeline", "ventas", "venta", "seguimiento comercial", "equipo comercial",
    "contacto comercial", "cliente interesado", "prospecto",
}

# Términos generales de ventas para scoring rápido.
SALES_TERMS = {
    "ventas", "venta", "comercial", "pipeline", "lead", "leads", "oportunidad",
    "oportunidades", "captacion", "captación", "seguimiento comercial",
    "equipo comercial", "crm",
}

# Si aparece esto sin intención económica ni comercial clara, no es presupuesto.
SUPPORT_TERMS = {
    "error", "problema", "incidencia", "falla", "fallo", "bug", "no funciona",
    "roto", "bloqueado", "bloquea", "soporte", "ayuda",
}


@dataclass(frozen=True)
class RouteMatch:
    """Resultado estable del router."""
    name: str
    score: float
    utterance: str | None = None


def env_flag(value: str | None) -> bool:
    """Convierte una variable de entorno en booleano."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def strip_accents(value: str) -> str:
    """Quita tildes para comparar mejor."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_text(value: str) -> str:
    """Normaliza texto para rutas."""
    text = strip_accents(str(value or "").lower().strip())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(value: str) -> set[str]:
    """Tokeniza quitando palabras poco útiles."""
    return {t for t in normalize_text(value).split() if len(t) > 2 and t not in STOPWORDS}


def has_any(text: str, terms: set[str]) -> bool:
    """Comprueba si aparece alguna frase normalizada."""
    return any(normalize_text(term) in text for term in terms)


def count_hits(text: str, terms: set[str]) -> int:
    """Cuenta coincidencias por frase."""
    return sum(normalize_text(term) in text for term in terms)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Calcula similitud coseno entre dos vectores."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return 0.0 if not left_norm or not right_norm else dot / (left_norm * right_norm)


class SemanticTicketRouter:
    """Router híbrido: reglas claras primero, scoring después."""

    def __init__(
        self,
        route_definitions: tuple[RouteDefinition, ...],
        embeddings_client: OllamaEmbeddings | None = None,
        embeddings_enabled: bool | None = None,
    ):
        self._routes = route_definitions
        self._embeddings_enabled = env_flag(ROUTER_EMBEDDINGS_ENABLED) if embeddings_enabled is None else embeddings_enabled
        self._embeddings_client = embeddings_client
        self._route_embeddings: dict[str, list[tuple[str, list[float]]]] = {}
        self._embedding_failed = False

    def __call__(self, text: str) -> RouteMatch:
        """Devuelve la mejor ruta para el texto recibido."""
        normalized_text = normalize_text(text)
        text_tokens = tokenize(text)

        priority_match = self._match_priority_route(normalized_text, text_tokens)
        if priority_match:
            return priority_match

        best_match = self._best_scored_route(normalized_text, text_tokens)
        return self._apply_threshold(best_match)

    def _match_priority_route(self, text: str, tokens: set[str]) -> RouteMatch | None:
        """Aplica reglas fuertes antes del scoring semántico."""
        budget_route = self._route("budget")
        sales_route = self._route("sales")
        if not budget_route:
            return None

        commercial_hits = count_hits(text, BUDGET_COMMERCIAL_TERMS)
        scope_hits = count_hits(text, BUDGET_SCOPE_TERMS)
        support_hits = count_hits(text, SUPPORT_TERMS)
        sales_hits = count_hits(text, SALES_TERMS)
        budget_keyword_hits = len(tokens & tokenize(" ".join(budget_route.keywords)))

        # 3. Soporte claro sin intención comercial/económica → agente RAG
        if support_hits >= 1 and commercial_hits == 0 and sales_hits == 0:
            return RouteMatch("rag", 1.0, "priority_rag_match")

        # 1. Sales explícito: no debe morir como discard por llevar "soporte" o "incidencia".
        if sales_route and (has_any(text, SALES_ACTION_TERMS) or sales_hits >= 2) and commercial_hits == 0:
            return RouteMatch("sales", 1.0, "priority_sales_match")

        # 2. Presupuesto explícito: necesita intención económica, no solo "Odoo" o "CRM".
        if commercial_hits >= 1 and (scope_hits >= 1 or budget_keyword_hits >= 2):
            return RouteMatch("budget", 1.0, "priority_budget_match")

        
        return None

    def _best_scored_route(self, text: str, tokens: set[str]) -> RouteMatch:
        """Calcula la mejor ruta por keywords, ejemplos y embeddings."""
        best = RouteMatch(discard_route.name, 0.0)

        for route in self._routes:
            match = self._score_route(route, text, tokens)
            if match.score > best.score:
                best = match

        return best

    def _apply_threshold(self, match: RouteMatch) -> RouteMatch:
        """Descarta rutas que no superan su umbral."""
        if match.name == discard_route.name:
            return match

        route = self._route(match.name)
        if route and match.score >= route.threshold:
            return match

        return RouteMatch(discard_route.name, match.score)

    def _score_route(self, route: RouteDefinition, text: str, tokens: set[str]) -> RouteMatch:
        """Puntúa una ruta usando keywords, utterances y embeddings."""
        keyword_hits = sum(normalize_text(k) in text for k in route.keywords)
        keyword_score = keyword_hits / max(len(route.keywords), 1)

        best_utterance, utterance_score = self._best_utterance(route, text, tokens)
        embedding_score, embedding_utterance = self._score_route_embeddings(route, text)

        if embedding_score > utterance_score and embedding_utterance:
            best_utterance = embedding_utterance

        score = round((utterance_score * 0.55) + (keyword_score * 0.20) + (embedding_score * 0.25), 4)
        return RouteMatch(route.name, score, best_utterance)

    def _best_utterance(self, route: RouteDefinition, text: str, tokens: set[str]) -> tuple[str | None, float]:
        """Busca el ejemplo más parecido dentro de una ruta."""
        best_text, best_score = None, 0.0

        for utterance in route.utterances:
            score = self._score_utterance(text, tokens, utterance)
            if score > best_score:
                best_text, best_score = utterance, score

        return best_text, best_score

    @staticmethod
    def _score_utterance(text: str, tokens: set[str], utterance: str) -> float:
        """Compara el texto con un ejemplo de entrenamiento."""
        normalized_utterance = normalize_text(utterance)
        utterance_tokens = tokenize(utterance)
        if not text or not normalized_utterance:
            return 0.0

        overlap = len(tokens & utterance_tokens) / max(len(utterance_tokens), 1)
        sequence = SequenceMatcher(None, text, normalized_utterance).ratio()
        contains_bonus = 1.0 if normalized_utterance in text else 0.0
        return max(overlap, (overlap * 0.6) + (sequence * 0.4), contains_bonus)

    def _score_route_embeddings(self, route: RouteDefinition, text: str) -> tuple[float, str | None]:
        """Usa embeddings si están activos; si fallan, los desactiva."""
        if not self._embeddings_enabled or self._embedding_failed or not text:
            return 0.0, None

        try:
            client = self._get_embeddings_client()
            if not client:
                return 0.0, None

            if route.name not in self._route_embeddings:
                vectors = client.embed_documents([normalize_text(item) for item in route.utterances])
                self._route_embeddings[route.name] = list(zip(route.utterances, vectors))

            text_vector = client.embed_query(text)
        except Exception:
            self._embedding_failed = True
            return 0.0, None

        best_score, best_utterance = 0.0, None
        for utterance, vector in self._route_embeddings.get(route.name, []):
            similarity = cosine_similarity(text_vector, vector)
            score = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
            if score > best_score:
                best_score, best_utterance = score, utterance

        return best_score, best_utterance

    def _get_embeddings_client(self) -> OllamaEmbeddings | None:
        """Crea el cliente de embeddings solo cuando se necesita."""
        if self._embeddings_client:
            return self._embeddings_client

        model_name = ROUTER_EMBED_MODEL or OLLAMA_MODEL
        if not model_name:
            return None

        self._embeddings_client = OllamaEmbeddings(model=model_name, base_url=OLLAMA_BASE_URL)
        return self._embeddings_client

    def _route(self, name: str) -> RouteDefinition | None:
        """Busca una ruta por nombre."""
        return next((route for route in self._routes if route.name == name), None)


router = SemanticTicketRouter(routes)