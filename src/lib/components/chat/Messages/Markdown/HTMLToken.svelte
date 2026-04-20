<script lang="ts">
	import DOMPurify from 'dompurify';
	import { getContext } from 'svelte';
	import type { Token } from 'marked';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { settings } from '$lib/stores';

	export let id: string;
	export let token: Token;

	const i18n = getContext('i18n');

	let html: string | null = null;
	let jumpIframe: HTMLIFrameElement | null = null;

	const parseJumpToken = (text: string) => {
		const match = text.match(/<jump\s+[^>]*url="([^"]+)"[^>]*>/i);
		const heightMatch = text.match(/<jump\s+[^>]*height="(\d+)"[^>]*>/i);
		if (!match?.[1]) {
			return null;
		}

		return {
			src: match[1],
			height: heightMatch?.[1] ? Number.parseInt(heightMatch[1], 10) : 600
		};
	};

	const openJumpContent = async (url: string) => {
		const iframe = jumpIframe;

		if (iframe) {
			try {
				if (iframe.requestFullscreen) {
					await iframe.requestFullscreen();
					return;
				}

				const iframeWithVendorFullscreen = iframe as HTMLIFrameElement & {
					webkitRequestFullscreen?: () => Promise<void> | void;
					msRequestFullscreen?: () => Promise<void> | void;
				};

				if (iframeWithVendorFullscreen.webkitRequestFullscreen) {
					iframeWithVendorFullscreen.webkitRequestFullscreen();
					return;
				}

				if (iframeWithVendorFullscreen.msRequestFullscreen) {
					iframeWithVendorFullscreen.msRequestFullscreen();
					return;
				}
			} catch {}
			}

		window.open(url, '_blank', 'noopener,noreferrer');
	};

	$: if (token.type === 'html' && token?.text) {
		html = DOMPurify.sanitize(token.text);
	} else {
		html = null;
	}
</script>

{#if token.type === 'html'}
	{#if html && html.includes('<video')}
		{@const video = html.match(/<video[^>]*>([\s\S]*?)<\/video>/)}
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
		{@const audio = html.match(/<audio[^>]*>([\s\S]*?)<\/audio>/)}
		{@const audioSrc = audio && audio[1]}
		{#if audioSrc}
			<!-- svelte-ignore a11y-media-has-caption -->
			<audio
				class="w-full my-2"
				src={audioSrc.replaceAll('&amp;', '&')}
				title="Audio player"
				controls
			></audio>
		{:else}
			{token.text}
		{/if}
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
			>
			</iframe>
		{/if}
	{:else if token.text && token.text.includes('<iframe')}
		{@const match = token.text.match(/<iframe\s+[^>]*src="([^"]+)"[^>]*><\/iframe>/)}
		{@const iframeSrc = match && match[1]}
		{#if iframeSrc}
			<iframe
				class="w-full my-2"
				src={iframeSrc}
				title="Embedded content"
				frameborder="0"
				on:load={(e) => {
					try {
						e.currentTarget.style.height =
							e.currentTarget.contentWindow.document.body.scrollHeight + 20 + 'px';
					} catch {}
				}}
			></iframe>
		{:else}
			{token.text}
		{/if}
	{:else if token.text && token.text.includes('<jump')}
		{@const jumpContent = parseJumpToken(token.text)}
		{#if jumpContent?.src}
			<div class="w-full my-2">
				<iframe
					bind:this={jumpIframe}
					class="w-full rounded-lg border border-gray-200 dark:border-gray-700"
					src={jumpContent.src}
					title="Jump content"
					frameborder="0"
					height={String(jumpContent.height)}
				></iframe>
				<div class="mt-2 flex justify-end">
					<button
						type="button"
						class="px-3 py-1.5 text-xs font-medium rounded-md bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700"
						on:click={() => openJumpContent(jumpContent.src)}
					>
						{$i18n?.t('Open') ?? 'Open'}
					</button>
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
	{:else if token.text.includes(`<file type="html"`)}
		{@const match = token.text.match(/<file type="html" id="([^"]+)"/)}
		{@const fileId = match && match[1]}
		{#if fileId}
			<iframe
				class="w-full my-2"
				src={`${WEBUI_BASE_URL}/api/v1/files/${fileId}/content/html`}
				title="Content"
				frameborder="0"
				referrerpolicy="strict-origin-when-cross-origin"
				allowfullscreen
				width="100%"
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
