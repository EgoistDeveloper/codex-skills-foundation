# Codex Skills Foundation: Bağımsız Mimari ve Harness Denetimi

**Tarih:** 15 Ağustos 2026
**İncelenen hedef:** `EgoistDeveloper/codex-skills-foundation` Pull Request #1
**Kanıt durumu:** PR kaynak ağacı bu çalışma ortamından okunamadı
**Üretilen çıktı:** PR'a uygulanmış yama değil, doğrulanabilir temiz-oda `v0.2.0-candidate`

## 1. Yönetici kararı

Mevcut fikir doğru, fakat başarı ölçütü “çok skill, çok agent, çok dosya” olmamalı. En iyi foundation; her göreve daha fazla talimat yükleyen değil, doğru davranışı en küçük bağlamla tetikleyen, gereksiz delegasyonu engelleyen ve tamamlanma iddiasını kanıta bağlayan sistemdir.

Bu denetimin sonucu:

1. Tek dev plugin yerine **çekirdek + isteğe bağlı Laravel + isteğe bağlı tasarım** paketi kullanılmalı.
2. Taşınabilir davranış `SKILL.md` içinde kalmalı; Agent Plugins, Codex ve Claude dağıtım manifestleri ayrı şemalar olarak korunmalı.
3. Varsayılan çalışma şekli **tek agent** olmalı. Subagent ve multi-agent yalnız ayrık, read-heavy veya bağımsız doğrulama işlerinde devreye girmeli.
4. Statik eşiklerden oluşan “akıllı router”, canlı eval ile kalibre edilmedikçe güvenilir otorite yapılmamalı.
5. Goal, plan, milestone ve handoff ayrı törenler değil, aynı task contract ve evidence zincirinin farklı görünüşleri olmalı.
6. Completion gate, yalnız agent'ın seçtiği satırları değil, task contract içindeki bütün kabul kriterlerini denetlemeli.
7. Eval scorer hiçbir koşulda sentetik fixture, eksik matris veya yalnız baseline verisinden “release qualified” sonucu üretmemeli.
8. Laravel Boost proje içinde isteğe bağlı bağlam sağlayıcı olarak kullanılmalı; foundation içine kopyalanmamalı.
9. Tasarım kalitesi yalnız “neon/glassmorphism yapma” yasaklarıyla değil, tek direction, tipografi, semantic token, gerçek durum ve render evidence sözleşmesiyle yönetilmeli.
10. MCP, hook, secret bridge ve global installer varsayılan olarak bulunmamalı.

## 2. Kanıt sınırı

Paylaşılan sohbet dökümünde PR #1 için 80 dosya, 15 skill, altı read-only subagent, deterministik router, evidence gate, on unit test ve başarılı CI gibi sonuçlar bildiriliyor. Bu ortamda:

- repo ve PR URL'si 404 döndü;
- GitHub yazma/okuma kimliği yoktu;
- `git ls-remote` ile uzaktaki özel repoya erişilemedi;
- yalnız sohbet dökümü ve kullanıcının verdiği kaynak listesi mevcuttu.

Bu yüzden aşağıdaki iddialar **doğrulanmadı**:

- PR'daki gerçek dosya sayısı ve içerik;
- branch/commit SHA;
- CI sonucu;
- mevcut skill ve agent tanımlarının biçimi;
- önceki router/evidence/eval scriptlerinin gerçek davranışı;
- provider kurulumlarının çalışıp çalışmadığı.

Gerçek PR görülmeden “PR iyileştirildi” demek, önceki yanlış tamamlanma raporunu yeni bir kapakla basmak olurdu. Bu çalışma o nedenle ayrı bir temiz-oda aday paketidir.

## 3. Kaynak ağırlıklandırma yöntemi

Kaynaklar yıldız sayısına göre değil, aşağıdaki sırayla değerlendirildi:

1. **Normatif şema ve resmî istemci belgeleri**
   Agent Plugins 1.0.0, OpenAI Codex/plugin/subagent belgeleri, Claude Code plugin/skill/subagent belgeleri, MCP specification.
2. **Resmî framework bağlamı**
   Laravel Boost, GitHub Spec Kit, Google `DESIGN.md`.
3. **Production mühendislik örnekleri**
   OpenAI Codex `AGENTS.md`, OpenAI Agents SDK, Pydantic AI, Harness Engineering yaklaşımı.
4. **Test/eval içeren güçlü topluluk sistemleri**
   Superpowers, Compound Engineering, Codex-Orchestration.
5. **Fikir ve desen kaynakları**
   12 Factor Agents, mini-swe-agent, ECC, Open Design, Karpathy skills, mattpocock/skills, kepano/obsidian-skills.

