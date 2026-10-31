import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import jsdom from '../node_modules/.feedback-qa/node_modules/jsdom/lib/api.js';

test('equipment and facilities pickers preserve structured requirements and draft/none choices', async () => {
  const dom = new jsdom.JSDOM('<div id="root"></div>', { url: 'http://localhost/' });
  const previous = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT };
  globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const server = await createServer({ root: fileURLToPath(new URL('../', import.meta.url)),
    server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  let root;
  try {
    const { createElement: h, act } = await import('react');
    const { createRoot } = await import('react-dom/client');
    const { default: Picker } = await server.ssrLoadModule('/src/components/EquipmentRequirementsPicker.jsx');
    root = createRoot(document.getElementById('root'));
    const render = async (initialItems, key) => act(async () => root.render(h('form', null, h(Picker, { initialItems, key }))));
    const form = () => document.querySelector('form');
    const value = () => new dom.window.FormData(form()).get('equipment_requirements');
    const click = async node => act(async () => node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })));
    const select = async (index, type) => act(async () => {
      const node = document.querySelectorAll('select')[index];
      node.value = type; node.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    });
    const quantity = async number => act(async () => {
      const node = document.querySelector('input[type="number"]');
      Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(node, String(number));
      node.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    });
    await render(null, 'new');
    assert.equal(value(), '', 'unanswered draft remains null when submitted to API');
    assert.equal(form().checkValidity(), false);
    assert.deepEqual([...document.querySelectorAll('select option')].slice(1).map(item => item.textContent),
      ['Projector', 'Microphone', 'Speaker', 'Laptop', 'HDMI Cable', 'Extension Cable', 'Webcam', 'Lighting']);
    await select(0, 'Projector');
    await quantity(0);
    assert.equal(form().checkValidity(), false);
    await quantity(2);
    assert.equal(form().checkValidity(), true);
    assert.deepEqual(JSON.parse(value()), [{ equipment_type: 'Projector', quantity: 2, notes: null }]);
    await click([...document.querySelectorAll('button')].find(item => item.textContent === 'Add equipment'));
    assert.equal(form().checkValidity(), false, 'new row needs a type');
    assert.equal(document.querySelectorAll('select')[1].querySelector('option[value="Projector"]').disabled, true);
    await select(1, 'Microphone');
    assert.equal(JSON.parse(value()).length, 2);
    await click(document.querySelector('input[type="checkbox"]'));
    assert.deepEqual(JSON.parse(value()), []);
    assert.equal(form().checkValidity(), true, 'no equipment does not require row values');
    await click(document.querySelector('input[type="checkbox"]'));
    assert.equal(JSON.parse(value()).length, 2, 'switching back retains selections');
    await click(document.querySelector('[aria-label="Remove equipment 1"]'));
    assert.equal(JSON.parse(value())[0].equipment_type, 'Microphone');
    await render([{ equipment_type: 'projector', quantity: 3, notes: 'Existing note' }], 'saved');
    assert.deepEqual(JSON.parse(value()), [{ equipment_type: 'Projector', quantity: 3, notes: 'Existing note' }]);
    await render([], 'none');
    assert.equal(document.querySelector('input[type="checkbox"]').checked, true);
    assert.deepEqual(JSON.parse(value()), []);
    const { default: FacilitiesPicker } = await server.ssrLoadModule('/src/components/RequiredFacilitiesPicker.jsx');
    await act(async () => root.render(h('form', null, h(FacilitiesPicker, { key: 'facilities-new' }))));
    const facilities = () => new dom.window.FormData(form()).getAll('required_facilities');
    assert.deepEqual(facilities(), []);
    assert.equal(form().checkValidity(), false, 'facility requirements must be answered before submission');
    await click(document.querySelector('input[value="wifi"]'));
    await click(document.querySelector('input[value="air_conditioning"]'));
    assert.deepEqual(facilities(), ['wifi', 'air_conditioning']);
    assert.equal(form().checkValidity(), true);
    await click(document.querySelector('input[value="none"]'));
    assert.deepEqual(facilities(), ['none']);
    assert.equal(document.querySelector('input[value="wifi"]').checked, false);
    await click(document.querySelector('input[value="stage"]'));
    assert.deepEqual(facilities(), ['stage']);
    assert.equal(document.querySelector('input[value="none"]').checked, false);
    await act(async () => root.render(h('form', null, h(FacilitiesPicker, { key: 'facilities-saved', initialItems: ['wifi'] }))));
    assert.deepEqual(facilities(), ['wifi']);
    await act(async () => root.render(h('form', null, h(FacilitiesPicker, { key: 'facilities-none', initialItems: [] }))));
    assert.deepEqual(facilities(), ['none']);
    assert.equal(form().checkValidity(), true);
  } finally {
    if (root) { const { act } = await import('react'); await act(async () => root.unmount()); }
    await server.close(); dom.window.close();
    globalThis.window = previous.window; globalThis.document = previous.document; globalThis.IS_REACT_ACT_ENVIRONMENT = previous.act;
  }
});
