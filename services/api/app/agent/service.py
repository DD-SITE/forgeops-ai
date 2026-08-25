from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.checkpointer import get_checkpointer
from app.agent.graph import build_graph
from app.models.agent_run import (
    AgentAction,
    AgentActionStatus,
    AgentRun,
    AgentRunStatus,
    AuditLog,
)


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        query: str,
    ) -> AgentRun:
        run = AgentRun(
            workspace_id=workspace_id,
            user_id=user_id,
            thread_id=str(uuid4()),
            query=query.strip(),
            status=AgentRunStatus.QUEUED,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def stream_run(self, run: AgentRun):
        run.status = AgentRunStatus.RUNNING
        await self.session.commit()

        config = {"configurable": {"thread_id": run.thread_id}}

        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer)
            initial = {
                "workspace_id": str(run.workspace_id),
                "user_id": str(run.user_id),
                "query": run.query,
            }

            try:
                interrupted = False
                async for event in graph.astream(
                    initial,
                    config=config,
                    stream_mode="updates",
                ):
                    if "__interrupt__" in event:
                        interrupted = True
                    yield event

                snapshot = await graph.aget_state(config)
                await self._persist_snapshot(run, snapshot.values)
                await self._finish_from_state(
                    run,
                    snapshot.values,
                    interrupted=interrupted,
                )

            except Exception as exc:
                run.status = AgentRunStatus.FAILED
                run.error = f"{type(exc).__name__}: {exc}"
                await self.session.commit()
                raise

    async def resume(
        self,
        *,
        run: AgentRun,
        decision: str,
        payload: dict | None = None,
        approver_id: UUID,
    ):
        if run.status != AgentRunStatus.AWAITING_APPROVAL:
            raise ValueError("This run is not awaiting approval.")

        config = {"configurable": {"thread_id": run.thread_id}}
        resume_value = {"decision": decision}
        if payload is not None:
            resume_value["payload"] = payload

        async with get_checkpointer() as checkpointer:
            graph = build_graph(checkpointer)

            async for _event in graph.astream(
                Command(resume=resume_value),
                config=config,
                stream_mode="updates",
            ):
                pass

            snapshot = await graph.aget_state(config)
            await self._persist_snapshot(run, snapshot.values)
            await self._finish_from_state(run, snapshot.values, interrupted=False)

            action = await self._get_action(run.id)
            if action is not None:
                if decision == "reject":
                    action.status = AgentActionStatus.REJECTED
                elif decision in {"approve", "edit"}:
                    action.status = (
                        AgentActionStatus.EXECUTED
                        if snapshot.values.get("action_result", {}).get("status")
                        == "executed"
                        else AgentActionStatus.FAILED
                    )
                    action.approved_by = approver_id
                    action.result = snapshot.values.get("action_result")

                await self.session.commit()

            self.session.add(
                AuditLog(
                    workspace_id=run.workspace_id,
                    user_id=approver_id,
                    action_type=f"agent_action_{decision}",
                    resource_type="agent_run",
                    resource_id=str(run.id),
                    payload={"payload": payload or {}},
                )
            )
            await self.session.commit()

            return snapshot.values

    async def _finish_from_state(
        self,
        run: AgentRun,
        state: dict,
        *,
        interrupted: bool,
    ) -> None:
        if interrupted:
            run.status = AgentRunStatus.AWAITING_APPROVAL
            plan = state.get("action_plan")
            if plan and not await self._get_action(run.id):
                action = AgentAction(
                    run_id=run.id,
                    action_type=plan.get("action_type", "unknown"),
                    status=AgentActionStatus.PROPOSED,
                    payload=plan,
                )
                self.session.add(action)
                run.actions.append(action)
        else:
            result = state.get("action_result") or {}
            run.status = (
                AgentRunStatus.REJECTED
                if result.get("status") == "rejected"
                else AgentRunStatus.COMPLETED
            )
            run.answer = state.get("answer")
            run.completed_at = datetime.now(UTC)

        await self.session.commit()

    async def _persist_snapshot(self, run: AgentRun, state: dict) -> None:
        # Keep a compact application-level snapshot for dashboards/audit.
        safe_state = {
            key: value
            for key, value in state.items()
            if key not in {"sources", "context"}
        }
        run.state_snapshot = safe_state
        await self.session.commit()

    async def _get_action(self, run_id: UUID) -> AgentAction | None:
        result = await self.session.execute(
            select(AgentAction)
            .where(AgentAction.run_id == run_id)
            .order_by(AgentAction.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
