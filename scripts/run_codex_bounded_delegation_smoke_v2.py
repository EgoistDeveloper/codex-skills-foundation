#!/usr/bin/env python3
"""Run bounded delegation smoke revision 2.

Revision 1 allowed delegation in natural language while the hard gate required at
least one child. That contract was ambiguous: completing the small read-only
fixture in the parent remained consistent with the selected skill's default-to-
one-agent rule. Revision 2 makes positive activation an explicit requirement,
pins the stable Codex multi-agent v1 feature on for both variants, and otherwise
reuses the established isolation, scoring, diagnostics, and restoration logic.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_codex_bounded_delegation_smoke as delegation

CASE_REVISION = 2
DELEGATION_PROMPT = """Bu repository yalnızca read-only denetim fixture'ıdır.

Üç bağımsız çalışma akışını denetle:
1. auth/session-policy.md
2. billing/refunds.md
3. inventory/reservations.md

Bu pozitif aktivasyon testinde delegation yalnızca izin verilen bir seçenek değildir; ölçülen davranışın zorunlu parçasıdır. Codex'in native `spawn_agent` collaboration aracını kullanarak en az bir, en fazla üç doğrudan alt agent oluştur. En az bir bağımsız çalışma akışını bir child agente devretmeden bütün denetimi parent olarak tek başına tamamlama. Her child'a sınırlandırılmış bir dosya veya çalışma akışı ver; child agentlar başka child açmamalı.

Hiçbir dosyayı değiştirme ve commit oluşturma. Parent olarak child sonuçlarını doğrula ve tek bir entegre risk raporunda birleştir. Her bulgu için dosya yolunu, fixture içindeki tam Risk-ID değerini, riski ve önerilen en küçük güvenli aksiyonu yaz. Sadece kaynaklarda bulunan bulguları raporla; kaynakta olmayan ayrıntı uydurma.
"""

_ORIGINAL_SESSION_CONFIG = delegation.session_config


def session_config(
    *,
    safe_session_builder: Any,
    disabled_skill_paths: list[str],
    disabled_mcp_names: list[str],
    plugin_ids: list[str],
    enable_core: bool,
) -> dict[str, Any]:
    """Build the established isolated config with explicit collab availability.

    Codex CLI 0.147.0 ships the stable `multi_agent` feature enabled by default.
    Pinning it here removes ambient user configuration as a possible explanation
    for a zero-child result. `multi_agent_v2` stays disabled so this campaign
    continues to measure the default v1 collaboration surface used by end users.
    """
    config = _ORIGINAL_SESSION_CONFIG(
        safe_session_builder=safe_session_builder,
        disabled_skill_paths=disabled_skill_paths,
        disabled_mcp_names=disabled_mcp_names,
        plugin_ids=plugin_ids,
        enable_core=enable_core,
    )
    features = config.setdefault("features", {})
    if not isinstance(features, dict):
        raise delegation.base.HarnessError("session features must be an object.")
    features["multi_agent"] = True
    features["multi_agent_v2"] = False
    config["include_collaboration_mode_instructions"] = True
    return config


def apply_revision_contract() -> None:
    delegation.CASE_REVISION = CASE_REVISION
    delegation.DELEGATION_PROMPT = DELEGATION_PROMPT
    delegation.session_config = session_config


def main() -> int:
    apply_revision_contract()
    return delegation.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
