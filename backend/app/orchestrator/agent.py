import asyncio
import logging
from groq import AsyncGroq
from app.core.config import get_settings
from app.orchestrator.intent.extractor import IntentExtractor
from app.orchestrator.intent.router import BusinessContextRouter
from app.orchestrator.memory.manager import MemoryManager
from app.orchestrator.context.assembler import ContextAssembler, AgentContext
from app.orchestrator.planner.planner import AgentPlanner
from app.orchestrator.planner.executor import PlanExecutor
from app.orchestrator.tools.orchestrator import ToolOrchestrator
from app.orchestrator.rag.manager import RAGManager
from app.orchestrator.policy.engine import PolicyEngine
from app.orchestrator.workflows.executor import WorkflowExecutor
from app.orchestrator.summary.generator import CallSummaryGenerator, EscalationHandler
from app.api.websocket.events import (
    IntentDetectedEvent, SentimentUpdatedEvent, ResponseGeneratedEvent, RagRetrievedEvent
)
from app.observability.bus import event_bus
from app.database.session import async_session_factory
from app.models.conversation import Message
from app.enterprise.crm.service import CRMService

_crm = CRMService()

logger = logging.getLogger(__name__)
settings = get_settings()

RESPONSE_SYSTEM = (
    "You are a helpful, empathetic AI customer service agent for InsureAI, an Indian insurance company covering Health, Home, and Motor insurance.\n\n"

    "CORE RULES:\n"
    "- If [CUSTOMER] is in the context, the customer is ALREADY authenticated. "
    "Address them by name. NEVER ask for re-verification.\n"
    "- Answer questions directly using the data in [CUSTOMER], [ACCOUNT], [INVOICES], and [TOOL RESULTS].\n"
    "- For phone/email/account queries: read the value directly from [CUSTOMER] or [TOOL RESULTS] and state it.\n"
    "- For balance/billing: explain the exact premium amount from [ACCOUNT], and if negative, explain why based on [INVOICES].\n"
    "- For profile updates: confirm the change was made successfully.\n"
    "- If data is not in context and no tool result has it, say you will look it up.\n\n"

    "REFUND / CLAIM VALIDATION — FOLLOW THIS FLOW STRICTLY:\n"
    "Step 1 — Gather reason: If the customer mentions a refund or claim credit but has NOT yet stated a reason, ask them:\n"
    "  'I can help with that. Could you please tell me the reason for your refund or claim credit request?\n"
    "   For example: duplicate premium payment, overbilling, policy cancellation within free-look period, or claim settlement dispute.'\n"
    "Step 2 — Validate claim: Once the reason is given and [TOOL RESULTS] contain invoice data:\n"
    "  - Compare the customer's claim against the premium invoice line items and amounts.\n"
    "  - If the claim IS supported by the data (e.g. disputed premium charge appears in line items, amount matches): proceed.\n"
    "  - If the claim is NOT supported (no matching line item, amount does not match): inform the customer.\n"
    "    Example: 'Looking at your premium invoice, the charge of Rs.X appears correct based on your current policy plan.\n"
    "    Could you clarify which specific charge you believe is incorrect?'\n"
    "Step 3 — Confirm before acting: Before the refund tool is called, briefly confirm with the customer:\n"
    "  'I can see the disputed premium of Rs.X on invoice [number]. I will now raise a refund request for Rs.X. Shall I proceed?'\n"
    "Step 4 — Report outcome: After [TOOL RESULTS] confirm the refund:\n"
    "  - If approved: 'Your premium refund of Rs.X has been processed successfully. Reference: [refund_number].'\n"
    "  - If queued for review: 'Your refund request has been logged. Reference: [reference_number]. A specialist will review it within 48 hours.'\n"
    "  - If flagged as investigation: 'A case has been opened for your account. Case reference: [CASE-ID]. Our claims specialist will contact you shortly.'\n\n"

    "STRICT GUARDRAILS — NEVER VIOLATE:\n"
    "- NEVER mention any internal approval limits, thresholds, or specific currency amounts that the system uses to decide whether to auto-process or escalate a request.\n"
    "- NEVER tell the customer which amount triggers a manual review or human approval.\n"
    "- If a refund or request was referred for review, simply say it has been logged and provide the reference number from [TOOL RESULTS]. Do NOT explain why it was referred.\n"
    "- If a request was flagged for investigation, tell the customer their case reference number and that a specialist will contact them. Do NOT explain the internal reason for flagging.\n"
    "- NEVER claim that a refund is processed, a ticket is created, or an action is complete UNLESS you see the exact confirmation and reference number in [TOOL RESULTS]. If you do not see it in [TOOL RESULTS], tell the customer you will process it now.\n\n"

    "RESPONSE STYLE:\n"
    "- Natural spoken language. No markdown. No bullet points.\n"
    "- Keep it concise: 2-3 sentences for simple queries, up to 5 for complex billing or claims.\n"
    "- Always end by asking if there is anything else you can help with.\n"
    "- Use Rs. for currency amounts and Indian number format."
)



