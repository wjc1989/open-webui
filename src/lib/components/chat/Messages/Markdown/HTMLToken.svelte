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
</script>

{#if token.type === 'html'}
	{#if html && html.includes('<video')}
		{@const video = html.match(/<video[^>]*>([\s\S]*?)<\/video>/i)}
		{@const videoSrc = video && video[1]}
		{#if videoSrc}
			<!-- svelte-ignore a11y-media-has-caption -->
			<video
				class="w-full my-2"
				src={videoSrc.replaceAll('&amp;', '&')}
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
			<audio class="w-full my-2" src={audioSrc.replaceAll('&amp;', '&')} title="Audio player" controls></audio>
		{:else}
			{token.text}
		{/if}

	<!-- 1) Custom marker: <jump url="..." height="300"></jump> -->
	{:else if html && html.includes('<jump')}
		{@const jm = html.match(/<jump\s+[^>]*url="([^"]+)"[^>]*>/i)}
		{@const hm = html.match(/<jump\s+[^>]*height="(\d+)"[^>]*>/i)}
		{@const jumpUrl = jm && jm[1]}
		{@const jumpHeight = (hm && hm[1]) ? Number(hm[1]) : 300}

		{#if jumpUrl}
			<div class="w-full my-2" height=500>
				<iframe
					style="width:100%;height:100%;border:0;"
					src={jumpUrl.replaceAll('&amp;', '&')}
					title="Embedded content"
					frameborder="0"
					allowfullscreen
					sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
					referrerpolicy="strict-origin-when-cross-origin" height=500 width="100%"
				></iframe>
			</div>
		{:else}
			{token.text}
		{/if}

	<!-- 2) Backward-compatible marker: <jumpopen url="..."></jumpopen> -->
	{:else if html && html.includes('<jumpopen')}
		{@const om = html.match(/<jumpopen\s+[^>]*url="([^"]+)"[^>]*>/i)}
		{@const openUrl = om && om[1]}
		{#if openUrl}
			<button
				class="px-3 py-1.5 my-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm hover:opacity-80"
				type="button"
				on:click={() => openNewWindow(openUrl)}
			>
				Open in new window
			</button>
		{:else}
			{token.text}
		{/if}

	<!-- 3) YouTube iframe: keep existing behavior -->
	{:else if token.text && token.text.match(/<iframe\s+[^>]*src="https:\/\/www\.youtube\.com\/embed\/([a-zA-Z0-9_-]{11})(?:\?[^"]*)?"[^>]*><\/iframe>/)}
		{@const match = token.text.match(
			/<iframe\s+[^>]*src="https:\/\/www\.youtube\.com\/embed\/([a-zA-Z0-9_-]{11})(?:\?[^"]*)?"[^>]*><\/iframe>/
		)}
		{@const ytId = match && match[1]}
		{#if ytId}
			<iframe
				class="w-full aspect-video my-2"
				src={`https://www.youtube.com/embed/${ytId}`}
				title="YouTube video player"
				frameborder="0"
				allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
				referrerpolicy="strict-origin-when-cross-origin"
				allowfullscreen
			></iframe>
		{/if}

	<!-- 4) Generic iframe (fallback): use sanitized html, NOT token.text -->
	{:else if html && html.includes('<iframe')}
		{@const match = html.match(/<iframe\s+[^>]*src="([^"]+)"[^>]*><\/iframe>/i)}
		{@const iframeSrc = match && match[1]}
		{#if iframeSrc}
			<iframe
				class="w-full my-2"
				src={iframeSrc.replaceAll('&amp;', '&')}
				title="Embedded content"
				frameborder="0" width="100%"
				sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
				referrerpolicy="strict-origin-when-cross-origin" height=500
			></iframe>
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

	{:else if token.text.includes(`<file type="html"`)}
		{@const match = token.text.match(/<file type="html" id="([^"]+)"/)}
		{@const fileId = match && match[1]}
		{#if fileId}
			<iframe
				class="w-full my-2"
				src={`${WEBUI_BASE_URL}/api/v1/files/${fileId}/content/html`}
				title="Content"
				frameborder="0"
				sandbox="allow-scripts allow-downloads{($settings?.iframeSandboxAllowForms ?? false)
					? ' allow-forms'
					: ''}{($settings?.iframeSandboxAllowSameOrigin ?? false) ? ' allow-same-origin' : ''}"
				referrerpolicy="strict-origin-when-cross-origin"
				allowfullscreen
				width="100%" height=500
				on:load={(e) => {
					try {
						e.currentTarget.style.height =
							e.currentTarget.contentWindow.document.body.scrollHeight + 20 + 'px';
					} catch {}
				}}
			></iframe>
		{/if}

	{:else if token.text.trim().match(/^<br\s*\/?>$/i)}
		<br />

	{:else}
		{token.text}
	{/if}
{/if}
