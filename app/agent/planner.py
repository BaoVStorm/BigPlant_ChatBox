from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.chat.facets import FacetResult
from app.plant_detect.schemas import ImagePlantContext
from app.router.schemas import IntentRoute


@dataclass(frozen=True)
class ToolStep:
    name: str
    reason: str
    required: bool = True
    inputs: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "reason": self.reason,
            "required": self.required,
            "inputs": self.inputs,
        }


@dataclass(frozen=True)
class AgentPlan:
    goal: str
    confidence: float
    needs_clarification: bool
    response_policy: str
    tools: list[ToolStep]
    verification: list[str]

    def model_dump(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "confidence": self.confidence,
            "needs_clarification": self.needs_clarification,
            "response_policy": self.response_policy,
            "tools": [tool.model_dump() for tool in self.tools],
            "verification": self.verification,
        }


class AgentPlanner:
    def plan(
        self,
        message: str,
        route: IntentRoute,
        facet: FacetResult,
        memory: dict[str, Any] | None = None,
        image_context: ImagePlantContext | None = None,
    ) -> AgentPlan:
        entities = route.entities or {}
        memory = memory or {}

        if route.intent == "product_info":
            return self._plan_product_info(message, route, facet, entities, memory, image_context)
        if route.intent == "recommendation":
            return self._plan_recommendation(route, facet, entities)
        if route.intent == "plant_care":
            return self._plan_plant_care(route, facet, entities)
        if route.intent == "cart_order":
            return AgentPlan(
                goal="cart_action",
                confidence=route.confidence,
                needs_clarification=False,
                response_policy="delegate_to_cart_api",
                tools=[ToolStep("cart_action", "Cart and order mutations must use a transactional commerce API.", inputs={"entities": entities})],
                verification=[
                    "Do not mutate cart state in chatbot-only code.",
                    "Confirm product, variant, quantity, and current price through Cart API.",
                ],
            )
        if route.intent == "general":
            return AgentPlan(
                goal="general_chat",
                confidence=route.confidence,
                needs_clarification=False,
                response_policy="short_general_response",
                tools=[ToolStep("general_answer", "No catalog or knowledge lookup is required.", required=False)],
                verification=["Redirect product, price, stock, and care questions back to grounded tools."],
            )

        return AgentPlan(
            goal="clarify_user_goal",
            confidence=route.confidence,
            needs_clarification=True,
            response_policy="ask_clarification",
            tools=[ToolStep("ask_clarification", "The router could not determine a reliable commerce or care goal.")],
            verification=["Ask the user to choose product info, recommendation, or plant care."],
        )

    def _plan_product_info(
        self,
        message: str,
        route: IntentRoute,
        facet: FacetResult,
        entities: dict[str, Any],
        memory: dict[str, Any],
        image_context: ImagePlantContext | None,
    ) -> AgentPlan:
        has_subject = bool(entities.get("product_name") or entities.get("context_subject") or (image_context and image_context.resolved_product_context))
        tools = []
        if image_context:
            tools.append(ToolStep("resolve_image_product", "Use image detection result as product context when available.", required=False))
        tools.append(ToolStep("get_product_detail", "Load product, plant, profile, variants, inventory, and images.", inputs={"product_name": entities.get("product_name")}))

        return AgentPlan(
            goal=f"answer_product_{facet.name}",
            confidence=route.confidence,
            needs_clarification=not has_subject,
            response_policy="grounded_product_json_then_compose",
            tools=tools if has_subject else [ToolStep("ask_clarification", "A product-specific answer needs a product name or image context.")],
            verification=[
                "Price and stock must come from variants/inventory/computed fields.",
                "Care and safety claims must come from plant or plant_profile.",
                "Do not invent pot, size, image, or toxicity data.",
            ],
        )

    def _plan_recommendation(self, route: IntentRoute, facet: FacetResult, entities: dict[str, Any]) -> AgentPlan:
        return AgentPlan(
            goal=f"recommend_products_{facet.name}",
            confidence=route.confidence,
            needs_clarification=False,
            response_policy="grounded_recommendation_json_then_compose",
            tools=[
                ToolStep("search_products", "Apply structured filters from extracted entities.", inputs={"filters": entities}),
                ToolStep("semantic_product_search", "Use product embeddings for soft style, placement, and natural-language needs.", required=False, inputs={"filters": entities}),
                ToolStep("rank_products", "Rank by in-stock status, structured profile match, budget, and vector score.", inputs={"facet": facet.name}),
            ],
            verification=[
                "Only recommend products returned from MongoDB.",
                "Verify price, stock, care_profile, safety_profile, and recommendation_profile before answering.",
                "If hard constraints eliminate all products, ask to relax constraints instead of hallucinating.",
            ],
        )

    def _plan_plant_care(self, route: IntentRoute, facet: FacetResult, entities: dict[str, Any]) -> AgentPlan:
        return AgentPlan(
            goal=f"answer_plant_care_{facet.name}",
            confidence=route.confidence,
            needs_clarification=False,
            response_policy="rag_with_score_and_evidence_gate",
            tools=[
                ToolStep("search_knowledge", "Retrieve relevant knowledge_chunks through vector search.", inputs={"filters": entities}),
                ToolStep("verify_evidence", "Reject chunks below score threshold or missing lexical evidence for symptoms."),
                ToolStep("compose_care_answer", "Answer only from accepted context.", required=False),
            ],
            verification=[
                "Use no-answer policy when retrieval is weak.",
                "Do not give disease, chemical, ingestion, or medical advice without source context.",
                "Ask for plant name, symptoms, light, and watering schedule when evidence is insufficient.",
            ],
        )
