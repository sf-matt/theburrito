from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime

from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

from .config import Settings
from .detector import detect_privileged_containers
from .investigator import OpenAIInvestigator
from .investigator_protocol import Investigator
from .kube import (
    KubernetesReader,
    WorkloadResolver,
    load_core_api,
    validate_pod_reference,
)
from .logging_config import configure_logging
from .registry import InvestigationRegistry
from .tools import ToolExecutor
from .watcher import InvestigationWorker, PodWatcher


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect and investigate privileged Kubernetes Pods"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("watch", help="continuously watch Pods cluster-wide")
    investigate = subparsers.add_parser(
        "investigate", help="investigate privileged containers in one Pod"
    )
    investigate.add_argument("--namespace", required=True)
    investigate.add_argument("--pod", required=True)
    inventory = subparsers.add_parser(
        "inventory", help="show persistent workload assessment records"
    )
    inventory.add_argument("--disposition")
    inventory.add_argument("--acknowledged-only", action="store_true")
    acknowledge = subparsers.add_parser(
        "acknowledge", help="human-acknowledge one assessment record"
    )
    acknowledge.add_argument("--record-id", required=True)
    acknowledge.add_argument("--reason", required=True)
    acknowledge.add_argument(
        "--review-after",
        help="RFC 3339 timestamp or YYYY-MM-DD date requiring later review",
    )
    return parser


def build_investigator(
    settings: Settings, reader: KubernetesReader
) -> Investigator | None:
    if settings.dry_run:
        return None
    assert settings.llm_model is not None
    if settings.llm_provider == "openai":
        assert settings.openai_api_key is not None
        return OpenAIInvestigator(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            tool_executor=ToolExecutor(reader),
            max_tool_calls=settings.max_tool_calls,
            reasoning_effort=settings.llm_reasoning_effort,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def run_watch(settings: Settings) -> None:
    api = load_core_api(settings.kubeconfig)
    reader = KubernetesReader(api)
    cluster_id = api.api_client.configuration.host
    worker = InvestigationWorker(
        registry=InvestigationRegistry(
            settings.investigation_cooldown_seconds,
            state_file=settings.agent_state_file,
            cluster_id=cluster_id,
            observation_flush_seconds=settings.state_observation_flush_seconds,
        ),
        investigator=build_investigator(settings, reader),
        dry_run=settings.dry_run,
    )
    PodWatcher(
        api=api,
        label_selector=settings.watch_label_selector,
        worker=worker,
        workload_resolver=WorkloadResolver.from_core_api(api),
    ).run()


def run_manual(settings: Settings, namespace: str, pod_name: str) -> int:
    valid_namespace, valid_name = validate_pod_reference(
        namespace=namespace,
        pod_name=pod_name,
    )
    api = load_core_api(settings.kubeconfig)
    pod = api.read_namespaced_pod(name=valid_name, namespace=valid_namespace)
    workload = WorkloadResolver.from_core_api(api).resolve(pod)
    findings = detect_privileged_containers(pod, workload)
    if not findings:
        LOGGER.info(
            "No privileged containers detected", extra={"pod_name": valid_name}
        )
        return 0

    reader = KubernetesReader(api)
    investigator = build_investigator(settings, reader)
    registry = InvestigationRegistry(
        settings.investigation_cooldown_seconds,
        state_file=settings.agent_state_file,
        cluster_id=api.api_client.configuration.host,
        observation_flush_seconds=settings.state_observation_flush_seconds,
    )
    for finding in findings:
        if not registry.begin(finding, observation_only=settings.dry_run):
            record = registry.get(finding)
            print(json.dumps(record.to_dict() if record else {}, indent=2, sort_keys=True))
            continue
        try:
            if settings.dry_run:
                print(json.dumps(finding.to_dict(), indent=2, sort_keys=True))
                registry.complete(finding)
            else:
                assert investigator is not None
                assessment = investigator.investigate(finding)
                registry.complete(finding, assessment)
                print(json.dumps(assessment.to_dict(), indent=2, sort_keys=True))
        except Exception:
            registry.fail(finding)
            raise
    return 0


def _review_after_epoch(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "--review-after must be an RFC 3339 timestamp or YYYY-MM-DD"
        ) from exc
    if parsed.tzinfo is None:
        if len(value) == 10:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            raise ValueError("--review-after timestamp must include a timezone")
    return parsed.timestamp()


def _state_registry(settings: Settings) -> InvestigationRegistry:
    return InvestigationRegistry(
        settings.investigation_cooldown_seconds,
        state_file=settings.agent_state_file,
        cluster_id="inventory-only",
        observation_flush_seconds=settings.state_observation_flush_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    try:
        needs_kubernetes = args.command in {"watch", "investigate"}
        settings = Settings.from_environment(
            require_kubeconfig=needs_kubernetes,
            require_llm=needs_kubernetes,
        )
        configure_logging()
        if args.command == "watch":
            run_watch(settings)
            return 0
        if args.command == "investigate":
            return run_manual(settings, args.namespace, args.pod)
        registry = _state_registry(settings)
        if args.command == "inventory":
            print(
                json.dumps(
                    registry.inventory(
                        args.disposition,
                        acknowledged_only=args.acknowledged_only,
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        record = registry.acknowledge(
            args.record_id,
            args.reason,
            _review_after_epoch(args.review_after),
        )
        print(json.dumps(record.to_dict(), indent=2, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested")
        return 130
    except (ApiException, ConfigException, OSError, RuntimeError, ValueError) as exc:
        LOGGER.error("Application error", extra={"error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
