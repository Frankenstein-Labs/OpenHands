import json
import os

import httpx
import pytest

from app.core.config import Settings
from app.runner.agent_server import AgentServerRunner, RunnerUnavailable
from app.worker.context import WorkerContext
from app.worker.handlers import execute_agent_run, reconcile_agent_run, settle_abandoned_run
from app.worker.queue import Job, new_job


class RecordingSupabase:
    def __init__(self, run: dict, model: dict | None = None) -> None:
        self.run = run
        self.model = model
        self.calls: list[tuple[str, str, dict]] = []
        self.settled: dict | None = None

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == 'GET' and path == 'agent_runs':
            return [self.run]
        if method == 'GET' and path == 'models':
            return [self.model] if self.model else []
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


def make_ctx(
    run: dict, runner: FakeRunner, model: dict | None = None
) -> tuple[WorkerContext, RecordingSupabase, RecordingQueue]:
    supabase = RecordingSupabase(run, model)
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

    assert result == {'settled': 'completed', 'credits_used': 0.0}
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
    body = json.loads(seen['body'])
    assert body['initial_message']['content'][0]['text'] == 'fix the bug'
    assert body['agent_settings'] == {'llm': {'model': 'cortex-0'}}
    assert body['workspace'] == {'kind': 'LocalWorkspace', 'working_dir': '/workspace'}


@pytest.mark.asyncio
async def test_runner_sends_agent_settings_and_workspace_without_a_model() -> None:
    """The Agent Server rejects a conversation missing either field with 422."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen['body'] = json.loads(request.read().decode())
        return httpx.Response(201, json={'id': 'conv-10'})

    settings = Settings(agent_server_url='http://agent-server', agent_server_workspace_root='/tmp/runs')
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    runner = AgentServerRunner(settings, client=client)

    await runner.start(prompt='hello')
    await client.aclose()

    assert seen['body']['agent_settings'] == {}
    assert seen['body']['workspace'] == {'kind': 'LocalWorkspace', 'working_dir': '/tmp/runs'}


@pytest.mark.asyncio
async def test_runner_reports_unavailable_without_a_server_url() -> None:
    runner = AgentServerRunner(Settings(agent_server_url=None))
    with pytest.raises(RunnerUnavailable):
        await runner.start(prompt='hello')


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get('CORTEX_AGENT_SERVER_URL'),
    reason='set CORTEX_AGENT_SERVER_URL to run against a live Agent Server',
)
async def test_runner_creates_and_cancels_a_real_conversation() -> None:
    settings = Settings(
        agent_server_url=os.environ['CORTEX_AGENT_SERVER_URL'],
        agent_server_api_key=os.environ.get('CORTEX_AGENT_SERVER_API_KEY') or None,
        agent_server_timeout_seconds=120.0,
        agent_server_llm_model=os.environ.get('CORTEX_AGENT_SERVER_LLM_MODEL') or None,
        agent_server_llm_base_url=os.environ.get('CORTEX_AGENT_SERVER_LLM_BASE_URL') or None,
        agent_server_llm_api_key=os.environ.get('CORTEX_AGENT_SERVER_LLM_API_KEY') or None,
    )
    runner = AgentServerRunner(settings)
    try:
        conversation = await runner.start(
            prompt='Reply with the single word: pong',
            title='cortex-runner-integration',
            working_dir='/tmp/cortex-runner-integration',
        )
        assert conversation['id']
        state = await runner.status(conversation['id'])
        assert state.get('execution_status')
        await runner.cancel(conversation['id'])
    finally:
        await runner.aclose()
