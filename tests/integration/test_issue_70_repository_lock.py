from __future__ import annotations

import copy
import multiprocessing
from pathlib import Path
from queue import Empty

import harness_core


SOURCE = {
    "source_type": "repository_fact",
    "reference": "snapshot:issue-70-cross-process",
    "digest": "sha256:" + ("7" * 64),
}
RACE_COUNT = 100


def _payload(index: int) -> dict:
    return {
        "domain": "delivery",
        "directive": f"Require linearized delivery evidence {index}.",
        "scope": [f"delivery/race-{index}/**"],
        "sources": [copy.deepcopy(SOURCE)],
    }


def _race_worker(
    repository_path: str,
    action: str,
    operation_ids: tuple[str, ...],
    start_barrier,
    finish_barrier,
    result_queue,
) -> None:
    repository = harness_core.GovernanceRepository(Path(repository_path))
    for index, operation_id in enumerate(operation_ids):
        start_barrier.wait(timeout=30)
        if action == "apply":
            result = repository.apply(operation_id)
        else:
            result = repository.cancel(operation_id)
        diagnostic = (
            result["diagnostics"][0]["code"]
            if result["diagnostics"]
            else None
        )
        result_queue.put((index, action, result["status"], diagnostic))
        finish_barrier.wait(timeout=30)


def test_apply_cancel_is_linearized_across_processes_for_100_races(
    tmp_path: Path,
) -> None:
    repository = harness_core.GovernanceRepository(tmp_path)
    operation_ids = tuple(f"op-race-{index}" for index in range(RACE_COUNT))
    rule_ids = tuple(f"race-rule-{index}" for index in range(RACE_COUNT))
    for index, (operation_id, rule_id) in enumerate(
        zip(operation_ids, rule_ids, strict=True)
    ):
        request = harness_core.build_operation_request(
            operation_id,
            "add",
            rule_id,
            base_revision=0,
            payload=_payload(index),
        )
        assert repository.register(request)["status"] == "pending"

    context = multiprocessing.get_context("spawn")
    start_barrier = context.Barrier(3)
    finish_barrier = context.Barrier(3)
    result_queue = context.Queue()
    workers = [
        context.Process(
            target=_race_worker,
            args=(
                str(tmp_path),
                action,
                operation_ids,
                start_barrier,
                finish_barrier,
                result_queue,
            ),
        )
        for action in ("apply", "cancel")
    ]
    records: list[tuple[int, str, str, str | None]] = []
    for worker in workers:
        worker.start()
    try:
        for _ in operation_ids:
            start_barrier.wait(timeout=30)
            finish_barrier.wait(timeout=30)
            records.extend(
                result_queue.get(timeout=30) for _ in range(2)
            )
    finally:
        for worker in workers:
            worker.join(timeout=30)
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=10)

    assert [worker.exitcode for worker in workers] == [0, 0]
    try:
        unexpected = result_queue.get_nowait()
    except Empty:
        unexpected = None
    assert unexpected is None

    by_index: dict[int, list[tuple[str, str, str | None]]] = {}
    for index, action, status, diagnostic in records:
        by_index.setdefault(index, []).append((action, status, diagnostic))

    final = harness_core.GovernanceRepository(tmp_path).read()
    assert len(by_index) == RACE_COUNT
    for index, (operation_id, rule_id) in enumerate(
        zip(operation_ids, rule_ids, strict=True)
    ):
        terminal = final["operations"][operation_id]["status"]
        outcomes = by_index[index]
        assert len(outcomes) == 2
        if terminal == "applied":
            assert rule_id in final["rules"]
            assert ("apply", "applied", None) in outcomes
            assert (
                "cancel",
                "rejected",
                "OPERATION_ALREADY_COMMITTED",
            ) in outcomes
        else:
            assert terminal == "cancelled"
            assert rule_id not in final["rules"]
            assert ("cancel", "cancelled", None) in outcomes
            assert ("apply", "rejected", "OPERATION_CANCELLED") in outcomes
