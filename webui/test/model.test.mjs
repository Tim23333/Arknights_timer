import test from "node:test";
import assert from "node:assert/strict";
import {assessField, pathValues, metaLabel, metaParts, formatClock, policyFields} from "../model.mjs";

test("WS probe accepts zero and empty status list but not null or missing fields", () => {
  const field = {id: "enemy.hp", domain: "enemy", paths: ["items[].hp"], collect: true};
  assert.equal(assessField(field, {items: [{hp: 0}]}).status, "received");
  assert.equal(assessField(field, {items: [{hp: null}]}).status, "unavailable");
  assert.equal(assessField(field, {items: []}).status, "no_entities");
  assert.equal(assessField({...field, collect: false}, {items: [{hp: 15}]}).status, "not_collected");
  assert.equal(assessField({...field, paths: ["items[].abnormal"]}, {items: [{abnormal: []}]}).status, "received");
  assert.equal(assessField(field, {items: [{hp: 15, fieldStates: {"enemy.hp": {collectionState: "unavailable"}}}]}).status, "unavailable");
  assert.equal(assessField(field, {items: [{hp: 15, fieldStates: {"enemy.hp": {collectionState: "unavailable"}}}, {hp: 0, fieldStates: {"enemy.hp": {collectionState: "current"}}}]}).status, "received");
});

test("actual registry paths resolve per entity and wildcard RNG role", () => {
  assert.equal(assessField({id: "enemy.hp", domain: "enemy", paths: ["hp"], collect: true}, {items: [{hp: 0}]}).status, "received");
  assert.equal(assessField({id: "rng.history", domain: "rng", paths: ["by_role.*.history"], collect: true}, {by_role: {imp: {history: []}}}).status, "received");
  const result = policyFields({generation: 2, registry: [{id: "enemy.hp", label: "生命"}], fields: {"enemy.hp": {collect: false, display: true, publish: false}}});
  assert.equal(result.fields[0].collect, false);
  assert.equal(result.fields[0].label, "生命");
});

test("registered nested paths fan out without counting transport heartbeat as game data", () => {
  assert.deepEqual(pathValues({items: [{pathing: {route: 0}}, {pathing: {route: 2}}]}, "items[].pathing.route"), [0, 2]);
  assert.equal(assessField({id: "clock", domain: "battle", paths: ["gameTime"], collect: true}, {heartbeat: true}).status, "unavailable");
});

test("source and completion clock stay visibly distinct and unknown clock is not zero", () => {
  assert.match(metaLabel({sourceFrame: 100, latestKnownFrame: 101, state: "current"}), /来源帧 100.*最近已知帧 101/);
  assert.equal(formatClock(null), "—");
  assert.equal(formatClock(64), "01:04.00");
  assert.equal(formatClock(64.033), "01:04.03");
  assert.equal(formatClock(59.999), "00:59.99");
  assert.match(metaLabel({collectionState: 'static', sourceFrame: null}), /已验证静态数据.*来源帧 —/);
  assert.match(metaLabel({collectionState: 'historical', sourceFrame: 91}), /最后已知历史值.*来源帧 91/);
});

// ROOT CAUSE: one variable-width metadata string moves every label when a
// numeric frame changes to unknown. Separate values are rendered in fixed slots.
test('metadata provides independent frame values, preserving zero and unknown', () => {
  assert.deepEqual(metaParts({collectionState:'current', sourceFrame:0, latestKnownFrame:null}),
    {status:'本次读取成功', source:'0', latest:'—'});
  assert.deepEqual(metaParts({collectionState:'unavailable', sourceFrame:null, latestKnownFrame:2147483647}),
    {status:'读取不可用', source:'—', latest:'2147483647'});
  assert.deepEqual(metaParts(null), {status:'来源状态待确认', source:'—', latest:'—'});
});
