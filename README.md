# Codex Skills Foundation

Codex, Codex Cloud, Claude Code, Hermes Agent ve Agent Skills uyumlu diğer istemciler için **kanıta dayalı, token-bilinçli ve sınırlandırılmış yazılım mühendisliği iş akışları**.

Bu repository tek bir dev prompt değildir. Taşınabilir skill çekirdeği, Codex ve Claude adaptörleri, dar yetkili uzman agent tanımları, deterministik yönlendirme araçları ve davranış eval'ları içerir.

## Temel hedef

Agent'ın:

- görevi anlamadan koda atlamamasını;
- gereksiz multi-agent ve subagent maliyeti oluşturmamasını;
- mevcut kod stiline uyan en küçük doğru değişikliği yapmasını;
- testler geçtikten sonra gerekçesiz biçimde kendi kodunu tekrar refaktör etmemesini;
- tasarım görevlerinde tek, kurumsal ve doğrulanabilir bir yön üretmesini;
- “tamamlandı” demeden önce taze kanıt sunmasını

sağlayan bir çalışma sözleşmesi sunmak.

> Hiçbir talimat paketi olasılıksal bir agent için sıfır hata garantisi veremez. Bu foundation; hata olasılığını, kapsam kaymasını, gereksiz yeniden çalışmayı ve yanlış tamamlanma iddialarını ölçülebilir kapılarla azaltır.

## Repository yapısı

```text
.
├── .agents/plugins/marketplace.json
├── .claude-plugin/marketplace.json
├── .codex/agents/                 # Bu repository için Codex uzmanları
├── plugins/engineering-foundation/
│   ├── plugin.json                # Agent Plugins v1 taşınabilir manifest
│   ├── .codex-plugin/plugin.json  # Codex görünüm/uyumluluk katmanı
│   ├── .claude-plugin/plugin.json # Claude Code manifesti
│   ├── agents/                    # Claude Code uzman agent'ları
│   ├── adapters/                  # Kurulabilir istemci adaptörleri
│   ├── scripts/                   # Router, evidence gate, adapter installer
│   └── skills/                    # Taşınabilir mühendislik skill'leri
├── evals/                         # Deterministik davranış vakaları
├── scripts/                       # Repository doğrulama ve bootstrap
└── tests/                         # Standart kütüphane ile unit testler
```

## Skill kataloğu

| Skill | Amaç |
|---|---|
| `engineering-router` | Görevi sınıflandırır; tek agent, subagent veya bounded multi-agent yolunu seçer |
| `goal-contract` | İsteği kabul kriterleri, non-goals ve kanıt sözleşmesine dönüştürür |
| `bounded-plan` | Gerektiği kadar plan üretir; plan döngülerini sınırlar |
| `surgical-implementation` | En küçük doğru diff'i üretir; drive-by refactor'ı yasaklar |
| `test-first-change` | Uygun seam'lerde red-green-refactor uygular |
| `systematic-debugging` | Reproduce → localize → hypothesize → fix → guard döngüsü |
| `bounded-multi-agent` | Bağımsız işleri sınırlı ve token-bilinçli biçimde delege eder |
| `independent-review` | Spec uyumu ve kod kalitesini taze bağlamla inceler |
| `verification-gate` | Taze komut çıktısı ve requirement kanıtı olmadan tamamlanmayı engeller |
| `source-grounded-research` | Güncel teknik kararları birincil kaynak ve provenance ile temellendirir |
| `corporate-ui-design` | Tek yönlü, kurumsal, erişilebilir ve görsel olarak doğrulanmış UI üretir |
| `laravel-engineering` | Laravel/PHP için sürüm-duyarlı, mevcut konvansiyonlara uygun değişiklikler |
| `cloud-readiness` | Codex Cloud setup, cache, secrets ve network sınırlarını doğrular |
| `context-handoff` | Uzun veya kesintiye uğramış görevleri kanıt odaklı bir handoff'a sıkıştırır |
| `skill-authoring` | Skill trigger, progressive disclosure, yardımcı script ve eval tasarımını yönlendirir |

## Hızlı doğrulama

Linux/macOS/WSL:

```bash
./scripts/bootstrap.sh
```

Windows PowerShell:

```powershell
./scripts/bootstrap.ps1
```

Doğrudan:

```bash
python scripts/validate_repository.py --strict
python -m unittest discover -s tests -v
```

## Codex yerel marketplace

```bash
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref main
codex plugin add engineering-foundation@egoistdeveloper-foundation
```

Geliştirme branch'ini test etmek için `--ref <branch>` kullanın ve yeni bir Codex thread'i başlatın.

## Claude Code marketplace

Claude Code içinde:

```text
/plugin marketplace add EgoistDeveloper/codex-skills-foundation
/plugin install engineering-foundation@egoistdeveloper-foundation
```

## Codex uzman agent adaptörleri

Plugin skill'leri tek başına çalışır. İsteğe bağlı Codex uzmanlarını hedef projeye kurmak için:

```bash
python plugins/engineering-foundation/scripts/install_codex_agents.py --target .codex/agents --apply
```

Komut mevcut farklı dosyaları varsayılan olarak ezmez. Önce `--dry-run` ile önizleme yapılabilir.

## Codex Cloud

Cloud environment setup script:

```bash
./scripts/bootstrap.sh
```

Maintenance script:

```bash
python scripts/validate_repository.py
```

Agent-phase internet erişimini varsayılan olarak kapalı tutun. Güncel kaynak araştırması gereken görevlerde yalnızca gerekli domain ve HTTP yöntemlerini allowlist'e ekleyin. Ayrıntılar: [`docs/codex-cloud.md`](docs/codex-cloud.md).

## Tasarım sözleşmesi

Tasarım görevleri için önce mevcut design system okunur; yoksa tek bir yön kilitlenir. `corporate-ui-design` skill'i:

- light ve dark temayı ayrı kalite yüzeyleri olarak ele alır;
- Türkçe glyph desteğini doğrular;
- rastgele neon, kart mozaiği, glassmorphism ve “AI görünümü”nü engeller;
- typography, spacing, layout ve component token'larını `DESIGN.md` ile sabitler;
- Playwright veya mevcut browser aracıyla görsel ve davranışsal kontrol ister;
- kabul kriterleri sağlandıktan sonra yeni varyant üretmez.

Şablon: [`plugins/engineering-foundation/skills/corporate-ui-design/assets/DESIGN.template.md`](plugins/engineering-foundation/skills/corporate-ui-design/assets/DESIGN.template.md).

## Güvenlik

Bu sürüm:

- MCP server kurmaz;
- secret istemez veya saklamaz;
- harici model/provider yapılandırmasını değiştirmez;
- agent internet erişimini açmaz;
- recursive delegation kullanmaz;
- reviewer ve verifier agent'larını read-only tanımlar.

Güvenlik politikası: [`SECURITY.md`](SECURITY.md).

## Durum

`0.1.0` foundation sürümü. Kapsam, doğrulanan çekirdek davranışlar ve adaptörlerle sınırlıdır. Canlı model eval sonuçları ancak gerçek Codex/Claude/Hermes oturumları çalıştırıldığında kaydedilecektir; deterministik eval harness sahte başarı üretmez.
