# Codex Skills Foundation v0.2 Aday Sürüm

Bu paket; Codex, ChatGPT, Claude Code ve açık Agent Skills / Agent Plugins biçimlerini kullanan istemciler için yalın, kanıt odaklı bir mühendislik temelidir.

Bu çalışma **Pull Request #1'e uygulanmış ve doğrulanmış bir yama değildir**. İlgili PR bu ortamdan okunamadığı için temiz odada hazırlanmış bir karşılaştırma adayıdır. Gerçek dalla dosya ve davranış bazında karşılaştırılmadan merge edilmemelidir. Aynı dosya adına sahip olmak, aynı işi doğru yapmak anlamına gelmiyor. İnsanlar klasör isimlerine gereğinden fazla güveniyor. 🫠

## Paket modeli

| Paket | Varsayılan mı? | Amaç |
|---|---:|---|
| `engineering-foundation-core` | Evet | Görev sözleşmesi, plan, sınırlı orkestrasyon, uygulama, debugging, review, verification ve handoff |
| `engineering-foundation-laravel` | Yalnız Laravel/PHP | Projenin gerçek sürümlerine ve kalıplarına göre Laravel çalışma disiplini; Boost varsa güncel bağlam kaynağı |
| `engineering-foundation-design` | Yalnız UI/tasarım | Tek tasarım yönü, tipografi/token sözleşmesi, gerçek durumlar ve görsel doğrulama |

Skill adları ve açıklamaları, skill gövdesi yüklenmeden önce keşif bağlamına girebilir. Bu yüzden bütün yetenekleri tek pakete doldurmak token ekonomisi değil, dijital erzak istifçiliğidir.

## Manifest katmanları

Her plugin üç ayrı hedef taşır:

- `plugin.json`: Agent Plugins 1.0.0 taşınabilir manifesti;
- `.codex-plugin/plugin.json`: OpenAI ChatGPT/Codex adaptörü;
- `.claude-plugin/plugin.json`: Claude Code adaptörü.

Ortak metadata `catalog/plugins.json` dosyasından üretilir. Provider şemaları ve runtime davranışları aynı olmadığı için adaptörler tek JSON'muş gibi davranmaz.

## Gereksinim ve doğrulama

Normal bootstrap üçüncü taraf Python paketi istemez; Python 3.11 veya daha yeni sürüm gerekir.

```powershell
./scripts/bootstrap.ps1
```

veya:

```bash
./scripts/bootstrap.sh
```

Evidence gate, bir task contract verilirse kabul kriterlerinden birinin sessizce atlanmasını da yakalar:

```bash
python scripts/evidence_gate.py \
  examples/completion-evidence.pass.json \
  --contract examples/task-contract.static-validation.json
```

Eval fixture'ları sentetiktir. Scorer'ın yeşil çıkması yalnız scorer mantığının çalıştığını gösterir; Codex veya Claude'un görevi doğru yaptığına dair canlı kanıt değildir.

## İsteğe bağlı proje agent profilleri

Taşınabilir skill, host'un native subagent'larıyla çalışır. Tekrarlanan işler için ayrıca model sabitlemeyen üç dar, read-only profil bulunur: explorer, reviewer ve evidence auditor.

Önce dry-run:

```powershell
python scripts/install_agent_profiles.py --provider codex --target D:\proje
python scripts/install_agent_profiles.py --provider claude --target D:\proje
```

Dosyalar incelendikten sonra `--apply` eklenir. Çakışan mevcut dosyalar `--force` açıkça verilmeden ezilmez. Ayrıntı: `docs/agent-profiles.md`.

## Bilinçli olarak eklenmeyenler

- MCP server ve hook;
- credential veya telemetry;
- kontrolsüz external-model router;
- sabit model adları;
- recursive subagent zinciri;
- otomatik commit, push, merge, migration veya deploy;
- statik unit testlerden uydurulmuş “agent davranışı doğrulandı” iddiası.

Mimari gerekçeler `AUDIT_REPORT_TR.md`, gerçek PR ile güvenli karşılaştırma sırası `MIGRATION_FROM_PR1.md` içindedir.
