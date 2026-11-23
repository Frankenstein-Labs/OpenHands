from __future__ import annotations

from dataclasses import dataclass

from app.database.supabase import SupabaseClient
from app.runner.agent_server import AgentServerRunner
from app.worker.queue import JobQueue


@dataclass
class WorkerContext:
    supabase: SupabaseClient
    queue: JobQueue
    runner: AgentServerRunner
