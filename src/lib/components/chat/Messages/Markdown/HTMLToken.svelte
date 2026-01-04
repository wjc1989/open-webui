<script lang="ts">
	import DOMPurify from 'dompurify';
	import type { Token } from 'marked';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { settings } from '$lib/stores';

	export let id: string;
	export let token: Token;

	let html: string | null = null;

	$: if (token.type === 'html' && token?.text) {
		// We sanitize but we do NOT rely on iframe-in-html for custom pages.
		// Instead, we render <jump ...> markers as real iframes (safer and more controllable).
		html = DOMPurify.sanitize(token.text, {
			ADD_TAGS: ['jump', 'jumpopen', 'iframe'],
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
				'rel'
			]
		});
	} else {
		html = null;
	}

	function openNewWindow(url: string) {
		try {
			window.open(url, '_blank', 'noopener,noreferrer');
		} catch {}
	}

	// Open URL in a new "fullscreen-sized" window (browser UI like address bar can't be forced hidden)
	function openFullscreenWindow(rawUrl: string) {
		const url = (rawUrl || '').replaceAll('&amp;', '&');

		const w = window.screen?.availWidth || window.innerWidth;
		const h = window.screen?.availHeight || window.innerHeight;

		try {
			window.open(
				url,
				'_blank',
				`noopener,noreferrer,popup=yes,width=${w},height=${h},left=0,top=0`
			);
		} catch {
			try {
				window.open(url, '_blank', 'noopener,noreferrer');
			} catch {}
		}
	}

	function normalizeUrl(rawUrl: string) {
		return (rawUrl || '').replaceAll('&amp;', '&');
	}
</script>

{#if token.type === 'html'}
	{#if html && html.includes('<video')}
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

	{:else if html && html.includes('<audio')}
		{@const audio = html.match(/<audio[^>]*>([\s\S]*?)<\/audio>/i)}
		{@const audioSrc = audio && audio[1]}
		{#if audioSrc}
			<!-- svelte-ignore a11y-media-has-caption -->
			<audio class="w-full my-2" src={normalizeUrl(audioSrc)} title="Audio player" controls></audio>
		{:else}
			{token.text}
		{/if}

	<!-- 1) Custom marker: <jump url="..."></jump> -->
	{:else if html && html.includes('<jump')}
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
	{:else if html && html.includes('<jumpopen')}
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

	<!-- 3) YouTube iframe: keep existing behavior; toolbar BELOW -->
	{:else if token.text &&
		token.text.match(
			/<iframe\s+[^>]*src="https:\/\/www\.youtube\.com\/embed\/([a-zA-Z0-9_-]{11})(?:\?[^"]*)?"[^>]*><\/iframe>/
		)}
		{@const match = token.text.match(
			/<iframe\s+[^>]*src="https:\/\/www\.youtube\.com\/embed\/([a-zA-Z0-9_-]{11})(?:\?[^"]*)?"[^>]*><\/iframe>/
		)}
		{@const ytId = match && match[1]}
		{@const ytUrl = ytId ? `https://www.youtube.com/embed/${ytId}` : ''}

		{#if ytUrl}
			<div class="w-full my-2">
				<!-- iframe -->
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

				<!-- toolbar BELOW -->
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

	<!-- 4) Generic iframe (fallback): use sanitized html, NOT token.text; toolbar BELOW -->
	{:else if html && html.includes('<iframe')}
		<!-- support both <iframe ...></iframe> and self-closing <iframe ... /> -->
		{@const match = html.match(/<iframe\s+[^>]*src="([^"]+)"[^>]*(?:><\/iframe>|\/>)/i)}
		{@const iframeSrc = match && match[1]}
		{@const iu = iframeSrc ? normalizeUrl(iframeSrc) : ''}

		{#if iu}
			<div class="w-full my-2">
				<!-- iframe -->
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

				<!-- toolbar BELOW -->
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

	{:else if token.text && token.text.includes('<status')}
		{@const match = token.text.match(/<status title="([^"]+)" done="(true|false)" ?\/?>/)}
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

	<!-- file html iframe: toolbar BELOW -->
	{:else if token.text.includes(`<file type="html"`)}
		{@const match = token.text.match(/<file type="html" id="([^"]+)"/)}
		{@const fileId = match && match[1]}
		{@const fileUrl = fileId ? `${WEBUI_BASE_URL}/api/v1/files/${fileId}/content/html` : ''}

		{#if fileUrl}
			<div class="w-full my-2">
				<!-- iframe -->
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

				<!-- toolbar BELOW -->
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

	{:else if token.text.trim().match(/^<br\s*\/?>$/i)}
		<br />

	{:else}
		{token.text}
	{/if}
{/if}
