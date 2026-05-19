# Module classification

This table is the working map for loose or overlapping modules. It is not a
deletion list by itself; archived modules should stay importable until callers
are migrated and regression tests cover the replacement path.

| Module | Class | Next action | Reason |
| :--- | :--- | :--- | :--- |
| `apps/web_gui.py` | ativo | Split by route domain with regression tests first. | It is the current Python FastAPI runtime backend and still owns the live API surface. |
| `nexus_core/organization/*` | ativo | Keep as the default supervised daemon/runtime layer. | It owns approvals, execution plans, verification, replay and organizational memory. |
| `nexus_core/execution_protocol.py` | ativo | Keep as the command approval/execution contract. | It is already wired into backend action approval and execution flows. |
| `nexus_core/interaction/interaction_engine.py` | integrar | Use as the prompt/response normalization layer. | It should modularize intent handling, prompt assembly and response shaping now done manually in backend flows. |
| `nexus_core/conversation/conversation_manager.py` | integrar | Move chat turn assembly and persistence behind this manager. | It can replace duplicated conversation state handling in `apps/web_gui.py`. |
| `nexus_core/actions_registry.py` | integrar | Promote to the official action/tool registry. | Tool metadata and allow/deny behavior should have one registry instead of route-local definitions. |
| `nexus_core/simulation_layer.py` | integrar | Place before approval execution for dry-run impact checks. | It belongs in the approval/execution pipeline, especially for commands with filesystem or system impact. |
| `nexus_core/recovery_engine.py` | integrar | Place after failed execution and verification. | It should generate safe recovery proposals without bypassing human approval. |
| `nexus_core/cognitive/*` | ativo | Keep, but expose through route modules instead of direct backend globals. | Tests already cover cognitive state, planner, simulator, learning and profile behavior. |
| `nexus_core/memory/*` | ativo | Keep as durable memory implementation. | SQLite-backed memory is part of the current runtime. |
| `nexus_core/nexus_core_v3.py` | arquivar | Freeze and remove callers after v4/organization coverage is complete. | It is a legacy core path beside the current v4 and organization runtime. |
| `core_modules/nexus_core_v3.py` | arquivar | Keep only as migration reference until no docs/tests point to it. | Duplicate legacy placement increases confusion. |
| `nexus_core/execution_engine.py` | arquivar | Prefer `execution_protocol.py` and `organization/runtime.py`. | The newer flow has approvals, budgets, evidence and replay. |
| `nexus_core/memory_hierarchy.py` | arquivar | Keep as reference unless a concrete caller needs hierarchical memory. | Current durable memory paths are SQLite and organizational memory. |
| `nexus_core/skill_engine.py` | arquivar | Do not enable dynamic code writing without a formal policy. | Safe operation needs explicit sandboxing, approvals and audit before runtime code generation. |
| `backend/` | arquivar | Treat as Rust/Axum lab, not default runtime. | Python FastAPI is the package/runtime backend today; the Rust backend can inform future migration. |
| `dist/`, `test_db/`, `memory/long_term.json` | remover | Keep out of Git and regenerate locally. | These are generated artifacts or local data, not product source. |

## Integration order

1. `actions_registry.py`: make tool/action metadata central first.
2. `interaction_engine.py`: route prompt/response shaping through a single layer.
3. `conversation_manager.py`: move chat state and persistence behind the manager.
4. `simulation_layer.py`: run dry-run checks before approval execution.
5. `recovery_engine.py`: generate recovery proposals after failed execution.

## Refactor guardrails

- Keep route behavior stable before moving code out of `apps/web_gui.py`.
- Add or extend route regression tests for every extracted route group.
- Archive by removing imports and docs references first, then deleting code in a
  separate change.
