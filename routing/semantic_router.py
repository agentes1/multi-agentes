from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata

from routing.routes import RouteDefinition, discard_route, routes

_STOPWORDS = {
    "a",
    "al",
    "con",
    "de",
    "del",
    "el",
    "en",
    "es",
    "esta",
    "este",
    "la",
    "las",
    "lo",
    "los",
    "mi",
    "necesito",
    "necesitamos",
    "para",
    "por",
    "que",
    "queremos",
    "se",
    "sin",
    "su",
    "un",
    "una",
    "y",
}

_BUDGET_COMMERCIAL_TERMS = {
    "presupuesto",
    "precio",
    "coste",
    "costo",
    "cotizacion",
    "cotización",
    "propuesta",
}

_BUDGET_SCOPE_TERMS = {
    "crm",
    "erp",
    "odoo",
    "implantar",
    "implantacion",
    "implantación",
    "modulos",
    "módulos",
    "automatizacion",
    "automatización",
}

_ISSUE_BLOCKER_TERMS = {
    "error",
    "problema",
    "incidencia",
    "falla",
    "fallo",
    "bug",
    "no funciona",
    "roto",
    "bloqueado",
    "bloquea",
}


@dataclass(frozen=True)
class RouteMatch:
    name: str
    score: float
    utterance: str | None = None


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_text(value: str) -> str:
    normalized = _strip_accents(str(value).lower().strip())
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in _normalize_text(value).split()
        if len(token) > 2 and token not in _STOPWORDS
    }


class SemanticTicketRouter:
    def __init__(self, route_definitions: tuple[RouteDefinition, ...]):
        self._routes = route_definitions

    def __call__(self, text: str) -> RouteMatch:
        normalized_text = _normalize_text(text)
        text_tokens = _tokenize(text)
        priority_match = self._match_priority_route(normalized_text, text_tokens)
        if priority_match is not None:
            return priority_match
        best_match = RouteMatch(name=discard_route.name, score=0.0, utterance=None)

        for route in self._routes:
            candidate_match = self._score_route(route, normalized_text, text_tokens)
            if candidate_match.score > best_match.score:
                best_match = candidate_match

        if best_match.name != discard_route.name:
            route_threshold = next(
                route.threshold for route in self._routes if route.name == best_match.name
            )
            if best_match.score < route_threshold:
                return RouteMatch(name=discard_route.name, score=best_match.score, utterance=None)

        return best_match

    def _match_priority_route(
        self,
        normalized_text: str,
        text_tokens: set[str],
    ) -> RouteMatch | None:
        budget_route = next((route for route in self._routes if route.name == "budget"), None)
        if not budget_route:
            return None

        commercial_hits = sum(
            1 for term in _BUDGET_COMMERCIAL_TERMS if _normalize_text(term) in normalized_text
        )
        scope_hits = sum(
            1 for term in _BUDGET_SCOPE_TERMS if _normalize_text(term) in normalized_text
        )
        issue_hits = sum(
            1 for term in _ISSUE_BLOCKER_TERMS if _normalize_text(term) in normalized_text
        )
        total_keyword_hits = len(text_tokens & _tokenize(" ".join(budget_route.keywords)))

        if issue_hits >= 1 and commercial_hits == 0:
            return None

        if (commercial_hits >= 1 and scope_hits >= 1) or (
            commercial_hits >= 1 and total_keyword_hits >= 2
        ):
            return RouteMatch(name="budget", score=1.0, utterance="priority_budget_match")

        return None

    def _score_route(
        self,
        route: RouteDefinition,
        normalized_text: str,
        text_tokens: set[str],
    ) -> RouteMatch:
        keyword_hits = sum(
            1 for keyword in route.keywords if _normalize_text(keyword) in normalized_text
        )
        keyword_score = keyword_hits / max(len(route.keywords), 1)

        best_utterance = None
        best_utterance_score = 0.0
        for utterance in route.utterances:
            utterance_score = self._score_utterance(
                normalized_text=normalized_text,
                text_tokens=text_tokens,
                utterance=utterance,
            )
            if utterance_score > best_utterance_score:
                best_utterance_score = utterance_score
                best_utterance = utterance

        score = round((best_utterance_score * 0.75) + (keyword_score * 0.25), 4)
        return RouteMatch(name=route.name, score=score, utterance=best_utterance)

    @staticmethod
    def _score_utterance(normalized_text: str, text_tokens: set[str], utterance: str) -> float:
        normalized_utterance = _normalize_text(utterance)
        utterance_tokens = _tokenize(utterance)
        if not normalized_text or not normalized_utterance:
            return 0.0

        overlap = len(text_tokens & utterance_tokens) / max(len(utterance_tokens), 1)
        sequence = SequenceMatcher(None, normalized_text, normalized_utterance).ratio()
        contains_bonus = 1.0 if normalized_utterance in normalized_text else 0.0
        return max(overlap, (overlap * 0.6) + (sequence * 0.4), contains_bonus)


router = SemanticTicketRouter(routes)
