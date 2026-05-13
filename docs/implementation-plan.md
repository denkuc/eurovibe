# План імплементації ЄвроВайб для агентів

Цей документ розкладає PRD на послідовні робочі етапи для агентів. Ціль v1: mobile-first SSR-вебзастосунок на Django + PostgreSQL + Tailwind CSS з мінімальним JavaScript, SortableJS лише для сторінки голосування, кастомним суперадмінським бекофісом і без зайвої інфраструктурної складності.

## 0. Принципи роботи агентів

1. Кожен етап має завершуватися робочим, мігрованим і перевіреним станом застосунку.
2. Не додавати SPA, DRF/API-first архітектуру, WebSocket, email flow, password reset, chat, reactions або зовнішню інтеграцію з Eurovision API у v1.
3. Основний UX має бути server-rendered. JavaScript використовується тільки для локальної інтерактивності: drag/tap голосування, copy invite link, enable/disable кнопок, polling рейтингів.
4. Бізнес-правила дублюються на бекенді навіть тоді, коли є UI-обмеження.
5. Стани системи, режим голосування і незмінність бюлетеня є ключовими інваріантами. Не обходити їх у view, form, service або admin action.
6. Усі кольори й візуальні параметри Vienna 2026 look зберігати як конфігуровані дизайн-токени, а не розкидати hardcoded-значеннями по шаблонах.
7. Django admin використовується як аварійний внутрішній інструмент перегляду моделей. Основні процеси суперадміна реалізуються кастомними сторінками.

## 1. Цільова структура проєкту

Рекомендована структура після bootstrap:

```text
eurovibe/
  manage.py
  pyproject.toml або requirements.txt
  render.yaml
  .env.example
  eurovibe/
    settings.py
    urls.py
    wsgi.py
  accounts/
  groups/
  contest/
  voting/
  leaderboards/
  admin_panel/
  templates/
    base.html
    partials/
  static/
    css/
    js/
  docs/
    prd.md
    implementation-plan.md
```

Модулі:

- `accounts`: реєстрація, логін, вихід, role helpers, password validation.
- `contest`: edition, state machine, finalists, official results, seed/import.
- `groups`: friend groups, memberships, join code, invite token, owner actions.
- `voting`: ballot domain model, голосувальна сторінка, submit validation.
- `leaderboards`: рейтинги країн і користувачів, aggregation services.
- `admin_panel`: кастомний backoffice для `denkuc` і audit log.

## 2. Етап 1: Bootstrap і технічний фундамент

### Хід виконання

- 2026-05-13: Розпочато Foundation bootstrap у поточному репозиторії.
- 2026-05-13: Додано Django project skeleton, env-based settings, базовий SSR layout, static assets, `/healthz/`, `.env.example` і `render.yaml`.
- 2026-05-13: Додано Tailwind CLI setup (`package.json`, `tailwind.config.js`, `assets/css/app.css`) із checked-in compiled CSS для `collectstatic`.
- 2026-05-13: Перевірено `npm run build:css`, `python manage.py check`, `collectstatic`, `migrate`, `runserver`; `/healthz/` і `/` повертають HTTP 200.
- 2026-05-13: Додано README з інструкціями локального та Docker запуску, `Dockerfile`, `docker-compose.yml` і `.dockerignore`; перевірено Docker build і Compose запуск з Postgres, `/healthz/` та `/` повертають HTTP 200.
- 2026-05-13: Додано accounts foundation: app `accounts`, register/login/logout, приватний dashboard placeholder, superadmin placeholder, `login_required` redirect із `next`, helper `is_superadmin(user)`, role-aware top nav, password policy min 15 chars і базові тести.

### Завдання

