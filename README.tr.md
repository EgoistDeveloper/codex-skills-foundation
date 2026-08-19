# Codex Skills Foundation

Codex, ChatGPT, Codex Cloud, Claude Code ve Agent Skills / Agent Plugins uyumlu istemciler için modüler, kanıta dayalı ve token-bilinçli mühendislik foundation'ı.

**Public beta:** `engineering-foundation-core` `0.3.0-beta.2`. Kapsam, kurulum, güncelleme, kaldırma, kanıtlanan davranışlar ve sınırlar için [`docs/public-beta.md`](docs/public-beta.md) belgesine bakın.

## Hangi paket kurulmalı?

| Paket | Bu release içindeki sürüm | Kullanım |
|---|---:|---|
| `engineering-foundation-core` | `0.3.0-beta.2` | Her yazılım projesinde |
| `engineering-foundation-laravel` | `0.2.1` | Yalnız Laravel/PHP projelerinde |
| `engineering-foundation-design` | `0.2.1` | Arayüz üretimi, redesign ve visual QA işlerinde |
| `engineering-foundation-cloud` | `0.2.1` | Codex Cloud veya başka remote-agent ortamlarında |
| `engineering-foundation-authoring` | `0.2.1` | Skill/plugin üretirken veya bakım yaparken |

Core; task contract, plan/milestone, sınırlı delegasyon, küçük ve doğru diff, sistematik debugging, güncel kaynak araştırması, review, doğrulama ve handoff davranışlarını içerir. Diğer paketler yalnız gerektiğinde kurulur. Böylece backend düzeltmesinde tasarım manifestosu, normal projede Cloud setup talimatı taşınmaz. İnsanlar her şeyi tek çekmeceye koymayı sever; agent context'i bu geleneğe katılmak zorunda değil.

Bu beta için genişletilmiş authenticated canlı davranış kanıtı yalnız Core paketine aittir. İsteğe bağlı paketler mevcut sürümleriyle statik ve provider-package doğrulamasından geçmiştir.

## Codex son kullanıcı kurulumu

Tekrarlanabilir kurulum için beta tag'ini kullanın:

```text
codex plugin marketplace add EgoistDeveloper/codex-skills-foundation --ref v0.3.0-beta.2
codex plugin add engineering-foundation-core@egoist-engineering-foundation
```

Laravel, design, cloud ve authoring paketlerini yalnız ihtiyaç olduğunda aynı marketplace adıyla ekleyin. Yeni skill metadata'sının yüklenmesi için yeni bir Codex thread'i başlatın.

Son kullanıcı Python testlerini, paket hash kontrollerini, JSON-RPC discovery problarını veya canlı eval harness'ini çalıştırmaz. Bunlar paketi geliştiren ve yayımlayan maintainer'ın kalite kontrolüdür. Araba alan kişiye motor bloğunu ölçtürmek gibi bir kurulum süreci tasarlamıyoruz.

Güncelleme ve kaldırma komutları [`docs/public-beta.md`](docs/public-beta.md) belgesinde bulunur.

## Claude Code son kullanıcı kurulumu

```text
claude plugin marketplace add EgoistDeveloper/codex-skills-foundation
claude plugin install engineering-foundation-core@egoist-engineering-foundation
```

İsteğe bağlı paketler aynı marketplace suffix'iyle kurulur. Yerel plugin geliştirmesinde bir dizin doğrudan yüklenebilir:

```text
claude --plugin-dir ./plugins/engineering-foundation-core
```

Claude manifestleri ve paketleri doğrulanmıştır; authenticated canlı davranış matrisi şu anda Claude Code değil Codex CLI yüzeyini kapsar.

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

Authenticated Codex davranış kampanyaları ayrıdır:

```powershell
python scripts/run_codex_positive_smoke_isolated.py --confirm-live
python scripts/run_codex_negative_smoke_v4.py --confirm-live
python scripts/run_codex_core_repeatability.py --confirm-live --repetitions 3
python scripts/run_codex_bounded_delegation_smoke_v5.py --confirm-live
python scripts/run_codex_evidence_refusal_smoke.py --confirm-live
```

Son sıfır-model public-beta lifecycle kontrolü:

```powershell
python scripts/run_public_beta_lifecycle.py
```

Bu harness geçici bir `CODEX_HOME` ve yalnız loopback üzerinde çalışan geçici Git marketplace kullanır; önceki Core sürümünün kurulumunu, marketplace güncellemesini, beta Core reinstall/update akışını, bütün paketlerin namespaced skill discovery'sini, tam kaldırmayı ve temiz izole durumu doğrular. Ayrıntılar: [`docs/live-smoke.md`](docs/live-smoke.md).

## Kanıtlanan Core davranışları

Kaydedilmiş Codex CLI kampanyaları şu bounded iddiaları destekler:

- açıkça seçilen `systematic-debugging`, reproduction ve fresh verification kapılarını uygular;
- küçük bir edit üç tekrarda da planlama veya sub-agent açmaz;
- ayrıştırılabilir read-only denetim doğrudan child agent kullanır, delegation depth'i birde tutar ve parent entegrasyonuyla biter;
- zorunlu verifier bloke kaldığında yapılandırılmış `BLOCKED` kanıtı üretir ve sahte `COMPLETE` iddiasını reddeder.

## Doğruluk sınırı

Statik test, manifest doğrulaması ve kurulum smoke testi; olasılıksal modelin her gerçek görevde kusursuz davranacağını kanıtlamaz. Bu repo modeli yeniden eğitmez ve halüsinasyonu sıfırlamaz. Yanlış activation, gereksiz subagent, kapsam kayması, kontrolsüz fan-out ve sahte completion riskini ölçülebilir kapılarla azaltmaya çalışır.

Canlı qualification şu anda Codex CLI ile sınırlıdır. Positive delegation ve evidence-refusal vakaları tek tekrardır; diğer istemciler ve isteğe bağlı paketler aynı canlı kapsama sahip değildir.

Ayrıntılar: [`docs/architecture.md`](docs/architecture.md), [`docs/evals.md`](docs/evals.md), [`docs/live-smoke.md`](docs/live-smoke.md), [`docs/public-beta.md`](docs/public-beta.md), [`docs/qualification.md`](docs/qualification.md).
