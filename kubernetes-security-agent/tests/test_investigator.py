import logging
from types import SimpleNamespace

import pytest

from agent.investigator import OpenAIInvestigator
from agent.models import AssessmentDisposition, SecurityFinding, WorkloadIdentity


class RecordingToolExecutor:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, name: str, arguments: str) -> str:
        self.calls.append((name, arguments))
        return '{"ok":true,"result":{"name":"risky-pod"}}'


class FakeResponses:
    def __init__(self, outputs: list[SimpleNamespace]) -> None:
        self.outputs = outputs
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.outputs.pop(0)


def finding() -> SecurityFinding:
    return SecurityFinding(
        namespace="ai-lab",
        pod_name="risky-pod",
        pod_uid="uid-1",
        container_name="risky",
        detection_reason="privileged",
        relevant_security_configuration={"privileged": True},
        workload=WorkloadIdentity(
            api_version="apps/v1",
            kind="DaemonSet",
            namespace="ai-lab",
            name="risky-workload",
            uid="workload-uid-1",
        ),
        fingerprint="fingerprint-1",
    )


def test_native_tool_loop_returns_final_assessment(caplog) -> None:
    call = SimpleNamespace(
        type="function_call",
        name="get_pod_details",
        arguments='{"namespace":"ai-lab","pod_name":"risky-pod"}',
        call_id="call-1",
    )
    responses = FakeResponses(
        [
            SimpleNamespace(
                output=[call],
                output_text="",
                usage=SimpleNamespace(
                    input_tokens=100,
                    input_tokens_details=SimpleNamespace(
                        cached_tokens=20, cache_write_tokens=30
                    ),
                    output_tokens=40,
                    output_tokens_details=SimpleNamespace(reasoning_tokens=25),
                    total_tokens=140,
                ),
            ),
            SimpleNamespace(
                output=[],
                output_text=(
                    '{"disposition":"review_warranted",'
                    '"summary":"Privilege needs review",'
                    '"observed_concern":"Container is privileged",'
                    '"supporting_evidence":["privileged is true"],'
                    '"potential_implications":["host compromise impact"],'
                    '"recommended_next_steps":["confirm owner"],'
                    '"uncertainties":["workload purpose is unknown"]}'
                ),
                usage=SimpleNamespace(
                    input_tokens=150,
                    input_tokens_details=SimpleNamespace(
                        cached_tokens=80, cache_write_tokens=0
                    ),
                    output_tokens=60,
                    output_tokens_details=SimpleNamespace(reasoning_tokens=15),
                    total_tokens=210,
                ),
            ),
        ]
    )
    client = SimpleNamespace(responses=responses)
    executor = RecordingToolExecutor()
    investigator = OpenAIInvestigator(
        model="test-model",
        api_key="test-key",
        tool_executor=executor,
        max_tool_calls=2,
        client=client,
    )

    with caplog.at_level(logging.INFO, logger="agent.investigator"):
        assessment = investigator.investigate(finding())

    assert assessment.disposition == AssessmentDisposition.REVIEW_WARRANTED
    assert assessment.summary == "Privilege needs review"
    assert executor.calls == [
        (
            "get_pod_details",
            '{"namespace":"ai-lab","pod_name":"risky-pod"}',
        )
    ]
    second_input = responses.requests[1]["input"]
    assert second_input[-1] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": '{"ok":true,"result":{"name":"risky-pod"}}',
    }
    assert responses.requests[0]["text"]["format"]["type"] == "json_schema"
    assert responses.requests[0]["text"]["verbosity"] == "low"
    assert responses.requests[0]["reasoning"] == {"effort": "low"}
    assert responses.requests[0]["max_output_tokens"] == 2048
    prompt = responses.requests[0]["input"][0]["content"]
    assert "fingerprint-1" not in prompt
    assert "uid-1" not in prompt
    usage_record = next(
        record for record in caplog.records if record.message == "LLM investigation usage"
    )
    assert usage_record.api_call_count == 2
    assert usage_record.tool_call_count == 1
    assert usage_record.input_tokens == 250
    assert usage_record.cached_input_tokens == 100
    assert usage_record.cache_write_tokens == 30
    assert usage_record.output_tokens == 100
    assert usage_record.reasoning_tokens == 40
    assert usage_record.total_tokens == 350


def test_tool_call_limit_is_enforced_before_execution() -> None:
    call = SimpleNamespace(
        type="function_call",
        name="get_namespace_pods",
        arguments='{"namespace":"ai-lab"}',
        call_id="call-1",
    )
    responses = FakeResponses(
        [SimpleNamespace(output=[call, call], output_text="")]
    )
    executor = RecordingToolExecutor()
    investigator = OpenAIInvestigator(
        model="test-model",
        api_key="test-key",
        tool_executor=executor,
        max_tool_calls=1,
        client=SimpleNamespace(responses=responses),
    )

    with pytest.raises(RuntimeError, match="MAX_TOOL_CALLS=1"):
        investigator.investigate(finding())

    assert executor.calls == []