1. Створити Django-проєкт і базову конфігурацію під PostgreSQL.
2. Додати env-конфігурацію для `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `CSRF_TRUSTED_ORIGINS`.
3. Налаштувати static files для локальної розробки й Render.
4. Підключити Tailwind CSS у найпростішій підтримуваній формі для Django-проєкту.
5. Створити `base.html`, responsive shell, top navigation і базові layout primitives.
6. Додати health check route, наприклад `/healthz/`.
7. Підготувати `render.yaml` і `.env.example`.

### Критерії готовності

- `python manage.py migrate` проходить на чистій базі.
- `python manage.py runserver` стартує без помилок.
- `/healthz/` повертає 200.
- Головна сторінка рендериться з темною базою, верхнім меню й responsive layout.
- Немає секретів у git.

## 3. Етап 2: Дизайн-система і базова навігація

### Завдання

1. Закласти дизайн-токени:
   - deep indigo / violet background;
   - white foreground;
   - cyan-magenta gradient accents;
   - functional gold state для України в режимі `without_ukraine`;
   - card, border, muted text, danger, success, warning.
2. Створити базові компоненти шаблонів:
   - page container;
   - card;
   - form field;
   - button variants;
   - badge/chip;
   - empty state;
   - toast/snackbar container.
3. Реалізувати top menu з role/state-aware пунктами.
4. Додати default home redirect після логіну:
   - до відкриття голосування: `Мої групи`;
   - під час голосування: `Голосування`;
   - після публікації результатів: `Рейтинг користувачів`.

### Критерії готовності

- Навігація коректно відрізняє гостя, користувача і суперадміна.
- На mobile меню не ламає ширину viewport.
- Дизайн-токени централізовані.
- Немає one-off inline style для ключових кольорів.

### Хід виконання

- 2026-05-13: Реалізовано role-aware top nav для гостя, авторизованого користувача і superadmin. Для superadmin показується пункт `Superadmin`, якщо `accounts.roles.is_superadmin(user)` повертає `True`, і веде на захищений placeholder `/accounts/superadmin/`.
- 2026-05-13: Додано базові стилі форм, кнопок і private panel у централізовані CSS assets.

## 4. Етап 3: Accounts, ролі та доступ

### Завдання

1. Використати стандартну Django auth model або мінімальне розширення, якщо воно справді потрібне.
2. Реалізувати реєстрацію за `username + password`, без обов'язкового email.
3. Додати password policy:
   - мінімум 15 символів;
   - приймати довгі значення щонайменше до 64 символів;
   - без composition rules;
   - показати strength meter у формі;
   - постійний info-row: `Використай унікальний пароль і збережи його. У цій версії застосунку заміна або нагадування пароля недоступні.`
4. Реалізувати login/logout стандартними session-based механізмами Django.
5. Додати helper `is_superadmin(user)`, який для v1 повертає true для username `denkuc` або для staff/superuser за явно описаним правилом.
6. Захистити приватні маршрути `login_required`.
7. Налаштувати redirect гостя на login із `next`.

### Хід виконання

- 2026-05-13: Використано стандартну Django `User` model без кастомного розширення.
- 2026-05-13: Реалізовано `/accounts/register/`, `/accounts/login/`, `/accounts/logout/`, `/accounts/dashboard/` і `/accounts/superadmin/`.
- 2026-05-13: Парольна політика налаштована через `MinimumLengthValidator` з `min_length=15`; composition rules не додавались.
- 2026-05-13: У help text форм явно вказано, що password reset/заміна/нагадування пароля у v1 недоступні.
- 2026-05-13: `logout` виконується через POST, приватний dashboard захищений `login_required`, guest redirect зберігає `next`.
- 2026-05-13: Додано базові тести на register/login/logout, duplicate username, short password, `next` redirect і `is_superadmin(user)`.

### Критерії готовності

- Новий користувач може зареєструватися, увійти і вийти.
- Дубльований username відхиляється.
- Короткий пароль відхиляється сервером.
- Гість не може зайти на приватну URL без redirect на login.
- Сесія не зберігається в `localStorage`.

## 5. Етап 4: Contest state machine і seed фіналістів

### Моделі

Реалізувати мінімально:

```text
ContestEdition:
  year
  state: setup | voting_open | voting_closed | official_results_entered | scores_published
  voting_open_at
  voting_closed_at
  created_at
  updated_at

ContestEntry:
  edition
  running_order
  country_name
  country_code
  artist_name
  song_title
  is_ukraine
  created_at
  updated_at