Bir topluluk reposundaki iyi fikir, resmî istemci şemasını geçersiz kılamaz. Aynı şekilde resmî bir örnek de her projede kurulması gereken workflow anlamına gelmez.

## 4. Paket mimarisi

### 4.1 Neden üç paket?

Aday paketler:

| Paket | Varsayılan kullanım | İçerik |
|---|---|---|
| `engineering-foundation-core` | Genel mühendislik görevleri | task contract, plan/milestone, bounded orchestration, implementation, debugging, review, verification, handoff |
| `engineering-foundation-laravel` | Laravel/PHP projeleri | sürüm ve repository gerçekliğine göre Laravel workflow |
| `engineering-foundation-design` | UI/tasarım işleri | tek design direction ve rendered visual verification |

Skill keşfinde ad ve description metni gövde yüklenmeden önce bağlama girebilir. Her projeye Laravel ve UI talimatı yüklemek hem context maliyeti hem yanlış tetiklenme yüzeyidir.

### 4.2 Neden tek paket değil?

Tek paket şu sorunları üretir:

- birbirine yakın description'lar implicit activation'ı belirsizleştirir;
- normal backend işinde tasarım bağlamı taşınır;
- CLI veya küçük düzeltmede milestone/handoff gibi ağır davranışlar gereksiz tetiklenebilir;
- paket nitelendirmesinde hangi davranışın regress ettiği anlaşılmaz;
- upstream değişiklikleri bütün sistemi birlikte oynatır.

## 5. Manifest ve dağıtım katmanları

Doğru model üç katmanlıdır:

- `plugin.json`: Agent Plugins 1.0.0 taşınabilir manifesti;
- `.codex-plugin/plugin.json`: OpenAI/Codex adaptörü;
- `.claude-plugin/plugin.json`: Claude Code adaptörü;
- marketplace dosyaları: istemciye özgü dağıtım kataloğu;
- `skills/`: taşınabilir davranış;
- `mcp.json`, hook ve agent dosyaları: yalnız gerçekten gerekiyorsa provider adapter yüzeyi.

Ortak metadata `catalog/plugins.json` dosyasından üretiliyor. Böylece isim, sürüm ve açıklama drift'i engelleniyor; provider alanları ise yanlış biçimde ortaklaştırılmıyor.

### 5.1 Resmî şema çapraz kontrolünde bulunan kusurlar

Temiz-oda adayının ilk taslağı resmî kaynaklarla çapraz kontrol edilirken aşağıdaki gerçek kusurlar yakalandı ve düzeltildi:

- OpenAI marketplace girdilerinde zorunlu installation/authentication policy eksikti.
- Publisher metadata içinde sahte/placeholder e-posta bulunuyordu.
- Claude manifestlerinde canonical `$schema` ve UI `displayName` doğrulaması eksikti.
- Provider manifestlerinin yalnız kendi validator'ımızla kontrol edilmesi riski vardı.

Bu bulgular PR #1'e atfedilmemelidir; PR içeriği görülmedi. Bunlar aday geliştirme sırasında yakalanan ve nihai pakette kapatılan kusurlardır.

## 6. Skill envanteri ve token ekonomisi

Adayda toplam on bir taşınabilir skill vardır.

### Çekirdek

1. `task-contract`
2. `plan-and-milestones`
3. `bounded-orchestration`
4. `surgical-implementation`
5. `systematic-debugging`
6. `verify-before-completion`
7. `review-diff`
8. `handoff`

### İsteğe bağlı

9. `laravel-project-engineering`
10. `design-direction`
11. `visual-verification`

Yeni skill ancak şu şartların tamamında eklenmelidir:

- tekrar eden gerçek bir hata sınıfını çözüyor;
- mevcut skill'e eklenmesi description/body sınırını bozuyor;
- positive ve negative trigger'ı test edilebiliyor;
- davranış sonucu ölçülebiliyor;
- discovery ve bakım maliyetinden daha yüksek değer üretiyor.

“Her iyi tavsiyeyi ayrı skill yapalım” yaklaşımı, bir çekmeceyi düzenlemek için yüz çekmece satın almaya benzer.

## 7. Goal, plan, milestone ve handoff

### Goal

Goal bir provider komutu değil, tamamlanma sözleşmesidir:

- objective;
- acceptance;
- non-goals;
- constraints;
- evidence;
- risk;
- reopen conditions.

Codex veya Claude istemcisindeki goal durumu bu sözleşmeyi yansıtabilir; kanıt yerine geçmez.

