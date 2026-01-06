<script lang="ts">
	import DOMPurify from 'dompurify';
	import type { Token } from 'marked';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { settings } from '$lib/stores';

	export let id: string;
	export let token: Token;

	let html: string | null = null;

	// ---- helpers ----
	function normalizeUrl(rawUrl: string) {
		return (rawUrl || '').replaceAll('&amp;', '&');
	}

	function openNewWindow(url: string) {
		try {
			window.open(url, '_blank', 'noopener,noreferrer');
		} catch {}
	}

	// Open URL in a new "fullscreen-sized" window (browser UI like address bar can't be forced hidden)
	function openFullscreenWindow(rawUrl: string) {
		const url = normalizeUrl(rawUrl);

		const w = window.screen?.availWidth || window.innerWidth;
		const h = window.screen?.availHeight || window.innerHeight;

		try {
			window.open(url, '_blank', `noopener,noreferrer,popup=yes,width=${w},height=${h},left=0,top=0`);
		} catch {
			try {
				window.open(url, '_blank', 'noopener,noreferrer');
			} catch {}
		}
	}

	function looksLikeJson(s: string) {
		const t = (s || '').trim();
		return (t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'));
	}

	/**
	 * Extract renderable html from token.text.
	 * Priority:
	 * 1) If token.text is JSON: use obj.message, else obj.text, else token.text
	 * 2) If token.text contains special tags: use token.text
	 * 3) Else: null
	 */
	function extractRenderableHtmlFromTokenText(raw: string): string | null {
		const t = raw || '';
		if (!t.trim()) return null;

		// 1) JSON content: try parse {message/text/...}
		if (looksLikeJson(t)) {
			try {
				const obj: any = JSON.parse(t);
				// tool outputs often are {"message": "...<jump...>", "text": "..."} etc.
				const candidate =
					(typeof obj?.message === 'string' && obj.message) ||
					(typeof obj?.text === 'string' && obj.text) ||
					(typeof obj?.content === 'string' && obj.content) ||
					null;

				if (candidate && typeof candidate === 'string') return candidate;
			} catch {
				// ignore parse errors and fall through
			}
		}

		// 2) Not JSON: if it contains our tags, treat it as renderable HTML
		const hasRenderableMarker =
			t.includes('<jump') ||
			t.includes('<jumpopen') ||
			t.includes('<iframe') ||
			t.includes('<video') ||
			t.includes('<audio') ||
			t.includes('<status') ||
			t.includes('<file type="html"');

		return hasRenderableMarker ? t : null;
	}

	// ---- decide html to render (not only token.type === 'html') ----
	$: {
		const rawText = (token as any)?.text || '';
		const candidate = extractRenderableHtmlFromTokenText(rawText);

		if (candidate) {
			html = DOMPurify.sanitize(candidate, {
				ADD_TAGS: ['jump', 'jumpopen', 'iframe', 'video', 'audio', 'status', 'file'],
				ADD_ATTR: [
					'url',
					'height',
					'src',
					'style',
					'width',
					'allow',
					'allowfullscreen',
					'frameborder',
					'sandbox',
					'referrerpolicy',
					'title',
					'target',
					'rel',
					'id',
					'type',
					'done'
				]
			});
		} else if (token.type === 'html' && rawText) {
			// keep original behavior for pure html tokens
			html = DOMPurify.sanitize(rawText, {
				ADD_TAGS: ['jump', 'jumpopen', 'iframe', 'video', 'audio', 'status', 'file'],
				ADD_ATTR: [
					'url',
					'height',
					'src',
					'style',
					'width',
					'allow',
					'allowfullscreen',
					'frameborder',
					'sandbox',
					'referrerpolicy',
					'title',
					'target',
					'rel',
					'id',
					'type',
					'done'
				]
			});
		} else {
			html = null;
		}
	}
</script>

<!-- ✅ 这里不再强依赖 token.type === 'html'：只要 html 存在就按可渲染逻辑走 -->
{#if html}
	{#if html.includes('<video')}
		{@const video = html.match(/<video[^>]*>([\s\S]*?)<\/video>/i)}
		{@const videoSrc = video && video[1]}
		{#if videoSrc}
			<!-- svelte-ignore a11y-media-has-caption -->
			<video
				class="w-full my-2"
				src={normalizeUrl(videoSrc)}
				title="Video player"
				frameborder="0"
				referrerpolicy="strict-origin-when-cross-origin"
				controls
				allowfullscreen
			></video>
		{:else}
			{token.text}
		{/if}

	{:else if html.includes('<audio')}
		{@const audio = html.match(/<audio[^>]*>([\s\S]*?)<\/audio>/i)}
		{@const audioSrc = audio && audio[1]}
		{#if audioSrc}
			<!-- svelte-ignore a11y-media-has-caption -->
			<audio class="w-full my-2" src={normalizeUrl(audioSrc)} title="Audio player" controls></audio>
		{:else}
			{token.text}
		{/if}

	<!-- 1) Custom marker: <jump url="..."></jump> -->
	{:else if html.includes('<jump')}
		{@const jm = html.match(/<jump\s+[^>]*url="([^"]+)"[^>]*>/i)}
		{@const jumpUrl = jm && jm[1]}
		{@const u = jumpUrl ? normalizeUrl(jumpUrl) : ''}

		{#if u}
			<div class="w-full my-2">
				<!-- iframe -->
				<div
					class="w-full border border-gray-200 dark:border-gray-800 rounded-t-md overflow-hidden"
					style="height:500px"
				>
					<iframe
						style="width:100%;height:100%;border:0;"
						src={u}
						title="Embedded content"
						frameborder="0"
						allowfullscreen
						sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
						referrerpolicy="strict-origin-when-cross-origin"
					></iframe>
				</div>

				<!-- toolbar BELOW -->
				<div
					class="flex items-center justify-between px-2 py-1 border border-t-0 border-gray-200 dark:border-gray-800 rounded-b-md bg-gray-50 dark:bg-gray-900/40"
				>
					<div class="text-xs opacity-80 truncate pr-2">Embedded content</div>
					<div class="flex gap-2">
						<button
							class="px-2 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-xs hover:opacity-80"
							type="button"
							on:click={() => openFullscreenWindow(u)}
							title="Open in new window"
						>
							Open
						</button>
					</div>
				</div>
			</div>
		{:else}
			{token.text}
		{/if}

	<!-- 2) Backward-compatible marker: <jumpopen url="..."></jumpopen> -->
	{:else if html.includes('<jumpopen')}
		{@const om = html.match(/<jumpopen\s+[^>]*url="([^"]+)"[^>]*>/i)}
		{@const openUrl = om && om[1]}
		{@const openU = openUrl ? normalizeUrl(openUrl) : ''}

		{#if openU}
			<button
				class="px-3 py-1.5 my-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm hover:opacity-80"
				type="button"
				on:click={() => openNewWindow(openU)}
			>
				Open in new window
			</button>
		{:else}
			{token.text}
		{/if}

	<!-- 3) YouTube iframe -->
	{:else if html.match(
		/<iframe\s+[^>]*src="https:\/\/www\.youtube\.com\/embed\/([a-zA-Z0-9_-]{11})(?:\?[^"]*)?"[^>]*>(?:<\/iframe>|\/>)/i
	)}
		{@const match = html.match(
			/<iframe\s+[^>]*src="https:\/\/www\.youtube\.com\/embed\/([a-zA-Z0-9_-]{11})(?:\?[^"]*)?"[^>]*>(?:<\/iframe>|\/>)/i
		)}
		{@const ytId = match && match[1]}
		{@const ytUrl = ytId ? `https://www.youtube.com/embed/${ytId}` : ''}

		{#if ytUrl}
			<div class="w-full my-2">
				<div class="w-full border border-gray-200 dark:border-gray-800 rounded-t-md overflow-hidden">
					<iframe
						class="w-full aspect-video"
						src={ytUrl}
						title="YouTube video player"
						frameborder="0"
						allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
						referrerpolicy="strict-origin-when-cross-origin"
						allowfullscreen
					></iframe>
				</div>

				<div
					class="flex items-center justify-between px-2 py-1 border border-t-0 border-gray-200 dark:border-gray-800 rounded-b-md bg-gray-50 dark:bg-gray-900/40"
				>
					<div class="text-xs opacity-80 truncate pr-2">YouTube</div>
					<div class="flex gap-2">
						<button
							class="px-2 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-xs hover:opacity-80"
							type="button"
							on:click={() => openFullscreenWindow(ytUrl)}
							title="Open in new window"
						>
							Open
						</button>
					</div>
				</div>
			</div>
		{/if}

	<!-- 4) Generic iframe (fallback) -->
	{:else if html.includes('<iframe')}
		{@const match = html.match(/<iframe\s+[^>]*src="([^"]+)"[^>]*(?:><\/iframe>|\/>)/i)}
		{@const iframeSrc = match && match[1]}
		{@const iu = iframeSrc ? normalizeUrl(iframeSrc) : ''}

		{#if iu}
			<div class="w-full my-2">
				<div class="w-full border border-gray-200 dark:border-gray-800 rounded-t-md overflow-hidden">
					<iframe
						class="w-full"
						src={iu}
						title="Embedded content"
						frameborder="0"
						width="100%"
						sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
						referrerpolicy="strict-origin-when-cross-origin"
						height="500"
					></iframe>
				</div>

				<div
					class="flex items-center justify-between px-2 py-1 border border-t-0 border-gray-200 dark:border-gray-800 rounded-b-md bg-gray-50 dark:bg-gray-900/40"
				>
					<div class="text-xs opacity-80 truncate pr-2">Embedded content</div>
					<div class="flex gap-2">
						<button
							class="px-2 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-xs hover:opacity-80"
							type="button"
							on:click={() => openFullscreenWindow(iu)}
							title="Open in new window"
						>
							Open
						</button>
					</div>
				</div>
			</div>
		{:else}
			{token.text}
		{/if}

	{:else if html.includes('<status')}
		{@const match = html.match(/<status title="([^"]+)" done="(true|false)" ?\/?>/)}
		{@const statusTitle = match && match[1]}
		{@const statusDone = match && match[2] === 'true'}
		{#if statusTitle}
			<div class="flex flex-col justify-center -space-y-0.5">
				<div
					class="{statusDone === false
						? 'shimmer'
						: ''} text-gray-500 dark:text-gray-500 line-clamp-1 text-wrap"
				>
					{statusTitle}
				</div>
			</div>
		{:else}
			{token.text}
		{/if}

	<!-- file html iframe -->
	{:else if html.includes(`<file type="html"`)}
		{@const match = html.match(/<file type="html" id="([^"]+)"/)}
		{@const fileId = match && match[1]}
		{@const fileUrl = fileId ? `${WEBUI_BASE_URL}/api/v1/files/${fileId}/content/html` : ''}

		{#if fileUrl}
			<div class="w-full my-2">
				<div class="w-full border border-gray-200 dark:border-gray-800 rounded-t-md overflow-hidden">
					<iframe
						class="w-full"
						src={fileUrl}
						title="Content"
						frameborder="0"
						sandbox="allow-scripts allow-downloads{($settings?.iframeSandboxAllowForms ?? false)
							? ' allow-forms'
							: ''}{($settings?.iframeSandboxAllowSameOrigin ?? false) ? ' allow-same-origin' : ''}"
						referrerpolicy="strict-origin-when-cross-origin"
						allowfullscreen
						width="100%"
						height="500"
						on:load={(e) => {
							try {
								e.currentTarget.style.height =
									e.currentTarget.contentWindow.document.body.scrollHeight + 20 + 'px';
							} catch {}
						}}
					></iframe>
				</div>

				<div
					class="flex items-center justify-between px-2 py-1 border border-t-0 border-gray-200 dark:border-gray-800 rounded-b-md bg-gray-50 dark:bg-gray-900/40"
				>
					<div class="text-xs opacity-80 truncate pr-2">HTML file</div>
					<div class="flex gap-2">
						<button
							class="px-2 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-xs hover:opacity-80"
							type="button"
							on:click={() => openFullscreenWindow(fileUrl)}
							title="Open in new window"
						>
							Open
						</button>
					</div>
				</div>
			</div>
		{/if}

	{:else if token.text?.trim?.().match(/^<br\s*\/?>$/i)}
		<br />

	{:else}
		{token.text}
	{/if}
{:else}
	<!-- 没有可渲染 html，就回退原始渲染 -->
	{token.text}
{/if}