```

### Завдання

1. Додати state constants і helper-и:
   - `get_current_edition()`;
   - `is_setup`;
   - `is_voting_open`;
   - `is_voting_closed_or_later`;
   - `can_edit_finalists`;
   - `can_vote`;
   - `can_publish_scores`.
2. Додати унікальні constraints:
   - один `ContestEdition` на `year`;
   - `running_order` унікальний у межах edition;
   - лише одна `is_ukraine=True` entry у межах edition, перевірити на рівні validation/service.
3. Створити management command для dev seed із PRD.
4. Додати просту read-only сторінку списку фіналістів для перевірки seed.

### Критерії готовності

- Dev seed створює edition 2026 і 25 entries.
- Повторний запуск seed не дублює entries або має явний idempotent/update режим.
- Голосування неможливо відкрити без фіналістів.
- Після переходу з `setup` фіналісти не редагуються через процесні сторінки.

### Хід виконання

- 2026-05-13: Додано app `contest` із моделями `ContestEdition` і `ContestEntry`, state constants/helper-и, унікальні constraints для року, running order і єдиної України в edition.
- 2026-05-13: Додано доменні transition methods `open_voting()`/`close_voting()`; `open_voting()` відхиляє відкриття без фіналістів, а entries валідатор блокує редагування після `setup`.
- 2026-05-13: Додано idempotent management command `seed_dev_contest`, який створює edition 2026 і 25 dev finalist entries із PRD.
- 2026-05-13: Додано read-only сторінку `/contest/finalists/` і покриття тестами для seed, constraints, state helper-ів і сторінки списку.

## 6. Етап 5: Групи друзів

### Моделі

```text
FriendGroup:
  name
  owner
  includes_ukraine
  join_code
  invite_token
  created_at
  updated_at

GroupMembership:
  group
  user
  joined_at
```

### Завдання

1. Реалізувати створення групи:
   - name optional;
   - default name: `Група <username>`;
   - owner автоматично стає member;
   - join code: 6 символів, uppercase, case-insensitive input;
   - invite token: достатньо довгий URL-safe token.
2. Реалізувати список `Мої групи`.
3. Реалізувати detail сторінку групи:
   - назва;
   - режим `з Україною` / `без України`;
   - список учасників;
   - emoji `👑` біля власника;
   - join code;
   - invite link;
   - copy button для invite link.
4. Реалізувати owner actions:
   - видалити іншого учасника;
   - оновити join code/token;
   - змінити `includes_ukraine` тільки у стані `setup`.
5. Реалізувати join by code.
6. Реалізувати join by invite link.
7. Якщо користувач уже member, не дублювати membership, а вести на групу.

### Критерії готовності

- Користувач може створити кілька груп.
- Один користувач може бути в багатьох групах.
- Не-owner не бачить або не може виконати owner actions.
- Власник не може видалити самого себе через remove-member flow.
- Після `voting_open` `includes_ukraine` заблокований.
- Join code lookup працює case-insensitive.

## 7. Етап 6: Domain model голосування

### Моделі

```text
Ballot:
  edition
  user
  mode: with_ukraine | without_ukraine
  submitted_at
  immutable
  created_at

BallotItem:
  ballot
  points
  contest_entry