### Plan

Plan yalnız belirsiz, çapraz kesen, yüksek riskli, migration içeren veya session'lar arası sürecek işlerde durable artefact olmalıdır. Küçük ve lokal görevde plan dosyası üretmek yasak değil, yalnız gereksizdir.

### Milestone

Milestone yüzde tahmini değildir. Her milestone şunları taşır:

- gözlenebilir outcome;
- sınır/dosya yüzeyi;
- bağımlılıklar;
- evidence;
- rollback/failure action;
- sonraki milestone.

Durumlar: `PENDING`, `ACTIVE`, `BLOCKED`, `VERIFIED`, `SUPERSEDED`.

### Handoff

Üç mekanizma ayrıldı:

1. host-native sohbet/session transferi;
2. kalıcı project handoff artefact'i;
3. subagent return packet.

Tam transcript, handoff değildir. Handoff; karar, repo state, evidence, risk ve sonraki atomik adımı taşır; log ve diff'i linkler.

## 8. Multi-agent ve subagent politikası

Varsayılan **tek agent**.

Delegasyon yalnız şu işlerde savunulabilir:

- bağımsız read-heavy repository keşfi;
- güncel dış kaynak araştırması;
- implementasyondan farklı uzman review;
- edit yapmadan bağımsız verification;
- gerçekten ayrık write surface'e sahip implementasyon kolları.

Bağlayıcı sınırlar:

- en fazla üç aktif worker;
- delegation depth bir;
- dosya başına tek writer;
- parent task contract, integration, final diff ve completion sahibi;
- reviewer/verifier varsayılan report-only;
- ortak write surface'te paralel implementer yok;
- aynı geniş soruyu agent'lara oylatma yok;
- child iddiası evidence olmadan kabul edilmez.

OpenAI'nin güncel belgeleri subagent'ların ayrı model ve tool çalışması nedeniyle tek-agent çalışmadan daha fazla token tükettiğini açıkça belirtiyor. Bu yüzden multi-agent kalite rozeti değil, ölçülmesi gereken maliyetli bir optimizasyondur.

## 9. Neden statik task router kaldırıldı?

Dosya sayısı, risk puanı, context büyüklüğü ve uzmanlık sayısına bakıp `single-agent` veya `multi-agent` döndüren script ilk bakışta deterministik görünür. Fakat eşikler canlı eval ile kalibre edilmediyse:

- risk modelini doğrulamaz;
- görev bağımsızlığını anlayamaz;
- write-surface çakışmasını güvenilir biçimde ölçemez;
- agent'ın gerçekten delegasyon yapıp yapmadığını kanıtlamaz;
- yanlış kararı yalnız JSON çıktısıyla resmileştirir.

Bu adayda routing, davranış sözleşmesi ve eval case'leriyle yönetiliyor. İleride gerçek kampanya verisi yeterli olursa, ölçülen karar destek modeli eklenebilir.

## 10. Gereksiz refactor sınırı

“Tamamlandıktan sonra hiçbir refactor yok” çok katıdır; “agent daha iyi olana kadar devam etsin” ise görev bitirme mekanizması değildir.

Doğru sınır:

- final verification öncesinde değişen kodla sınırlı tek cleanup geçişi;
- acceptance ve evidence geçtikten sonra speculative architecture değişikliği yok;
- tek kullanımlık helper kanıtsız genelleştirilmez;
- komşu kod sırf yakın olduğu için temizlenmez;
- ikinci alternatif implementasyon üretilmez;
- yalnız failed evidence, unmet acceptance, requirement değişikliği veya somut regression/security bulgusu task'ı reopen eder.

## 11. Completion evidence gate

Gate'in amacı model güvenini doğrulamak değil, completion iddiasının açık sözleşmeyle tutarlı olmasını sağlamaktır.

Adayın ilk iterasyonunda iki kritik sahte başarı yolu bulundu:

1. `NOT_RUN` içeren matrix yine de complete kabul edilebiliyordu.
2. Agent task contract'taki bir kabul kriterini evidence belgesinden tamamen çıkarabiliyordu.

Nihai gate artık:

- `COMPLETE`, `PARTIAL`, `BLOCKED` durumlarını ayırıyor;
- required `FAIL` ve `NOT_RUN` ile complete durumunu reddediyor;
- empty evidence, duplicate criteria ve unknown field'i reddediyor;
- task ID'yi karşılaştırıyor;
- task contract sağlandığında acceptance setinin bire bir kapsandığını denetliyor;
- kendi sınırını açıkça bildiriyor: yazılan command'in gerçekte çalıştığını tek başına kanıtlayamaz.

