import httpx
import pytest

from app.core.config import Settings
from app.runner.agent_server import AgentServerRunner, RunnerUnavailable
from app.worker.context import WorkerContext
from app.worker.handlers import execute_agent_run, reconcile_agent_run, settle_abandoned_run
from app.worker.queue import Job, new_job


class RecordingSupabase:
    def __init__(self, run: dict) -> None:
        self.run = run
        self.calls: list[tuple[str, str, dict]] = []
        self.settled: dict | None = None

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == 'GET' and path == 'agent_runs':
            return [self.run]
        if path == 'rpc/settle_agent_run':
            self.settled = kwargs['json']
            return [self.run]
        return []

    async def close(self):
        return None


class RecordingQueue:
    def __init__(self) -> None:
        self.scheduled: list[tuple[Job, float]] = []

    async def schedule(self, job, delay_seconds):
        self.scheduled.append((job, delay_seconds))


class FakeRunner:
    def __init__(self, conversation: dict | None = None, status: dict | None = None) -> None:
        self.conversation = conversation or {'id': 'conv-1'}
        self.status_payload = status or {}
        self.started: list[dict] = []
        self.settings = Settings(agent_server_url='http://agent-server')

    async def start(self, **kwargs):
        self.started.append(kwargs)
        return self.conversation

    async def status(self, conversation_id):
        return self.status_payload

    async def aclose(self):
        return None


def make_ctx(run: dict, runner: FakeRunner) -> tuple[WorkerContext, RecordingSupabase, RecordingQueue]:
    supabase = RecordingSupabase(run)
    queue = RecordingQueue()
    return WorkerContext(supabase=supabase, queue=queue, runner=runner), supabase, queue


@pytest.mark.asyncio
async def test_execute_agent_run_starts_conversation_and_schedules_reconcile() -> None:
    run = {'id': 'run-1', 'status': 'queued', 'prompt': 'hello', 'model_id': None}
    runner = FakeRunner()
    ctx, supabase, queue = make_ctx(run, runner)

    result = await execute_agent_run(ctx, new_job('execute_agent_run', {'run_id': 'run-1'}))

    assert result == {'conversation_id': 'conv-1'}
    assert runner.started and runner.started[0]['prompt'] == 'hello'
    patches = [call for call in supabase.calls if call[0] == 'PATCH']
    assert patches[0][2]['json']['status'] == 'provisioning'
    assert patches[1][2]['json']['status'] == 'running'
    assert patches[1][2]['json']['conversation_id'] == 'conv-1'
    assert queue.scheduled[0][0].type == 'reconcile_agent_run'


@pytest.mark.asyncio
async def test_execute_agent_run_skips_a_run_that_is_already_running() -> None:
    run = {'id': 'run-1', 'status': 'running', 'prompt': 'hello', 'model_id': None}
    runner = FakeRunner()
    ctx, supabase, queue = make_ctx(run, runner)

    result = await execute_agent_run(ctx, new_job('execute_agent_run', {'run_id': 'run-1'}))

    assert result == {'skipped': 'running'}
    assert runner.started == []
    assert supabase.calls == [('GET', 'agent_runs', supabase.calls[0][2])]


@pytest.mark.asyncio
async def test_reconcile_settles_a_finished_run() -> None:
    run = {'id': 'run-1', 'status': 'running'}
    runner = FakeRunner(status={'execution_status': 'finished'})
    ctx, supabase, _ = make_ctx(run, runner)

    result = await reconcile_agent_run(
        ctx, new_job('reconcile_agent_run', {'run_id': 'run-1', 'conversation_id': 'conv-1'})
    )

    assert result == {'settled': 'completed'}
    assert supabase.settled['target_status'] == 'completed'
    assert supabase.settled['target_run_id'] == 'run-1'


@pytest.mark.asyncio
async def test_reconcile_reschedules_while_the_agent_is_still_working() -> None:
    run = {'id': 'run-1', 'status': 'running'}
    runner = FakeRunner(status={'execution_status': 'running'})
    ctx, supabase, queue = make_ctx(run, runner)

    result = await reconcile_agent_run(
        ctx, new_job('reconcile_agent_run', {'run_id': 'run-1', 'conversation_id': 'conv-1'})
    )

    assert result == {'rescheduled': True}
    assert supabase.settled is None
    assert queue.scheduled and queue.scheduled[0][0].type == 'reconcile_agent_run'


@pytest.mark.asyncio
async def test_abandoned_job_settles_the_run_as_failed() -> None:
    run = {'id': 'run-1', 'status': 'provisioning'}
    ctx, supabase, _ = make_ctx(run, FakeRunner())

    await settle_abandoned_run(ctx, new_job('execute_agent_run', {'run_id': 'run-1'}))

    assert supabase.settled['target_status'] == 'failed'
    assert 'retries' in supabase.settled['target_error']


@pytest.mark.asyncio
async def test_runner_posts_the_prompt_to_the_agent_server() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen['path'] = request.url.path
        seen['key'] = request.headers.get('X-Session-API-Key')
        seen['body'] = request.read().decode()
        return httpx.Response(200, json={'id': 'conv-9'})

    settings = Settings(agent_server_url='http://agent-server', agent_server_api_key='secret-key')
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    runner = AgentServerRunner(settings, client=client)

    result = await runner.start(prompt='fix the bug', model_id='cortex-0', title='run 1')
    await client.aclose()

    assert result == {'id': 'conv-9'}
    assert seen['path'] == '/api/conversations'
    assert seen['key'] == 'secret-key'
    assert 'fix the bug' in seen['body']


@pytest.mark.asyncio
async def test_runner_reports_unavailable_without_a_server_url() -> None:
    runner = AgentServerRunner(Settings(agent_server_url=None))
    with pytest.raises(RunnerUnavailable):
        await runner.start(prompt='hello')