```

### Constraints

1. `Ballot` унікальний для `edition + user + mode`.
2. `BallotItem.points` унікальний у межах ballot.
3. `BallotItem.contest_entry` унікальний у межах ballot.
4. Дозволені points: `1,2,3,4,5,6,7,8,10,12`.
5. У `without_ukraine` не можна зберегти item для entry `is_ukraine=True`.
6. Ballot вважається valid тільки якщо має рівно 10 items.

### Завдання

1. Створити service `get_available_voting_modes(user, edition)`.
2. Режим доступний, якщо user має хоча б одну групу відповідного типу:
   - `with_ukraine`: хоча б одна group `includes_ukraine=True`;
   - `without_ukraine`: хоча б одна group `includes_ukraine=False`.
3. Створити service `submit_ballot(user, edition, mode, assignments)`.
4. Серверна validation має перевіряти:
   - edition state is `voting_open`;
   - user має доступ до mode;
   - ballot ще не існує;
   - рівно 10 оцінок;
   - всі points з дозволеного набору;
   - всі entries належать поточній edition;
   - Україна не оцінюється в `without_ukraine`.

### Критерії готовності

- Друга submit-спроба для тієї самої пари `user + mode` відхиляється сервером.
- Неможливо submit до `voting_open` і після `voting_closed`.
- Неможливо submit неповний або дубльований набір points.
- Неможливо submit Україну в `without_ukraine`.

## 8. Етап 7: UI голосування

### Desktop layout

1. Лівий контейнер: 2/3 ширини.
2. Правий контейнер: 1/3 ширини.
3. Ліворуч вертикальний список країн.
4. Картка країни:
   - running order;
   - прапор або country code fallback;
   - country name як найпомітніший шар;
   - artist і song менш контрастно;
   - комірка під бал.
5. Праворуч 10 chips: `1,2,3,4,5,6,7,8,10,12`.

### Mobile layout

1. Список країн займає основну висоту.
2. Points tray стає sticky bottom tray або bottom sheet.
3. Має бути tap-to-assign fallback:
   - user натискає бал;
   - user натискає країну;
   - бал переноситься на країну.

### Поведінка сортування

1. Неоцінені країни сортуються за `running_order`.
2. Оцінені країни переходять у верхню частину.
3. Оцінені країни сортуються за points desc: `12,10,8,7,6,5,4,3,2,1`.
4. Якщо бал забрали з країни, вона повертається у свою позицію серед неоцінених за `running_order`.

### Україна в `without_ukraine`

1. Україна показується у списку.
2. Картка має світло-золотий functional state.
3. У комірці балу показати heart marker.
4. Desktop hover: tooltip з поясненням.
5. Mobile tap attempt: toast/snackbar з поясненням.
6. UI не має дозволяти поставити бал Україні, але бекенд теж має це відхиляти.

### Завдання

1. Реалізувати voting page з tabs для режимів, якщо user має обидва режими.
2. Показати readonly submitted state, якщо ballot уже існує.
3. Підключити SortableJS лише на цій сторінці.
4. Реалізувати tap fallback без залежності від drag.
5. Активувати `Підтвердити голосування` тільки після 10 призначених балів.
6. Перед submit показати confirm step або чіткий immutable warning.
7. Після submit redirect на readonly ballot або leaderboard.

### Критерії готовності

- Voting page працює без горизонтального scroll на mobile.
- Кнопка submit неактивна до повного набору 10 оцінок.
- Submit без JS або з підробленим payload усе одно проходить серверну validation.
- Submitted ballot неможливо змінити через UI і через повторний POST.
- Україна помітна в `without_ukraine`, але не оцінюється.

## 9. Етап 8: Рейтинги країн

### Завдання

1. Реалізувати aggregation service для country leaderboard:
   - global;
   - by group.
2. Global leaderboard доступний анонімно.
3. Group leaderboard доступний тільки member-ам відповідної групи.
4. Сортування:
   - `total_points DESC`;
   - `number_of_voters DESC`;
   - `count_12 DESC`;
   - `count_10 DESC`;
   - `count_8 DESC`;
   - `country_name ASC`.
5. Додати mode-aware агрегацію:
   - група `includes_ukraine=True` агрегує `with_ukraine`;
   - група `includes_ukraine=False` агрегує `without_ukraine`.
6. Додати polling refresh кожні 10-15 секунд для відкритих read-heavy рейтингів.
7. Додати короткий cache TTL для global leaderboard, якщо це не ускладнює invalidation.

### Критерії готовності

- Гість бачить global country leaderboard.
- Користувач не бачить leaderboard групи, де він не member.
- Tie-break deterministic.
- Рейтинги не падають на порожніх даних.

## 10. Етап 9: Суперадмінський backoffice

### Access

Backoffice доступний тільки суперадміну. Для v1 суперадмін: користувач із username `denkuc` або явно узгоджений staff/superuser rule.

### Завдання

1. Створити dashboard `/superadmin/`.
2. Додати процесні сторінки:
   - імпорт/внесення фіналістів одним списком;
   - перегляд поточного edition і state;
   - відкрити голосування;
   - закрити голосування;
   - внести повний офіційний фінальний порядок усіх фіналістів;
   - запустити підрахунок користувацьких балів;
   - опублікувати рейтинги користувачів.
3. Для імпорту фіналістів підтримати простий textarea format. Рекомендований формат: CSV-like або YAML-like, але парсити структуровано, не fragile split без validation.
4. Для official results вимагати повний порядок усіх фіналістів, не лише top 10.
5. Додати preview/validation перед збереженням official results.
6. Додати audit log для admin actions:
   - actor;
   - action;
   - timestamp;
   - metadata.

### State transitions

Дозволені переходи:

```text
setup -> voting_open
voting_open -> voting_closed
voting_closed -> official_results_entered
official_results_entered -> scores_published
```

Не додавати backward transition у звичайному UI. Якщо буде потрібна аварійна операція, вона має бути окремою, явно небезпечною і не в v1 default flow.

### Критерії готовності

- Не-суперадмін отримує 403 або redirect без доступу до backoffice.
- Неможливо відкрити голосування без finalists.
- Неможливо внести official results до `voting_closed`.
- Неможливо опублікувати scores без обчислених `UserScore`.
- Кожна admin action пишеться в audit log.

## 11. Етап 10: Офіційні результати і scoring користувачів

### Моделі

```text
OfficialResult:
  edition
  final_rank
  contest_entry