class AgentOrchestrator:
    def __init__(self):
        self._intent_extractor = IntentExtractor()
        self._router = BusinessContextRouter()
        self._memory = MemoryManager()
        self._assembler = ContextAssembler()
        self._planner = AgentPlanner()
        self._tool_orchestrator = ToolOrchestrator()
        self._executor = PlanExecutor(self._tool_orchestrator)
        self._rag = RAGManager()
        self._policy = PolicyEngine()
        self._workflow_executor = WorkflowExecutor()
        self._groq = AsyncGroq(api_key=settings.groq_api_key)

    async def run_turn(
        self,
        session_id: str,
        transcript: str,
        turn_index: int,
        conversation_id=None,
        message_id=None,
    ) -> str:
        async with async_session_factory() as db:
            memory = await self._memory.load(session_id, db)

        # ── Run intent extraction + RAG embedding concurrently ──────────────────
        # This cuts ~2-4s of sequential wait per turn.
        async def _do_rag():
            try:
                async with async_session_factory() as db:
                    result = await self._rag.retrieve(
                        query=transcript,
                        db=db,
                        conversation_id=conversation_id,
                        top_k=3,
                    )
                return result
            except Exception as exc:
                logger.error("RAG retrieval error: %s", exc)
                return None

        intent_result, rag_result = await asyncio.gather(
            self._intent_extractor.extract(transcript, memory.history),
            _do_rag(),
        )

        domain = self._router.route(intent_result)

        await event_bus.emit(session_id, IntentDetectedEvent(
            session_id=session_id,
            intents=intent_result.intents,
            entities=intent_result.entities,
            sentiment=intent_result.sentiment,
            urgency=intent_result.urgency,
            confidence=intent_result.confidence,
        ))
        await event_bus.emit(session_id, SentimentUpdatedEvent(
            session_id=session_id,
            sentiment=intent_result.sentiment,
            urgency=intent_result.urgency,
        ))

        rag_context = ""
        if rag_result:
            rag_context = rag_result.to_context_block()
            await event_bus.emit(session_id, RagRetrievedEvent(
                session_id=session_id,
                query=transcript,
                passages=[{"title": p.title, "score": p.score, "category": p.category} for p in rag_result.passages],
                doc_count=len(rag_result.passages),
            ))

        # ── Read pre-loaded customer context from session state ─────────────────
        # CustomerContextLoader populates this at session creation so we never
        # hit the DB mid-conversation. Falls back to a live CRM fetch if missing.
        customer_profile: dict | None = memory.state.get("customer_profile")
        customer_context: dict | None = memory.state.get("customer_context")
        stored_customer_id: str | None = memory.state.get("customer_id")

        if stored_customer_id and not customer_profile:
            # Fallback: context wasn't pre-loaded (e.g., session created without auth token)
            try:
                crm_result = await _crm.get_customer(customer_id=stored_customer_id)
                if crm_result.get("found"):
                    customer_profile = crm_result["customer"]
                    await self._memory.set_field(session_id, "customer_profile", customer_profile)
                    await self._memory.set_field(session_id, "customer_verified", True)
                    memory.state["customer_profile"] = customer_profile
                    memory.state["customer_verified"] = True
            except Exception as exc:
                logger.error("Customer profile fallback fetch error: %s", exc)

        context = self._assembler.assemble(
            session_id=session_id,
            transcript=transcript,
            intent_result=intent_result,
            domain=domain,
            memory=memory,
            customer_profile=customer_profile,
            rag_context=rag_context,
            customer_context=customer_context,
        )


        plan = await self._planner.plan(context)
        logger.info("Plan: %d steps, direct_answer=%s, session=%s", len(plan.steps), plan.direct_answer, session_id)

        tool_results: list[dict] = []
        if not plan.direct_answer and plan.steps:
            for step in plan.steps:
                policy_check = self._policy.evaluate_tool_use(step.tool, memory.state.get("customer_verified", False))
                if not policy_check.authorized:
                    async with async_session_factory() as db:
                        await self._policy.emit_and_persist(session_id, conversation_id, policy_check, db)
                    logger.warning("Policy blocked tool %s for session %s: %s", step.tool, session_id, policy_check.reason)
                    continue

            # ── Inject real customer_id + context into every plan step ────────────────
            # The planner may omit customer_id or use a placeholder like "c001".
            # We resolve the real UUID from the pre-loaded session state here, at the
            # only point where all session context is available.
            real_customer_id: str | None = None
            if customer_profile and isinstance(customer_profile, dict):
                real_customer_id = (
                    customer_profile.get("customer_id")
                    or memory.state.get("customer_id")
                )
            if not real_customer_id:
                real_customer_id = memory.state.get("customer_id")

            for step in plan.steps:
                if real_customer_id:
                    # Always inject the real customer_id so tools don't fall back to "c001"
                    if not step.params.get("customer_id") or step.params.get("customer_id") == "c001":
                        step.params["customer_id"] = real_customer_id

                if step.tool == "escalate_to_human":
                    # Inject everything the escalation function needs
                    step.params.setdefault("reason", transcript)
                    step.params["sentiment"] = intent_result.sentiment
                    step.params["session_id"] = session_id
                    step.params["conversation_id"] = str(conversation_id) if conversation_id else None
                    step.params["conversation_history"] = memory.history[-20:]
                    step.params["customer_profile"] = customer_profile
                    step.params["customer_context"] = customer_context

                if step.tool == "get_payment_history" and not step.params.get("customer_id") and real_customer_id:
                    step.params["customer_id"] = real_customer_id
                
                # update_customer_details also needs customer_id
                if step.tool == "update_customer_details" and not step.params.get("customer_id") and real_customer_id:
                    step.params["customer_id"] = real_customer_id

            tool_results = await self._executor.execute(plan, session_id, conversation_id)

            # Mutate the customer_profile in memory if update was successful
            for res in tool_results:
                if res.get("tool") == "update_customer_details":
                    result_data = res.get("result", {})
                    if result_data.get("success"):
                        # Use the updated profile returned from DB — most accurate
                        returned_profile = result_data.get("customer")
                        if returned_profile and customer_profile and isinstance(customer_profile, dict):
                            customer_profile.update(returned_profile)
                            await self._memory.set_field(session_id, "customer_profile", customer_profile)
                            logger.info("Synced memory customer_profile from DB for session %s", session_id)



            if tool_results:
                context = self._assembler.assemble(
                    session_id=session_id,
                    transcript=transcript,
                    intent_result=intent_result,
                    domain=domain,
                    memory=memory,
                    tool_results=tool_results,
                    rag_context=rag_context,
                )

        workflow_result = await self._check_and_run_workflow(intent_result, tool_results, memory, session_id, conversation_id)
        if workflow_result:
            context = self._assembler.assemble(
                session_id=session_id,
                transcript=transcript,
                intent_result=intent_result,
                domain=domain,
                memory=memory,
                tool_results=tool_results,
                rag_context=rag_context,
                workflow_result=workflow_result,
            )

        response = await self._generate_response(context, memory.history)
        await event_bus.emit(session_id, ResponseGeneratedEvent(session_id=session_id, text=response))

        escalation_handler = EscalationHandler()
        should_escalate, reason = escalation_handler.should_escalate(
            sentiment=intent_result.sentiment,
            intents=intent_result.intents,
            turn_count=turn_index + 1,
            customer_verified=memory.state.get("customer_verified", False),
        )

        async with async_session_factory() as db:
            await self._memory.after_turn(
                session_id=session_id,
                db=db,
                transcript=transcript,
                response=response,
                intent_result=intent_result,
                domain=domain,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            if should_escalate:
                await escalation_handler.escalate(session_id, conversation_id, reason, memory, db)
                logger.info("Escalation triggered for session %s: %s", session_id, reason)

        return response

    async def _check_and_run_workflow(self, intent_result, tool_results, memory, session_id, conversation_id) -> dict | None:
        intents = intent_result.intents
        entities = intent_result.entities

        if "refund_request" in intents or "billing_dispute" in intents:
            invoice_id = entities.get("invoice_id")
            if not invoice_id and tool_results:
                for r in tool_results:
                    if r.get("tool") == "get_invoice":
                        invoices = r.get("output", {}).get("invoices", [])
                        if invoices:
                            invoice_id = invoices[0].get("invoice_id")
                            break
            if invoice_id:
                amount_str = entities.get("amount", "0")
                try:
                    amount = float(str(amount_str).replace("INR", "").replace(",", "").strip())
                except ValueError:
                    amount = 0.0

                if amount > 0:
                    policy_result = self._policy.evaluate_refund(
                        amount=amount,
                        invoice_amount=amount * 1.5,
                    )
                    if policy_result.authorized:
                        return await self._workflow_executor.run(
                            "refund_workflow", session_id, conversation_id,
                            {"invoice_id": invoice_id, "amount": amount},
                        )

        if "cancellation_request" in intents:
            return await self._workflow_executor.run(
                "cancellation_workflow", session_id, conversation_id,
                {"in_contract": False},
            )

        if "plan_upgrade" in intents:
            target_plan = entities.get("plan_name")
            if target_plan:
                return await self._workflow_executor.run(
                    "upgrade_workflow", session_id, conversation_id,
                    {"target_plan": target_plan},
                )

        return None

    async def _generate_response(self, context: AgentContext, history: list[dict]) -> str:
        context_block = self._assembler.build_llm_context_block(context)
        messages = [{"role": "system", "content": RESPONSE_SYSTEM}]
        for turn in history[-12:]:
            messages.append(turn)
        messages.append({"role": "user", "content": context_block})

        try:
            resp = await self._groq.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=messages,
                max_tokens=500,
                temperature=0.3,
            )
            content = resp.choices[0].message.content or ""
            content = content.strip()
            if len(content) > 10:
                return content
            logger.warning("Model returned very short response (%d chars): %r", len(content), content)
            return "I'm sorry, I couldn't generate a response. Could you please repeat your question?"
        except Exception as exc:
            logger.error("Response generation failed: %s", exc)
            return "I'm sorry, something went wrong. Please try again."

    async def end_session(self, session_id: str, conversation_id, duration_sec: int = 0) -> None:
        try:
            async with async_session_factory() as db:
                memory = await self._memory.load(session_id, db)
                tools_used = list(memory.state.get("task_status", {}).keys())
                generator = CallSummaryGenerator()
                # Shield from cancellation — the WebSocket close event can race with this
                # LLM call. Without shield, the DB write never happens.
                await asyncio.shield(generator.generate(
                    session_id=session_id,
                    conversation_id=conversation_id,
                    memory=memory,
                    tools_used=tools_used,
                    duration_sec=duration_sec,
                    db=db,
                ))
        except Exception as exc:
            logger.error("End session summary error: %s", exc)
