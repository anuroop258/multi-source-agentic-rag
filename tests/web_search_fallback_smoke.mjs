import assert from 'node:assert/strict';
import { copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { webcrypto } from 'node:crypto';

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const target = process.argv[2];
assert.ok(target, 'Pass the Cloudflare Pages API source path as the first argument.');
const modulePath = join(tmpdir(), `multi-source-rag-search-${process.pid}.mjs`);
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
async function runChat(envOverrides = {}, bodyOverrides = {}) {
  return onRequest({
    request: new Request('https://rag.test/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: 'c'.repeat(32),
        message: 'Find the latest open-source LLM developments this week.',
        ...bodyOverrides,
      }),
    }),
    env: { DB: db, GROQ_API_KEY: 'test-key', GROQ_MODEL: 'openai/gpt-oss-120b', ...envOverrides },
  });
}

function groqToolReply(query = 'latest open source LLM developments this week') {
  return new Response(JSON.stringify({ choices: [{ message: {
    role: 'assistant', content: null,
    tool_calls: [{ id: 'search-call-1', type: 'function', function: {
      name: 'web_search', arguments: JSON.stringify({ query }),
    } }],
  }, finish_reason: 'tool_calls' }] }), { headers: { 'Content-Type': 'application/json' } });
}
function groqFinalReply() {
  return new Response(JSON.stringify({ choices: [{ message: {
    role: 'assistant', content: 'I found current source material and summarized it.',
  } }] }), { headers: { 'Content-Type': 'application/json' } });
}

try {
  // Test 1: DDG challenge -> Bing fallback returns usable web results.
  let groqCount = 0;
  const seen = [];
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    if (url.includes('api.groq.com/openai/v1/chat/completions')) {
      groqCount += 1;
      return groqCount === 1 ? groqToolReply() : groqFinalReply();
    }
    if (url.includes('html.duckduckgo.com/html/')) {
      seen.push('ddg-html');
      assert.equal(init.method, 'POST');
      assert.match(String(init.body), /kl=in-en/);
      return new Response('<html><body><form id="challenge-form">unusual traffic</form></body></html>', { status: 202, headers: { 'Content-Type': 'text/html' } });
    }
    if (url.includes('lite.duckduckgo.com/lite/')) {
      seen.push('ddg-lite');
      return new Response('<html><body>anomaly.js challenge</body></html>', { status: 202, headers: { 'Content-Type': 'text/html' } });
    }
    if (url.includes('www.bing.com/search')) {
      seen.push('bing');
      return new Response('<ol><li class="b_algo"><h2><a href="https://example.org/inkling-2-mini">Inkling 2 Mini open-weights model</a></h2><p>Released on November 20.</p></li></ol>', { headers: { 'Content-Type': 'text/html' } });
    }
    throw new Error(`Unexpected mocked fetch URL: ${url}`);
  };
  const bingResponse = await runChat();
  const bingEvents = await readEvents(bingResponse);
  assert.equal(bingEvents.some(event => event.type === 'error'), false);
  const bingTool = bingEvents.find(event => event.type === 'tool_done');
  assert.match(bingTool?.result_preview || '', /Search provider: Bing \(fallback\)/);
  assert.match(bingTool?.result_preview || '', /https:\/\/example\.org\/inkling-2-mini/);
  assert.deepEqual(seen, ['ddg-html', 'ddg-lite', 'bing']);

  // Test 2: DDG and Bing have no parseable results -> Google News RSS fallback
  // supplies dated article titles and source links for recent-news queries.
  let secondGroqCount = 0;
  const secondSeen = [];
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    if (url.includes('api.groq.com/openai/v1/chat/completions')) {
      secondGroqCount += 1;
      return secondGroqCount === 1 ? groqToolReply() : groqFinalReply();
    }
    if (url.includes('html.duckduckgo.com/html/')) {
      secondSeen.push('ddg-html');
      return new Response('<html><body>empty result page</body></html>', { headers: { 'Content-Type': 'text/html' } });
    }
    if (url.includes('lite.duckduckgo.com/lite/')) {
      secondSeen.push('ddg-lite');
      return new Response('<html><body>empty result page</body></html>', { headers: { 'Content-Type': 'text/html' } });
    }
    if (url.includes('www.bing.com/search')) {
      secondSeen.push('bing');
      return new Response('<html><body>empty page</body></html>', { headers: { 'Content-Type': 'text/html' } });
    }
    if (url.includes('news.google.com/rss/search')) {
      secondSeen.push('google-news-rss');
      assert.match(decodeURIComponent(url), /when:7d/i);
      return new Response(`<?xml version="1.0"?><rss><channel><item><title>Inkling 2 Mini open-weights model</title><link>https://news.google.com/rss/articles/example-id</link><source>Research News</source><pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate><description><![CDATA[An open-weights laptop model was released.]]></description></item></channel></rss>`, { headers: { 'Content-Type': 'application/rss+xml' } });
    }
    throw new Error(`Unexpected mocked fetch URL: ${url}`);
  };
  const newsResponse = await runChat();
  const newsEvents = await readEvents(newsResponse);
  assert.equal(newsEvents.some(event => event.type === 'error'), false);
  const newsTool = newsEvents.find(event => event.type === 'tool_done');
  assert.match(newsTool?.result_preview || '', /Google News RSS/);
  assert.match(newsTool?.result_preview || '', /Published: Fri, 20 Nov 2026/);
  assert.deepEqual(secondSeen, ['ddg-html', 'ddg-lite', 'bing', 'google-news-rss']);

  // Test 3: If optional Tavily fails, the tool falls back to no-key search.
  let thirdGroqCount = 0;
  let tavilyCalled = false;
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    if (url.includes('api.groq.com/openai/v1/chat/completions')) {
      thirdGroqCount += 1;
      return thirdGroqCount === 1 ? groqToolReply() : groqFinalReply();
    }
    if (url.includes('api.tavily.com/search')) {
      tavilyCalled = true;
      return new Response(JSON.stringify({ message: 'quota exceeded' }), { status: 429, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.includes('html.duckduckgo.com/html/')) {
      return new Response('<div><a class="result__a" href="https://example.org/independent-result">Independent result</a><div class="result__snippet">Useful snippet</div></div>', { headers: { 'Content-Type': 'text/html' } });
    }
    throw new Error(`Unexpected mocked fetch URL: ${url}`);
  };
  const tavilyResponse = await runChat({ TAVILY_API_KEY: 'test-tavily-key' }, { search_provider: 'tavily' });
  const tavilyEvents = await readEvents(tavilyResponse);
  assert.equal(tavilyEvents.some(event => event.type === 'error'), false);
  assert.equal(tavilyCalled, true);
  const tavilyTool = tavilyEvents.find(event => event.type === 'tool_done');
  assert.match(tavilyTool?.result_preview || '', /Search provider: DuckDuckGo \(html\)/);
  assert.match(tavilyTool?.result_preview || '', /https:\/\/example\.org\/independent-result/);

  console.log('PASS: Cloudflare web search falls back from DuckDuckGo challenge to Bing; uses date-filtered Google News RSS for recent-news queries; Tavily failures fall back without a paid provider switch.');
} finally {
  globalThis.fetch = originalFetch;
}