UserScore:
  edition
  user
  mode
  exact_hits
  top10_hits_wrong_place
  total_score
  calculated_at
```

### Scoring rules

Prediction mapping:

```text
12 -> rank 1
10 -> rank 2
8  -> rank 3
7  -> rank 4
6  -> rank 5
5  -> rank 6
4  -> rank 7
3  -> rank 8
2  -> rank 9
1  -> rank 10
```

Score:

- exact rank match: 2 points;
- entry in predicted top 10 and official top 10, but wrong place: 1 point;
- otherwise: 0 points.

For `without_ukraine`:

1. Remove Ukraine from full official ranking.
2. Shift all lower entries up.
3. Take normalized top 10.
4. Apply the same scoring rules.

### Завдання

1. Реалізувати official result validation:
   - усі entries поточної edition присутні рівно один раз;
   - ranks без дірок від 1 до N;
   - ranks унікальні.
2. Реалізувати scoring service idempotently:
   - може перерахувати scores після виправлення official results до publication;
   - не створює дублікати.
3. Реалізувати user leaderboard:
   - global by mode;
   - group by group mode;
   - сортування `total_score DESC`, `exact_hits DESC`, `top10_hits_wrong_place DESC`, `username ASC`.
4. Показувати user leaderboard тільки після `scores_published`.

### Критерії готовності

- `without_ukraine` scoring коректно зсуває офіційний порядок.
- Users без ballot не отримують score або отримують явно нульовий score за узгодженим правилом. Рекомендація: не включати users без ballot у leaderboard.
- Повторний запуск scoring не дублює `UserScore`.
- User leaderboard недоступний до `scores_published`.

## 12. Етап 11: Security hardening

### Завдання

1. Увімкнути й перевірити Django protections:
   - CSRF middleware;
   - clickjacking protection;
   - secure cookies in production;
   - `SESSION_COOKIE_HTTPONLY=True`;
   - `CSRF_COOKIE_HTTPONLY` за потреби UX;
   - `SESSION_COOKIE_SECURE=True` у production;
   - `CSRF_COOKIE_SECURE=True` у production;
   - `SameSite=Lax` або суворіше, якщо не ламає flow.
2. Додати базові rate limits для:
   - login;
   - register;
   - join by code;
   - submit ballot.
3. Додати CSP через middleware/package або простий header policy.
4. Перевірити, що всі POST мають CSRF.
5. Перевірити object-level permissions:
   - group detail;
   - group owner actions;
   - group leaderboard;
   - admin panel;
   - submitted ballots.
6. Логувати admin actions окремо від звичайних request logs.

### Критерії готовності

- Security-sensitive settings мають production-safe default через env.
- Rate limit не блокує нормальний UX, але ріже очевидний brute force.
- Приватні об'єкти не доступні через direct URL.
- Немає secrets або real credentials у репозиторії.

## 13. Етап 12: Тести

### Мінімальний test matrix

Accounts:

- registration success;
- duplicate username;
- short password rejected;
- login/logout;
- private page redirects guest.

Groups:

- create group;
- owner becomes member;
- default group name;
- join by code case-insensitive;
- join by invite token;
- duplicate membership not created;
- non-owner cannot remove member;
- owner cannot change `includes_ukraine` after `voting_open`.

Contest:

- seed creates 25 entries;
- state transition happy path;
- invalid state transition rejected;
- cannot open voting without finalists.

Voting:

- available modes from group membership;
- submit valid `with_ukraine`;
- submit valid `without_ukraine`;
- reject duplicate ballot;
- reject incomplete ballot;
- reject duplicate points;
- reject Ukraine in `without_ukraine`;
- reject submit outside `voting_open`.

Leaderboards:

- global leaderboard public;
- group leaderboard member-only;
- deterministic tie-break.

Admin/results:

- non-superadmin forbidden;
- full official ranking validation;
- scoring exact match gives 2;
- scoring wrong-place top10 gives 1;
- `without_ukraine` official normalization;
- idempotent score recalculation.

Frontend smoke:

- mobile voting page has no horizontal overflow;
- submit button state changes after 10 assignments;
- submitted ballot page is readonly;
- copy invite link does not break without clipboard permission.

## 14. Етап 13: Launch і Render

### Завдання

1. Підготувати Render web service config.
2. Підключити managed PostgreSQL.
3. Налаштувати build command:
   - install dependencies;
   - collectstatic;
   - migrate або окремий release command, залежно від Render setup.
4. Налаштувати start command через gunicorn.
5. Додати production env vars.
6. Перед фіналом вручну виставити мінімум 2 web instances.
7. Увімкнути autoscaling, якщо доступно.
8. Перевірити health check.
9. Прогнати smoke flow на production/staging:
   - register;
   - create group;
   - join group;
   - open voting as admin;
   - submit ballot;
   - close voting;
   - enter official results;
   - calculate scores;
   - publish scores.

### Критерії готовності

- Production deploy стартує з чистої бази.
- Static assets віддаються коректно.
- HTTPS cookies працюють.
- Health check stable.
- Є documented rollback/redeploy procedure.

## 15. Рекомендований порядок агентських задач

### Agent 1: Foundation

Відповідальність: bootstrap Django, settings, base templates, Tailwind, health check, Render skeleton.

Вихід:

- робочий Django-проєкт;
- базовий layout;
- `.env.example`;
- `render.yaml`;
- smoke notes.

### Agent 2: Accounts і access

Відповідальність: auth flows, role helpers, protected routes, password policy.

Вихід:

- register/login/logout;
- password validation;
- role-aware navigation;
- tests для accounts.

### Agent 3: Contest і groups

Відповідальність: edition state machine, contest entries, seed, groups, memberships, join flows.

Вихід:

- models/migrations;
- seed command;
- create/list/detail group;
- owner actions;
- tests для contest/groups.

### Agent 4: Voting

Відповідальність: ballot models, submit service, voting UI, SortableJS/tap fallback.

Вихід:

- ballot persistence;
- server validation;
- responsive voting page;
- immutable submitted state;
- tests для voting.

### Agent 5: Leaderboards і scoring

Відповідальність: country leaderboards, official results, user scoring, user leaderboards.

Вихід:

- aggregation services;
- public/private leaderboard pages;
- scoring service;
- tests для leaderboard/scoring.

### Agent 6: Admin і hardening

Відповідальність: custom superadmin backoffice, audit log, rate limits, CSP/security settings, launch checklist.

Вихід:

- `/superadmin/` flow;
- audit log;
- rate limits;
- production settings review;
- launch checklist.

## 16. Definition of Done для v1

1. Користувач може зареєструватися без email.
2. Користувач може створити групу й запросити інших кодом або лінком.
3. Один користувач може бути в кількох групах.
4. Режими `with_ukraine` і `without_ukraine` визначаються membership-ами.
5. Користувач може подати максимум один ballot на mode.
6. Ballot має рівно 10 оцінок із buckets `1-8,10,12`.
7. Україна видима, але не оцінюється в `without_ukraine`.
8. Глобальний рейтинг країн доступний гостям.
9. Груповий рейтинг доступний тільки member-ам.
10. Суперадмін `denkuc` може керувати фіналістами, станом голосування, official results і publication.
11. Official results зберігають повний порядок усіх фіналістів.
12. User scoring працює для обох режимів, включно з normalization без України.
13. User leaderboards відкриваються тільки після `scores_published`.
14. Основні flows покриті тестами.
15. Production settings не зберігають secrets у repo і мають secure cookie/CSRF defaults.

## 17. Відомі обмеження v1

У v1 свідомо не реалізовуються:

- password reset;
- password reminder;
- email verification;
- native mobile app;
- WebSocket real-time;
- chat/reactions;
- інтеграція із зовнішніми Eurovision API;
- складні moderation workflows;
- multi-edition public archive.

Будь-який агент, який натрапляє на потребу в цих функціях під час реалізації, має оформити це як backlog item, а не додавати в основний scope v1.
