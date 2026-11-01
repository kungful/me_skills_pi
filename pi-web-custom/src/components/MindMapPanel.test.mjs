import assert from "node:assert/strict";
import test from "node:test";
import { createJiti } from "jiti";

const jiti = createJiti(import.meta.url, {
  jsx: { runtime: "automatic" },
  tsconfigPaths: true,
});
const React = await jiti.import("react");
const { renderToStaticMarkup } = await jiti.import("react-dom/server");
const { MindMapPanel } = await jiti.import("./MindMapPanel.tsx");
const { ChatInput } = await jiti.import("./ChatInput.tsx");
const { I18nProvider } = await jiti.import("@/hooks/useI18n");

const render = (element) => renderToStaticMarkup(React.createElement(I18nProvider, null, element));

test("the panel opens as its own dialog and never renders on its own", () => {
  const html = render(React.createElement(MindMapPanel, {
    storageKey: "pi-web:mindmap:test",
    onInsert() {},
    onClose() {},
  }));

  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-label="Logic mind map"/);
  // Empty state, no serialized text: the insert button is disabled.
  assert.match(html, /No nodes yet/);
  assert.match(html, /disabled=""[^>]*>Insert into composer/);
  // Both directions of the text hand-off, plus image loading, live in the toolbar.
  assert.match(html, /From text/);
  assert.match(html, /From a prompt/);
  assert.match(html, /Add image/);
  assert.match(html, /type="file"/);
});

test("the panel starts with no import sheet and no kind picker", () => {
  const html = render(React.createElement(MindMapPanel, {
    storageKey: "pi-web:mindmap:test",
    onInsert() {},
    onClose() {},
  }));

  assert.doesNotMatch(html, /Rebuild the graph from text/);
  assert.doesNotMatch(html, /Pick a kind/);
});

test("the composer keeps a mind-map toggle next to the other composer controls", () => {
  const html = render(React.createElement(ChatInput, { onSend() {}, onAbort() {}, isStreaming: false }));

  assert.match(html, /title="Open the logic mind map"/);
  assert.match(html, />Mind map</);
});
