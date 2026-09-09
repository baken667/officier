const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const util = require('node:util');
const path = require('node:path');
const constants = require('../server/Common/sources/constants');
const license = require('../server/Common/sources/license');

// Exercise the actual quota generator without booting databases or the HTTP server.
const source = fs.readFileSync(path.join(__dirname, '../server/DocService/sources/DocsCoServer.js'), 'utf8');
const start = source.indexOf('  function* _checkLicenseAuth(');
const end = source.indexOf('  //publish subscribe message brocker', start);
assert(start > 0 && end > start, 'Upstream quota function boundary changed; review test harness');

function quotaFunction(stat) {
  return vm.runInNewContext(`(${source.slice(start, end).trim()})`, {
    constants, util, process: {env: {}},
    cfgWarningLimitPercents: 90,
    cfgNotificationRuleLicenseLimitEdit: '%s %s',
    cfgNotificationRuleLicenseLimitLiveViewer: '%s %s',
    notificationTypes: {LICENSE_LIMIT_EDIT: 'edit', LICENSE_LIMIT_LIVE_VIEWER: 'view'},
    notificationService: {notify() {}}, connections: [], editorStat: stat
  });
}

async function execute(iterator) {
  let step = iterator.next();
  while (!step.done) step = iterator.next(await step.value);
  return step.value;
}

test('Community exposes customization without claiming a commercial license', async () => {
  const [info, payload] = await license.readLicense();
  assert.equal(info.branding, true);
  assert.equal(info.customization, true);
  assert.equal(info.advancedApi, true);
  assert.equal(info.packageType, constants.PACKAGE_TYPE_OS);
  assert.equal(info.hasLicense, false);
  assert.equal(info.multitenancy, false);
  assert.equal(info.type, constants.LICENSE_RESULT.Success);
  assert.equal(payload, null);
});

test('Community edit/view/seat quotas do not consult counters, even with small supplied quotas', async () => {
  const [info] = await license.readLicense();
  const check = quotaFunction(new Proxy({}, {get() { throw Error('Quota counter accessed'); }}));
  for (const view of [false, true]) {
    for (const usersCount of [0, 1]) {
      assert.equal(await execute(check({}, {...info, connections: 1, connectionsView: 1, usersCount}, 'u', view)), constants.LICENSE_RESULT.Success);
    }
  }
});

test('Community shortcut preserves error/expired status', async () => {
  const [info] = await license.readLicense();
  for (const type of [constants.LICENSE_RESULT.Error, constants.LICENSE_RESULT.Expired]) {
    assert.equal(await execute(quotaFunction({})({}, {...info, type}, 'u', false)), type);
  }
});

test('other edition/license paths retain their connection checks', async () => {
  const [base] = await license.readLicense();
  const ctx = {getCfg: (_, fallback) => fallback, logger: {error() {}, warn() {}}};
  for (const overrides of [{packageType: -1}, {hasLicense: true}]) {
    for (const view of [false, true]) {
      for (const count of [0, 2]) {
        const info = {...base, ...overrides, connections: 2, connectionsView: 2};
        const check = quotaFunction({getEditorConnectionsCount: async () => count, getLiveViewerConnectionsCount: async () => count});
        const limited = view
          ? (info.hasLicense ? constants.LICENSE_RESULT.ConnectionsLive : constants.LICENSE_RESULT.ConnectionsLiveOS)
          : (info.hasLicense ? constants.LICENSE_RESULT.Connections : constants.LICENSE_RESULT.ConnectionsOS);
        assert.equal(await execute(check(ctx, info, 'u', view)), count < 2 ? constants.LICENSE_RESULT.Success : limited);
      }
    }
  }
});