## 12. Eval ve harness

Routing fixture, schema testi ve parser unit testi **behavior eval değildir**.

### 12.1 Gerekli kampanya yapısı

Her normal release kampanyasında:

- plugin kapalı baseline;
- önceki release;
- candidate;
- positive activation;
- negative activation;
- gerçek repo fixture;
- provider/client/version kaydı;
- tekrarlı koşu;
- redacted trace, artifact, diff, command ve screenshot;
- task/safety/activation/evidence hard gate;
- token, tool, agent, duration, unrelated-file ve post-completion churn metriği.

İlk release'te previous bulunmayabilir; sonraki sürümlerde zorunlu tutulmalıdır.

### 12.2 Scorer denetiminde bulunan kritik kusurlar

Aday scorer'ın erken iterasyonunda aşağıdaki sahte başarı yolları bulundu ve kapatıldı:

- yalnız baseline satırlarıyla PASS üretme;
- string `"false"` değerini truthy kabul etme;
- candidate activation'ı hard gate yapmama;
- duplicate run identity kabul etme;
- repetition setlerini eşleştirmeme;
- synthetic ve live satırları karıştırma;
- live artifact/trace bulunmadan geçme;
- yalnız verilen küçük bir subset'i `QUALIFIED` etiketleme.

Nihai scorer:

- campaign ID ve case revision ister;
- provider/client/version/package commit/repetition kimliğini sabitler;
- candidate ve baseline'ı zorunlu kılar;
- `--require-previous` ve minimum repetition desteği verir;
- candidate hard gate regression'ını reddeder;
- live artifact path'lerini repo/run sınırı içinde doğrular;
- trace yoksa açık disclosure ister;
- sentetik fixture için ayrıca `--allow-synthetic` ister;
- sentetik sonucu `NOT_QUALIFIED`, temiz live subset'i `COVERAGE_NOT_ASSESSED` olarak raporlar.

Full release qualification, scorer'ın değil `docs/qualification.md` matrisinin sorumluluğundadır.

## 13. Laravel kararı

Laravel Boost foundation'a kopyalanmamalıdır. Proje içinde kuruluysa sürüm uyumlu documentation ve project-tool kaynağı olarak kullanılmalıdır.

Laravel skill önce şunları okur:

- `composer.json` ve `composer.lock`;
- PHP ve Laravel sürümü;
- DB engine;
- test stack;
- Pint/static analysis;
- Blade, Livewire, Inertia/Vue veya API boundary;
- yakın domain kalıpları;
- Boost kurulumu ve sağlığı.

Performance değişikliğinde query evidence olmadan cache veya index eklenmez. Riskli migration'da expand-contract düşünülür. Tenant, policy, audit, queue/event ve notification ownership sınırları korunur.

## 14. Tasarım kararı

Tasarım sistemi yalnız anti-pattern listesi değildir.

`design-direction` şunları bağlar:

- audience/job/content hierarchy;
- tek visual premise;
- typeface, weight, fallback ve loading budget;
- spacing/grid/density/radius/border/shadow/motion;
- semantic color tokens ve contrast intent;
- component/icon geometry;
- responsive davranış;
- loading/empty/error/validation/success/disabled/permission durumları;
- accessibility ve performance.

`visual-verification`, source code'a bakıp “güzel” demek yerine render edilen yüzeyi viewport, keyboard, focus, overflow, localized long content, console/network ve screenshot evidence ile denetler.

Google `DESIGN.md` mevcutsa tüketilir ve linter'ı çalıştırılır. Format halen evolving/alpha olduğu için bütün projelere zorunlu dependency yapılmaz. Türkçe ürünlerde `İ ı Ş ş Ğ ğ Ç ç Ö ö Ü ü` glyph seti ayrıca test edilir.

## 15. Güvenlik ve yetki modeli

Varsayılan adayda şunlar yoktur:

- MCP server;
- lifecycle hook;
- network çağrısı;
- credential/secret bridge;
- telemetry;
- global kullanıcı ayarı değişikliği;
- otomatik commit/push/merge;
- recursive agent zinciri;
- model adı sabitleme.

Future MCP veya hook eklemek için provenance, least privilege, filesystem/network kapsamı, command execution, secret flow, version pin, threat model, uninstall ve rollback zorunludur.

## 16. İsteğe bağlı provider-agent profilleri

Portable skill'ler host-native subagent'larla çalışır. Tekrarlanan read-only işler için ayrıca üç Codex TOML ve üç Claude Markdown profil sağlandı:

- explorer;
- reviewer;
- evidence auditor.

Profiller:

- project-scoped kurulur;
- model sabitlemez;
- read-only/report-only davranır;
- implementer içermez;
- nested delegation'ı engeller;
- dry-run-first installer ile kurulur;
- mevcut dosyayı `--force` olmadan ezmez.

Bunlar portable contract değil provider adapter'ıdır; gerçek istemcide ayrı qualify edilmelidir.

## 17. Statik doğrulama yüzeyi

Aday repository şu kontrolleri çalıştırır:

- generated manifest drift;
- portable/Codex/Claude manifest alan ve path tutarlılığı;
- marketplace plugin seti ve policy;
- skill frontmatter/name/description/body sınırları;
- portable skill'lerde pre-approved tool yasağı;
- optional agent profile parse ve read-only sınırları;
- eval case referans bütünlüğü;
- sentetik eval fixture campaign kimliği;
- task contract ile completion evidence bire bir eşleşmesi;
- evidence gate negatif fixture'ları;
- eval scorer negatif ve regression vakaları;
- Python compile;
- unit tests.

Ek build sırasında bütün yerel JSON Schema dosyaları Draft 2020-12 meta-schema ile, örnekler ilgili schema ile, skill/Claude frontmatter'ları gerçek YAML parser ile ve göreli Markdown bağlantıları dosya sistemiyle çapraz doğrulandı.

## 18. PR #1 açıldığında yapılacak gerçek diff denetimi

Öncelik sırası:

### P0

1. Manifestler resmî şemaları geçiyor mu?
2. OpenAI marketplace installation/authentication policy eksiksiz mi?
3. Evidence gate required `NOT_RUN` ve omitted acceptance kriterini reddediyor mu?
4. Eval scorer baseline-only, type confusion, duplicate identity ve missing artifact ile sahte başarı üretiyor mu?
5. Live eval çalıştırılmadan `PASS` veya `qualified` iddiası var mı?
6. Secret, hook, MCP veya global installer geniş yetki açıyor mu?

### P1

7. On beş skill description çakışması veya discovery bloat üretiyor mu?
8. Laravel ve design core'dan ayrılmalı mı?
9. Router canlı veriyle kalibre edilmiş mi?
10. Review/verifier agent runtime'da gerçekten read-only mi?
11. Subagent depth ve writer ownership yalnız metinde mi, yoksa istemcide uygulanıyor mu?
12. Handoff compact state yerine transcript dump mı?
13. Provider/model isimleri gereksiz hard-code edilmiş mi?

### P2

14. Doküman tekrarları ve gereksiz framework jargonları azaltılabilir mi?
15. Release/upgrade/changelog süreci yeterli mi?
16. Windows path, line-ending ve PowerShell davranışı test edilmiş mi?

## 19. Doğrulama statüsü

| Alan | Durum | Açıklama |
|---|---|---|
| Temiz-oda dosya yapısı | PASS | Yerel aday üzerinde doğrulandı |
| Manifest drift ve repository validator | PASS | Yerel bootstrap içinde |
| Unit tests ve Python compile | PASS | Yerel bootstrap içinde |
| JSON Schema/YAML/Markdown link çapraz kontrolü | PASS | Build-time bağımsız kontroller |
| Negative evidence fixtures | PASS | Beklendiği gibi reddedildi |
| Synthetic scorer self-test | PASS | Release qualification değildir |
| PR #1 file-by-file diff | NOT_RUN | Kaynak ağaca erişim yok |
| GitHub commit/push/PR güncellemesi | NOT_RUN | GitHub kimliği/yazma erişimi yok |
| Codex desktop/CLI/cloud kurulumu | NOT_RUN | Authenticated live client yok |
| Claude Code kurulumu | NOT_RUN | Authenticated live client yok |
| Gerçek token ve activation ölçümü | NOT_RUN | Live campaign yok |
| Windows PowerShell runtime | NOT_RUN | `pwsh` bu build ortamında yok |

## 20. Nihai hüküm

Temiz-oda aday, önceki iddia edilen yapının daha küçük ve daha savunulabilir bir v0.2 yönünü sunuyor. En güçlü farkı daha fazla özellik eklemek değil; sahte tamamlanma, sahte eval başarısı, gereksiz multi-agent fan-out ve discovery bloat için açık sınırlar koymasıdır.

Bununla birlikte bu paket henüz release değildir. Gerçek PR branch'iyle dosya/davranış bazında karşılaştırılmalı, güçlü mevcut parçalar korunmalı ve canlı Codex/Claude qualification matrisi tamamlanmalıdır. Statik kalite önemlidir; olasılıksal agent davranışının yerine geçmez.
