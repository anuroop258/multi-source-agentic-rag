import assert from 'node:assert/strict';
import { copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { webcrypto } from 'node:crypto';

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const target = process.argv[2];
assert.ok(target, 'Pass the Cloudflare Pages API source path as the first argument.');
const modulePath = join(tmpdir(), `multi-source-rag-groq-${process.pid}.mjs`);
copyFileSync(target, modulePath);
const { onRequest } = await import(pathToFileURL(modulePath).href);

const originalFetch = globalThis.fetch;
const db = {
  prepare(_sql) {
    return {
      bind(..._values) {
        return {
          all: async () => ({ results: [] }),
          first: async () => null,
          run: async () => ({ success: true }),
        };
      },
      all: async () => ({ results: [] }),
      first: async () => null,
      run: async () => ({ success: true }),
    };
  },
};

async function readEvents(response) {
  const raw = await response.text();
  return raw.split('\n').filter(line => line.startsWith('data: ')).map(line => JSON.parse(line.slice(6)));
}
async function runChat(overrides = {}) {
  return onRequest({
    request: new Request('https://rag.test/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: 'a'.repeat(32),
        message: 'What are the latest open-source LLM developments this week?',
        ...overrides,
      }),
    }),
    env: { DB: db, GROQ_API_KEY: 'test-key', GROQ_MODEL: 'openai/gpt-oss-120b' },
  });
}

try {
  // Test 1: 429 is retried, each local-tool round includes its definitions,
  // and the final synthesis request is sanitized to plain text.
  let groqCalls = 0;
  let toolCalls = 0;
  let sawFinalSynthesis = false;
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    if (url.includes('api.groq.com/openai/v1/chat/completions')) {
      const payload = JSON.parse(init.body);
      groqCalls += 1;
      if (groqCalls === 1) {
        return new Response(JSON.stringify({ error: { message: 'Rate limit. Please try again in 0.01s.' } }), {
          status: 429,
          headers: { 'Content-Type': 'application/json', 'x-ratelimit-reset-tokens': '0.01s' },
        });
      }
      assert.equal(payload.include_reasoning, false);
      assert.equal(Object.hasOwn(payload, 'reasoning_format'), false);
      if (Array.isArray(payload.tools)) {
        assert.equal(payload.tool_choice, 'auto');
        assert.equal(payload.parallel_tool_calls, false);
        toolCalls += 1;
        return new Response(JSON.stringify({ choices: [{ message: {
          role: 'assistant', content: null,
          tool_calls: [{ id: `call-${toolCalls}`, type: 'function', function: {
            name: 'web_search', arguments: JSON.stringify({ query: `open source model development ${toolCalls}` }),
          } }],
        }, finish_reason: 'tool_calls' }] }), { headers: { 'Content-Type': 'application/json' } });
      }
      sawFinalSynthesis = true;
      assert.match(payload.messages[0]?.content || '', /No tools are available/);
      assert.equal(payload.tool_choice, undefined);
      assert.equal(payload.messages.some(m => m.role === 'tool' || Array.isArray(m.tool_calls)), false);
      assert.match(payload.messages.at(-1)?.content || '', /Collected research and tool results/);
      return new Response(JSON.stringify({ choices: [{ message: { role: 'assistant', content: 'Here is the synthesized research summary with source links.' } }] }), { headers: { 'Content-Type': 'application/json' } });
    }
    if (url.includes('html.duckduckgo.com/html/')) {
      return new Response('<div><a class="result__a" href="https://example.org/research">Open-source model research result</a></div>', { headers: { 'Content-Type': 'text/html' } });
    }
    throw new Error(`Unexpected mocked fetch URL: ${url}`);
  };
  const response = await runChat();
  assert.equal(response.status, 200);
  const events = await readEvents(response);
  assert.equal(events.some(e => e.type === 'error'), false);
  assert.equal(events.some(e => e.type === 'answer' && e.answer.includes('synthesized research summary')), true);
  assert.equal(toolCalls, 4);
  assert.equal(groqCalls, 6, 'One 429 retry + four tool calls + one final synthesis call expected.');
  assert.equal(sawFinalSynthesis, true);

  // Test 2: if Groq still emits a forbidden tool call in final mode, the app
  // returns gathered findings instead of exposing the 400 to the user.
  let secondGroqCalls = 0;
  let secondToolCalls = 0;
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    if (url.includes('api.groq.com/openai/v1/chat/completions')) {
      const payload = JSON.parse(init.body);
      secondGroqCalls += 1;
      if (Array.isArray(payload.tools)) {
        secondToolCalls += 1;
        return new Response(JSON.stringify({ choices: [{ message: {
          role: 'assistant', content: null,
          tool_calls: [{ id: `fallback-${secondToolCalls}`, type: 'function', function: {
            name: 'web_search', arguments: JSON.stringify({ query: 'fallback source' }),
          } }],
        }, finish_reason: 'tool_calls' }] }), { headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify({
        message: 'Tool choice is none, but model called a tool',
        type: 'invalid_request_error',
        code: 'tool_use_failed',
      }), { status: 400, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.includes('html.duckduckgo.com/html/')) {
      return new Response('<div><a class="result__a" href="https://example.org/fallback">Fallback web result</a></div>', { headers: { 'Content-Type': 'text/html' } });
    }
    throw new Error(`Unexpected mocked fetch URL: ${url}`);
  };
  const fallbackResponse = await runChat();
  const fallbackEvents = await readEvents(fallbackResponse);
  assert.equal(fallbackEvents.some(e => e.type === 'error'), false);
  const fallbackAnswer = fallbackEvents.find(e => e.type === 'answer')?.answer || '';
  assert.match(fallbackAnswer, /could not complete the final synthesis/i);
  assert.match(fallbackAnswer, /https:\/\/example\.org\/fallback/);
  assert.equal(secondToolCalls, 4);
  assert.equal(secondGroqCalls, 5, 'Four tool rounds plus one final synthesis attempt expected.');

  // Test 3: built-in browser search gets its own system prompt and exact tool.
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    if (url.includes('api.groq.com/openai/v1/chat/completions')) {
      const payload = JSON.parse(init.body);
      assert.match(payload.messages[0]?.content || '', /built-in browser_search tool/);
      assert.equal(payload.tool_choice, 'required');
      assert.deepEqual(payload.tools, [{ type: 'browser_search' }]);
      return new Response(JSON.stringify({ choices: [{ message: { role: 'assistant', content: 'Browser search result synthesized.' } }] }), { headers: { 'Content-Type': 'application/json' } });
    }
    throw new Error(`Unexpected mocked fetch URL: ${url}`);
  };
  const browserResponse = await runChat({ browser_search: true });
  const browserEvents = await readEvents(browserResponse);
  assert.equal(browserEvents.some(e => e.type === 'answer' && e.answer.includes('Browser search result synthesized.')), true);
  assert.equal(browserEvents.some(e => e.type === 'error'), false);

  console.log('PASS: Groq 429 retry; bounded and consistent local-tool loop; final synthesis avoids stale tool calls; fallback handles tool_choice 400; native browser-search prompt/tool stay aligned.');
} finally {
  globalThis.fetch = originalFetch;
}
