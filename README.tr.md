# Codex Skills Foundation

Codex, ChatGPT, Codex Cloud, Claude Code ve Agent Skills / Agent Plugins uyumlu istemciler için modüler, kanıta dayalı ve token-bilinçli mühendislik foundation'ı.

## Hangi paket kurulmalı?

| Paket | Kullanım |
|---|---|
| `engineering-foundation-core` | Her yazılım projesinde |
| `engineering-foundation-laravel` | Yalnız Laravel/PHP projelerinde |
| `engineering-foundation-design` | Arayüz üretimi, redesign ve visual QA işlerinde |
| `engineering-foundation-cloud` | Codex Cloud veya başka remote-agent ortamlarında |
| `engineering-foundation-authoring` | Skill/plugin üretirken veya bakım yaparken |

Core; task contract, plan/milestone, sınırlı delegasyon, küçük ve doğru diff, sistematik debugging, güncel kaynak araştırması, review, doğrulama ve handoff davranışlarını içerir. Diğer paketler yalnız gerektiğinde kurulur. Böylece backend düzeltmesinde tasarım manifestosu, normal projede Cloud setup talimatı taşınmaz. İnsanlar her şeyi tek çekmeceye koymayı sever; agent context'i bu geleneğe katılmak zorunda değil.

## Codex son kullanıcı kurulumu

Normal bir Codex kullanıcısının yapacağı işlem şudur:

```text
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref main
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Laravel, design, cloud ve authoring paketlerini yalnız ihtiyaç olduğunda aynı marketplace adıyla ekleyin. Yeni skill metadata'sının yüklenmesi için yeni bir Codex thread'i başlatın.

Son kullanıcı Python testlerini, paket hash kontrollerini, JSON-RPC discovery problarını veya canlı eval harness'ini çalıştırmaz. Bunlar paketi geliştiren ve yayımlayan maintainer'ın kalite kontrolüdür. Araba alan kişiye motor bloğunu ölçtürmek gibi bir kurulum süreci tasarlamıyoruz.

## Claude Code son kullanıcı kurulumu

```text
claude plugin marketplace add EgoistDeveloper/codex-skills-foundation
claude plugin install engineering-foundation-core@egoist-engineering-foundation
```

İsteğe bağlı paketler aynı marketplace suffix'iyle kurulur. Yerel plugin geliştirmesinde bir dizin doğrudan yüklenebilir:

```text
claude --plugin-dir ./plugins/engineering-foundation-core
```

## Maintainer doğrulaması

Repository'yi geliştiren kişi Python 3.11+ ve geliştirme bağımlılıklarıyla deterministik doğrulamayı çalıştırır:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/bootstrap.py
```

Bootstrap şunları birlikte çalıştırır:

- generated manifest drift;
- strict repository validator;
- JSON Schema ve gerçek YAML parsing;
- Markdown link, secret ve placeholder kontrolü;
- unit testler;
- positive/negative completion evidence;
- sentetik eval scorer self-test;
- deterministik plugin ZIP paketleri ve SHA-256.

Bu aşama model çağırmaz ve skill'lerin davranışsal olarak yararlı olduğunu tek başına kanıtlamaz.

Gerçek Codex davranışı için ayrı, tek komutluk smoke harness bulunur:

```powershell
python scripts/run_codex_live_smoke.py --confirm-live
```

Harness bir pluginsiz baseline ve açıkça seçilmiş core-skill candidate koşusu yapar, `.eval-runs/` altında incelenebilir kanıt üretir ve başlangıçtaki Codex plugin/config durumunu geri yükler. Ayrıntılar: [`docs/live-smoke.md`](docs/live-smoke.md).

## Doğruluk sınırı

Statik test, manifest doğrulaması ve kurulum smoke testi; olasılıksal modelin her gerçek görevde kusursuz davranacağını kanıtlamaz. Tek canlı smoke koşusu da tam qualification değildir. Bu repo, yanlış activation, gereksiz subagent, kapsam kayması ve sahte completion riskini ölçülebilir kapılarla azaltır. Canlı Codex/Claude qualification yalnız tekrarlı ve review edilebilir run artifact'larıyla ileri sürülebilir.

Ayrıntılar: [`docs/architecture.md`](docs/architecture.md), [`docs/evals.md`](docs/evals.md), [`docs/live-smoke.md`](docs/live-smoke.md), [`docs/qualification.md`](docs/qualification.md).
