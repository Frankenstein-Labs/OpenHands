import pytest

from app.worker.metering import accumulated_usage, credits_for_usage

# Shape captured from a live Agent Server conversation state (OpenHands 1.63.1).
CONVERSATION_STATE = {
    'execution_status': 'idle',
    'stats': {
        'usage_to_metrics': {
            'default': {
                'model_name': 'gpt-5.6',
                'accumulated_token_usage': {
                    'prompt_tokens': 1200,
                    'completion_tokens': 300,
                },
            },
            'condenser': {
                'model_name': 'gpt-5.6',
                'accumulated_token_usage': {
                    'prompt_tokens': 200,
                    'completion_tokens': 0,
                },
            },
        }
    },
}

MODEL = {'id': 'cortex-0', 'input_cost_per_1k': 0.5, 'output_cost_per_1k': 1.5}


def test_usage_is_summed_across_every_model_profile() -> None:
    assert accumulated_usage(CONVERSATION_STATE) == {
        'prompt_tokens': 1400,
        'completion_tokens': 300,
    }


def test_usage_of_a_conversation_without_metrics_is_zero() -> None:
    assert accumulated_usage({'execution_status': 'running'}) == {
        'prompt_tokens': 0,
        'completion_tokens': 0,
    }


def test_credits_use_the_catalogue_rates_of_the_run_model() -> None:
    usage = {'prompt_tokens': 1400, 'completion_tokens': 300}

    assert credits_for_usage(usage, MODEL) == pytest.approx(0.7 + 0.45)


def test_unpriced_model_books_no_credits() -> None:
    usage = {'prompt_tokens': 1400, 'completion_tokens': 300}
    unpriced = {'id': 'cortex-0', 'input_cost_per_1k': None, 'output_cost_per_1k': None}

    assert credits_for_usage(usage, unpriced) == 0.0
    assert credits_for_usage(usage, None) == 0.0


def test_credits_never_exceed_the_reserved_budget() -> None:
    usage = {'prompt_tokens': 100_000, 'completion_tokens': 100_000}

    assert credits_for_usage(usage, MODEL, budget_credits=2.0) == 2.0
    assert credits_for_usage(usage, MODEL, budget_credits=None) == pytest.approx(200.0)
