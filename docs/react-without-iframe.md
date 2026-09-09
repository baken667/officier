# React-интерфейс поверх движка ONLYOFFICE без iframe

Решение от 2026-09-09: собственный интерфейс React с прямым обращением к движку
`sdkjs`. Первый технический срез — один DOCX-редактор на странице. XLSX, PPTX и
несколько одновременных редакторов потребуют отдельных адаптеров и изоляции состояния.

Создан отдельный репозиторий [officier-react](https://github.com/baken667/officier-react):
начальный мост команд к `asc_docs_api`, React-панель, типы, unit-тесты и ручной
workflow GitHub Packages. В сервере Officier добавлен thin direct runtime bridge:
manifest грузит socket.io, `sdkjs/word/sdk-all-min.js` и adapter, adapter создаёт
`Asc.asc_docs_api` в DOM-контейнере React-приложения и подаёт WOPI bootstrap.
Полное browser-подтверждение DOCX open/edit/save без iframe ещё впереди.
Пакет `@baken667/officier-react@0.1.0-alpha.0` опубликован в GitHub Packages
([успешный workflow](https://github.com/baken667/officier-react/actions/runs/34324910219)).
Локальная копия находится в `clients/officier-react` как независимый
Git-репозиторий и не включается в коммиты сервера.

## Почему npm-пакет сам по себе не устраняет iframe

[Официальный React-компонент](https://api.onlyoffice.com/docs/docs-api/get-started/frontend-frameworks/react/)
оборачивает Docs API. В нашей закреплённой версии `web-apps/apps/api/documents/api.js`
функция `createIframe()` создаёт iframe, а команды идут через `postMessage`.
Публикация другой обёртки в GitHub Packages этого поведения не меняет.

При прямом подключении движка нужно заменить роль старого приложения `web-apps`:
загрузить ресурсы, создать canvas, передать документ и права, подписаться на события,
управлять выделением, фокусом, буфером обмена, историей и сохранением.
DocumentServer остаётся нужен для конвертации, совместного редактирования и сохранения;
npm-пакет не заменяет серверную часть.

## Разделение репозиториев и пакетов

- `officier`: сервер, патчи, закреплённые исходники и собственная сборка сервера.
- `officier-react`: сейчас контракты, мост команд и React-панель; далее загрузчик
  движка, тестовое приложение и npm-пакет `@baken667/officier-react`.
- Скомпилированные SDK, WASM, шрифты и прочие ресурсы поставляются отдельно от лёгкого
  React-пакета и имеют явную версию, совпадающую с сервером.

```text
React: toolbar / panels / document surface
                  |
        typed commands and events
                  |
       Officier engine adapter
                  |
       sdkjs in the same document
                  |
  DocumentServer: WebSocket / conversion / save callbacks
```

## Подтверждённые препятствия

| Исходники | Что требуется переработать |
| --- | --- |
| `sdkjs/word/api.js`, конструктор `asc_docs_api` | Глобальные `window.editor` и `Asc.editor`; нельзя обещать несколько независимых инстансов |
| `sdkjs/word/api.js`, `document.getElementById(...)` | Жёсткие ID и поиск по всему документу; простой Shadow DOM их ломает |
| `web-apps/apps/common/Gateway.js` | Транспорт `window.parent.postMessage`; заменить прямыми командами/событиями |
| `web-apps/apps/documenteditor/main/app.js` | RequireJS и пути ресурсов привязаны к старому web-приложению |
| `web-apps/apps/documenteditor/main/app/controller/Main.js` | Инициализация DocInfo, загрузка, права, фокус, сохранение и обработчики страницы |

Shadow DOM изолирует часть CSS, но не создаёт отдельный `window` и не исправляет
глобальное состояние SDK. Массовая подмена `document.getElementById` непригодна:
она затронет и приложение пользователя. Нужны явный root контейнера и lifecycle.

## Критерии первого работающего прототипа

1. Реальный DOCX открывается в canvas внутри DOM React-приложения, без iframe.
2. Своя панель React меняет выделенный текст; undo/redo и сохранение работают.
3. Документ после сохранения повторно открывается без потери внесённых изменений.
4. Права view/edit и неверный JWT обрабатываются сервером корректно.
5. React mount/unmount/remount освобождает события, сокеты, таймеры и глобальные ссылки.
6. В браузерном тесте нет iframe редактора; CSS и клавиатурные события не ломают host.
7. Есть доступные сведения об исходном ONLYOFFICE, модификации и лицензии.

Пока эти критерии не выполнены, пакет следует обозначать как экспериментальный,
а не полноценную замену ONLYOFFICE Docs React. Проверки с mock API доказывают
контракт адаптера, но не работоспособность настоящего движка.

## GitHub Packages

GitHub поддерживает scoped npm-пакеты и публикацию workflow через `GITHUB_TOKEN`
с `packages: write`. Пакет React может иметь `react` и `react-dom` в peerDependencies,
а SDK загружать по явно заданному URL и версии. Установка даже публичного пакета
GitHub Packages требует аутентификации. См.
[документацию реестра](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-npm-registry).

Публикация пакета не меняет лицензию производного движка. Применимые условия AGPL
и дополнительные условия сохраняются; сведения находятся в [LICENSE](../LICENSE).
