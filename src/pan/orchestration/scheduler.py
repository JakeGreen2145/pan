import uuid

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from langgraph.graph.state import CompiledStateGraph

from pan.orchestration.router import extract_ai_response, route_message

logger = structlog.get_logger()


class PanScheduler:
    def __init__(self, graph: CompiledStateGraph) -> None:
        self.graph = graph
        self._scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        self._scheduler.add_job(
            self._run_rent_check,
            trigger="cron",
            day=1,
            hour=9,
            minute=0,
            id="rent_check_monthly",
            replace_existing=True,
        )

        self._scheduler.add_job(
            self._run_transaction_sync,
            trigger="interval",
            hours=6,
            id="plaid_transaction_sync",
            replace_existing=True,
        )

        self._scheduler.add_job(
            self._run_payment_matching,
            trigger="interval",
            hours=6,
            minutes=15,
            id="payment_auto_match",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("scheduler_started", job_count=len(self._scheduler.get_jobs()))

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

    async def _run_rent_check(self) -> None:
        thread_id = f"scheduled-rent-check-{uuid.uuid4().hex[:8]}"
        logger.info("scheduled_rent_check_started", thread_id=thread_id)

        try:
            events: list[dict] = []
            async for event in route_message(
                self.graph,
                "Check rent status for all tenants this month. "
                "List who has paid and who hasn't, including any late fees.",
                user_id="scheduler",
                user_role="owner",
                thread_id=thread_id,
                target_domain="house_manager",
            ):
                events.append(event)

            response = extract_ai_response(events)
            logger.info(
                "scheduled_rent_check_completed",
                thread_id=thread_id,
                response_preview=response[:200],
            )

        except Exception:
            logger.exception("scheduled_rent_check_failed", thread_id=thread_id)

    async def _run_transaction_sync(self) -> None:
        from pan.services.plaid_service import sync_all_items

        logger.info("scheduled_transaction_sync_started")
        try:
            count = await sync_all_items()
            logger.info("scheduled_transaction_sync_completed", new_transactions=count)
        except Exception:
            logger.exception("scheduled_transaction_sync_failed")

    async def _run_payment_matching(self) -> None:
        from pan.services.notifications import (
            notify_reconciliation_summary,
        )
        from pan.services.payment_matcher import (
            get_reconciliation_summary,
            match_unmatched_transactions,
        )

        logger.info("scheduled_payment_matching_started")
        try:
            results = await match_unmatched_transactions()
            logger.info("scheduled_payment_matching_completed", results=results)

            if results.get("matched", 0) > 0 or results.get("partial", 0) > 0:
                summary = await get_reconciliation_summary()
                await notify_reconciliation_summary(
                    month=summary.get("month", ""),
                    total_expected=summary.get("total_expected", 0),
                    total_received=summary.get("total_received", 0),
                    unpaid_tenants=[
                        t["name"]
                        for t in summary.get("tenants", [])
                        if t.get("paid", 0) < t.get("expected", 0)
                    ],
                )
        except Exception:
            logger.exception("scheduled_payment_matching_failed")
