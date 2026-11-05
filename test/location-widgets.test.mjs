import assert from 'node:assert/strict';
import test from 'node:test';
import { boundaryUnits, featureUnits, loadBoundaries, unitAt } from '../ui/staff-ui/overrides/src/oan/widgets/boundaries.ts';

const square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]];
const hole = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]];

test('points in a hole and outside the country do not acquire a geographic unit', () => {
  const units = featureUnits({type:'FeatureCollection',features:[
    {properties:{pcode:'A'},geometry:{type:'Polygon',coordinates:[square,hole]}},
  ]});
  assert.equal(unitAt(units, 2, 2)?.properties.pcode, 'A');
  assert.equal(unitAt(units, 5, 5), null);
  assert.equal(unitAt(units, 20, 20), null);
});

test('multipolygon islands retain the source administrative identity', () => {
  const units = featureUnits({type:'FeatureCollection',features:[
    {properties:{pcode:'islands'},geometry:{type:'MultiPolygon',coordinates:[[square],[square.map(([x,y])=>[x+20,y])]]}},
  ]});
  assert.equal(unitAt(units, 2, 22)?.properties.pcode, 'islands');
  assert.equal(unitAt(units, 2, 15), null);
});

test('quantized TopoJSON with reversed arcs decodes geographic coordinates', () => {
  const units = boundaryUnits({type:'Topology',transform:{scale:[1,1],translate:[30,5]},
    arcs:[[[0,0],[10,0],[0,10],[-10,0],[0,-10]]],
    objects:{woreda:{geometries:[{type:'Polygon',arcs:[[-1]],properties:{pcode:'topology'}}]}}});
  assert.equal(unitAt(units, 7, 32)?.properties.pcode, 'topology');
  assert.equal(unitAt(units, 2, 2), null);
});

test('authenticated boundary reads are shared and a failed read can recover', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(options.credentials, 'include');
    return calls === 1 ? {ok:false,status:503} : {ok:true,json:async()=>({type:'FeatureCollection',features:[]})};
  };
  try {
    await assert.rejects(loadBoundaries('/verification-boundary'), /503/);
    const one = loadBoundaries('/verification-boundary');
    const two = loadBoundaries('/verification-boundary');
    assert.equal(one, two);
    assert.deepEqual(await one, []);
    assert.equal(calls, 2);
  } finally { globalThis.fetch = original; }
});
